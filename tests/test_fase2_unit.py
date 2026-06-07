"""
Unit tests de la Fase 2.1 (cambio de contrato de process_video).
Puros: sin red, sin API keys reales. Ver plans/Plan de mejoras de la app.md (tarea 2.1).

Contrato nuevo: process_video retorna path o LEVANTA OmniScribeError tipada.
Los "return None" silenciosos desaparecen (salvo el caso 25MB, scope de 2.2).
"""
import os

import pytest

import app_config
import errors
from scraper import OmniScraper


@pytest.fixture(autouse=True)
def reset_cookie_cache():
    """El cookie loader es singleton por proceso; resetearlo entre tests."""
    app_config._cookie_cache["initialized"] = False
    app_config._cookie_cache["path"] = None
    yield
    app_config._cookie_cache["initialized"] = False
    app_config._cookie_cache["path"] = None


URL = "https://www.youtube.com/watch?v=vid12345678"
METADATA = {"title": "Test Video", "id": "vid12345678", "duration": 60, "clean_url": URL}


class FakeTranscriptApiEmpty:
    """Simula list() exitoso pero sin transcripts utilizables -> fuerza fallback."""
    def list(self, video_id):
        return []


def _make_scraper_without_client(monkeypatch) -> OmniScraper:
    """Scraper sin Groq client (simula deploy sin GROQ_API_KEY)."""
    monkeypatch.setattr(app_config, "get_groq_api_key", lambda: None)
    return OmniScraper(groq_api_key=None)


def _make_scraper_with_fake_client() -> OmniScraper:
    """El constructor de Groq no valida la key contra red."""
    return OmniScraper(groq_api_key="gsk_fake_key_for_tests")


def _patch_happy_path_until_groq(monkeypatch, scraper, tmp_path, transcript_result):
    """Mockea metadata + transcript api vacía + download OK; controla el resultado de Groq."""
    audio = tmp_path / "vid12345678.m4a"
    audio.write_bytes(b"fake-audio-bytes")
    monkeypatch.setattr(scraper, "get_metadata", lambda url: METADATA)
    monkeypatch.setattr(OmniScraper, "_build_transcript_api",
                        staticmethod(lambda: FakeTranscriptApiEmpty()))
    monkeypatch.setattr(scraper, "_download_audio",
                        lambda url, temp_dir, video_id: str(audio))
    if isinstance(transcript_result, Exception):
        def _boom(audio_file):
            raise transcript_result
        monkeypatch.setattr(scraper, "_transcribe_with_groq", _boom)
    else:
        monkeypatch.setattr(scraper, "_transcribe_with_groq",
                            lambda audio_file: transcript_result)


# ---------------------------------------------------------------------------
# 2.1 — _transcribe_with_groq: errores tipados (no Exception genérica)
# ---------------------------------------------------------------------------
class _CountingTranscriptions:
    """Fake del endpoint de Groq que cuenta llamadas reales al API."""
    def __init__(self, behavior):
        self.calls = 0
        self._behavior = behavior

    def create(self, **kwargs):
        self.calls += 1
        if isinstance(self._behavior, Exception):
            raise self._behavior
        return self._behavior


def _install_fake_client(scraper, behavior) -> _CountingTranscriptions:
    from types import SimpleNamespace
    fake = _CountingTranscriptions(behavior)
    scraper.client = SimpleNamespace(audio=SimpleNamespace(transcriptions=fake))
    return fake


@pytest.fixture()
def no_backoff(monkeypatch):
    """Neutraliza los sleeps de tenacity para testear retries sin esperar 2-10s."""
    monkeypatch.setattr(OmniScraper._transcribe_with_groq.retry, "sleep", lambda s: None)


class TestTranscribeWithGroq:
    def test_raises_groq_config_error_without_client(self, monkeypatch, tmp_path):
        """Sin client debe levantar GroqConfigError, no Exception genérica."""
        scraper = _make_scraper_without_client(monkeypatch)
        audio = tmp_path / "a.m4a"
        audio.write_bytes(b"x")
        with pytest.raises(errors.GroqConfigError):
            scraper._transcribe_with_groq(str(audio))

    def test_config_error_not_retried_by_tenacity(self, monkeypatch, tmp_path, no_backoff):
        """GroqConfigError es terminal: tenacity debe abortar al primer intento."""
        scraper = _make_scraper_without_client(monkeypatch)
        audio = tmp_path / "a.m4a"
        audio.write_bytes(b"x")
        with pytest.raises(errors.GroqConfigError):
            scraper._transcribe_with_groq(str(audio))
        assert scraper._transcribe_with_groq.statistics["attempt_number"] == 1

    def test_transient_error_is_retried_3_times(self, tmp_path, no_backoff):
        """Errores transitorios (red/API) SÍ se reintentan hasta agotar los 3 intentos."""
        scraper = _make_scraper_with_fake_client()
        fake = _install_fake_client(scraper, ConnectionError("Groq API down"))
        audio = tmp_path / "a.m4a"
        audio.write_bytes(b"x")
        with pytest.raises(ConnectionError):
            scraper._transcribe_with_groq(str(audio))
        assert fake.calls == 3

    def test_none_response_returns_empty_string_not_none_literal(self, tmp_path):
        """Si Groq retorna None, el método NO debe retornar el string truthy 'None'."""
        scraper = _make_scraper_with_fake_client()
        _install_fake_client(scraper, None)
        audio = tmp_path / "a.m4a"
        audio.write_bytes(b"x")
        result = scraper._transcribe_with_groq(str(audio))
        assert result == ""  # cae en el guard de TranscriptUnavailableError aguas arriba


# ---------------------------------------------------------------------------
# 2.1 — process_video: contrato "return path o raise tipado"
# ---------------------------------------------------------------------------
class TestProcessVideoContract:
    def test_reraises_typed_errors_untouched(self, monkeypatch):
        """OmniScribeError conocidas se propagan tal cual, sin envolver."""
        scraper = _make_scraper_with_fake_client()
        original = errors.VideoBlockedError("bloqueado", url=URL, video_id="vid12345678")

        def _blocked(url):
            raise original
        monkeypatch.setattr(scraper, "get_metadata", _blocked)

        with pytest.raises(errors.VideoBlockedError) as exc_info:
            scraper.process_video(URL)
        assert exc_info.value is original  # misma instancia, no re-envuelta

    def test_wraps_unknown_errors_with_cause(self, monkeypatch):
        """Errores desconocidos se envuelven en OmniScribeError con __cause__ (no return None)."""
        scraper = _make_scraper_with_fake_client()
        original = ValueError("boom inesperado")

        def _boom(url):
            raise original
        monkeypatch.setattr(scraper, "get_metadata", _boom)

        with pytest.raises(errors.OmniScribeError) as exc_info:
            scraper.process_video(URL)
        assert exc_info.value.__cause__ is original
        assert not isinstance(exc_info.value, (errors.VideoBlockedError,
                                               errors.VideoUnavailableError))

    def test_raises_groq_config_error_when_fallback_needed_without_client(
            self, monkeypatch):
        """Sin transcript oficial y sin GROQ_API_KEY -> GroqConfigError (antes: return None)."""
        scraper = _make_scraper_without_client(monkeypatch)
        monkeypatch.setattr(scraper, "get_metadata", lambda url: METADATA)
        monkeypatch.setattr(OmniScraper, "_build_transcript_api",
                            staticmethod(lambda: FakeTranscriptApiEmpty()))

        with pytest.raises(errors.GroqConfigError) as exc_info:
            scraper.process_video(URL)
        assert exc_info.value.video_id == "vid12345678"

    def test_groq_failure_wrapped_in_transcription_error(self, monkeypatch, tmp_path):
        """Fallo de la API de Groq tras retries -> GroqTranscriptionError con __cause__."""
        scraper = _make_scraper_with_fake_client()
        original = ConnectionError("Groq API unreachable")
        _patch_happy_path_until_groq(monkeypatch, scraper, tmp_path, original)

        with pytest.raises(errors.GroqTranscriptionError) as exc_info:
            scraper.process_video(URL)
        assert exc_info.value.__cause__ is original

    def test_empty_transcript_raises_transcript_unavailable(self, monkeypatch, tmp_path):
        """Groq retorna texto vacío -> TranscriptUnavailableError (antes: return None final)."""
        scraper = _make_scraper_with_fake_client()
        _patch_happy_path_until_groq(monkeypatch, scraper, tmp_path, "")

        with pytest.raises(errors.TranscriptUnavailableError):
            scraper.process_video(URL)

    def test_noise_only_transcript_raises_not_empty_file(self, monkeypatch, tmp_path):
        """Texto que _clean_text reduce a '' (solo ruido) -> error, no archivo vacío 'exitoso'."""
        scraper = _make_scraper_with_fake_client()
        _patch_happy_path_until_groq(monkeypatch, scraper, tmp_path,
                                     "[Música] (Risas) [00:01:23]")
        scraper.output_path = tmp_path / "outputs"
        scraper.output_path.mkdir()

        with pytest.raises(errors.TranscriptUnavailableError):
            scraper.process_video(URL)
        assert not list(scraper.output_path.iterdir())  # cero archivos basura

    def test_audio_too_large_raises_audio_too_large_error(self, monkeypatch, tmp_path):
        """Audio >25MB -> AudioTooLargeError con size_mb (antes: return None silencioso)."""
        scraper = _make_scraper_with_fake_client()
        audio = tmp_path / "vid12345678.m4a"
        # 26MB exactos
        audio.write_bytes(b"x" * (26 * 1024 * 1024))
        monkeypatch.setattr(scraper, "get_metadata", lambda url: METADATA)
        monkeypatch.setattr(OmniScraper, "_build_transcript_api",
                            staticmethod(lambda: FakeTranscriptApiEmpty()))
        monkeypatch.setattr(scraper, "_download_audio",
                            lambda url, temp_dir, video_id: str(audio))

        with pytest.raises(errors.AudioTooLargeError) as exc_info:
            scraper.process_video(URL)
        err = exc_info.value
        assert err.size_mb is not None and err.size_mb > 25
        assert err.video_id == "vid12345678"
        assert "25" in err.message  # el mensaje menciona el límite

    def test_success_path_still_returns_file_path(self, monkeypatch, tmp_path):
        """El happy path sigue retornando el path del transcript guardado."""
        scraper = _make_scraper_with_fake_client()
        _patch_happy_path_until_groq(monkeypatch, scraper, tmp_path,
                                     "Hola este es el transcript de prueba")
        # Aislar outputs/ del repo real
        scraper.output_path = tmp_path / "outputs"
        scraper.output_path.mkdir()

        result = scraper.process_video(URL)
        assert result is not None
        assert os.path.exists(result)
        with open(result, encoding="utf-8") as f:
            assert "transcript de prueba" in f.read()
