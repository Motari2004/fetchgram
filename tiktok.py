"""
TikTok posting via Buffer GraphQL API.

- Buffer API key is managed from the UI and stored in app_settings.
- Supports manual posts and autonomous pipelines.
"""

import os
import logging
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

BUFFER_API_URL = "https://api.buffer.com"


# ---------------------------------------------------------------------------
# Key helpers (loaded from app_settings / env)
# ---------------------------------------------------------------------------

def get_buffer_api_key() -> Optional[str]:
    """
    Prefer the key saved from the UI (app_settings), fall back to env.
    """
    try:
        # Late import to avoid circular imports with app.py
        from app import get_setting
        key = get_setting("buffer_api_key")
        if key and str(key).strip():
            return str(key).strip()
    except Exception as e:
        logger.debug(f"Could not load buffer_api_key from settings: {e}")

    return os.environ.get("BUFFER_API_KEY") or None


def _headers() -> Dict[str, str]:
    key = get_buffer_api_key()
    if not key:
        raise ValueError(
            "Buffer API key is not configured. "
            "Please save it in the UI (Buffer API Key section)."
        )
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _gql(query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"query": query}
    if variables is not None:
        payload["variables"] = variables

    resp = requests.post(
        BUFFER_API_URL,
        json=payload,
        headers=_headers(),
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    if "errors" in data and data["errors"]:
        messages = []
        for err in data["errors"]:
            if isinstance(err, dict):
                messages.append(err.get("message", str(err)))
            else:
                messages.append(str(err))
        raise Exception("; ".join(messages) or "Buffer GraphQL error")

    return data.get("data") or {}


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------

def list_channels() -> List[Dict[str, Any]]:
    """Return all channels connected to the Buffer account."""
    query = """
    query {
      channels {
        id
        name
        service
        avatar
      }
    }
    """
    data = _gql(query)
    return data.get("channels") or []


def list_tiktok_channels() -> List[Dict[str, Any]]:
    """Return only TikTok channels."""
    channels = list_channels()
    return [
        c for c in channels
        if (c.get("service") or "").lower() in ("tiktok", "tik tok")
    ]


# ---------------------------------------------------------------------------
# Posting
# ---------------------------------------------------------------------------

def post_video_to_tiktok(
    channel_id: str,
    video_url: str,
    text: str = "",
    due_at: Optional[str] = None,
    thumbnail_offset_ms: int = 1000,
    add_to_queue: bool = False,
) -> Dict[str, Any]:
    """
    Create a TikTok video post via Buffer.

    Args:
        channel_id: Buffer channel ID for the TikTok account
        video_url: Publicly accessible direct video URL
        text: Caption (max ~2200 chars for TikTok)
        due_at: ISO-8601 UTC datetime string for custom schedule
                e.g. "2026-09-12T14:30:00.000Z"
        thumbnail_offset_ms: Frame (ms) to use as thumbnail
        add_to_queue: If True and no due_at, add to the channel queue

    Returns:
        dict with post id, status, dueAt, etc.
    """
    if not channel_id:
        raise ValueError("channel_id is required")
    if not video_url:
        raise ValueError("video_url is required")

    # Decide scheduling mode
    if due_at:
        mode = "customScheduled"
    elif add_to_queue:
        mode = "addToQueue"
    else:
        # Safe default: put in queue so Buffer handles timing
        mode = "addToQueue"

    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post {
            id
            text
            dueAt
            status
          }
        }
        ... on MutationError {
          message
        }
      }
    }
    """

    input_data: Dict[str, Any] = {
        "text": (text or "")[:2200],
        "channelId": channel_id,
        "schedulingType": "automatic",
        "mode": mode,
        "assets": [
            {
                "video": {
                    "url": video_url,
                    "metadata": {"thumbnailOffset": int(thumbnail_offset_ms)},
                }
            }
        ],
    }

    if due_at:
        # Ensure Buffer-friendly ISO format
        if due_at.endswith("Z") or "+" in due_at:
            input_data["dueAt"] = due_at
        else:
            input_data["dueAt"] = due_at + "Z"

    data = _gql(mutation, {"input": input_data})
    result = data.get("createPost") or {}

    if "message" in result:
        raise Exception(result["message"])

    post = result.get("post") or {}
    logger.info(
        f"✅ TikTok post created via Buffer | channel={channel_id} | "
        f"post_id={post.get('id')} | dueAt={post.get('dueAt')}"
    )
    return {
        "success": True,
        "post_id": post.get("id"),
        "text": post.get("text"),
        "due_at": post.get("dueAt"),
        "status": post.get("status"),
        "channel_id": channel_id,
        "platform": "tiktok",
        "provider": "buffer",
    }


def validate_buffer_key(api_key: str) -> Dict[str, Any]:
    """
    Quick validation: try listing channels with the provided key.
    Does not persist the key.
    """
    if not api_key or not api_key.strip():
        return {"valid": False, "message": "API key is empty"}

    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
    }
    query = """
    query {
      channels {
        id
        name
        service
      }
    }
    """
    try:
        resp = requests.post(
            BUFFER_API_URL,
            json={"query": query},
            headers=headers,
            timeout=30,
        )
        if resp.status_code != 200:
            return {
                "valid": False,
                "message": f"HTTP {resp.status_code}: {resp.text[:200]}",
            }
        data = resp.json()
        if "errors" in data and data["errors"]:
            msg = data["errors"][0].get("message", str(data["errors"]))
            return {"valid": False, "message": msg}

        channels = (data.get("data") or {}).get("channels") or []
        tiktok = [
            c for c in channels
            if (c.get("service") or "").lower() in ("tiktok", "tik tok")
        ]
        return {
            "valid": True,
            "channel_count": len(channels),
            "tiktok_count": len(tiktok),
            "tiktok_channels": tiktok,
            "message": f"Key OK — {len(tiktok)} TikTok channel(s) found",
        }
    except Exception as e:
        return {"valid": False, "message": str(e)}
