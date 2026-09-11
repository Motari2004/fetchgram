"""
buffer_platforms.py
====================
Multi-platform posting via Buffer's GraphQL API — Twitter, YouTube, TikTok.

This is an ADDITIVE module. It does not touch your existing Zernio
(Facebook) or native Bluesky code — it gives pipelines a new set of
`platform` values they can use instead.

--------------------------------------------------------------------
INTEGRATION (3 lines in app.py)
--------------------------------------------------------------------
    from buffer_platforms import buffer_bp, init_buffer_tables, publish_via_buffer

    app.register_blueprint(buffer_bp)
    init_buffer_tables()          # call right after init_db()

Then, inside run_pipeline() / process_post_with_caption(), branch on the
pipeline's platform BEFORE falling back to your existing Zernio call:

    platform = pipeline.get('platform') or 'facebook'

    if platform in ('buffer_twitter', 'buffer_youtube', 'buffer_tiktok'):
        result = publish_via_buffer(pipeline, direct_video_url, caption)
    else:
        result = publish_to_facebook(                 # unchanged
            video_url=direct_video_url,
            text=caption,
            account_id=pipeline['facebook_account_id'],
            publish_now=True,
            key_id=pipeline.get('zernio_key_id')
        )

`publish_via_buffer()` returns the SAME shape your `publish_to_facebook()`
returns — `{"post": {...}, "already_posted": False}` on success or
`{"error": "..."}` on failure — so the rest of your dedup / retry logic in
run_pipeline() needs no changes.

--------------------------------------------------------------------
⚠️ TIKTOK FIELD NAMES ARE A BEST-EFFORT GUESS
--------------------------------------------------------------------
Buffer does not publicly document the exact GraphQL input field names for
TikTok metadata. The names used below (`metadata.tiktok.privacyLevel`,
`allowComment`, `allowDuet`, `allowStitch`, `discloseBrandedContent`,
`discloseYourBrand`, `isAiGenerated`) follow the pattern Buffer uses for
YouTube (`metadata.youtube.*`) and TikTok's own Content Posting API
vocabulary. Before relying on this in production, introspect Buffer's
schema once with your key:

    query {
      __type(name: "TiktokMetadataInput") {
        inputFields { name type { name kind } }
      }
    }

...and fix `_tiktok_metadata()` below to match whatever comes back.
"""

import os
import requests
from datetime import datetime
from flask import Blueprint, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor

buffer_bp = Blueprint('buffer_platforms', __name__)

BUFFER_API = "https://api.buffer.com"
DATABASE_URL = os.environ.get('DATABASE_URL')

SUPPORTED_SERVICES = ('twitter', 'youtube', 'tiktok')


# =================================================================
# DB HELPERS
# =================================================================

def _get_conn():
    if not DATABASE_URL:
        return None
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"❌ buffer_platforms DB connect error: {e}")
        return None


def init_buffer_tables():
    """Call once at startup, right after your existing init_db()."""
    conn = _get_conn()
    if not conn:
        return
    try:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS buffer_accounts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT NOT NULL,
                api_key TEXT NOT NULL,
                organization_id TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS buffer_channels (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                buffer_account_id UUID REFERENCES buffer_accounts(id) ON DELETE CASCADE,
                channel_id TEXT NOT NULL,
                service TEXT NOT NULL,
                display_name TEXT,
                avatar TEXT,
                is_disconnected BOOLEAN DEFAULT FALSE,
                synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(buffer_account_id, channel_id)
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS buffer_posted (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                pipeline_id UUID,
                reel_url TEXT NOT NULL,
                service TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                buffer_post_id TEXT,
                caption TEXT,
                status TEXT DEFAULT 'success',
                error_message TEXT,
                posted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(pipeline_id, reel_url, service)
            );
        """)

        # Extend the pipelines table your main app already created.
        try:
            cur.execute("ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS platform TEXT DEFAULT 'facebook';")
            cur.execute("ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS buffer_account_id UUID REFERENCES buffer_accounts(id);")
            cur.execute("ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS buffer_channel_id TEXT;")
            cur.execute("ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS platform_options JSONB DEFAULT '{}'::jsonb;")
            # Buffer-only pipelines pass '' for facebook_account_id (see app.py's
            # create_pipeline()), so the original NOT NULL constraint has to go.
            cur.execute("ALTER TABLE pipelines ALTER COLUMN facebook_account_id DROP NOT NULL;")
        except Exception as e:
            print(f"⚠️ pipelines table not extendable yet (create it first): {e}")

        cur.execute("CREATE INDEX IF NOT EXISTS idx_buffer_channels_account ON buffer_channels(buffer_account_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_buffer_channels_service ON buffer_channels(service);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_buffer_posted_pipeline ON buffer_posted(pipeline_id);")

        conn.commit()
        cur.close()
        conn.close()
        print("✅ Buffer platform tables ready")
    except Exception as e:
        print(f"❌ Buffer table init error: {e}")


# =================================================================
# BUFFER GRAPHQL CLIENT
# =================================================================

def _buffer_query(api_key, query, variables=None):
    resp = requests.post(
        BUFFER_API,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json={"query": query, "variables": variables or {}},
        timeout=30,
    )
    data = resp.json()
    if data.get("errors"):
        raise Exception("; ".join(e.get("message", "") for e in data["errors"]))
    return data.get("data")


def _fetch_orgs_and_channels(api_key):
    """Validate a Buffer API key and pull every channel across every org."""
    data = _buffer_query(api_key, """
        query {
          account {
            id
            organizations { id name }
          }
        }
    """)
    orgs = (data.get("account") or {}).get("organizations") or []
    all_channels = []
    for org in orgs:
        ch_data = _buffer_query(api_key, """
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
        """, {"input": {"organizationId": org["id"]}})
        for c in ch_data.get("channels") or []:
            all_channels.append({**c, "organizationId": org["id"]})
    return orgs, all_channels


# =================================================================
# METADATA BUILDERS (per-service GraphQL input)
# =================================================================

def _twitter_assets(image_urls):
    return [
        {"image": {"url": u, "metadata": {"altText": ""}}}
        for u in (image_urls or [])
        if u and u.startswith("http")
    ][:4]  # Twitter allows max 4 images


def _video_asset(video_url, thumbnail_offset=1000):
    return [{
        "video": {
            "url": video_url,
            "metadata": {"thumbnailOffset": int(thumbnail_offset)},
        }
    }]


def _youtube_metadata(extra):
    extra = extra or {}
    return {
        "youtube": {
            "title": (extra.get("title") or "Untitled video")[:100],
            "privacy": extra.get("privacy", "public"),
            "categoryId": str(extra.get("category_id", "22")),
            "notifySubscribers": bool(extra.get("notify_subscribers", True)),
            "madeForKids": bool(extra.get("made_for_kids", False)),
        }
    }


def _tiktok_metadata(extra):
    """⚠️ See module docstring — field names are unverified, introspect Buffer's
    schema and adjust before relying on this in production."""
    extra = extra or {}
    return {
        "tiktok": {
            "privacyLevel": extra.get("privacy_level", "PUBLIC_TO_EVERYONE"),
            "allowComment": bool(extra.get("allow_comment", True)),
            "allowDuet": bool(extra.get("allow_duet", True)),
            "allowStitch": bool(extra.get("allow_stitch", True)),
            "discloseBrandedContent": bool(extra.get("disclose_branded_content", False)),
            "discloseYourBrand": bool(extra.get("disclose_your_brand", False)),
            "isAiGenerated": bool(extra.get("is_ai_generated", False)),
        }
    }


# =================================================================
# CORE: create a post on a single Buffer-managed channel
# =================================================================

def create_post_for_channel(api_key, channel_id, service, text=None,
                             video_url=None, image_urls=None, extra=None,
                             mode="addToQueue", due_at=None):
    """
    service: 'twitter' | 'youtube' | 'tiktok'
    Returns the raw Buffer `post` object on success, raises on error.
    """
    extra = extra or {}

    if service == "twitter":
        if not text or len(text) > 280:
            raise ValueError("Tweet text must be 1–280 characters")
        assets = _twitter_assets(image_urls)
        metadata = None
        link = extra.get("link")
        if link:
            metadata = {"twitter": {"linkAttachment": {"url": link}}}

    elif service == "youtube":
        if not video_url or not video_url.startswith("http"):
            raise ValueError("A public video URL is required for YouTube")
        assets = _video_asset(video_url, extra.get("thumbnail_offset", 1000))
        metadata = _youtube_metadata(extra)
        text = text or extra.get("description") or extra.get("title") or ""

    elif service == "tiktok":
        if not video_url or not video_url.startswith("http"):
            raise ValueError("A public video URL is required for TikTok")
        assets = _video_asset(video_url, extra.get("thumbnail_offset", 1000))
        metadata = _tiktok_metadata(extra)
        text = (text or "")[:2200]

    else:
        raise ValueError(f"Unsupported service: {service}")

    gql_input = {
        "channelId": channel_id,
        "text": text or "",
        "schedulingType": "automatic",
        "mode": mode,
        "assets": assets,
    }
    if metadata:
        gql_input["metadata"] = metadata
    if due_at:
        gql_input["dueAt"] = due_at

    data = _buffer_query(api_key, """
        mutation CreatePost($input: CreatePostInput!) {
          createPost(input: $input) {
            ... on PostActionSuccess {
              post { id text status dueAt shareMode externalLink }
            }
            ... on MutationError { message }
          }
        }
    """, {"input": gql_input})

    result = data.get("createPost")
    if result and result.get("message"):
        raise Exception(result["message"])
    return result.get("post")


# =================================================================
# ACCOUNT / CHANNEL MANAGEMENT (mirrors your Zernio-key pattern)
# =================================================================

def _save_account_and_channels(name, api_key):
    orgs, channels = _fetch_orgs_and_channels(api_key)
    if not orgs:
        raise Exception("No Buffer organizations found for this key")

    conn = _get_conn()
    if not conn:
        raise Exception("Database connection failed")
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO buffer_accounts (name, api_key, organization_id)
            VALUES (%s, %s, %s) RETURNING id
        """, (name, api_key, orgs[0]["id"]))
        account_id = cur.fetchone()[0]

        for c in channels:
            cur.execute("""
                INSERT INTO buffer_channels
                    (buffer_account_id, channel_id, service, display_name, avatar, is_disconnected, synced_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (buffer_account_id, channel_id) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    avatar = EXCLUDED.avatar,
                    is_disconnected = EXCLUDED.is_disconnected,
                    synced_at = NOW()
            """, (account_id, c["id"], c.get("service"), c.get("displayName") or c.get("name"),
                  c.get("avatar"), bool(c.get("isDisconnected"))))

        conn.commit()
        cur.close()
        conn.close()
        return account_id, channels
    except Exception:
        conn.rollback()
        conn.close()
        raise


# =================================================================
# ROUTES
# =================================================================

@buffer_bp.route("/api/buffer/validate-key", methods=["POST"])
def validate_buffer_key():
    data = request.get_json(silent=True) or {}
    api_key = data.get("api_key")
    if not api_key:
        return jsonify({"valid": False, "message": "API key required"}), 400
    try:
        orgs, channels = _fetch_orgs_and_channels(api_key)
        by_service = {}
        for c in channels:
            by_service.setdefault(c.get("service"), []).append(c)
        return jsonify({
            "valid": True,
            "organizations": orgs,
            "channels": channels,
            "channel_count": len(channels),
            "by_service": {k: len(v) for k, v in by_service.items()},
        })
    except Exception as e:
        return jsonify({"valid": False, "message": str(e)}), 400


@buffer_bp.route("/api/buffer/accounts", methods=["POST"])
def add_buffer_account():
    data = request.get_json(silent=True) or {}
    name = data.get("name") or f"Buffer {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
    api_key = data.get("api_key")
    if not api_key:
        return jsonify({"error": "api_key is required"}), 400
    try:
        account_id, channels = _save_account_and_channels(name, api_key)
        return jsonify({
            "status": "success",
            "message": f"Buffer account '{name}' added with {len(channels)} channels",
            "account_id": account_id,
            "channels": channels,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@buffer_bp.route("/api/buffer/accounts", methods=["GET"])
def list_buffer_accounts():
    conn = _get_conn()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, name, organization_id, is_active, created_at
            FROM buffer_accounts ORDER BY created_at DESC
        """)
        accounts = cur.fetchall()

        for acc in accounts:
            cur.execute("""
                SELECT channel_id, service, display_name, avatar, is_disconnected
                FROM buffer_channels
                WHERE buffer_account_id = %s AND is_disconnected = FALSE
                ORDER BY service, display_name
            """, (acc["id"],))
            acc["channels"] = cur.fetchall()

        cur.close()
        conn.close()
        return jsonify({"status": "success", "accounts": accounts, "total": len(accounts)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@buffer_bp.route("/api/buffer/accounts/<account_id>", methods=["DELETE"])
def delete_buffer_account(account_id):
    conn = _get_conn()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM buffer_accounts WHERE id = %s RETURNING id", (account_id,))
        deleted = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        if deleted:
            return jsonify({"status": "success", "message": "Buffer account deleted"})
        return jsonify({"error": "Account not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@buffer_bp.route("/api/buffer/accounts/<account_id>/sync", methods=["POST"])
def sync_buffer_account(account_id):
    conn = _get_conn()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT api_key FROM buffer_accounts WHERE id = %s", (account_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Account not found"}), 404
        api_key = row["api_key"]
        cur.close()
        conn.close()

        orgs, channels = _fetch_orgs_and_channels(api_key)

        conn2 = _get_conn()
        cur2 = conn2.cursor()
        for c in channels:
            cur2.execute("""
                INSERT INTO buffer_channels
                    (buffer_account_id, channel_id, service, display_name, avatar, is_disconnected, synced_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (buffer_account_id, channel_id) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    avatar = EXCLUDED.avatar,
                    is_disconnected = EXCLUDED.is_disconnected,
                    synced_at = NOW()
            """, (account_id, c["id"], c.get("service"), c.get("displayName") or c.get("name"),
                  c.get("avatar"), bool(c.get("isDisconnected"))))
        conn2.commit()
        cur2.close()
        conn2.close()

        return jsonify({"status": "success", "channels_synced": len(channels)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@buffer_bp.route("/api/buffer/channels", methods=["GET"])
def list_buffer_channels():
    """Optional ?service=twitter|youtube|tiktok filter, across ALL accounts."""
    service = request.args.get("service")
    conn = _get_conn()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT bc.channel_id, bc.service, bc.display_name, bc.avatar,
                   ba.id as account_id, ba.name as account_name
            FROM buffer_channels bc
            JOIN buffer_accounts ba ON bc.buffer_account_id = ba.id
            WHERE bc.is_disconnected = FALSE AND ba.is_active = TRUE
        """
        params = []
        if service:
            query += " AND bc.service = %s"
            params.append(service)
        query += " ORDER BY bc.service, bc.display_name"
        cur.execute(query, params)
        channels = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify({"status": "success", "channels": channels, "total": len(channels)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@buffer_bp.route("/api/buffer/post", methods=["POST"])
def buffer_post_now():
    """
    One-off manual post, mirrors /api/zernio/publish.
    Body: { account_id, channel_id, service, text, video_url, image_urls, extra }
    """
    data = request.get_json(silent=True) or {}
    account_id = data.get("account_id")
    channel_id = data.get("channel_id")
    service = data.get("service")

    if not account_id or not channel_id or service not in SUPPORTED_SERVICES:
        return jsonify({"error": "account_id, channel_id and a supported service are required"}), 400

    conn = _get_conn()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT api_key FROM buffer_accounts WHERE id = %s AND is_active = TRUE", (account_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({"error": "Buffer account not found or inactive"}), 404

        post = create_post_for_channel(
            api_key=row["api_key"],
            channel_id=channel_id,
            service=service,
            text=data.get("text"),
            video_url=data.get("video_url"),
            image_urls=data.get("image_urls"),
            extra=data.get("extra"),
        )
        return jsonify({"status": "success", "post": post})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =================================================================
# AUTONOMOUS PIPELINE HOOK
# =================================================================

def publish_via_buffer(pipeline, video_url, caption):
    """
    Drop-in replacement call for publish_to_facebook() when
    pipeline['platform'] is 'buffer_twitter' / 'buffer_youtube' / 'buffer_tiktok'.

    Returns the same shape your run_pipeline() already expects:
        success        -> {"post": {...}, "already_posted": False}
        genuine failure -> {"error": "..."}
    """
    platform = pipeline.get("platform") or ""
    if not platform.startswith("buffer_"):
        return {"error": f"publish_via_buffer called with non-buffer platform: {platform}"}

    service = platform.replace("buffer_", "")
    account_id = pipeline.get("buffer_account_id")
    channel_id = pipeline.get("buffer_channel_id")
    extra = pipeline.get("platform_options") or {}

    if not account_id or not channel_id:
        return {"error": "Pipeline is missing buffer_account_id / buffer_channel_id"}

    conn = _get_conn()
    if not conn:
        return {"error": "Database connection failed"}
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT api_key FROM buffer_accounts WHERE id = %s AND is_active = TRUE", (account_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return {"error": "Buffer account not found or inactive"}

        # Idempotency: Buffer has no built-in dedup like Zernio's "existingPostId",
        # so we check our own buffer_posted table before publishing again.
        dedup_conn = _get_conn()
        dcur = dedup_conn.cursor(cursor_factory=RealDictCursor)
        dcur.execute("""
            SELECT buffer_post_id FROM buffer_posted
            WHERE pipeline_id = %s AND reel_url = %s AND service = %s AND status = 'success'
            LIMIT 1
        """, (pipeline.get("id"), pipeline.get("reel_url") or video_url, service))
        existing = dcur.fetchone()
        dcur.close()
        dedup_conn.close()
        if existing:
            return {
                "already_posted": True,
                "post": {"id": existing["buffer_post_id"]},
            }

        text = caption
        if service == "youtube":
            extra = dict(extra)
            extra.setdefault("title", (caption or "New video")[:100])

        post = create_post_for_channel(
            api_key=row["api_key"],
            channel_id=channel_id,
            service=service,
            text=text,
            video_url=video_url,
            extra=extra,
        )

        # Record for dedup / history.
        log_conn = _get_conn()
        lcur = log_conn.cursor()
        lcur.execute("""
            INSERT INTO buffer_posted (pipeline_id, reel_url, service, channel_id, buffer_post_id, caption, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'success')
            ON CONFLICT (pipeline_id, reel_url, service) DO UPDATE SET
                buffer_post_id = EXCLUDED.buffer_post_id,
                caption = EXCLUDED.caption,
                status = 'success',
                posted_at = NOW()
        """, (pipeline.get("id"), pipeline.get("reel_url") or video_url, service, channel_id,
              post.get("id") if post else None, caption))
        log_conn.commit()
        lcur.close()
        log_conn.close()

        return {"post": post, "already_posted": False}

    except Exception as e:
        return {"error": str(e)}