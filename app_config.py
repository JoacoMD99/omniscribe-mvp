import base64
import binascii
import logging
import os
import tempfile
from typing import Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

def get_groq_api_key():
    """
    Carga las variables de entorno desde .env y valida
    los tokens requeridos para el funcionamiento de la app,
    sobreescribiendo variables para captar cambios en tiempo real.
    """
    load_dotenv(override=True)

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

    load_dotenv(override=True)
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

# Singleton variables for the app
GROQ_API_KEY = get_groq_api_key()
