"""
Unit tests de la Fase 2.3 (logging estructurado + redacción de secretos).
Puros: sin red. Ver plans/Plan de mejoras de la app.md (tarea 2.3).

Foco de seguridad: ningún secreto (cookies, API keys de Groq, tokens de YouTube)
debe poder llegar a un handler de logging sin redactar — ni en el mensaje, ni
pasado como argumento de logging (logger.info("x %s", secret)).
"""
import io
import logging

import pytest

import app_config
from app_config import RedactionFilter, configure_logging


def _record(msg, args=None):
    """Construye un LogRecord crudo para pasar por el filtro."""
    return logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg=msg, args=args, exc_info=None,
    )


# ---------------------------------------------------------------------------
# RedactionFilter — núcleo de seguridad
# ---------------------------------------------------------------------------
class TestRedactionFilter:
    def test_redacts_groq_key_in_message(self):
        rec = _record("Configurando cliente con key gsk_ABC123def456GHI789jkl")
        RedactionFilter().filter(rec)
        out = rec.getMessage()
        assert "gsk_ABC123def456GHI789jkl" not in out
        assert "REDACTED" in out

    def test_redacts_groq_key_passed_as_logging_arg(self):
        """El secreto pasado como arg (%s) también debe redactarse, no solo en el msg."""
        rec = _record("api key = %s", ("gsk_SECRETkey1234567890",))
        RedactionFilter().filter(rec)
        out = rec.getMessage()
        assert "gsk_SECRETkey1234567890" not in out
        assert "REDACTED" in out

    def test_redacts_cookie_header(self):
        rec = _record("Cookie: SID=abc123; HSID=def456; SSID=ghi789")
        RedactionFilter().filter(rec)
        out = rec.getMessage()
        assert "abc123" not in out
        assert "REDACTED" in out

    def test_redacts_authorization_header(self):
        rec = _record("Authorization: Bearer gsk_LEAKED1234567890abcdef")
        RedactionFilter().filter(rec)
        out = rec.getMessage()
        assert "gsk_LEAKED1234567890abcdef" not in out
        assert "REDACTED" in out

    @pytest.mark.parametrize("token", [
        "SAPISID=AbCdEf123456",
        "APISID=token_value_here",
        "HSID=secretohsid",
        "SSID=secretossid",
        "SID=plainsidcookie",
        "__Secure-3PSID=deadbeefcafe",
    ])
    def test_redacts_youtube_auth_tokens(self, token):
        secret_value = token.split("=", 1)[1]
        rec = _record(f"netscape cookie line: {token}")
        RedactionFilter().filter(rec)
        out = rec.getMessage()
        assert secret_value not in out, f"{token} no fue redactado"
        assert "REDACTED" in out

    def test_passes_through_non_secret_unchanged(self):
        rec = _record("Procesando video 3 de 10: Mi Video Genial")
        result = RedactionFilter().filter(rec)
        assert result is True
        assert rec.getMessage() == "Procesando video 3 de 10: Mi Video Genial"

    def test_filter_never_drops_records(self):
        """El filtro redacta pero SIEMPRE deja pasar el record (return True)."""
        rec = _record("Cookie: SID=secret")
        assert RedactionFilter().filter(rec) is True

    def test_filter_survives_malformed_format_args(self):
        """Un log mal formado (%s sin args) no debe crashear el filtro/logging."""
        rec = _record("valor faltante %s", ())  # getMessage() no rompe con args vacío
        # No debe lanzar:
        assert RedactionFilter().filter(rec) is True


# ---------------------------------------------------------------------------
# configure_logging — wiring centralizado
# ---------------------------------------------------------------------------
class TestConfigureLogging:
    def test_sets_level_from_env(self, monkeypatch):
        monkeypatch.setattr(app_config, "load_dotenv", lambda *a, **k: None)
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        configure_logging()
        assert logging.getLogger().level == logging.DEBUG

    def test_default_level_is_info(self, monkeypatch):
        monkeypatch.setattr(app_config, "load_dotenv", lambda *a, **k: None)
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        configure_logging()
        assert logging.getLogger().level == logging.INFO

    def test_invalid_level_falls_back_to_info(self, monkeypatch):
        monkeypatch.setattr(app_config, "load_dotenv", lambda *a, **k: None)
        monkeypatch.setenv("LOG_LEVEL", "NOTAREALLEVEL")
        configure_logging()
        assert logging.getLogger().level == logging.INFO

    def test_idempotent_no_handler_stacking(self, monkeypatch):
        monkeypatch.setattr(app_config, "load_dotenv", lambda *a, **k: None)
        configure_logging()
        n1 = len(logging.getLogger().handlers)
        configure_logging()
        configure_logging()
        n2 = len(logging.getLogger().handlers)
        assert n2 == n1

    def test_every_root_handler_carries_redaction_filter(self, monkeypatch):
        """Garantía de seguridad: TODO handler de root redacta (incluye los preexistentes)."""
        monkeypatch.setattr(app_config, "load_dotenv", lambda *a, **k: None)
        # Simular un handler "ajeno" (ej. el que instala Streamlit) sin filtro.
        foreign = logging.StreamHandler(io.StringIO())
        logging.getLogger().addHandler(foreign)
        try:
            configure_logging()
            for h in logging.getLogger().handlers:
                assert any(isinstance(f, RedactionFilter) for f in h.filters), h
        finally:
            logging.getLogger().removeHandler(foreign)

    def test_end_to_end_emitted_output_is_redacted(self, monkeypatch):
        """Un logger hijo cualquiera, emitido por un handler con el filtro, sale redactado."""
        monkeypatch.setattr(app_config, "load_dotenv", lambda *a, **k: None)
        configure_logging()
        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(logging.Formatter("%(name)s - %(message)s"))
        handler.addFilter(RedactionFilter())
        root = logging.getLogger()
        root.addHandler(handler)
        try:
            logging.getLogger("scraper.child").error(
                "fallo con Authorization: Bearer gsk_REALLEAK1234567890")
            out = buf.getvalue()
            assert "gsk_REALLEAK1234567890" not in out
            assert "REDACTED" in out
        finally:
            root.removeHandler(handler)
