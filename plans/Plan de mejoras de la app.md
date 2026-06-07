# Plan de Mejoras de la App — OmniScribe AI

> **Fecha de análisis:** 2026-06-06 · **Versión base:** commit `caa998a` (v1.1-Stable)
> **Objetivo:** Llevar OmniScribe AI a estado production-ready: corregir el fallo de descarga en producción, eliminar vulnerabilidades, migrar el deploy y luego ampliar capacidades.

---

## 📋 Diagnóstico (resumen ejecutivo)

### Causa raíz del fallo en producción

La app "falla desde la descarga del primer video" en Streamlit Cloud porque **YouTube bloquea las IPs de datacenter** ("Sign in to confirm you're not a bot"). La configuración actual de `yt-dlp` agrava el problema:

- Sin `User-Agent` realista, sin cookies, sin `socket_timeout` (cuelgues infinitos), sin retries ante `DownloadError`.
- `get_metadata()` es la **primera** llamada de `process_video()` y no está protegida → un bloqueo ahí mata todo el batch.
- Los errores se tragan con `except Exception → return None` → el usuario solo ve "❌ Error" sin contexto.
- `youtube-transcript-api` solo captura `IpBlocked` en `fetch()`, pero en cloud el bloqueo ocurre antes, en `list()`.

**Importante:** este bloqueo ocurre en *cualquier* hosting cloud gratuito. Migrar de plataforma no lo resuelve por sí solo — por eso la Fase 1 (anti-bot) es el corazón de este plan.

### Hallazgos de seguridad

| # | Hallazgo | Severidad |
|---|----------|-----------|
| 1 | API key de Groq viva en `.env` local. **Verificado (2026-06-06): nunca entró al historial de git** (`git log --all -- .env` vacío; `git log -S "gsk_"` solo encuentra el placeholder). Rotación = higiene preventiva, no emergencia. Atención: el repo es **público** | 🟡 Media |
| 2 | App pública sin autenticación → cualquiera quema la cuota de Groq | 🔴 Alta |
| 3 | Dependencias sin pinear (`yt-dlp` puede romper en cada deploy) | 🟠 Alta |
| 4 | Errores silenciados sin contexto para el usuario | 🟠 Alta |
| 5 | Límite de 25MB de Groq → fallo silencioso (`return None`) | 🟡 Media |
| 6 | Archivos temporales/`.part` huérfanos dentro de `outputs/` | 🟡 Media |
| 7 | `_download_audio` retorna paths inexistentes | 🟡 Media |
| 8 | devcontainer deshabilita CORS/XSRF | 🟡 Media |
| 9 | `.python-version` contiene el literal `venv` | 🟢 Baja |

### Decisiones de arquitectura (confirmadas con el owner)

| Decisión | Elección | Justificación |
|----------|----------|---------------|
| **Deploy** | Hugging Face Spaces (free tier) | Vercel/Cloudflare no pueden correr Streamlit ni procesos de 30s–5min. HF Spaces: Streamlit nativo, 16GB RAM / 2 vCPU, secrets como env vars, `packages.txt` soportado. |
| **Anti-bot** | Cookies de YouTube como secret (base64) + fixes técnicos | Máxima tasa de éxito en IPs cloud. Renovar cookies cada ~2-4 semanas. |
| **Auth** | Password simple contra secret del deploy | Protege la cuota de Groq con ~30 min de implementación. |

### Versiones verificadas en el entorno (2026-06-06)

`yt-dlp 2026.03.17` · `youtube-transcript-api 1.2.4` · `groq 1.1.1` · `streamlit 1.55.0` — son las versiones a pinear en la Fase 0.

---

## 📖 Leyenda de uso

- `- [ ]` tarea pendiente → al completarla, Claude la marca `- [X]`.
- **Modelo:** `Opus 4.8` para tareas complejas (seguridad, control-flow, arquitectura, debugging) · `Sonnet 4.6` para tareas mecánicas bien especificadas.
- **Skills:** los skills de Claude Code que el ejecutor debe invocar para esa tarea.
- **Orden:** ejecutar las fases en orden (ver dependencias al final). Dentro de una fase, las tareas son mayormente independientes salvo que se indique.

---

## 🔥 FASE 0 — Hotfix de seguridad, pinning y quick wins

> Objetivo: detener el sangrado. Bajo riesgo, rápido, sin cambios de comportamiento del pipeline.

- [ ] **0.1 — Rotar la API key de Groq + blindar el repo público** 🟡 ⏸️ **DIFERIDA**
  - ⏸️ *Diferida el 2026-06-06 por decisión del owner: la key fue verificada como funcional contra la API y nunca entró al historial de git. Se rotará solo si deja de funcionar. Pendiente recomendado: habilitar GitHub Secret Scanning + Push Protection.*
  - **Modelo:** Sonnet 4.6 · **Skills:** `security-review`, `verification-before-completion`
  - Contexto verificado (2026-06-06): la key NUNCA entró al historial de git (la búsqueda `git log -S "gsk_" --all` solo encuentra el placeholder de `.env.example`). La rotación es **higiene preventiva**, no emergencia: la key quedó replicada fuera de `.env` (transcripts locales de sesiones de Claude Code, dashboard de secrets de Streamlit Cloud) y el repo `JoacoMD99/omniscribe-mvp` es **público** (un commit accidental futuro sería cosechado por bots en segundos).
  - Acción manual del owner: revocar la key actual en console.groq.com y generar una nueva. La nueva key va SOLO en `.env` local (ya gitignoreado) y en los secrets del deploy (Fase 3). Nunca commitear.
  - Habilitar **GitHub Secret Scanning + Push Protection** en el repo (Settings → Code security and analysis) — gratis en repos públicos; bloquea pushes que contengan keys.
  - Documentar el procedimiento de rotación en el README.

- [X] **0.2 — Pinear dependencias en `requirements.txt`** ✅ *(2026-06-06: pins ajustados a versiones reales del venv: `python-dotenv~=1.2.2`, `tenacity~=9.1.4`; dry-run de pip resolvió sin conflictos)*
  - **Modelo:** Sonnet 4.6 · **Skills:** `verification-before-completion`
  - Contenido exacto:
    ```
    streamlit~=1.55.0
    yt-dlp>=2026.3.17
    youtube-transcript-api~=1.2.4
    groq~=1.1.1
    python-dotenv~=1.2.2
    tenacity~=9.1.4
    ```
  - ⚠️ `yt-dlp` lleva floor (`>=`), NO ceiling: pinearlo duro es un anti-patrón porque las roturas de YouTube solo se arreglan actualizándolo. Documentar tarea periódica de bump.
  - Verificar: `pip install -r requirements.txt` resuelve limpio en un venv fresco.

- [X] **0.3 — Corregir `.python-version`** ✅ *(2026-06-06)*
  - **Modelo:** Sonnet 4.6 · **Skills:** —
  - Contiene el literal `venv` (footgun de pyenv). Reemplazar por `3.11` (coincide con devcontainer y default de HF Spaces).

- [X] **0.4 — Eliminar scripts throwaway de la raíz** ✅ *(2026-06-06: eliminados `test_env.py`, `test_playlist.py`, `test_free_path.py`; redundancia verificada contra `tests/test_extraction.py` que cubre metadata, fallback Groq y playlists)*
  - **Modelo:** Sonnet 4.6 · **Skills:** —
  - Borrar `test_env.py` (smoke script muerto) y cualquier otro script de prueba manual confirmado muerto en la raíz (`test_playlist.py`, `test_free_path.py` — evaluar si su lógica ya está cubierta por `tests/`). **No tocar `tests/test_extraction.py`.**

- [X] **0.5 — Ampliar `.env.example` y `.gitignore`** ✅ *(2026-06-06)*
  - **Modelo:** Sonnet 4.6 · **Skills:** —
  - `.env.example` queda:
    ```
    GROQ_API_KEY=gsk_tu_api_key_aqui
    APP_PASSWORD=elige_una_contraseña_fuerte
    YOUTUBE_COOKIES_B64=        # base64 de un cookies.txt (formato Netscape) exportado de una sesión de YouTube logueada
    ```
  - Agregar a `.gitignore`: `cookies.txt` y `*.part`.

---

## 🛡️ FASE 1 — Anti-bot + resiliencia de descarga (EL FIX CORE)

> Objetivo: corregir el fallo de producción. Todos los cambios en `scraper.py` y `app_config.py`.

- [X] **1.1 — Cookie loader: secret base64 → cookiefile temporal** ✅ *(2026-06-06: `app_config.get_youtube_cookiefile()` con singleton y fail-safe; 4 unit tests verdes)*
  - **Modelo:** Opus 4.8 · **Skills:** `security-review`, `verification-before-completion`, `test-driven-development`
  - En `app_config.py`, agregar `get_youtube_cookiefile() -> Optional[str]`:
    1. Leer env `YOUTUBE_COOKIES_B64`.
    2. Si existe: `base64.b64decode` → escribir cookies (formato Netscape) a `tempfile.NamedTemporaryFile(delete=False, suffix=".txt")` → retornar el path.
    3. Cachear el path en singleton a nivel módulo (se escribe una vez por proceso; el proceso de HF Spaces es long-lived).
    4. Si falta el secret o falla el decode: log warning y retornar `None` (la app sigue funcionando sin cookies).
  - Por qué base64: los secrets de HF Spaces son env vars de una línea; un cookies.txt multilínea debe codificarse.
  - ⚠️ Nota operativa (documentar en README): YouTube invalida cookies reusadas desde una IP distinta a la del navegador que las creó. Exportarlas idealmente de una cuenta descartable y re-exportar cuando reaparezcan bloqueos.
  - Test unitario: round-trip decode→write→path con un base64 fixture (sin red).

- [X] **1.2 — Builder centralizado `_base_ydl_opts()` en `OmniScraper`** ✅ *(2026-06-06: los 3 dicts ad-hoc reemplazados; escape hatch `YTDLP_PLAYER_CLIENT` operativo; 4 unit tests verdes)*
  - **Modelo:** Opus 4.8 · **Skills:** `systematic-debugging`, `requesting-code-review`, `verification-before-completion`
  - Crear helper privado que retorne las opciones de hardening compartidas; los 3 dicts ad-hoc de `get_metadata`, `get_playlist_videos` y `_download_audio` parten de esta base + merge de extras por llamada:
    ```python
    {
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/131.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        'socket_timeout': 30,
        'retries': 5,
        'fragment_retries': 5,
        'extractor_retries': 3,
        'sleep_interval': 2,
        'max_sleep_interval': 6,   # yt-dlp randomiza en [2, 6] → jitter nativo a nivel red
        'sleep_interval_requests': 1,
    }
    ```
  - Agregar `'cookiefile': path` **solo si** `get_youtube_cookiefile()` retorna path.
  - ❌ NO hardcodear `extractor_args.player_client`: el yt-dlp moderno auto-selecciona clientes (y cambia a `tv_downgraded,web,web_safari` automáticamente cuando hay cookiefile). ✅ Sí agregar escape hatch: si env `YTDLP_PLAYER_CLIENT` está seteada (ej. `tv,web_safari`), inyectar `'extractor_args': {'youtube': {'player_client': valor.split(',')}}`. Fallbacks documentados sin PO token: `tv` y `android_vr`.
  - Merges por llamada: `get_metadata` agrega `skip_download`, `noplaylist`; `get_playlist_videos` agrega `extract_flat: 'in_playlist'`, `noplaylist: False`; `_download_audio` agrega `format`, `outtmpl`, `postprocessors` y `ffmpeg_location` opcional.
  - Verificar: dry-run imprimiendo el dict resuelto; cookiefile presente solo con secret seteado.

- [X] **1.3 — Modernizar uso de youtube-transcript-api 1.2.4** ✅ *(2026-06-06: `IpBlocked` capturado en `list()`, `TranscriptsDisabled`/`NoTranscriptFound` explícitos, `_build_transcript_api()` con proxy opcional)*
  - **Modelo:** Opus 4.8 · **Skills:** `systematic-debugging`
  - **Bug fix principal:** envolver TODO el bloque `api.list(video_id)` + selección de transcript en try/except que capture `IpBlocked` (hoy solo se captura alrededor de `fetch()`, pero en cloud `list()` es la primera llamada bloqueada), más `TranscriptsDisabled`, `NoTranscriptFound` y excepciones de red genéricas → caer limpiamente al fallback de Groq en vez de que lo trague el handler externo sin contexto.
  - Soporte opcional de proxy: si env `YTT_PROXY_HTTP`/`YTT_PROXY_HTTPS` existen, construir `YouTubeTranscriptApi(proxy_config=GenericProxyConfig(http_url=..., https_url=...))` (import desde `youtube_transcript_api.proxies`).
  - ❌ NO intentar pasar cookies a esta librería: los maintainers de 1.x confirman que cookie-auth no está disponible. Postura realista: esta capa es best-effort; el workhorse confiable es yt-dlp+Groq.

- [X] **1.4 — Proteger `get_metadata` + corregir `_download_audio`** ✅ *(2026-06-06: `errors.py` creado con la jerarquía completa de la 2.1 — a la 2.1 le queda solo el threading por `process_video` y el cambio de contrato; verificado con URL inexistente → `VideoUnavailableError` tipada, 0 huérfanos, 0 temp dirs)*
  - **Modelo:** Opus 4.8 · **Skills:** `systematic-debugging`, `verification-before-completion`
  - `get_metadata`: envolver `ydl.extract_info` para que `yt_dlp.utils.DownloadError`/bot-block levante una excepción tipada (clases de Fase 2.1) con video id y razón humana — es el "first-video failure point" documentado.
  - `_download_audio`:
    - No retornar paths inexistentes: tras `ydl.download`, resolver el output real (glob `f"{base}*.m4a"` / `info['requested_downloads']`) y **raise `FileNotFoundError`** si no existe nada.
    - Mover temp files fuera de `outputs/`: usar `tempfile.mkdtemp()` como destino del `outtmpl` (hoy los temp se mezclan con los transcripts descargables).
    - Mantener `.part` habilitado (permite resume) pero el `finally` debe limpiar `*.part`, `*.m4a`, `*.webm` del temp dir y borrar el dir completo.
  - Verificar: forzar fallo con URL inválida → no quedan huérfanos en `outputs/` y se levanta excepción tipada.

- [X] **1.5 — `_find_ffmpeg` cross-platform defensivo** ✅ *(2026-06-07: log INFO con path de ffmpeg cuando está en PATH/WinGet; WARNING si no se encuentra; verificado en runtime)*
  - **Modelo:** Sonnet 4.6 · **Skills:** `verification-before-completion`
  - Ya funciona en Linux (short-circuit con `shutil.which`); mantener fallback WinGet para dev local en Windows y agregar log claro indicando qué path se usa. Verificar en el contenedor que `which ffmpeg` resuelve (instalado vía `packages.txt`).

- [X] **1.6 — Jitter en los loops de UI** ✅ *(2026-06-07: `import random` agregado, 2x `time.sleep(random.uniform(2.0, 5.0))` en ambos loops; 0 `time.sleep(2)` fijos restantes)*
  - **Modelo:** Sonnet 4.6 · **Skills:** `verification-before-completion`
  - En `app.py`, reemplazar los dos `time.sleep(2)` fijos (loops batch ~línea 425 y playlist ~línea 575) por `time.sleep(random.uniform(2.0, 5.0))` (+ `import random`). El throttling pesado a nivel red ya lo cubre 1.2 (`sleep_interval`/`max_sleep_interval`).

---

## 🔍 FASE 2 — Manejo de errores, observabilidad y UX de errores

> Objetivo: reemplazar los `except Exception → return None` silenciosos y el "❌ Error" sin contexto por errores tipados, logs estructurados y mensajes accionables.

- [X] **2.1 — Jerarquía de excepciones tipadas (`errors.py`)** ✅ *(2026-06-07: contrato "return path o raise tipado" implementado en `process_video`; `GroqConfigError`/`GroqTranscriptionError`/`TranscriptUnavailableError` hilados; tenacity con `retry_if_not_exception_type(OmniScribeError)` — errores de dominio no se reintentan; desconocidos envueltos con `__cause__`; code review aplicado: respuesta None de Groq y transcript solo-ruido ya no producen archivos basura; 11 unit tests en `test_fase2_unit.py`; único `return None` restante: caso 25MB, scope de 2.2)*
  - **Modelo:** Opus 4.8 · **Skills:** `systematic-debugging`, `requesting-code-review`
  - Nuevo módulo `errors.py`: `OmniScribeError(Exception)` base + `VideoBlockedError` (bot-block/IpBlocked), `TranscriptUnavailableError`, `AudioDownloadError`, `AudioTooLargeError` (lleva tamaño en MB), `GroqConfigError`, `GroqTranscriptionError`. Cada una con `url`/`video_id` y atributo `message` en español para la UI.
  - `process_video` cambia de contrato: de "return path o None" a "return path o raise tipado". El `except Exception` externo pasa a: re-raise de `OmniScribeError` conocidas; envolver desconocidas en `OmniScribeError` con `__cause__`. El special-case actual de `RuntimeError` se reemplaza por `VideoBlockedError`.

- [X] **2.2 — Límite 25MB de Groq con error explícito** ✅ *(2026-06-07: `return None` silencioso → `raise AudioTooLargeError` con `size_mb` y mensaje accionable; `AudioTooLargeError` agregada al import de `scraper.py`; contrato "return path o raise tipado" ahora completo — ya no quedan `return None` de fallo)*
  - **Modelo:** Sonnet 4.6 · **Skills:** `verification-before-completion`
  - Reemplazar el `return None` silencioso cuando `file_size > 25MB` por `raise AudioTooLargeError(video_id, size_mb)` con mensaje claro ("video demasiado largo para la vía gratuita de Whisper"). En Fase 5.1 este error se vuelve recuperable (chunking).

- [X] **2.3 — Logging estructurado con redacción de secretos** ✅ *(2026-06-07: `configure_logging()` centralizado en `app_config.py` — formatter timestamp/nivel/nombre/mensaje, `LOG_LEVEL` con fallback a INFO, idempotente; `basicConfig` suelto removido de `scraper.py`; `RedactionFilter` adjuntado al HANDLER —no al logger, por el gotcha de propagación de hijos— redacta `gsk_*`, `Cookie:`/`Authorization:`, tokens YouTube (SAPISID/APISID/HSID/SSID/SID/SIDCC/LOGIN_INFO) y `__Secure-/__Host-*`, también cuando van como arg de logging; auditoría de call-sites: ningún secreto se loguea directo, filtro cubre fuga indirecta vía excepciones de yt-dlp/Groq; 19 tests en `test_fase2_logging.py`)*
  - **Modelo:** Opus 4.8 · **Skills:** `security-review`, `test-driven-development`
  - Configurar el logger una vez en `app_config.py` (no `basicConfig` suelto en `scraper.py`): formatter con timestamp/nivel/nombre/mensaje, nivel desde env `LOG_LEVEL` (default INFO).
  - Agregar `logging.Filter` que redacte por regex: `Cookie:.*`, `Authorization:.*`, `gsk_[A-Za-z0-9]+` (keys de Groq), tokens de YouTube (`SAPISID`, `HSID`, `SSID`, `__Secure-`).
  - Test unitario: loggear cookie falsa y key `gsk_` falsa → assert que el record emitido sale redactado.

- [X] **2.4 — UI: motivo del fallo visible por video** ✅ *(2026-06-07: helper `_process_video_to_result` extrae el try/except — `OmniScribeError` → `Estado="❌ {e.short_label}"` + `Motivo=e.message`; `Exception` genérica → `Motivo=str(e)`; `_path` interno excluido del `st.dataframe`; render histórico muestra Motivo; `st.error(result["Motivo"])` en el loop vivo; 9 tests en `test_fase2_ui.py`; 54/54 tests verdes)*
  - **Modelo:** Sonnet 4.6 · **Skills:** `frontend-design`, `verification-before-completion`
  - En ambos loops de `app.py`: un solo `try/except OmniScribeError as e` que haga `status.update(label=f"❌ Video {n}: {e.short_label}", state="error")` + `st.error(e.message)`, y guarde el motivo en `batch_results`/`playlist_results` (nueva columna **"Motivo"**).
  - Los bloques de render histórico y el `st.dataframe` final muestran la columna Motivo.
  - Distinguir mensajes recuperables ("rate limit → reintenta en unos minutos") de terminales ("sin transcript oficial y sin GROQ_API_KEY configurada").

---

## 🚀 FASE 3 — Auth + migración a Hugging Face Spaces

> Objetivo: deploy estable y gratuito con la cuota de Groq protegida. **3.1 debe estar antes de hacer público el Space.**

- [X] **3.1 — Password gate** ✅ *(2026-06-07: `app_config.get_app_password()` + `password_is_valid()` con `hmac.compare_digest` sobre bytes UTF-8 —soporta acentos/ñ—; fail-closed verificado: sin APP_PASSWORD bloquea, `''`vs`''` no autentica (el guard gana sobre compare_digest); `check_password()` al inicio de `main()` + `st.stop()`; `authenticated` persiste en session_state; 13 tests en `test_fase3_auth.py`; 67/67 suite verde. SIN COMMIT — Fase 3 cierra tras 3.5)*
  - **Modelo:** Opus 4.8 · **Skills:** `security-review`, `verification-before-completion`
  - `check_password()` al inicio de `main()` en `app.py` (antes de renderizar tabs): `st.text_input("Contraseña", type="password")` comparado con env `APP_PASSWORD` (nueva `app_config.get_app_password()`) usando `hmac.compare_digest` (constant-time). Guardar `st.session_state["authenticated"] = True` y `st.stop()` hasta autenticar.
  - **Fail-closed:** si `APP_PASSWORD` no está seteada → mostrar "App no configurada" y bloquear (nunca abrir por defecto).
  - Verificar: password incorrecta bloquea; correcta persiste entre reruns de la sesión.

- [X] **3.2 — Frontmatter YAML de HF Spaces en `README.md`** ✅ *(2026-06-07: prepend exacto al inicio del README; `sdk_version` como string entrecomillado para evitar que YAML lo interprete como float)*
  - **Modelo:** Sonnet 4.6 · **Skills:** —
  - Prepend exacto al inicio del README (el contenido existente queda debajo):
    ```yaml
    ---
    title: OmniScribe AI
    emoji: 🤖
    colorFrom: indigo
    colorTo: purple
    sdk: streamlit
    sdk_version: 1.55.0
    app_file: app.py
    pinned: false
    ---
    ```

- [X] **3.3 — `load_dotenv(override=False)`** ✅ *(2026-06-07: 4 ocurrencias en `app_config.py` reemplazadas — `configure_logging`, `get_groq_api_key`, `get_youtube_cookiefile`, `get_app_password`; precedencia correcta: secrets del servidor ganan sobre `.env` local; 67/67 tests verdes)*
  - **Modelo:** Sonnet 4.6 · **Skills:** `verification-before-completion`
  - En `app_config.py`, cambiar `load_dotenv(override=True)` → `override=False` para que los env vars reales del deploy (HF secrets) ganen sobre un `.env` accidental. Documentar que `.env` es solo para dev local.
  - Buena noticia ya verificada: `app_config` usa `os.getenv`, y HF inyecta Settings → "Variables and secrets" como env vars → `GROQ_API_KEY`, `APP_PASSWORD`, `YOUTUBE_COOKIES_B64`, `YTDLP_PLAYER_CLIENT`, `YTT_PROXY_*`, `LOG_LEVEL` funcionan sin más cambios de código.

- [X] **3.4 — Runbook de deploy en HF Spaces (README)** ✅ *(2026-06-07: sección "Deploy a Hugging Face Spaces" agregada al README — 5 pasos (crear Space, conectar repo, secrets, packages.txt, exportar cookies) + tabla de caveats del free tier)*
  - **Modelo:** Sonnet 4.6 · **Skills:** `verification-before-completion`
  - Documentar: crear Space (SDK Streamlit), conectar repo/push, configurar secrets en Settings → Variables and secrets, `packages.txt` con `ffmpeg` ya es compatible (HF instala apt packages nativamente).
  - Caveats a documentar: `outputs/` es **efímero** (se pierde en rebuild/restart — aceptable porque el zip se descarga en sesión); free tier = 16GB RAM sin disco persistente; el Space duerme tras 48h sin uso; refresh del browser pierde el estado de un run largo (motivación de 5.3); renovar `YOUTUBE_COOKIES_B64` cada ~2-4 semanas o cuando reaparezcan bloqueos.
  - Incluir instrucciones de exportación de cookies (extensión "Get cookies.txt LOCALLY" o similar → `base64 -w0 cookies.txt`).

- [X] **3.5 — Neutralizar flags inseguros del devcontainer** ✅ *(2026-06-07: comentario `// DEV-ONLY` explícito en `devcontainer.json` — los flags quedan para el preview de Codespaces pero documentados; HF Spaces ignora este archivo)*
  - **Modelo:** Sonnet 4.6 · **Skills:** `security-review`
  - `.devcontainer/devcontainer.json` corre Streamlit con `--server.enableCORS false --server.enableXsrfProtection false`. HF lo ignora, pero es un smell para Codespaces: quitar los flags o comentar explícitamente que es dev-only.

---

## ✅ FASE 4 — Testing + CI

> Objetivo: atrapar regresiones sin requerir API key ni red para la suite core.

- [ ] **4.1 — Separar unit vs integration tests**
  - **Modelo:** Opus 4.8 (diseño de mocks/fixtures) · **Skills:** `test-driven-development`, `verification-before-completion`
  - Marcar los tests con red/API key de `tests/test_extraction.py` con `@pytest.mark.integration` + config de markers en `pytest.ini`/`pyproject.toml` + skip automático si `GROQ_API_KEY` no está seteada.
  - Nuevos tests **unitarios puros** (sin red): `_clean_text` (regex timestamps/ruido), regex URL→video-id de `get_metadata`, cookie loader base64 (1.1), filtro de redacción (2.3), builder `_base_ydl_opts` (cookiefile presente solo con secret), mensajes de las excepciones tipadas (2.1).

- [ ] **4.2 — GitHub Actions CI**
  - **Modelo:** Sonnet 4.6 · **Skills:** `verification-before-completion`
  - `.github/workflows/ci.yml`: Python 3.11 → checkout → setup-python → `pip install -r requirements.txt` → `sudo apt-get install -y ffmpeg` → `pytest -m "not integration"` → smoke import (`python -c "import app"`) → lint con `ruff`.
  - Opcional: job manual-dispatch para integration tests con secret `GROQ_API_KEY` del repo.

---

## ✨ FASE 5 — Capacidades, workflows y UX (post-launch)

> Objetivo: ampliar valor una vez que la base es estable. **Ejecutar 5.4 primero** para no implementar features dos veces en los loops duplicados.

- [ ] **5.4 — De-duplicar los loops de procesamiento + extraer CSS** *(primera de la fase)*
  - **Modelo:** Opus 4.8 · **Skills:** `requesting-code-review`, `verification-before-completion`, `webapp-testing`
  - Los loops de tab1 (batch, ~líneas 363-449) y tab2 (playlist, ~líneas 513-599) de `app.py` son ~90 líneas casi idénticas. Extraer `render_processing_section(state_prefix, urls, ...)` parametrizado por prefijo de session-state (`batch_` vs playlist).
  - Mover el bloque CSS inline (~líneas 18-186) a `styles.css` cargado por helper.
  - Verificar con `webapp-testing` (Playwright) que pause/resume y progreso siguen funcionando en ambos tabs.

- [ ] **5.1 — Chunking/compresión de audio >25MB**
  - **Modelo:** Opus 4.8 · **Skills:** `brainstorming`, `test-driven-development`, `systematic-debugging`
  - Convertir `AudioTooLargeError` en path recuperable: re-encode a 16kHz mono (Whisper downsamplea a 16kHz igualmente) vía postprocessor FFmpeg (`-ar 16000 -ac 1`) → ~3-4x más chico. Si aún >25MB: segmentar con `ffmpeg -f segment -segment_time N`, transcribir cada chunk con `_transcribe_with_groq` y concatenar en orden antes de `_clean_text`. Helper `_chunk_audio()` + loop en `process_video`.

- [ ] **5.2 — Integrar `skills/` como resúmenes IA post-transcripción**
  - **Modelo:** Opus 4.8 · **Skills:** `brainstorming`, `frontend-design`
  - Los 16 prompts markdown (STAR/R-I-S-E) de `skills/` no están conectados a nada. Nuevo `summarizer.py`: carga el prompt elegido, envía `{transcript}` a un modelo chat de Groq (ej. `llama-3.3-70b-versatile`, reusa el cliente ya configurado) y escribe `_summary.md` junto al transcript. UI: selectbox de framework + checkbox "Generar resumen IA". Incluir resúmenes en el zip.

- [ ] **5.3 — Persistencia de progreso ante refresh**
  - **Modelo:** Opus 4.8 · **Skills:** `brainstorming`, `frontend-design`
  - Mitigar "refresh mata el run largo" (disco efímero de HF + pérdida de session state): checkpoint JSON periódico de `{processed_idx, results}` en temp file recargado al inicio si existe, + botón "Descargar progreso parcial" para rescatar transcripts completados antes de un refresh. Scope chico.

---

## 🔗 Dependencias entre fases

```
Fase 0 (independiente, primero — 0.1 es gate manual antes de cualquier deploy)
  └─→ Fase 1 (1.1 bloquea 1.2; 1.4 depende de 1.2)
        └─→ Fase 2 (2.1 requiere los puntos de fallo de Fase 1; 2.4 depende de 2.1)
              └─→ Fase 3 (deployar app ya estable; 3.1 ANTES de hacer público el Space)
              └─→ Fase 4 (en paralelo con Fase 3; testea código de Fases 1-2)
                    └─→ Fase 5 (post-launch; 5.4 antes que 5.1-5.3)
```

---

## 📎 Apéndice — Plan anti-bot existente (diferido)

El documento `implementation_plans/anti_bot_refactor_plan.md` (IdentityManager, pool de proxies residenciales con round-robin ponderado, spoofing JA3 con `curl_cffi`) queda **fuera de scope**: es sobre-ingeniería para un Space gratuito single-tenant y no es la best practice actual para este caso. El path soportado y mantenible es **cookiefile + UA + timeouts + retries + jitter** (Fase 1). Revisitar rotación de proxies solo si el owner pasa a un proveedor pago y las cookies resultan insuficientes — los seams de integración ya quedan listos (`proxy_config` en 1.3 y `YTDLP_PLAYER_CLIENT` en 1.2).

---

*Documento generado por Claude Code (Opus 4.8) tras análisis exhaustivo del codebase con 3 agentes de exploración + 1 agente de diseño. Para ejecutar una fase: usar el skill `executing-plans` y marcar cada tarea con `[X]` al completarla y verificarla (`verification-before-completion`).*
