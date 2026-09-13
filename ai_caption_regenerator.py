# ai_caption_regenerator.py
"""
AI-powered per-platform caption regeneration using Google Gemini.

Multi-key, multi-model fallback chain:
    key1×model1 → key2×model1 → key1×model2 → key2×model2 → ...
    → source caption (last resort — publishing never fails)

Handles:
  - 503 UNAVAILABLE (Gemini high demand) with short retries
  - 429 RESOURCE_EXHAUSTED / daily quota by rotating keys and models
  - Daily quota tracking per (key, model)
  - Circuit breaker for keys that recently failed hard
"""

import os
import time
import threading
from datetime import datetime, timedelta, timezone
from google import genai
from google.genai import types


# ============================================================
# CONFIG
# ============================================================

# Multiple Gemini API keys, comma-separated. Tried in order.
# Backward compat: falls back to GEMINI_API_KEY (singular) if the plural is unset.
GEMINI_API_KEYS = [
    k.strip()
    for k in (
        os.environ.get("GEMINI_API_KEYS")
        or os.environ.get("GEMINI_API_KEY")
        or ""
    ).split(",")
    if k.strip()
]

# Models tried in order. Cheapest/fastest first, escalating to stronger.
GEMINI_MODELS = [
    m.strip()
    for m in (
        os.environ.get("GEMINI_MODELS")
        or "gemini-2.5-flash-lite,gemini-3.5-flash,gemini-3.5-flash-lite"
    ).split(",")
    if m.strip()
]


# ============================================================
# RETRY / CIRCUIT BREAKER SETTINGS
# ============================================================

MAX_RETRIES_PER_ATTEMPT = 2              # retries within one (key, model)
RETRY_DELAYS = (0.5, 1.5)                # seconds — kept short for fast failover
CIRCUIT_BREAKER_COOLDOWN_SECONDS = 60    # skip a key this long after a hard failure


# ============================================================
# IN-MEMORY STATE
# ============================================================

_state_lock = threading.Lock()
_client_cache = {}          # {api_key: genai.Client}
_circuit_breaker = {}       # {key_ref: {"until": datetime, "reason": str}}
_daily_quota_hits = {}      # {key_ref: {"date": "YYYY-MM-DD", "count": int}}


def _key_ref(api_key: str, model: str) -> str:
    """Stable identifier for a (key, model) without exposing the key."""
    short = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else api_key[:8]
    return f"gemini:{short}:{model}"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _today_str() -> str:
    return _now_utc().strftime("%Y-%m-%d")


def _is_key_circuit_open(key_ref: str) -> bool:
    """Return True if the (key, model) is currently in cooldown."""
    with _state_lock:
        entry = _circuit_breaker.get(key_ref)
        if not entry:
            return False
        if _now_utc() >= entry["until"]:
            del _circuit_breaker[key_ref]
            return False
        return True


def _open_circuit_for_key(key_ref: str, reason: str,
                          seconds: int = CIRCUIT_BREAKER_COOLDOWN_SECONDS):
    with _state_lock:
        _circuit_breaker[key_ref] = {
            "until": _now_utc() + timedelta(seconds=seconds),
            "reason": reason[:120],
        }


def _record_daily_quota_hit(key_ref: str):
    """Mark this (key, model) as quota-exhausted for today."""
    with _state_lock:
        today = _today_str()
        entry = _daily_quota_hits.get(key_ref)
        if not entry or entry["date"] != today:
            _daily_quota_hits[key_ref] = {"date": today, "count": 1}
        else:
            entry["count"] += 1


def _is_daily_quota_exhausted(key_ref: str) -> bool:
    """
    Return True if this (key, model) already hit its daily cap today.

    We treat a single 429-with-quota as 'done for the day' because the
    Gemini API doesn't tell us the reset time inline.
    """
    with _state_lock:
        entry = _daily_quota_hits.get(key_ref)
        if not entry or entry["date"] != _today_str():
            return False
        return entry["count"] >= 1


# ============================================================
# PLATFORM RULES
# ============================================================

PLATFORM_RULES = {
    "twitter": {
        "max_chars": 240,
        "style": (
            "Punchy, conversational, 1-2 short sentences max. "
            "Lead with the hook. No hashtag spam (0-2 hashtags max). "
            "Avoid emojis unless they add meaning. "
            "Never use 'Check out this' or 'I just posted' — start with substance."
        ),
        "hashtags": "0-2 relevant hashtags at the end, or none.",
    },
    "instagram": {
        "max_chars": 2200,
        "style": (
            "Story-driven, warm, personal. 2-4 short paragraphs. "
            "First line must hook the reader (they see only 125 chars before 'more'). "
            "Line breaks between thoughts. Can include 1-3 emojis."
        ),
        "hashtags": "5-10 relevant hashtags on a separate line at the end.",
    },
    "tiktok": {
        "max_chars": 2200,
        "style": (
            "Casual, Gen-Z native, punchy. First line must hook in 3-5 words. "
            "Use 'POV:', 'Wait for it', or direct address if it fits naturally. "
            "Emojis okay, 1-2 max. No corporate tone."
        ),
        "hashtags": "3-5 trending-style hashtags (#fyp #viral etc.) mixed with niche ones.",
    },
    "facebook": {
        "max_chars": 2200,
        "style": (
            "Conversational, community-oriented. Slightly longer than Twitter. "
            "Encourage engagement (ask a question or invite comments). "
            "1-2 emojis. No hashtag spam."
        ),
        "hashtags": "0-3 hashtags at the end.",
    },
}

DEFAULT_RULES = PLATFORM_RULES["facebook"]


# ============================================================
# PROMPTS
# ============================================================

SYSTEM_PROMPT = """You are a social media copywriter who rewrites captions for specific platforms.

You will be given:
1. A source caption (usually from an Instagram Reel)
2. A target platform
3. Platform-specific rules

Your job: write a NEW caption in the target platform's voice that preserves
the original meaning but is optimized for that platform. Do NOT just truncate
or copy the source. Rewrite it.

Rules:
- Output ONLY the caption text. No preamble, no quotes, no explanation.
- Never include phrases like "Here's the caption:" or "Sure!".
- Match the platform's tone exactly.
- Respect the character limit strictly.
- If the source is in a non-English language, respond in that same language.
- Do not add hashtags that weren't relevant to the source content."""


def _build_user_prompt(source_caption: str, platform: str) -> str:
    rules = PLATFORM_RULES.get(platform, DEFAULT_RULES)
    return f"""Platform: {platform}

Character limit: {rules['max_chars']}

Style requirements:
{rules['style']}

Hashtags:
{rules['hashtags']}

Source caption to rewrite:
\"\"\"
{source_caption}
\"\"\"

Now write the {platform} caption."""


# ============================================================
# POST-PROCESSING
# ============================================================

def _clean_output(text: str) -> str:
    if not text:
        return ""
    text = text.strip()

    if (text.startswith('"') and text.endswith('"')) or \
       (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()

    for prefix in ("Here's the caption:", "Here is the caption:", "Caption:", "Sure,"):
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].strip()

    return text


def _enforce_limit(text: str, platform: str) -> str:
    limit = PLATFORM_RULES.get(platform, DEFAULT_RULES)["max_chars"]
    if len(text) <= limit:
        return text

    truncated = text[:limit - 1]
    last_space = truncated.rfind(" ")
    if last_space > limit * 0.6:
        truncated = truncated[:last_space]
    return truncated.rstrip() + "…"


# ============================================================
# ERROR CLASSIFICATION
# ============================================================

def _is_transient_error(err: Exception) -> bool:
    """503, timeouts, connection blips — retry briefly on the same key."""
    msg = str(err).lower()
    return any(t in msg for t in (
        "503", "unavailable", "timeout", "timed out",
        "deadline", "connection", "temporarily",
    ))


def _is_daily_quota_error(err: Exception) -> bool:
    """429 / quota / rate-limit — this (key, model) is done for the day."""
    msg = str(err).lower()
    return (
        "429" in msg
        or "resource_exhausted" in msg
        or "resource exhausted" in msg
        or "quota" in msg
        or "rate limit" in msg
    )


# ============================================================
# GEMINI CLIENT + ATTEMPT
# ============================================================

def _get_gemini_client(api_key: str):
    with _state_lock:
        client = _client_cache.get(api_key)
        if client is None:
            client = genai.Client(api_key=api_key)
            _client_cache[api_key] = client
        return client


def _try_gemini_once(api_key: str, model: str, user_prompt: str) -> str | None:
    """
    Single attempt against a specific (key, model).

    Returns raw text on success. Raises on any error so the caller
    can classify it (transient vs quota vs hard failure).
    """
    client = _get_gemini_client(api_key)
    response = client.models.generate_content(
        model=model,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.85,
            max_output_tokens=800,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
        contents=user_prompt,
    )
    return response.text


def _try_gemini_with_retries(api_key: str, model: str, user_prompt: str) -> str | None:
    """
    Try one (key, model) with short retries for transient errors.

    Returns text on success, None if exhausted.
    Raises on daily-quota errors so the caller can record + skip to next key.
    """
    last_err = None
    for attempt in range(MAX_RETRIES_PER_ATTEMPT + 1):
        try:
            text = _try_gemini_once(api_key, model, user_prompt)
            if text:
                return text
            last_err = "empty response"
        except Exception as e:
            last_err = e

            # Daily quota → propagate so caller marks key+model exhausted
            if _is_daily_quota_error(e):
                raise

            # Non-transient (bad key, invalid model) → propagate
            if not _is_transient_error(e):
                raise

            # Transient → retry with backoff
            if attempt < MAX_RETRIES_PER_ATTEMPT:
                wait = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                print(
                    f"[ai_caption] {model} transient error "
                    f"(attempt {attempt + 1}/{MAX_RETRIES_PER_ATTEMPT + 1}): "
                    f"{str(e)[:100]} — retrying in {wait}s"
                )
                time.sleep(wait)
                continue
            break

    print(f"[ai_caption] Gemini ({model}) exhausted retries: {str(last_err)[:120]}")
    return None


# ============================================================
# PUBLIC API
# ============================================================

def regenerate_caption(source_caption: str, platform: str) -> str:
    """
    Regenerate a caption using the multi-key, multi-model chain:

        key1×model1 → key2×model1 → key3×model1
        → key1×model2 → key2×model2 → key3×model2
        → key1×model3 → ...
        → source caption

    Returns the regenerated caption, or the source caption if every
    (key, model) combination fails. Never raises — publishing must
    never break because the AI layer is unavailable.
    """
    if not source_caption or not source_caption.strip():
        return source_caption

    if not GEMINI_API_KEYS:
        print("[ai_caption] No Gemini API keys configured; using source caption")
        return source_caption

    user_prompt = _build_user_prompt(source_caption, platform)

    # Nested loop: for each model, try all keys before moving on.
    # Keys are tried first (cheaper failover), then we escalate model strength.
    for model in GEMINI_MODELS:
        for api_key in GEMINI_API_KEYS:
            key_ref = _key_ref(api_key, model)

            if _is_key_circuit_open(key_ref):
                continue

            if _is_daily_quota_exhausted(key_ref):
                continue

            try:
                text = _try_gemini_with_retries(api_key, model, user_prompt)
            except Exception as e:
                if _is_daily_quota_error(e):
                    print(f"[ai_caption] {key_ref} daily quota hit — skipping")
                    _record_daily_quota_hit(key_ref)
                    continue

                print(f"[ai_caption] {key_ref} hard error: {str(e)[:120]}")
                _open_circuit_for_key(key_ref, str(e))
                continue

            if text:
                cleaned = _clean_output(text)
                if cleaned:
                    print(f"[ai_caption] ✅ {key_ref} succeeded")
                    return _enforce_limit(cleaned, platform)

    # Every (key, model) failed
    print("[ai_caption] ⚠️ All Gemini attempts exhausted; using source caption")
    return source_caption


# ============================================================
# INTROSPECTION (for debug endpoints)
# ============================================================

def get_provider_status() -> dict:
    """Snapshot of the current Gemini chain state — useful for /api/debug."""
    with _state_lock:
        return {
            "gemini_keys_configured": len(GEMINI_API_KEYS),
            "gemini_models": GEMINI_MODELS,
            "total_attempts_available": len(GEMINI_API_KEYS) * len(GEMINI_MODELS),
            "circuit_breaker_open": {
                k: v["until"].isoformat() for k, v in _circuit_breaker.items()
            },
            "daily_quota_hits_today": {
                k: v["count"] for k, v in _daily_quota_hits.items()
                if v["date"] == _today_str()
            },
        }