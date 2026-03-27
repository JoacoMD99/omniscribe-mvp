# 🛡️ Implementation Plan: Identity Resilient Infrastructure (Anti-Bot)

**Project:** OmniScribe AI
**Status:** Technical Debt / Planned Refactor
**Objective:** Transform the core scraping engine into a resilient, SaaS-ready infrastructure capable of evading YouTube's bot-mitigation systems (WAF, 429 Errors, IP Bans) using in-memory identity management, TLS fingerprint spoofing, and adaptive human simulation.

---

## 🏗️ Phase 1: The Core - `IdentityManager` & In-Memory Secrets

**Goal:** Establish the foundation for identity rotation without relying on physical `cookies.txt` files to prevent concurrency issues, disk I/O bottlenecks, and PII leaks in a cloud environment.

### 1.1 Secure Secret Vault Setup
- **Action:** Update `.env` and `app_config.py` to support cloud-native secret injection.
- **Variables to add:**
  - `YOUTUBE_COOKIES_JSON`: A Base64 encoded JSON string containing session cookies.
  - `PROXY_URLS`: A comma-separated list of residential proxies.
- **Implementation:** Create an in-memory vault loader in `app_config.py` that parses these variables at startup, failing fast if malformed.

### 1.2 Develop the `IdentityProfile` Data Class
- **Action:** Create `core/identity.py` and define `IdentityProfile`.
- **Structure:**
  ```python
  @dataclass
  class IdentityProfile:
      proxy_url: Optional[str]
      user_agent: str
      client_hints: Dict[str, str]
      cookies: Dict[str, str] # In-memory dictionary, NO physical files
  ```
- **Rule:** Identity Binding. An IP must always use the exact same User-Agent and Cookies to avoid triggering account-sharing anomalies in Google's ML models.

### 1.3 Develop the `IdentityManager` Singleton
- **Action:** Implement the orchestration class that manages the pool of `IdentityProfiles`.
- **Methods:**
  - `get_identity() -> IdentityProfile`: Returns a profile using a weighted Round-Robin algorithm (prioritizing profiles with higher historical success rates).
  - `mark_burned(profile: IdentityProfile, cooldown_minutes: int = 15)`: Quarantines an identity temporarily if it receives an HTTP 429 or CAPTCHA challenge.

---

## 🧠 Phase 2: Adaptive Jitter & Human Simulation

**Goal:** Break predictable, robotic scraping patterns by introducing statistically realistic delays that mimic human browsing behavior.

### 2.1 Gaussian Jitter Implementation
- **Action:** Create `utils/jitter.py` with an `@adaptive_delay` decorator.
- **Implementation:**
  ```python
  import time
  import random
  import functools

  def adaptive_delay(mu=3.0, sigma=1.5):
      """Simulates human attention span between actions using Gaussian distribution."""
      def decorator(func):
          @functools.wraps(func)
          def wrapper(*args, **kwargs):
              # Ensure delay is never negative and has a logical minimum
              delay = max(1.5, random.gauss(mu, sigma))
              time.sleep(delay)
              return func(*args, **kwargs)
          return wrapper
      return decorator
  ```
- **Integration:** Apply this decorator to the main execution loop in `app.py` (specifically within the Playlist processing iteration) to simulate a user naturally clicking the next video.

---

## 🔌 Phase 3: Core Integration & Network-Level Spoofing

**Goal:** Inject our `IdentityProfiles` directly into `youtube-transcript-api` and `yt-dlp` bypassing basic TLS/JA3 fingerprinting.

### 3.1 `youtube-transcript-api` Modernization
- **Action:** Refactor `OmniScraper.process_video()` to utilize the `IdentityManager`.
- **Implementation:**
  - `youtube-transcript-api` accepts a custom `requests.Session` object.
  - Build a custom session:
    ```python
    session = requests.Session()
    session.proxies = {"http": profile.proxy_url, "https": profile.proxy_url}
    session.headers.update(profile.client_hints)
    session.headers.update({
        "X-YouTube-Client-Name": "1", # Web client
        "X-YouTube-Client-Version": "2.20240101.00.00"
    })
    # Inject cookies into the session cookiejar directly
    requests.utils.add_dict_to_cookiejar(session.cookies, profile.cookies)
    ```
  - **Advanced (Optional):** Replace the standard `requests` adapter with `curl_cffi` to mimic the exact TLS/HTTP2 handshake of Chrome 120+, completely bypassing JA3 fingerprint checks.

### 3.2 `yt-dlp` Integration (Audio Fallback)
- **Action:** Update `OmniScraper._download_audio()` to use the active `IdentityProfile`.
- **Implementation:**
  - Avoid using the `cookiefile` ydl_opt to prevent disk writes.
  - Instead, construct a raw Cookie string from the in-memory dictionary and pass it via the `http_headers` option in `yt-dlp`.
  - Set the `proxy` ydl_opt dynamically from the profile.

---

## 🔄 Phase 4: Resilience & Exponential Backoff

**Goal:** Handle inevitable network failures and proxy timeouts gracefully.

### 4.1 Enhance Tenacity Retries
- **Action:** Update the `@retry` decorators across `scraper.py`.
- **Implementation:**
  - Catch specific exceptions (e.g., `requests.exceptions.HTTPError` for 429s).
  - Implement a custom retry callback that triggers `IdentityManager.mark_burned(current_profile)` and fetches a *new* profile for the next attempt.
  - Ensure the exponential backoff incorporates the Gaussian Jitter.

---

## 🔒 Phase 5: Security & Logging Audit

**Goal:** Guarantee Zero-Exposure of sensitive data (PII, Auth Tokens) in production logs.

### 5.1 Sanitize Logs (Data Scrubbing)
- **Action:** Implement a custom `logging.Formatter` in `app_config.py`.
- **Implementation:**
  - Use Regex to redact sensitive headers before they hit standard output or log files.
  - Targets: `Cookie: .*`, `Authorization: .*`, and specific YouTube tokens like `SAPISID`, `HSID`, `SSID`.
- **Action:** Review all `try/except` blocks in `app.py` and `scraper.py` to ensure raw Exception string representations do not inadvertently leak HTTP response objects containing session tokens.

---
*Generated by OmniScribe Tech Lead.*
*Keep this document as the single source of truth for the Anti-Bot architectural upgrade.*
