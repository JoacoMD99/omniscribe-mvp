import streamlit as st
import io
import time
import zipfile
from pathlib import Path
import app_config
from scraper import OmniScraper

# App Configuration
st.set_page_config(
    page_title="OmniScribe AI | Knowledge Engine",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for SaaS Dark Mode & Glassmorphism
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --glass-bg: rgba(30, 41, 59, 0.7);
        --glass-border: rgba(255, 255, 255, 0.1);
        --primary-accent: #6366F1;
        --primary-hover: #4F46E5;
    }
    
    /* Force Theme-Agnostic Dark Mode */
    .stApp {
        background-color: #0e1117 !important;
        color: #F8FAFC !important;
        font-family: 'Inter', system-ui, sans-serif !important;
    }
    
    .css-1d391kg, [data-testid="stSidebar"] {
        background-color: #1E293B !important;
        border-right: 1px solid var(--glass-border) !important;
    }
    
    /* Input Labels and Text */
    label, p, h1, h2, h3, h4, h5, h6 {
        color: #F1F5F9 !important;
    }
    
    /* Ensure Expander Title (including icon) is visible */
    [data-testid="stExpander"] summary, [data-testid="stExpander"] summary p {
        color: #FFFFFF !important;
        font-weight: 600 !important;
    }

    /* Glassmorphism Containers (Expanders, Metric cards) */
    [data-testid="stExpander"] {
        background-color: var(--glass-bg) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 12px !important;
        backdrop-filter: blur(12px) !important;
    }
    
    /* Metric Scorecards */
    [data-testid="metric-container"] {
        background-color: var(--glass-bg) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 12px !important;
        padding: 1.5rem !important;
        backdrop-filter: blur(12px) !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        text-align: center !important;
    }
    
    [data-testid="stMetricValue"] {
        color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 2.5rem !important;
    }
    
    [data-testid="stMetricLabel"] {
        color: #94A3B8 !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
    }

    /* Tabs margin */
    [data-testid="stTabs"] {
        margin-top: 1rem !important;
    }

    /* Primary Buttons */
    .stButton>button[kind="primary"] {
        width: 100% !important;
        background-color: var(--primary-accent) !important;
        color: white !important;
        font-weight: 600 !important;
        border: none !important;
        padding: 0.75rem 1rem !important;
        border-radius: 8px !important;
        transition: all 0.2s ease !important;
    }
    .stButton>button[kind="primary"]:hover {
        background-color: var(--primary-hover) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3) !important;
    }
    
    /* Secondary Buttons (Glassmorphism for Reset) */
    .stButton>button[kind="secondary"] {
        width: 100% !important;
        background: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        color: #FFFFFF !important;
        font-weight: 600 !important;
        padding: 0.75rem 1rem !important;
        border-radius: 8px !important;
        backdrop-filter: blur(12px) !important;
        transition: all 0.2s ease !important;
    }
    .stButton>button[kind="secondary"]:hover {
        background: rgba(255, 255, 255, 0.1) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2) !important;
    }
    
    /* Download Button */
    .stDownloadButton>button {
        width: 100% !important;
        background-color: #10B981 !important;
        color: white !important;
        font-weight: 600 !important;
        border: none !important;
        padding: 0.75rem 1rem !important;
        border-radius: 8px !important;
        margin-top: 1rem !important;
        transition: all 0.2s ease !important;
    }
    .stDownloadButton>button:hover {
        background-color: #059669 !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3) !important;
    }
    
    /* Text Inputs */
    .stTextInput input {
        background-color: rgba(15, 23, 42, 0.8) !important;
        color: white !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 6px !important;
        padding-left: 10px !important;
    }
    .stTextInput input:focus {
        border-color: var(--primary-accent) !important;
        box-shadow: 0 0 0 1px var(--primary-accent) !important;
    }

    /* Placeholders Contrast */
    ::placeholder {
        color: #a0a0a0 !important;
        opacity: 1 !important;
    }

    /* Header Controls (Deploy/Menu) Adaptive Contrast */
    [data-testid="stHeader"] {
        background-color: transparent !important;
    }
    [data-testid="stHeader"] button, [data-testid="stHeader"] svg {
        color: #FFFFFF !important;
        fill: #FFFFFF !important;
    }
    
    /* Hide Main Menu (Hamburger) to prevent theme switching */
    #MainMenu {
        display: none !important;
    }
    
    /* Status feedback text */
    [data-testid="stStatusWidget"] {
        background-color: var(--glass-bg) !important;
        border-radius: 8px !important;
        border: 1px solid var(--glass-border) !important;
    }
</style>
""", unsafe_allow_html=True)

def create_zip_in_memory(file_paths: list[str]) -> bytes:
    """Creates a ZIP file in memory containing the successfully processed text files."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in file_paths:
            path = Path(file_path)
            if path.exists():
                zip_file.write(path, path.name)
    return zip_buffer.getvalue()

def reset_all_inputs() -> None:
    """Callback to clear all URL inputs in session state."""
    for i in range(10):
        key = f"url_input_{i}"
        if key in st.session_state:
            st.session_state[key] = ""
        else:
            st.session_state[key] = ""
            
    # Reset playlist state
    st.session_state.playlist_urls = []
    st.session_state.is_processing = False
    st.session_state.current_idx = 0
    if "playlist_url_input" in st.session_state:
        st.session_state["playlist_url_input"] = ""

def main() -> None:
    # Session State Initialization
    if 'playlist_urls' not in st.session_state:
        st.session_state.playlist_urls = []
    if 'is_processing' not in st.session_state:
        st.session_state.is_processing = False
    if 'current_idx' not in st.session_state:
        st.session_state.current_idx = 0

    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 OmniScraper")
        st.markdown("---")
        st.markdown("OmniScribe es el motor de inteligencia de contenido para KAI Trades. Diseñado para automatizar la captura de conocimiento estratégico, permite procesar múltiples fuentes de video simultáneamente para alimentar modelos de IA especializados en trading y libertad financiera.")
        
        # Dynamic API Key Check
        current_api_key = app_config.get_groq_api_key()
        status_color = "🟢" if current_api_key else "🟡"
        status_text = "Conectado" if current_api_key else "Sin configurar (.env)"
        st.markdown("---")
        st.markdown(f"**Estado API Groq:** {status_color} {status_text}")

    # Header with Refresh Button
    col_title, col_refresh = st.columns([0.7, 0.3])
    with col_title:
        st.title("OmniScribe AI | Knowledge Engine")
    with col_refresh:
        st.markdown("<br>", unsafe_allow_html=True)
        st.button(
            "🔄 Reiniciar Links", 
            key="refresh_btn", 
            type="secondary", 
            on_click=reset_all_inputs
        )

    st.markdown("Plataforma SaaS de ingesta masiva para procesar contenido de YouTube de alto rendimiento.")

    # Top Metric Scorecards
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    metric_total = col1.empty()
    metric_success = col2.empty()
    metric_error = col3.empty()
    
    # Initialize empty scorecards
    metric_total.metric("Total Procesados", 0)
    metric_success.metric("Éxitos ✅", 0)
    metric_error.metric("Fallos ❌", 0)

    st.markdown("<br>", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📝 Links Individuales", "📂 Playlist Completa"])

    with tab1:
        # Dynamic Video Batch Configuration
        valid_urls = []
        with st.expander("⚙️ Configurar Lote de Videos", expanded=True):
            st.markdown("Ingresa hasta 10 links de YouTube para procesar en lote:")
            
            for i in range(10):
                url = st.text_input(
                    f"▶️ Video {i+1}", 
                    key=f"url_input_{i}", 
                    placeholder="https://www.youtube.com/watch?v=..."
                )
                if url.strip():
                    valid_urls.append(url.strip())

        st.markdown("<br>", unsafe_allow_html=True)

        # Main Action
        if st.button("🚀 Iniciar Extracción Masiva", key="btn_masiva"):
            if not valid_urls:
                st.warning("⚠️ Por favor, ingresa al menos un link válido en la configuración de lote.")
                return

            # Initialize Scraper
            try:
                scraper = OmniScraper()
            except Exception as e:
                st.error(f"❌ Error de inicialización: {str(e)}")
                return

            results = []
            successful_files = []
            
            success_count = 0
            error_count = 0

            progress_bar = st.progress(0)

            for idx, url in enumerate(valid_urls):
                current_num = idx + 1
                total_num = len(valid_urls)
                
                with st.status(f"Procesando video {current_num} de {total_num}...", expanded=True) as status:
                    st.write(f"Link: {url}")
                    try:
                        output_path = scraper.process_video(url)
                        
                        if output_path:
                            status.update(label=f"✅ Video {current_num} procesado con éxito", state="complete")
                            results.append({"URL": url, "Estado": "✅ Éxito", "Archivo": Path(output_path).name})
                            successful_files.append(output_path)
                            success_count += 1
                        else:
                            status.update(label=f"❌ Video {current_num} falló", state="error")
                            results.append({"URL": url, "Estado": "❌ Fallo", "Archivo": "-"})
                            error_count += 1
                    
                    except Exception as e:
                        status.update(label=f"❌ Error crítico en video {current_num}", state="error")
                        st.error(str(e))
                        results.append({"URL": url, "Estado": "❌ Fallo", "Archivo": "-"})
                        error_count += 1
                
                # Update Live Metrics
                metric_total.metric("Total Procesados", current_num)
                metric_success.metric("Éxitos ✅", success_count)
                metric_error.metric("Fallos ❌", error_count)
                
                # Update overall progress
                progress_bar.progress(current_num / total_num)

            # Results Summary
            st.markdown("### 📋 Resumen de Procesamiento")
            st.dataframe(results, width="stretch")

            # Download Action
            if successful_files:
                zip_data = create_zip_in_memory(successful_files)
                st.success(f"🎉 ¡Extracción completada! Se generaron {len(successful_files)} archivos.")
                st.download_button(
                    label="📦 Descargar Paquete Completo (.zip)",
                    data=zip_data,
                    file_name="omniscribe_batch.zip",
                    mime="application/zip",
                    width="stretch"
                )
            else:
                st.error("❌ No se pudo extraer ningún video en este lote.")
                
    with tab2:
        playlist_url_input = st.text_input(
            "URL de la Playlist",
            key="playlist_url_input",
            placeholder="https://www.youtube.com/playlist?list=PL..."
        )

        if st.button("🔍 Analizar Playlist", key="btn_analyze_playlist"):
            if not playlist_url_input.strip():
                st.warning("⚠️ Por favor, ingresa la URL de una playlist de YouTube.")
            else:
                with st.spinner("Analizando playlist..."):
                    try:
                        scraper = OmniScraper()
                        urls = scraper.get_playlist_videos(playlist_url_input.strip())
                        if urls:
                            st.session_state.playlist_urls = urls
                            st.session_state.current_idx = 0
                            st.session_state.is_processing = False
                        else:
                            st.session_state.playlist_urls = []
                            st.warning("⚠️ No se encontraron videos en esta playlist o la URL no es válida.")
                    except Exception as e:
                        st.error(f"❌ Error al analizar la playlist: {str(e)}")
                        st.session_state.playlist_urls = []

        if st.session_state.playlist_urls:
            n = len(st.session_state.playlist_urls)
            st.info(f"✅ Se han detectado {n} videos en esta lista de reproducción.")
            st.markdown("<br>", unsafe_allow_html=True)

            # Controles de Ejecución
            col_btn, col_spacer = st.columns([1, 2])
            with col_btn:
                if st.session_state.current_idx == 0 and not st.session_state.is_processing:
                    if st.button("🚀 Iniciar Extracción de Playlist", key="btn_playlist_play", type="primary"):
                        st.session_state.is_processing = True
                        st.rerun()
                elif st.session_state.is_processing:
                    if st.button("⏸️ Pausar", key="btn_playlist_pause", type="secondary"):
                        st.session_state.is_processing = False
                        st.rerun()
                elif not st.session_state.is_processing and 0 < st.session_state.current_idx < n:
                    if st.button("▶️ Reanudar", key="btn_playlist_resume", type="primary"):
                        st.session_state.is_processing = True
                        st.rerun()

            st.markdown("<hr>", unsafe_allow_html=True)

            # Execution Logic Loop
            if st.session_state.is_processing:
                try:
                    scraper = OmniScraper()
                except Exception as e:
                    st.error(f"❌ Error de inicialización: {str(e)}")
                    st.session_state.is_processing = False
                    st.rerun()

                results = []
                successful_files = []
                success_count = 0
                error_count = 0

                total = len(st.session_state.playlist_urls)
                progress_bar = st.progress(st.session_state.current_idx / total)

                # Iterar desde el offset guardado
                for idx in range(st.session_state.current_idx, total):
                    # Comprobación de estado persistente antes de cada vuelta
                    if not st.session_state.is_processing:
                        st.stop()

                    url = st.session_state.playlist_urls[idx]
                    current_num = idx + 1

                    with st.status(f"Procesando video {current_num} de {total}...", expanded=True) as status:
                        st.write(f"Link: {url}")
                        try:
                            output_path = scraper.process_video(url)
                            if output_path:
                                status.update(label=f"✅ Video {current_num} procesado con éxito", state="complete")
                                results.append({"URL": url, "Estado": "✅ Éxito", "Archivo": Path(output_path).name})
                                successful_files.append(output_path)
                                success_count += 1
                            else:
                                status.update(label=f"❌ Video {current_num} falló", state="error")
                                results.append({"URL": url, "Estado": "❌ Fallo", "Archivo": "-"})
                                error_count += 1
                        except Exception as e:
                            status.update(label=f"❌ Error crítico en video {current_num}", state="error")
                            st.error(str(e))
                            results.append({"URL": url, "Estado": "❌ Fallo", "Archivo": "-"})
                            error_count += 1

                    # Update Offset
                    st.session_state.current_idx = current_num

                    # Update shared Live Metrics
                    metric_total.metric("Total Procesados", current_num)
                    metric_success.metric("Éxitos ✅", success_count)
                    metric_error.metric("Fallos ❌", error_count)
                    progress_bar.progress(current_num / total)

                    if current_num < total:
                        time.sleep(2)
                        
                # Bucle terminado
                st.session_state.is_processing = False
                st.session_state.current_idx = 0

                # Results Summary
                st.markdown("### 📋 Resumen de Procesamiento")
                st.dataframe(results, width="stretch")

                if successful_files:
                    zip_data = create_zip_in_memory(successful_files)
                    st.success(f"🎉 ¡Extracción completada! Se generaron {len(successful_files)} archivos.")
                    st.download_button(
                        label="📦 Descargar Paquete Completo (.zip)",
                        data=zip_data,
                        file_name="omniscribe_playlist.zip",
                        mime="application/zip",
                        width="stretch"
                    )
                else:
                    st.error("❌ No se pudo extraer ningún video en esta playlist.")

if __name__ == "__main__":
    main()
