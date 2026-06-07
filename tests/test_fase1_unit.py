"""
Unit tests de la Fase 1 (anti-bot + resiliencia de descarga).
Puros: sin red, sin API keys reales. Ver plans/Plan de mejoras de la app.md (tareas 1.1-1.4).
"""
import base64
import os
from pathlib import Path

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


@pytest.fixture()
def scraper():
    """Instancia sin key real: el constructor de Groq no valida contra red."""
    return OmniScraper(groq_api_key="gsk_fake_key_for_tests")


# ---------------------------------------------------------------------------
# 1.1 — Cookie loader (YOUTUBE_COOKIES_B64 -> cookiefile temporal)
# ---------------------------------------------------------------------------
class TestCookieLoader:
    def test_round_trip_decode_write_path(self, monkeypatch):
        raw = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tTEST\tvalue\n"
        monkeypatch.setenv("YOUTUBE_COOKIES_B64", base64.b64encode(raw.encode("utf-8")).decode("ascii"))
        path = app_config.get_youtube_cookiefile()
        assert path is not None
        assert os.path.exists(path)
        assert Path(path).read_bytes().decode("utf-8") == raw

    def test_missing_env_returns_none(self, monkeypatch):
        monkeypatch.delenv("YOUTUBE_COOKIES_B64", raising=False)
        assert app_config.get_youtube_cookiefile() is None

    def test_invalid_base64_returns_none_without_crash(self, monkeypatch):
        monkeypatch.setenv("YOUTUBE_COOKIES_B64", "esto-no-es-base64-!!!")
        assert app_config.get_youtube_cookiefile() is None

    def test_singleton_same_path_on_second_call(self, monkeypatch):
        monkeypatch.setenv("YOUTUBE_COOKIES_B64", base64.b64encode(b"cookie-data").decode("ascii"))
        p1 = app_config.get_youtube_cookiefile()
        p2 = app_config.get_youtube_cookiefile()
        assert p1 == p2 and p1 is not None


# ---------------------------------------------------------------------------
# 1.2 — Builder centralizado _base_ydl_opts()
# ---------------------------------------------------------------------------
class TestBaseYdlOpts:
    def test_hardening_defaults(self, scraper, monkeypatch):
        monkeypatch.delenv("YOUTUBE_COOKIES_B64", raising=False)
        monkeypatch.delenv("YTDLP_PLAYER_CLIENT", raising=False)
        opts = scraper._base_ydl_opts()
        assert opts["socket_timeout"] == 30
        assert opts["retries"] == 5
        assert opts["fragment_retries"] == 5
        assert opts["extractor_retries"] == 3
        assert opts["sleep_interval"] == 2
        assert opts["max_sleep_interval"] == 6
        assert "User-Agent" in opts["http_headers"]
        assert "Chrome" in opts["http_headers"]["User-Agent"]

    def test_no_cookiefile_without_secret(self, scraper, monkeypatch):
        monkeypatch.delenv("YOUTUBE_COOKIES_B64", raising=False)
        monkeypatch.delenv("YTDLP_PLAYER_CLIENT", raising=False)
        opts = scraper._base_ydl_opts()
        assert "cookiefile" not in opts
        assert "extractor_args" not in opts

    def test_cookiefile_present_with_secret(self, scraper, monkeypatch):
        monkeypatch.setenv("YOUTUBE_COOKIES_B64", base64.b64encode(b"data").decode("ascii"))
        opts = scraper._base_ydl_opts()
        assert "cookiefile" in opts
        assert os.path.exists(opts["cookiefile"])

    def test_player_client_escape_hatch(self, scraper, monkeypatch):
        monkeypatch.setenv("YTDLP_PLAYER_CLIENT", "tv, android_vr")
        opts = scraper._base_ydl_opts()
        assert opts["extractor_args"]["youtube"]["player_client"] == ["tv", "android_vr"]


# ---------------------------------------------------------------------------
# 1.4 — Excepciones tipadas + clasificador de errores de descarga
# ---------------------------------------------------------------------------
class TestTypedErrors:
    def test_hierarchy_and_spanish_message(self):
        e = errors.VideoBlockedError("YouTube bloqueó la request", url="u", video_id="v")
        assert isinstance(e, errors.OmniScribeError)
        assert str(e) == "YouTube bloqueó la request"
        assert e.message == "YouTube bloqueó la request"
        assert e.url == "u" and e.video_id == "v"
        assert e.short_label  # etiqueta corta para la UI (Fase 2.4)

    def test_classifier_detects_bot_block(self, scraper):
        for msg in ("HTTP Error 403: Forbidden",
                    "Sign in to confirm you're not a bot",
                    "HTTP Error 429: Too Many Requests"):
            err = scraper._classify_download_error(Exception(msg), "url", "vid")
            assert isinstance(err, errors.VideoBlockedError), msg

    def test_classifier_other_errors_are_unavailable(self, scraper):
        err = scraper._classify_download_error(
            Exception("Video unavailable. This video is private"), "url", "vid")
        assert isinstance(err, errors.VideoUnavailableError)
        assert not isinstance(err, errors.VideoBlockedError)


class TestDownloadAudio:
    def test_raises_when_no_output_produced(self, scraper, monkeypatch, tmp_path):
        """_download_audio nunca debe retornar un path inexistente (bug original)."""
        class FakeYDL:
            def __init__(self, opts):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
            def download(self, urls):
                pass  # simula descarga que no produce ningún archivo
        monkeypatch.setattr("scraper.yt_dlp.YoutubeDL", FakeYDL)
        with pytest.raises(errors.AudioDownloadError):
            scraper._download_audio("https://www.youtube.com/watch?v=x", str(tmp_path), "vid123")

    def test_returns_real_m4a_when_produced(self, scraper, monkeypatch, tmp_path):
        produced = tmp_path / "vid123.m4a"

        class FakeYDL:
            def __init__(self, opts):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
            def download(self, urls):
                produced.write_bytes(b"fake-audio")
        monkeypatch.setattr("scraper.yt_dlp.YoutubeDL", FakeYDL)
        result = scraper._download_audio("https://www.youtube.com/watch?v=x", str(tmp_path), "vid123")
        assert result == str(produced)
        assert os.path.exists(result)

    def test_ignores_part_files(self, scraper, monkeypatch, tmp_path):
        """Un .part huérfano no debe ser tomado como audio válido."""
        part = tmp_path / "vid123.m4a.part"

        class FakeYDL:
            def __init__(self, opts):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
            def download(self, urls):
                part.write_bytes(b"incomplete")
        monkeypatch.setattr("scraper.yt_dlp.YoutubeDL", FakeYDL)
        with pytest.raises(errors.AudioDownloadError):
            scraper._download_audio("https://www.youtube.com/watch?v=x", str(tmp_path), "vid123")
