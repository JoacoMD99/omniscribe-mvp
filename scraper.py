import glob
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

import app_config
import yt_dlp
from yt_dlp.utils import DownloadError
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    IpBlocked,
    TranscriptsDisabled,
    NoTranscriptFound,
)
from groq import Groq
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from errors import (
    OmniScribeError,
    VideoBlockedError,
    VideoUnavailableError,
    AudioDownloadError,
)

# Setup Logging (python-pro.md)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OmniScraper:
    """
    OmniScraper: The core engine for OmniScribe AI.
    Handles YouTube extraction and transcription with resilient fallback logic.
    """
    
    def __init__(self, groq_api_key: Optional[str] = None) -> None:
        self.api_key = groq_api_key or app_config.get_groq_api_key()
        if not self.api_key:
            logger.warning("GROQ_API_KEY not found. Fallback transcription will be unavailable.")
        
        self.client = Groq(api_key=self.api_key) if self.api_key else None
        self.output_path = Path("outputs")
        self.output_path.mkdir(exist_ok=True)

    def _clean_text(self, text: str) -> str:
        """
        Removes timestamps and noise tags using Regex.
        Example: [00:00:12] or (Music) -> removed.
        """
        # Remove timestamps: [00:00], [00:00:00], 00:00, 00:00:00
        text = re.sub(r'\[?\d{1,2}:\d{2}(?::\d{2})?\]?', '', text)
        # Remove noise tags: [Musica], (Risas)
        text = re.sub(r'\[.*?\]|\(.*?\)', '', text)
        # Clean multiple spaces and newlines
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    # --- Fase 1 (plan de mejoras): anti-bot + resiliencia de descarga ------

    _BOT_BLOCK_MARKERS = (
        "sign in to confirm",
        "not a bot",
        "http error 403",
        "http error 429",
        "too many requests",
        "unable to download api page",
    )

    def _classify_download_error(self, exc: Exception, url: str,
                                 video_id: Optional[str] = None) -> OmniScribeError:
        """Convierte errores crudos de yt-dlp en excepciones tipadas con mensaje útil."""
        text = str(exc).lower()
        if any(marker in text for marker in self._BOT_BLOCK_MARKERS):
            return VideoBlockedError(
                "YouTube bloqueó la request (detección anti-bot). "
                "Configura cookies (YOUTUBE_COOKIES_B64) o reintenta en unos minutos.",
                url=url, video_id=video_id,
            )
        return VideoUnavailableError(
            f"No se pudo acceder al video (¿privado, eliminado o restringido?): {exc}",
            url=url, video_id=video_id,
        )

    def _base_ydl_opts(self) -> Dict[str, Any]:
        """
        Opciones de hardening compartidas por todas las llamadas a yt-dlp (Fase 1.2):
        UA realista, timeouts, retries y jitter nativo de yt-dlp. Cookies y
        player_client se inyectan solo si están configurados vía entorno.
        """
        opts: Dict[str, Any] = {
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/131.0.0.0 Safari/537.36'
                ),
                'Accept-Language': 'en-US,en;q=0.9',
            },
            'socket_timeout': 30,
            'retries': 5,
            'fragment_retries': 5,
            'extractor_retries': 3,
            # yt-dlp randomiza el delay en [sleep_interval, max_sleep_interval]: jitter nativo.
            'sleep_interval': 2,
            'max_sleep_interval': 6,
            'sleep_interval_requests': 1,
        }
        cookiefile = app_config.get_youtube_cookiefile()
        if cookiefile:
            opts['cookiefile'] = cookiefile
        # Escape hatch operativo: pivotar de player client sin redeploy si YouTube cambia.
        # Clientes sin PO token a la fecha: tv, android_vr. Por defecto yt-dlp auto-selecciona
        # (y cambia a tv_downgraded,web,web_safari automáticamente cuando hay cookiefile).
        player_client = (os.getenv("YTDLP_PLAYER_CLIENT") or "").strip()
        if player_client:
            opts['extractor_args'] = {
                'youtube': {
                    'player_client': [c.strip() for c in player_client.split(',') if c.strip()]
                }
            }
        return opts

    @staticmethod
    def _build_transcript_api() -> YouTubeTranscriptApi:
        """
        Construye el cliente de youtube-transcript-api con proxy genérico opcional
        (YTT_PROXY_HTTP / YTT_PROXY_HTTPS). La librería 1.x no soporta cookies;
        esta capa es best-effort y el workhorse confiable es yt-dlp + Groq.
        """
        http_url = os.getenv("YTT_PROXY_HTTP")
        https_url = os.getenv("YTT_PROXY_HTTPS")
        if http_url or https_url:
            from youtube_transcript_api.proxies import GenericProxyConfig
            logger.info("youtube-transcript-api usando proxy genérico (YTT_PROXY_*).")
            return YouTubeTranscriptApi(
                proxy_config=GenericProxyConfig(http_url=http_url, https_url=https_url)
            )
        return YouTubeTranscriptApi()

    def get_metadata(self, url: str) -> Dict[str, Any]:
        """
        Uses yt-dlp to extract title and basic info.
        """
        # Robust regex to extract just the video ID and ignore playlist parameters
        match = re.search(r"(?:v=|\/|youtu\.be\/)([0-9A-Za-z_-]{11})", url)
        clean_url = f"https://www.youtube.com/watch?v={match.group(1)}" if match else url

        ydl_opts = {
            **self._base_ydl_opts(),
            'skip_download': True,
            'noplaylist': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(clean_url, download=False)
        except DownloadError as e:
            # Fase 1.4: primer punto de fallo en producción — error tipado con contexto.
            raise self._classify_download_error(
                e, clean_url, match.group(1) if match else None
            ) from e

        if not info:
            raise VideoUnavailableError(
                f"No se pudo extraer información del video: {url}", url=clean_url
            )
        return {
            "title": info.get("title", "Unknown Title"),
            "id": info.get("id", match.group(1) if match else None),
            "duration": info.get("duration"),
            "clean_url": clean_url
        }

    def get_playlist_videos(self, playlist_url: str) -> list[str]:
        """
        Extracts all individual video URLs from a playlist using yt-dlp.
        """
        ydl_opts = {
            **self._base_ydl_opts(),
            'extract_flat': 'in_playlist',
            'noplaylist': False,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
        except DownloadError as e:
            raise self._classify_download_error(e, playlist_url) from e

        if not info or 'entries' not in info:
            return []

        urls = []
        for entry in info['entries']:
            if entry.get('url'):
                urls.append(entry['url'])
            elif entry.get('id'):
                urls.append(f"https://www.youtube.com/watch?v={entry['id']}")
        return urls

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        reraise=True
    )
    def _transcribe_with_groq(self, audio_file: str) -> str:
        """
        Uploads audio to Groq Whisper using resilient retries via Tenacity.
        (@api-patterns and @python-pro)
        """
        if not self.client:
            raise Exception("Groq client is not configured.")
            
        logger.info(f"Sending {audio_file} to Groq API...")
        with open(audio_file, "rb") as file:
            response = self.client.audio.transcriptions.create(
                file=(os.path.basename(audio_file), file.read()),
                model="whisper-large-v3",
                response_format="text"
            )
        return str(response)

    @staticmethod
    def _find_ffmpeg() -> Optional[str]:
        """Locates ffmpeg in PATH or known WinGet install location."""
        import shutil
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            logger.info(f"ffmpeg encontrado en PATH: {system_ffmpeg}")
            return None  # Already in PATH, yt-dlp will find it automatically
        winget_path = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
        for candidate in winget_path.glob("Gyan.FFmpeg*/**/bin"):
            if (candidate / "ffmpeg.exe").exists():
                logger.info(f"ffmpeg encontrado vía WinGet: {candidate}")
                return str(candidate)
        logger.warning("ffmpeg no encontrado en PATH ni en WinGet. La extracción de audio puede fallar.")
        return None

    def _download_audio(self, url: str, temp_dir: str, video_id: str) -> str:
        """
        Downloads the audio stream in a compressed format (m4a) into an isolated
        temp dir (Fase 1.4) and returns the REAL path of the produced file.
        Raises AudioDownloadError/VideoBlockedError instead of returning phantom paths.
        """
        logger.info("Downloading audio via yt-dlp...")
        ydl_opts = {
            **self._base_ydl_opts(),
            'format': 'm4a/bestaudio/best',
            'outtmpl': os.path.join(temp_dir, f"{video_id}.%(ext)s"),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }],
        }
        ffmpeg_location = self._find_ffmpeg()
        if ffmpeg_location:
            ydl_opts['ffmpeg_location'] = ffmpeg_location
            logger.info(f"Using ffmpeg at: {ffmpeg_location}")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except DownloadError as e:
            classified = self._classify_download_error(e, url, video_id)
            if isinstance(classified, VideoBlockedError):
                raise classified from e
            raise AudioDownloadError(
                f"Falló la descarga de audio: {e}", url=url, video_id=video_id
            ) from e

        # Resolver el archivo realmente producido (ignorando .part incompletos).
        candidates = [
            p for p in glob.glob(os.path.join(temp_dir, f"{video_id}*"))
            if not p.endswith(".part")
        ]
        m4a_files = [p for p in candidates if p.endswith(".m4a")]
        chosen = m4a_files[0] if m4a_files else (candidates[0] if candidates else None)

        if not chosen or not os.path.exists(chosen):
            raise AudioDownloadError(
                "La descarga no produjo ningún archivo de audio.",
                url=url, video_id=video_id,
            )
        return chosen

    def process_video(self, url: str) -> Optional[str]:
        """
        Orchestrates the transcription workflow:
        1. Attempt official transcripts.
        2. Fallback to Audio Download + Groq Whisper.
        """
        try:
            metadata = self.get_metadata(url)
            video_id = metadata["id"]
            title = metadata["title"]
            clean_url = metadata.get("clean_url", url)
            logger.info(f"🚀 Starting process for: {title} ({video_id})")

            transcript_text: Optional[str] = None

            # Attempt 1: youtube-transcript-api (best-effort; en IPs cloud suele estar bloqueado)
            try:
                logger.info("Attempt 1: Fetching official transcript...")
                api = self._build_transcript_api()
                transcript_list = api.list(video_id)
                
                selected_transcript = None
                # 1. Search for any English transcript
                en_transcripts = [t for t in transcript_list if 'en' in t.language_code.lower()]
                if en_transcripts:
                    manual_en = [t for t in en_transcripts if not t.is_generated]
                    selected_transcript = manual_en[0] if manual_en else en_transcripts[0]
                else:
                    # 2. Search for any Spanish transcript
                    es_transcripts = [t for t in transcript_list if 'es' in t.language_code.lower()]
                    if es_transcripts:
                        manual_es = [t for t in es_transcripts if not t.is_generated]
                        selected_transcript = manual_es[0] if manual_es else es_transcripts[0]

                if selected_transcript:
                    logger.info(f"Selected transcript: {selected_transcript.language} (Auto-generated: {selected_transcript.is_generated})")
                    try:
                        raw_transcript = selected_transcript.fetch()
                        transcript_text = " ".join([t.text for t in raw_transcript])
                        logger.info("Official transcript retrieved successfully.")
                    except IpBlocked:
                        if not self.client:
                            raise VideoBlockedError(
                                "YouTube bloqueó las requests de transcript (IpBlocked) y no hay "
                                "GROQ_API_KEY configurada para el fallback de audio. "
                                "Espera unos minutos antes de reintentar este video.",
                                url=clean_url, video_id=video_id,
                            )
                        logger.warning("IpBlocked en fetch(). Intentando fallback de Groq...")
                else:
                    logger.info("No suitable 'en' or 'es' transcript found (will fallback).")

            except OmniScribeError:
                raise
            except IpBlocked:
                # Fase 1.3: en cloud, list() es la PRIMERA llamada bloqueada
                # (antes solo se cubría fetch() y esto caía al except genérico sin contexto).
                if not self.client:
                    raise VideoBlockedError(
                        "YouTube bloqueó el listado de transcripts (IpBlocked) y no hay "
                        "GROQ_API_KEY configurada para el fallback de audio. "
                        "Espera unos minutos antes de reintentar este video.",
                        url=clean_url, video_id=video_id,
                    )
                logger.warning("IpBlocked en list(). Intentando fallback de Groq...")
            except (TranscriptsDisabled, NoTranscriptFound) as e:
                logger.info(f"Sin transcript oficial ({type(e).__name__}); se usará fallback.")
            except Exception as e:
                logger.info(f"Official transcript unavailable: {e} (will fallback).")

            # Attempt 2: Fallback (Audio + Groq)
            if not transcript_text:
                if not self.client:
                    logger.error("Groq API key missing, cannot use Whisper fallback.")
                    return None
                    
                logger.info("Attempt 2: Falling back to Audio Download + Groq Whisper...")

                # Fase 1.4: temp dir aislado FUERA de outputs/ — nada temporal
                # contamina el directorio de transcripts descargables.
                temp_dir = tempfile.mkdtemp(prefix=f"omniscribe_{video_id}_")
                try:
                    # Download audio (lanza error tipado si falla o no produce archivo)
                    audio_file = self._download_audio(clean_url, temp_dir, video_id)

                    # SECURITY OF WEIGHT: Check file size <= 25MB
                    file_size = os.path.getsize(audio_file)
                    max_size = 25 * 1024 * 1024

                    if file_size > max_size:
                        logger.error(f"Archivo demasiado grande para la API de Groq: {file_size / (1024 * 1024):.2f} MB")
                        return None

                    # Request transcription
                    transcript_text = self._transcribe_with_groq(audio_file)

                finally:
                    # CLEANUP RULE (Fase 1.4): borrar el temp dir completo,
                    # incluyendo .part de descargas incompletas.
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    logger.info(f"Cleanup: Deleted temp dir {temp_dir}")

            # Process and Save results
            if transcript_text:
                final_text = self._clean_text(transcript_text)
                
                # Clean title for filesystem safety
                safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
                file_name = f"{safe_title}_{video_id}.txt"
                file_path = self.output_path / file_name
                
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(final_text)
                
                logger.info(f"✅ Success! Transcript saved to: {file_path}")
                return str(file_path)

            return None

        except OmniScribeError as e:
            # Errores tipados: propagar hacia la UI con su mensaje en español.
            logger.error(f"❌ {type(e).__name__} processing {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error processing {url}: {e}")
            return None

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        scraper = OmniScraper()
        result = scraper.process_video(sys.argv[1])
        if result:
            print(f"Output generated at {result}")
        else:
            print("Failed to generate transcription.")
    else:
        print("Usage: python scraper.py <youtube_url>")
