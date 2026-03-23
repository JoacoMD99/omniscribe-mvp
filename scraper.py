import os
import re
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any

import config
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi, IpBlocked
from groq import Groq
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

# Setup Logging (python-pro.md)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OmniScraper:
    """
    OmniScraper: The core engine for OmniScribe AI.
    Handles YouTube extraction and transcription with resilient fallback logic.
    """
    
    def __init__(self, groq_api_key: Optional[str] = None) -> None:
        self.api_key = groq_api_key or config.get_groq_api_key()
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

    def get_metadata(self, url: str) -> Dict[str, Any]:
        """
        Uses yt-dlp to extract title and basic info.
        """
        # Robust regex to extract just the video ID and ignore playlist parameters
        match = re.search(r"(?:v=|\/|youtu\.be\/)([0-9A-Za-z_-]{11})", url)
        clean_url = f"https://www.youtube.com/watch?v={match.group(1)}" if match else url

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'noplaylist': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            if not info:
                raise ValueError(f"Could not extract info from URL: {url}")
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
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',
            'noplaylist': False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)
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
        if shutil.which("ffmpeg"):
            return None  # Already in PATH, yt-dlp will find it automatically
        winget_path = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
        for candidate in winget_path.glob("Gyan.FFmpeg*/**/bin"):
            if (candidate / "ffmpeg.exe").exists():
                return str(candidate)
        return None

    def _download_audio(self, url: str, temp_file_path: str) -> str:
        """
        Downloads the audio stream in a compressed format (m4a).
        """
        logger.info("Downloading audio via yt-dlp...")
        ydl_opts = {
            'format': 'm4a/bestaudio/best',
            'outtmpl': temp_file_path,
            'quiet': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }],
        }
        ffmpeg_location = self._find_ffmpeg()
        if ffmpeg_location:
            ydl_opts['ffmpeg_location'] = ffmpeg_location
            logger.info(f"Using ffmpeg at: {ffmpeg_location}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        # Optional: yt-dlp might append .m4a automatically, ensure we locate the actual file
        # If outtmpl doesn't end with .m4a but the postprocessor makes it .m4a, we must check.
        if not os.path.exists(temp_file_path):
            expected_m4a = f"{temp_file_path}.m4a"
            if os.path.exists(expected_m4a):
                return expected_m4a
        return temp_file_path

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

            # Attempt 1: youtube-transcript-api
            try:
                logger.info("Attempt 1: Fetching official transcript...")
                api = YouTubeTranscriptApi()
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
                            raise RuntimeError(
                                "YouTube bloqueó las requests de transcript (IpBlocked). "
                                "No hay API Key de Groq configurada para el fallback de audio. "
                                "Espera unos minutos antes de reintentar este video."
                            )
                        logger.warning("IpBlocked en fetch(). Intentando fallback de Groq...")
                else:
                    logger.info("No suitable 'en' or 'es' transcript found (will fallback).")

            except RuntimeError:
                raise
            except Exception as e:
                logger.info(f"Official transcript unavailable: {e} (will fallback).")

            # Attempt 2: Fallback (Audio + Groq)
            if not transcript_text:
                if not self.client:
                    logger.error("Groq API key missing, cannot use Whisper fallback.")
                    return None
                    
                logger.info("Attempt 2: Falling back to Audio Download + Groq Whisper...")
                
                # We will define a clear path for the audio, yt-dlp might append .m4a so we omit extension
                base_temp_name = str(self.output_path / f"{video_id}_temp")
                audio_file = ""
                
                try:
                    # Download audio
                    audio_file = self._download_audio(clean_url, base_temp_name)
                    
                    if not os.path.exists(audio_file):
                        raise FileNotFoundError("Audio file download failed.")

                    # SECURITY OF WEIGHT: Check file size <= 25MB
                    file_size = os.path.getsize(audio_file)
                    max_size = 25 * 1024 * 1024
                    
                    if file_size > max_size:
                        logger.error(f"Archivo demasiado grande para la API de Groq: {file_size / (1024 * 1024):.2f} MB")
                        return None
                        
                    # Request transcription
                    transcript_text = self._transcribe_with_groq(audio_file)
                    
                finally:
                    # CLEANUP RULE: Always delete the audio file on success or fatal error
                    if audio_file and os.path.exists(audio_file):
                        os.remove(audio_file)
                        logger.info(f"Cleanup: Deleted temp audio file {audio_file}")
                    # Also remove base temp file if postprocessor failed before returning path
                    if os.path.exists(base_temp_name):
                        os.remove(base_temp_name)
                        logger.info(f"Cleanup: Deleted orphan temp file {base_temp_name}")

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

        except RuntimeError:
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
