"""
TikTok posting via Buffer GraphQL API.

- Buffer API key is managed from the UI and stored in app_settings.
- Supports manual posts and autonomous pipelines.

This module has NO dependency on app.py (avoids circular imports).
Pass the API key via set_buffer_api_key() or the BUFFER_API_KEY env var.
"""

from __future__ import annotations

import os
import logging
import requests
from typing import Optional, Dict, Any, List, Callable

logger = logging.getLogger(__name__)

BUFFER_API_URL = "https://api.buffer.com"

# Module-level key (set by app after load_app_settings, or from env)
_BUFFER_API_KEY: Optional[str] = None

# Optional callback the app can register to fetch the key from DB/settings
_key_provider: Optional[Callable[[], Optional[str]]] = None


def set_buffer_api_key(key: Optional[str]) -> None:
    """Set the Buffer API key in memory (called by app after saving from UI)."""
    global _BUFFER_API_KEY
    _BUFFER_API_KEY = (key or "").strip() or None


def set_key_provider(provider: Callable[[], Optional[str]]) -> None:
    """
    Register a function that returns the current Buffer API key
    (e.g. lambda: get_setting('buffer_api_key')).
    """
    global _key_provider
    _key_provider = provider


def get_buffer_api_key() -> Optional[str]:
    """
    Resolve Buffer API key in this order:
    1. In-memory key set via set_buffer_api_key()
    2. Key provider callback (from app settings)
    3. BUFFER_API_KEY environment variable
    """
    if _BUFFER_API_KEY:
        return _BUFFER_API_KEY

    if _key_provider is not None:
        try:
            key = _key_provider()
            if key and str(key).strip():
                return str(key).strip()
        except Exception as e:
            logger.debug(f"Key provider failed: {e}")

    env_key = os.environ.get("BUFFER_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()

    return None


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
# Organizations & Channels
# ---------------------------------------------------------------------------

def list_organizations() -> List[Dict[str, Any]]:
    """Return organizations for the authenticated Buffer account."""
    query = """
    query {
      account {
        organizations {
          id
          name
        }
      }
    }
    """
    data = _gql(query)
    account = data.get("account") or {}
    return account.get("organizations") or []


def get_default_organization_id() -> Optional[str]:
    """
    Return the first organization ID (most accounts have one).
    """
    orgs = list_organizations()
    if not orgs:
        return None
    return orgs[0].get("id")


def list_channels(organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Return all channels for a Buffer organization.
    Buffer requires organizationId in ChannelsInput.
    """
    org_id = organization_id or get_default_organization_id()
    if not org_id:
        raise ValueError(
            "No Buffer organization found for this API key. "
            "Check the key and that the account has an organization."
        )

    query = """
    query GetChannels($orgId: OrganizationId!) {
      channels(input: { organizationId: $orgId }) {
        id
        name
        displayName
        service
        avatar
      }
    }
    """
    data = _gql(query, {"orgId": org_id})
    return data.get("channels") or []


def list_tiktok_channels(organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return only TikTok channels."""
    channels = list_channels(organization_id=organization_id)
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

    if due_at:
        mode = "customScheduled"
    elif add_to_queue:
        mode = "addToQueue"
    else:
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
    Quick validation: resolve org + list channels with the provided key.
    Does not persist the key.
    """
    if not api_key or not api_key.strip():
        return {"valid": False, "message": "API key is empty"}

    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
    }

    def _post(query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"query": query}
        if variables is not None:
            payload["variables"] = variables
        resp = requests.post(
            BUFFER_API_URL,
            json=payload,
            headers=headers,
            timeout=30,
        )
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")
        body = resp.json()
        if "errors" in body and body["errors"]:
            msg = body["errors"][0].get("message", str(body["errors"]))
            raise Exception(msg)
        return body.get("data") or {}

    try:
        # 1) Organizations
        org_data = _post("""
            query {
              account {
                organizations { id name }
              }
            }
        """)
        orgs = (org_data.get("account") or {}).get("organizations") or []
        if not orgs:
            return {
                "valid": True,
                "channel_count": 0,
                "tiktok_count": 0,
                "tiktok_channels": [],
                "message": "Key OK but no organizations found on this account",
            }

        org_id = orgs[0]["id"]
        org_name = orgs[0].get("name") or org_id

        # 2) Channels for that org
        ch_data = _post(
            """
            query GetChannels($orgId: OrganizationId!) {
              channels(input: { organizationId: $orgId }) {
                id
                name
                displayName
                service
              }
            }
            """,
            {"orgId": org_id},
        )
        channels = ch_data.get("channels") or []
        tiktok = [
            c for c in channels
            if (c.get("service") or "").lower() in ("tiktok", "tik tok")
        ]
        return {
            "valid": True,
            "organization_id": org_id,
            "organization_name": org_name,
            "channel_count": len(channels),
            "tiktok_count": len(tiktok),
            "tiktok_channels": tiktok,
            "message": (
                f"Key OK — org “{org_name}”, "
                f"{len(channels)} channel(s), {len(tiktok)} TikTok"
            ),
        }
    except Exception as e:
        return {"valid": False, "message": str(e)}