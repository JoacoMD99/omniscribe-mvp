# OmniScribe AI - Agentic Framework

Este directorio contiene el "cerebro" (Agentic Framework) de la inteligencia artificial de OmniScribe AI. Hemos instalado **10 Habilidades Estratégicas (Skills)** seleccionadas y extraídas directamente de `antigravity-awesome-skills` para especializar a este agente en la transcripción masiva de YouTube, manejo de datos y estrategia de contenido de KAI Trades.

## Habilidades Instaladas

A continuación, se detalla por qué cada *skill* es vital para el éxito del proyecto:

### 🛠️ Core Stack: Python & Arquitectura
1. **`python-pro.md`**: Define los más altos estándares de desarrollo en Python 3.12, asegurando código limpio, tipado estático y modularidad perfecta para nuestras integraciones en `app.py`.
2. **`python-patterns.md`**: Proporciona patrones de diseño esenciales para construir componentes desacoplados (UI de Streamlit, llamadas a Groq, limpieza de texto, etc.) que escalen a medida que crezca el volumen de videos.

### 🌐 Integración y Datos
3. **`api-patterns.md`**: Fundamental para establecer conexiones resilientes, eficientes y con reintentos automáticos contra la **Groq API** a la hora de procesar solicitudes simultáneas con `whisper-large-v3`.

### 🎬 Extracción Media & Audio
4. **`youtube-automation.md`**: Guía operativa para automatizar la extracción segura de metadatos, títulos y streams de video mediante `yt-dlp` en grandes volúmenes.
5. **`audio-transcriber.md`**: Proporciona el *know-how* sobre manipulación, empaquetado y procesamiento de archivos de audio para que la interacción con modelos Whisper sea lo más fidedigna y rápida posible.

### 🔄 Automatización de Flujos (Pipelines)
6. **`workflow-automation.md`**: Define la mentalidad y lógica necesarias para crear nuestro pipeline de transcripción en lote (procesamiento masivo de 10 en 10 videos) y empaquetamiento en .zip de forma ininterrumpida.

### 🧠 Crecimiento & Marca (KAI Trades)
7. **`youtube-summarizer.md`**: Otorga al agente la destreza mental para no solo transcribir mecánicamente, sino entender cómo resumir y estructurar los textos en formatos legibles.
8. **`content-strategy.md`**: Es la capa de "marketing". Esta habilidad ayuda a enfocar la limpieza y generación de *prompts* con el tono adecuado de **KAI Trades** (Trading, Libertad Financiera, Gen Z), pre-procesando el contenido para la futura Gema de Gemini.

### 🛡️ Calidad y Mantenibilidad
9. **`systematic-debugging.md`**: Metodología para aislar e investigar rápidamente cualquier error de red, falla en las descargas de YouTube o caídas de Groq, minimizando el tiempo de inactividad de OmniScribe.
10. **`test-driven-development.md`**: Garantiza la confiabilidad del sistema. Dictamina que cualquier nueva característica de Streamlit o extracción se pruebe rigurosamente antes de usarse en producción.

### 🎨 Frontend & UX/UI (SaaS Level)
11. **`ui-ux-designer.md`**: Asegura que cualquier componente interactivo respete la ergonomía visual y heurísticas para usuarios finales.
12. **`frontend-design.md`**: Define las directrices para implementar diseños adaptativos, limpios y "Theme-Agnostic" basados en Glassmorphism.
13. **`ui-visual-validator.md`**: Habilidad analítica para asegurar que el contraste, los paddings y alineaciones cumplan estándares profesionales.
14. **`senior-frontend.md`**: Eleva la calidad de la integración entre Streamlit y CSS puro (markdown injects), asegurando un código Frontend mantenible y escalable.

### 🧪 Advanced Testing & QA
15. **`python-testing-patterns.md`**: Provee las mejores prácticas para estructurar tests en Python (Pytest, Mocks, Fixtures).
16. **`testing-qa.md`**: Guías de Quality Assurance para validar flujos completos y asegurar la cobertura del sistema.
17. **`test-automator.md`**: Automatización de pruebas para integraciones continuas.
18. **`testing-patterns.md`**: Patrones arquitectónicos generales para garantizar la testabilidad del código desde su diseño.

---
> **Aviso de Seguridad:** Estos archivos son estrictamente de texto plano (Markdown) y sirven de *contexto* para el LLM. No existen scripts `.sh` ni `.bat` ejecutables en esta carpeta.
