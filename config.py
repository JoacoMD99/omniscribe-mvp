import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

def setup_environment():
    """
    Carga las variables de entorno desde .env y valida 
    los tokens requeridos para el funcionamiento de la app.
    """
    load_dotenv()
    
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.warning("GROQ_API_KEY no encontrada. El procesamiento con Groq Whisper (Fallback) no estará disponible.")
        
    return api_key

# Singleton variables for the app
GROQ_API_KEY = setup_environment()
