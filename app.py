import streamlit as st
import io
import zipfile
from pathlib import Path
import config
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

    /* Primary Buttons */
    .stButton>button {
        width: 100% !important;
        background-color: var(--primary-accent) !important;
        color: white !important;
        font-weight: 600 !important;
        border: none !important;
        padding: 0.75rem 1rem !important;
        border-radius: 8px !important;
        transition: all 0.2s ease !important;
    }
    .stButton>button:hover {
        background-color: var(--primary-hover) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3) !important;
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

def main() -> None:
    # Sidebar
    with st.sidebar:
        st.markdown("## 📊 OmniScraper")
        st.markdown("---")
        st.markdown("OmniScribe es el motor de inteligencia de contenido para KAI Trades. Diseñado para automatizar la captura de conocimiento estratégico, permite procesar múltiples fuentes de video simultáneamente para alimentar modelos de IA especializados en trading y libertad financiera.")

    # Main UI
    st.title("OmniScribe AI | Knowledge Engine")
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

    # Dynamic Video Batch Configuration
    valid_urls = []
    with st.expander("⚙️ Configurar Lote de Videos", expanded=True):
        st.markdown("Ingresa hasta 10 links de YouTube para procesar en lote:")
        
        for i in range(10):
            url = st.text_input(
                f"▶️ Video {i+1}", 
                key=f"url_{i}", 
                placeholder="https://www.youtube.com/watch?v=..."
            )
            if url.strip():
                valid_urls.append(url.strip())

    st.markdown("<br>", unsafe_allow_html=True)

    # Main Action
    if st.button("🚀 Iniciar Extracción Masiva"):
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
        st.dataframe(results, use_container_width=True)

        # Download Action
        if successful_files:
            zip_data = create_zip_in_memory(successful_files)
            st.success(f"🎉 ¡Extracción completada! Se generaron {len(successful_files)} archivos.")
            st.download_button(
                label="📦 Descargar Paquete Completo (.zip)",
                data=zip_data,
                file_name="omniscribe_batch.zip",
                mime="application/zip",
                use_container_width=True
            )
        else:
            st.error("❌ No se pudo extraer ningún video en este lote.")

if __name__ == "__main__":
    main()
