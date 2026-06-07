"""
Unit tests de la Fase 3.1 (password gate con hmac.compare_digest).
Puros: sin red, sin Streamlit real. Ver plans/Plan de mejoras de la app.md (tarea 3.1).

Foco de seguridad:
- Comparación en tiempo constante (no filtra por timing).
- Fail-closed: sin APP_PASSWORD configurada, la app NUNCA se abre.
- '' vs '' no debe autenticar (hmac.compare_digest('','') es True → el guard gana).
"""
import sys
from unittest.mock import MagicMock

import pytest

# Mockear streamlit ANTES de importar app (evita set_page_config real).
if "streamlit" not in sys.modules:
    sys.modules["streamlit"] = MagicMock()

import app  # noqa: E402
import app_config  # noqa: E402
from app_config import get_app_password, password_is_valid  # noqa: E402


# ---------------------------------------------------------------------------
# get_app_password — lectura del secret
# ---------------------------------------------------------------------------
class TestGetAppPassword:
    def test_returns_configured_password(self, monkeypatch):
        monkeypatch.setattr(app_config, "load_dotenv", lambda *a, **k: None)
        monkeypatch.setenv("APP_PASSWORD", "s3cr3t-fuerte")
        assert get_app_password() == "s3cr3t-fuerte"

    def test_returns_none_when_unset(self, monkeypatch):
        monkeypatch.setattr(app_config, "load_dotenv", lambda *a, **k: None)
        monkeypatch.delenv("APP_PASSWORD", raising=False)
        assert get_app_password() is None


# ---------------------------------------------------------------------------
# password_is_valid — núcleo de seguridad (tiempo constante + fail-closed)
# ---------------------------------------------------------------------------
class TestPasswordIsValid:
    def test_correct_password_authenticates(self):
        assert password_is_valid("hunter2", "hunter2") is True

    def test_wrong_password_rejected(self):
        assert password_is_valid("wrong", "hunter2") is False

    def test_empty_input_rejected(self):
        assert password_is_valid("", "hunter2") is False

    def test_fail_closed_when_expected_none(self):
        assert password_is_valid("lo-que-sea", None) is False

    def test_fail_closed_when_expected_empty(self):
        assert password_is_valid("lo-que-sea", "") is False

    def test_empty_input_and_empty_expected_does_not_authenticate(self):
        # CRÍTICO: hmac.compare_digest('', '') == True; el fail-closed debe ganar.
        assert password_is_valid("", "") is False

    def test_non_ascii_password_supported(self):
        # compare_digest sobre str exige ASCII; debe codificar a bytes y no romper.
        assert password_is_valid("contraseña-ñandú", "contraseña-ñandú") is True
        assert password_is_valid("contraseña-ñandu", "contraseña-ñandú") is False

    def test_differing_lengths_do_not_crash(self):
        assert password_is_valid("corta", "una-mucho-mas-larga") is False


# ---------------------------------------------------------------------------
# check_password — wiring del gate en la UI (fail-closed a nivel app)
# ---------------------------------------------------------------------------
class TestCheckPasswordGate:
    def test_returns_true_when_already_authenticated(self, monkeypatch):
        fake_session = MagicMock()
        fake_session.get.return_value = True
        monkeypatch.setattr(app.st, "session_state", fake_session)
        assert app.check_password() is True

    def test_fail_closed_when_password_not_configured(self, monkeypatch):
        fake_session = MagicMock()
        fake_session.get.return_value = None  # sesión no autenticada
        monkeypatch.setattr(app.st, "session_state", fake_session)
        monkeypatch.setattr(app.app_config, "get_app_password", lambda: None)
        fake_error = MagicMock()
        monkeypatch.setattr(app.st, "error", fake_error)

        assert app.check_password() is False
        fake_error.assert_called_once()  # muestra el aviso de "no configurada"

    def test_blocks_when_not_authenticated_but_configured(self, monkeypatch):
        """Configurada pero aún sin autenticar: el gate devuelve False (no abre)."""
        fake_session = MagicMock()
        fake_session.get.return_value = None
        monkeypatch.setattr(app.st, "session_state", fake_session)
        monkeypatch.setattr(app.app_config, "get_app_password", lambda: "secreta")
        # Sin click en "Ingresar" (st.button del MagicMock devuelve un Mock falsy-controlado):
        monkeypatch.setattr(app.st, "button", lambda *a, **k: False)
        monkeypatch.setattr(app.st, "text_input", lambda *a, **k: "")

        assert app.check_password() is False
