from youtube_transcript_api import YouTubeTranscriptApi

video_id = "JY4DK_ZLDqQ" # Video de TJR Trades
print(f"--- INICIANDO TEST PARA VIDEO: {video_id} ---")

try:
    # Creamos una instancia del API
    api = YouTubeTranscriptApi()
    # Intentamos listar las transcripciones disponibles
    transcript_list = api.list(video_id)
    print("✅ Conexión exitosa. Transcripciones encontradas.")
    
    # Intentamos obtener la primera disponible en inglés
    transcript = transcript_list.find_transcript(['en'])
    data = transcript.fetch()
    
    print("\n--- MUESTRA DEL TEXTO OBTENIDO ---")
    full_text = " ".join([t.text for t in data[:10]]) # Primeras 10 líneas
    print(full_text)
    print("\n✅ TEST FINALIZADO CON ÉXITO")
except Exception as e:
    print(f"❌ ERROR EN EL TEST: {e}")
    print("\nSugerencia: Si el error dice 'No transcript found', es un bloqueo de YouTube.")
