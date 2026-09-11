"""
TikTok posting via Buffer GraphQL API.

Matches the proven Buffer client pattern:
- Resolve organizations from account
- List channels with ChannelsInput { organizationId }
- createPost with video asset + thumbnailOffset

API key is managed from the UI (app_settings) or BUFFER_API_KEY env.
This module does NOT import app.py (no circular imports).
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


def buffer(query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Core Buffer GraphQL helper (same pattern as the working client).
    """
    key = get_buffer_api_key()
    if not key:
        raise ValueError(
            "Buffer API key is not configured. "
            "Please save it in the UI (Buffer API Key section)."
        )

    if variables is None:
        variables = {}

    res = requests.post(
        BUFFER_API_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        json={"query": query, "variables": variables},
        timeout=60,
    )
    json_data = res.json()
    if json_data.get("errors"):
        raise Exception(
            "; ".join(e.get("message", str(e)) for e in json_data["errors"])
        )
    return json_data.get("data") or {}


# ---------------------------------------------------------------------------
# Organizations & Channels
# ---------------------------------------------------------------------------

def list_organizations() -> List[Dict[str, Any]]:
    """Return organizations for the authenticated Buffer account."""
    data = buffer("""
        query {
          account {
            id
            organizations {
              id
              name
            }
          }
        }
    """)
    return (data.get("account") or {}).get("organizations") or []


def list_all_channels() -> List[Dict[str, Any]]:
    """
    Fetch channels across all organizations (working Buffer pattern).
    Each channel is annotated with organizationId.
    """
    orgs = list_organizations()
    if not orgs:
        return []

    all_channels: List[Dict[str, Any]] = []
    for org in orgs:
        ch_data = buffer(
            """
            query GetChannels($input: ChannelsInput!) {
              channels(input: $input) {
                id
                name
                service
                avatar
                displayName
                isDisconnected
              }
            }
            """,
            {"input": {"organizationId": org["id"]}},
        )
        for c in ch_data.get("channels") or []:
            all_channels.append({**c, "organizationId": org["id"]})

    return all_channels


def list_channels(organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Return channels. If organization_id is given, only that org;
    otherwise all orgs (same as list_all_channels).
    """
    if organization_id:
        ch_data = buffer(
            """
            query GetChannels($input: ChannelsInput!) {
              channels(input: $input) {
                id
                name
                service
                avatar
                displayName
                isDisconnected
              }
            }
            """,
            {"input": {"organizationId": organization_id}},
        )
        return [
            {**c, "organizationId": organization_id}
            for c in (ch_data.get("channels") or [])
        ]
    return list_all_channels()


def list_tiktok_channels(organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return connected (not disconnected) TikTok channels only."""
    channels = list_channels(organization_id=organization_id)
    return [
        c
        for c in channels
        if (c.get("service") or "").lower() == "tiktok" and not c.get("isDisconnected")
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
    mode: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a TikTok video post via Buffer (same mutation as the working client).

    mode: "addToQueue" | "customScheduled" | "shareNow" (if supported)
    If due_at is set, mode becomes customScheduled and dueAt is sent.
    """
    if not channel_id:
        raise ValueError("channel_id is required")
    if not video_url or not str(video_url).startswith("http"):
        raise ValueError("A public video URL is required")

    from datetime import datetime, timezone

    caption = (text or "").strip()
    if not caption:
        caption = "🎬"
    if len(caption) > 2200:
        caption = caption[:2200]

    # Buffer modes: addToQueue | customScheduled
    # "Publish now" (no schedule, not queue) -> customScheduled at current UTC
    if due_at:
        share_mode = "customScheduled"
    elif mode:
        share_mode = mode
    elif add_to_queue:
        share_mode = "addToQueue"
    else:
        share_mode = "customScheduled"
        due_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    input_data: Dict[str, Any] = {
        "channelId": channel_id,
        "text": caption,
        "schedulingType": "automatic",
        "mode": share_mode,
        "assets": [
            {
                "video": {
                    "url": video_url,
                    "metadata": {
                        "thumbnailOffset": int(thumbnail_offset_ms or 1000),
                    },
                }
            }
        ],
    }

    if due_at and share_mode == "customScheduled":
        if due_at.endswith("Z") or "+" in due_at:
            input_data["dueAt"] = due_at
        else:
            input_data["dueAt"] = due_at + "Z"

    logger.info(
        f"Buffer createPost payload: channel={channel_id} mode={share_mode} "
        f"dueAt={input_data.get('dueAt')} video={video_url[:80]}..."
    )

    data = buffer(
        """
        mutation CreatePost($input: CreatePostInput!) {
          createPost(input: $input) {
            ... on PostActionSuccess {
              post { id text status dueAt shareMode }
            }
            ... on MutationError { message }
          }
        }
        """,
        {"input": input_data},
    )

    result = data.get("createPost") or {}
    if result.get("message"):
        raise Exception(result["message"])

    post = result.get("post") or {}
    logger.info(
        f"✅ TikTok post via Buffer | channel={channel_id} | "
        f"post_id={post.get('id')} | status={post.get('status')} | dueAt={post.get('dueAt')}"
    )
    return {
        "success": True,
        "post_id": post.get("id"),
        "text": post.get("text"),
        "due_at": post.get("dueAt"),
        "status": post.get("status"),
        "share_mode": post.get("shareMode"),
        "channel_id": channel_id,
        "platform": "tiktok",
        "provider": "buffer",
        "post": post,
    }


def validate_buffer_key(api_key: str) -> Dict[str, Any]:
    """
    Validate a key by listing orgs + TikTok channels (does not persist the key).
    """
    if not api_key or not api_key.strip():
        return {"valid": False, "message": "API key is empty"}

    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
    }

    def _post(query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"query": query, "variables": variables or {}}
        resp = requests.post(
            BUFFER_API_URL,
            json=payload,
            headers=headers,
            timeout=30,
        )
        body = resp.json()
        if body.get("errors"):
            raise Exception(
                "; ".join(e.get("message", str(e)) for e in body["errors"])
            )
        return body.get("data") or {}

    try:
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

        all_channels: List[Dict[str, Any]] = []
        for org in orgs:
            ch_data = _post(
                """
                query GetChannels($input: ChannelsInput!) {
                  channels(input: $input) {
                    id
                    name
                    displayName
                    service
                    isDisconnected
                  }
                }
                """,
                {"input": {"organizationId": org["id"]}},
            )
            for c in ch_data.get("channels") or []:
                all_channels.append({**c, "organizationId": org["id"]})

        tiktok = [
            c
            for c in all_channels
            if (c.get("service") or "").lower() == "tiktok"
            and not c.get("isDisconnected")
        ]

        org_name = orgs[0].get("name") or orgs[0]["id"]
        return {
            "valid": True,
            "organization_id": orgs[0]["id"],
            "organization_name": org_name,
            "channel_count": len(all_channels),
            "tiktok_count": len(tiktok),
            "tiktok_channels": tiktok,
            "message": (
                f"Key OK — org \"{org_name}\", "
                f"{len(all_channels)} channel(s), {len(tiktok)} TikTok"
            ),
        }
    except Exception as e:
        return {"valid": False, "message": str(e)}