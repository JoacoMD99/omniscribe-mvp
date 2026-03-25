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
