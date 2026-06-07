---
title: OmniScribe AI
emoji: 🤖
colorFrom: indigo
colorTo: purple
sdk: streamlit
sdk_version: "1.55.0"
app_file: app.py
pinned: false
---

# OmniScribe AI | Knowledge Engine 🤖

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=Streamlit&logoColor=white)](https://streamlit.io/)
[![Groq Whisper](https://img.shields.io/badge/Groq-Whisper--v3-6366F1)](https://groq.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**OmniScribe AI** is a high-performance, AI-first content ingestion engine designed to automate the capture and transcription of strategic knowledge from YouTube. Built for researchers, and content strategists (specifically optimized for KAI Trades), it transforms massive video data into clean, LLM-ready text files.

---

## 🚀 Key Features

- **Massive Ingestion Engine**: Process batches of up to 10 individual URLs or entire YouTube Playlists with a single click.
- **Resilient Dual-Layer Transcription**:
  - **Layer 1 (Fast & Native)**: Attempts to fetch official or auto-generated transcripts using `youtube-transcript-api`.
  - **Layer 2 (AI Fallback)**: If Layer 1 fails (IP block or missing transcript), it automatically downloads the audio via `yt-dlp` and transcribes it using **Groq's Whisper-large-v3** (Ultra-fast inference).
- **Glassmorphic SaaS UI**: A modern, high-contrast dark mode interface built with Streamlit, optimized for productivity.
- **AI-Ready Outputs**: Automatically cleans transcripts of timestamps, noise tags (e.g., [Music]), and redundant spaces.
- **Knowledge Ecosystem**: Designed to feed the `skills/` library, a collection of AI frameworks (STAR + R-I-S-E) for summarizing and analyzing content.

---

## 🛠 Tech Stack

- **Frontend/UI**: [Streamlit](https://streamlit.io/) (Custom Glassmorphism CSS).
- **Video Processing**: [yt-dlp](https://github.com/yt-dlp/yt-dlp).
- **AI Inference**: [Groq Cloud API](https://groq.com/) (Whisper-large-v3).
- **Transcription**: [YouTube Transcript API](https://github.com/jdepoix/youtube-transcript-api).
- **Reliability**: [Tenacity](https://github.com/jd/tenacity) (Retries & Exponential Backoff).

---

## 📦 Installation & Setup

### 1. Prerequisites
- **Python 3.10+**
- **FFmpeg**: Required for audio extraction fallback.
  - **Windows (WinGet)**: `winget install Gyan.FFmpeg`
  - **macOS (Homebrew)**: `brew install ffmpeg`
  - **Linux (Apt)**: `sudo apt install ffmpeg`

### 2. Clone and Install
```powershell
# Clone the repository
git clone https://github.com/your-username/omniscribe-ai.git
cd omniscribe-ai

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file in the root directory and add your Groq API key (optional but highly recommended for the fallback layer):

```env
GROQ_API_KEY=gsk_your_api_key_here
```

---

## 🚀 Deploy a Hugging Face Spaces

> **Prerequisitos:** cuenta gratuita en [huggingface.co](https://huggingface.co) + repositorio de GitHub con el código.

### 1. Crear el Space

1. Ir a **huggingface.co → New Space**.
2. Nombre: `omniscribe-ai` (o el que prefieras).
3. **SDK → Streamlit** · Hardware → **CPU basic · Free**.
4. Visibilidad → **Private** (recomendado mientras usás `APP_PASSWORD`).
5. Click **Create Space**.

### 2. Conectar el repositorio de GitHub

En la pestaña **Files** del Space → **Connect a GitHub repository** (o clonar directamente).  
Alternativamente, agregar HF como remote y hacer push:

```bash
# Reemplazá TU_USUARIO y TU_SPACE_NAME con los reales
git remote add hf https://huggingface.co/spaces/TU_USUARIO/TU_SPACE_NAME
git push hf main
```

Cada `git push hf main` rebuildeará el Space automáticamente.

### 3. Configurar los secrets (Settings → Variables and secrets)

En la pestaña **Settings** del Space → sección **Variables and secrets**:

| Variable | Descripción | Requerida |
|---|---|---|
| `GROQ_API_KEY` | API key de Groq Cloud (console.groq.com) | ✅ Sí |
| `APP_PASSWORD` | Contraseña del equipo para el login | ✅ Sí |
| `YOUTUBE_COOKIES_B64` | Cookies de YouTube en base64 (ver abajo) | Recomendada |
| `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` (default: INFO) | No |
| `YTDLP_PLAYER_CLIENT` | Fallback de player client para yt-dlp (ej. `tv,android_vr`) | No |

> ⚠️ Los secrets se inyectan como variables de entorno. **Nunca** pongas credenciales en el código ni en archivos commiteados.

### 4. `packages.txt` — ffmpeg

El archivo `packages.txt` ya está en el repo con el contenido:
```
ffmpeg
```
HF Spaces instala automáticamente los paquetes de `packages.txt` vía `apt` en cada build. No hace falta configuración adicional.

### 5. Exportar cookies de YouTube (YOUTUBE_COOKIES_B64)

Las cookies permiten que `yt-dlp` sortee los bloqueos anti-bot de YouTube en IPs de datacenter.

**Paso a paso:**

1. Instalar la extensión **"Get cookies.txt LOCALLY"** en Chrome/Firefox.
2. Loguearse en YouTube con una **cuenta secundaria/descartable** (no usar cuenta principal — YouTube puede marcar el uso automatizado).
3. Abrir `youtube.com`, clic en la extensión → **Export cookies** → guardar como `cookies.txt`.
4. Codificar en base64:
   - **PowerShell (Windows):** `[Convert]::ToBase64String([IO.File]::ReadAllBytes("cookies.txt")) | Set-Clipboard`
   - **Linux/macOS:** `base64 -w0 cookies.txt | pbcopy` (macOS) o `base64 -w0 cookies.txt | xclip`
5. Pegar el resultado en la variable `YOUTUBE_COOKIES_B64` del Space.

> 🔄 **Renovar cada 2-4 semanas** o cuando reaparezcan bloqueos frecuentes. YouTube invalida cookies usadas desde IPs distintas a la del navegador original.

---

### Caveats importantes del free tier

| Caveat | Detalle |
|---|---|
| **Storage efímero** | El directorio `outputs/` se borra en cada restart/rebuild. Los transcripts se deben descargar vía el botón ZIP antes de cerrar la sesión. |
| **Sleep tras 48h** | El Space se "duerme" si no recibe tráfico en 48h. Al primera visita se despierta automáticamente (~30-60s de cold start). |
| **Sin disco persistente** | El free tier no tiene volúmenes persistentes. Para guardar historial entre sesiones, usar la funcionalidad de descarga ZIP inmediata. |
| **Refresh pierde el estado** | Refrescar el browser durante un run largo resetea la UI (el proceso de yt-dlp en el servidor sigue corriendo pero se pierde el seguimiento visual). Descargar el ZIP antes de cerrar. |

---

## 🕹 Usage

1. **Launch the Application**:
   ```bash
   streamlit run app.py
   ```
2. **Batch Processing**: Go to "📝 Links Individuales", paste up to 10 YouTube URLs, and click **"Iniciar Extracción Masiva"**.
3. **Playlist Processing**: Go to "📂 Playlist Completa", paste a playlist URL, analyze it, and start the extraction.
4. **Download**: Once finished, download all transcripts in a single `.zip` package.

---

## 📂 Project Structure

```text
omniscribe-ai/
├── app.py                # Streamlit UI & Orchestration
├── scraper.py            # Core Extraction & Transcription Engine
├── app_config.py         # Configuration & Env Var Management
├── requirements.txt      # Python Dependencies
├── outputs/              # Directory for generated .txt files
├── skills/               # AI Analysis Prompt Library (Markdown)
└── tests/                # Unit and Extraction tests
```

---

## 🛡 Architectural Integrity

- **Clean Text**: Implements Regex-based sanitization for human-like reading and LLM precision.
- **Resource Management**: Automatic cleanup of temporary audio files to preserve disk space.
- **Resiliency**: Uses exponential backoff for API calls to handle rate limits and network instability.
- **Security**: Environment variables used for all sensitive credentials.

---

## 🤝 Contributing

We welcome contributions! Please feel free to submit a Pull Request or open an issue for feature requests.

1. Fork the project.
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the Branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information (if applicable).

---
**Tech Lead Note**: *This tool is built for maximum throughput and reliability. Always ensure your Groq API usage limits are monitored when processing large playlists.*
