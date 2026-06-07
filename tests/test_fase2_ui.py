"""
Unit tests de la Fase 2.4 (columna "Motivo" en la UI de resultados).
Puros: sin red, sin Streamlit real. Ver plans/Plan de mejoras de la app.md (tarea 2.4).

Foco: _process_video_to_result produce el dict correcto para session_state.
Las llamadas de UI (status.update, st.error) se verifican a nivel de contrato de datos.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Streamlit debe estar mockeado ANTES de importar app para evitar set_page_config().
if "streamlit" not in sys.modules:
    sys.modules["streamlit"] = MagicMock()

from app import _process_video_to_result  # noqa: E402
from errors import (  # noqa: E402
    AudioTooLargeError,
    GroqConfigError,
    OmniScribeError,
    TranscriptUnavailableError,
    VideoBlockedError,
)

URL = "https://www.youtube.com/watch?v=test123"


class _FakeScraper:
    """Simula OmniScraper con comportamiento controlado."""

    def __init__(self, behavior):
        self._behavior = behavior

    def process_video(self, url: str):
        if isinstance(self._behavior, Exception):
            raise self._behavior
        return self._behavior  # path string on success


# ---------------------------------------------------------------------------
# Contrato del dict de resultado
# ---------------------------------------------------------------------------
class TestProcessVideoToResult:
    def test_success_returns_exito_estado(self, tmp_path):
        out = tmp_path / "vid.txt"
        out.write_text("contenido")
        result = _process_video_to_result(_FakeScraper(str(out)), URL)
        assert result["Estado"] == "✅ Éxito"

    def test_success_stores_full_path_for_zip(self, tmp_path):
        out = tmp_path / "vid.txt"
        out.write_text("contenido")
        result = _process_video_to_result(_FakeScraper(str(out)), URL)
        assert result["_path"] == str(out)

    def test_success_has_empty_motivo(self, tmp_path):
        out = tmp_path / "vid.txt"
        out.write_text("contenido")
        result = _process_video_to_result(_FakeScraper(str(out)), URL)
        assert result["Motivo"] == ""

    def test_omni_error_estado_contains_short_label(self):
        err = VideoBlockedError("bloqueado", url=URL)
        result = _process_video_to_result(_FakeScraper(err), URL)
        assert "Bloqueado por YouTube" in result["Estado"]
        assert result["Estado"].startswith("❌")

    def test_omni_error_motivo_contains_full_message(self):
        err = GroqConfigError("No hay GROQ_API_KEY configurada", url=URL)
        result = _process_video_to_result(_FakeScraper(err), URL)
        assert "No hay GROQ_API_KEY configurada" in result["Motivo"]

    def test_omni_error_path_is_none(self):
        err = TranscriptUnavailableError("sin transcripción", url=URL)
        result = _process_video_to_result(_FakeScraper(err), URL)
        assert result["_path"] is None
        assert result["Archivo"] == "-"

    def test_audio_too_large_exposes_size_in_motivo(self):
        err = AudioTooLargeError("El audio pesa 30.5 MB", size_mb=30.5, url=URL)
        result = _process_video_to_result(_FakeScraper(err), URL)
        assert "30" in result["Motivo"] or "MB" in result["Motivo"]

    def test_unknown_exception_captured_in_motivo(self):
        err = RuntimeError("fallo inesperado del sistema")
        result = _process_video_to_result(_FakeScraper(err), URL)
        assert result["Estado"].startswith("❌")
        assert "fallo inesperado del sistema" in result["Motivo"]
        assert result["_path"] is None

    def test_result_always_has_all_required_keys(self):
        """Garantía de contrato: todo resultado tiene las 5 claves."""
        for behavior in [
            "/tmp/fake_path.txt",
            VideoBlockedError("err", url=URL),
            ValueError("boom"),
        ]:
            result = _process_video_to_result(_FakeScraper(behavior), URL)
            assert set(result.keys()) >= {"URL", "Estado", "Archivo", "Motivo", "_path"}
