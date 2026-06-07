import base64
import binascii
import hmac
import logging
import os
import re
import tempfile
from typing import Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fase 2.3 — Logging estructurado con redacción de secretos
# ---------------------------------------------------------------------------
class RedactionFilter(logging.Filter):
    """
    Redacta secretos (cookies, API keys de Groq, tokens de YouTube) antes de
    que el record llegue al stream de salida.

    SEGURIDAD — el filtro DEBE adjuntarse al HANDLER, no al logger: los filtros
    a nivel logger no ven los records que propagan desde loggers hijos
    (gotcha conocido de la stdlib de logging). configure_logging() lo garantiza.

    Redacta tanto el mensaje como los argumentos de logging (logger.info("x %s",
    secreto)) renderizando el mensaje final y reescribiéndolo en el record.
    """
    _PLACEHOLDER = "***REDACTED***"

    _PATTERNS = (
        # API keys de Groq (gsk_...).
        (re.compile(r"gsk_[A-Za-z0-9]+"), "gsk_***REDACTED***"),
        # Headers de auth: redacta el valor completo hasta fin de línea.
        (re.compile(r"(?im)\b(Cookie|Authorization)\b\s*:\s*.+$"), r"\1: ***REDACTED***"),
        # Cookies de sesión de YouTube en pares nombre=valor (Netscape/headers).
        (re.compile(r"\b(SAPISID|APISID|HSID|SSID|SID|SIDCC|LOGIN_INFO)=[^\s;]+"),
         r"\1=***REDACTED***"),
        # Cookies __Secure-* y __Host-* (3PSID, 1PSID, etc.).
        (re.compile(r"(__Secure-|__Host-)[\w-]*=[^\s;]+"), r"\1***REDACTED***"),
    )

    @classmethod
    def redact(cls, text: str) -> str:
        for pattern, repl in cls._PATTERNS:
            text = pattern.sub(repl, text)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            # Un log mal formado no debe romper el pipeline ni filtrar el secreto:
            # redactamos el template crudo como fallback conservador.
            message = str(record.msg)
        redacted = self.redact(message)
        if redacted != message:
            record.msg = redacted
            record.args = None
        return True  # nunca descartar records


_LOGGING_CONFIGURED = False


def configure_logging() -> None:
    """
    Configura el logging una sola vez para todo el proceso (Fase 2.3):
    formatter con timestamp/nivel/nombre/mensaje, nivel desde env LOG_LEVEL
    (default INFO) y RedactionFilter en TODOS los handlers de root.

    Idempotente: seguro de llamar en cada rerun de Streamlit (no apila handlers).
    """
    global _LOGGING_CONFIGURED

    load_dotenv(override=False)
    level_name = (os.getenv("LOG_LEVEL") or "INFO").upper()
    level = logging.getLevelName(level_name)
    if not isinstance(level, int):  # getLevelName devuelve str para nombres inválidos
        level = logging.INFO

    root = logging.getLogger()

    # Si root no tiene handlers (proceso fresco / CLI / pytest), instalamos el nuestro.
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        ))
        root.addHandler(handler)

    # Garantía de seguridad: TODO handler (incluidos los preexistentes, p. ej. los
    # que pueda instalar Streamlit) debe redactar. Añadir el filtro sin duplicar.
    for h in root.handlers:
        if not any(isinstance(f, RedactionFilter) for f in h.filters):
            h.addFilter(RedactionFilter())
        h.setLevel(level)

    root.setLevel(level)
    _LOGGING_CONFIGURED = True

def get_groq_api_key():
    """
    Carga las variables de entorno desde .env y valida
    los tokens requeridos para el funcionamiento de la app,
    sobreescribiendo variables para captar cambios en tiempo real.
    """
    load_dotenv(override=False)

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("GROQ_API_KEY no encontrada. El procesamiento con Groq Whisper (Fallback) no estará disponible.")

    return api_key

# Cache del cookiefile: se materializa una sola vez por proceso (Fase 1.1).
_cookie_cache = {"initialized": False, "path": None}

def get_youtube_cookiefile() -> Optional[str]:
    """
    Materializa las cookies de YouTube desde el secret YOUTUBE_COOKIES_B64
    (base64 de un cookies.txt en formato Netscape) hacia un archivo temporal
    y retorna su path para usar como 'cookiefile' de yt-dlp.

    - Singleton por proceso: el archivo se escribe una sola vez.
    - Fail-safe: si el secret falta o el base64 es inválido, retorna None
      y la app continúa sin cookies (con menor tasa de éxito en IPs cloud).

    Nota operativa: YouTube invalida cookies reusadas desde una IP distinta a la
    del navegador que las generó. Exportarlas idealmente de una cuenta descartable
    y renovarlas cada ~2-4 semanas o cuando reaparezcan bloqueos.
    """
    if _cookie_cache["initialized"]:
        return _cookie_cache["path"]
    _cookie_cache["initialized"] = True

    load_dotenv(override=False)
    raw = (os.getenv("YOUTUBE_COOKIES_B64") or "").strip()
    if not raw:
        logger.info("YOUTUBE_COOKIES_B64 no configurada. yt-dlp correrá sin cookies.")
        return None

    try:
        data = base64.b64decode(raw, validate=True)
        tmp = tempfile.NamedTemporaryFile(mode="wb", suffix="_yt_cookies.txt", delete=False)
        tmp.write(data)
        tmp.close()
        _cookie_cache["path"] = tmp.name
        logger.info("Cookies de YouTube cargadas desde YOUTUBE_COOKIES_B64 (cookiefile temporal).")
    except (binascii.Error, ValueError, OSError) as e:
        # No loggear el contenido del secret: solo el tipo de fallo.
        logger.warning(f"YOUTUBE_COOKIES_B64 inválida ({type(e).__name__}). Se continúa sin cookies.")
        _cookie_cache["path"] = None

    return _cookie_cache["path"]

# ---------------------------------------------------------------------------
# Fase 3.1 — Password gate (auth simple para proteger la cuota de Groq)
# ---------------------------------------------------------------------------
def get_app_password() -> Optional[str]:
    """
    Lee APP_PASSWORD del entorno (secret del deploy / .env local).

    Retorna None si no está configurada → el gate bloquea el acceso (fail-closed):
    la app NUNCA se abre sin contraseña configurada.
    """
    load_dotenv(override=False)
    return os.getenv("APP_PASSWORD")


def password_is_valid(provided: str, expected: Optional[str]) -> bool:
    """
    Verifica la contraseña en TIEMPO CONSTANTE (hmac.compare_digest) para no
    filtrar información por timing.

    SEGURIDAD:
    - Fail-closed: si `expected` no está configurada (None/vacía), SIEMPRE False
      —la app nunca se abre sin APP_PASSWORD—, y una `provided` vacía nunca
      autentica. El guard va ANTES de compare_digest porque compare_digest('','')
      es True (autenticaría a cualquiera con la config vacía).
    - Se codifica a bytes UTF-8: compare_digest sobre `str` exige ASCII y rompería
      con una contraseña con acentos/ñ (p. ej. la del .env.example).
    """
    if not expected or not provided:
        return False
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


# Configurar logging (con redacción de secretos) antes de cualquier log de la app.
configure_logging()

# Singleton variables for the app
GROQ_API_KEY = get_groq_api_key()
