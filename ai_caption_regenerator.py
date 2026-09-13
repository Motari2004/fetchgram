# ai_caption_regenerator.py
"""
AI-powered per-platform caption regeneration using Google Gemini.

Takes a source caption (e.g. an Instagram Reel caption) and rewrites it
for a specific platform (twitter / instagram / tiktok / facebook).
"""

import os
import re
from google import genai
from google.genai import types


# ---------- Config ----------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

_client = None


def _get_client():
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY not set")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


# ---------- Platform rules ----------
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


# ---------- Prompts ----------
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


# ---------- Post-processing ----------
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


# ---------- Public API ----------
def regenerate_caption(source_caption: str, platform: str) -> str:
    """
    Regenerate a caption for the target platform using Gemini.

    Returns the new caption, or the source caption unchanged if:
      - API key is missing
      - API call fails
      - Response is empty
    """
    if not source_caption or not source_caption.strip():
        return source_caption

    if not GEMINI_API_KEY:
        print("[ai_caption] GEMINI_API_KEY not set; using source caption")
        return source_caption

    try:
        client = _get_client()
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.85,
                max_output_tokens=800,
            ),
            contents=_build_user_prompt(source_caption, platform),
        )
        output = response.text
    except Exception as e:
        print(f"[ai_caption] Gemini error: {e}")
        return source_caption

    if not output:
        return source_caption

    cleaned = _clean_output(output)
    if not cleaned:
        return source_caption

    return _enforce_limit(cleaned, platform)