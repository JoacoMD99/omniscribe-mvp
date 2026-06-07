"""
Jerarquía de excepciones tipadas de OmniScribe AI.

Creada en Fase 1.4 del plan de mejoras (mínimo necesario para download resiliency);
la Fase 2.1 la completa hilándola por todo process_video y cambiando el contrato
de "return None" a "raise tipado".

Cada excepción lleva un `message` en español apto para mostrarse en la UI,
un `short_label` para etiquetas compactas (st.status) y contexto opcional
(url, video_id) para logging.
"""
from typing import Optional


class OmniScribeError(Exception):
    """Base de errores de dominio de OmniScribe."""
    short_label = "Error"

    def __init__(self, message: str, *, url: Optional[str] = None,
                 video_id: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.url = url
        self.video_id = video_id


class VideoBlockedError(OmniScribeError):
    """YouTube bloqueó la request (detección anti-bot / IpBlocked / 403 / 429)."""
    short_label = "Bloqueado por YouTube"


class VideoUnavailableError(OmniScribeError):
    """El video no existe, es privado, fue eliminado o está restringido por región."""
    short_label = "Video no disponible"


class TranscriptUnavailableError(OmniScribeError):
    """No hay transcript oficial utilizable y no se pudo generar uno."""
    short_label = "Sin transcripción"


class AudioDownloadError(OmniScribeError):
    """La descarga del audio falló o no produjo ningún archivo."""
    short_label = "Fallo de descarga"


class AudioTooLargeError(OmniScribeError):
    """El audio supera el límite de 25MB de la API de Groq Whisper."""
    short_label = "Audio >25MB"

    def __init__(self, message: str, *, size_mb: Optional[float] = None,
                 url: Optional[str] = None, video_id: Optional[str] = None) -> None:
        super().__init__(message, url=url, video_id=video_id)
        self.size_mb = size_mb


class GroqConfigError(OmniScribeError):
    """No hay GROQ_API_KEY configurada y se necesita el fallback de Whisper."""
    short_label = "Groq no configurado"


class GroqTranscriptionError(OmniScribeError):
    """La transcripción vía Groq Whisper falló tras los reintentos."""
    short_label = "Fallo de Groq"
