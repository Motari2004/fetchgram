import os
import re
import uuid
import shutil
import tempfile
import json
import time
import io
import base64
import random
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file, render_template, after_this_request, session
from flask_cors import CORS
import yt_dlp
import requests
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import psycopg2
from psycopg2.extras import RealDictCursor

# Load .env file manually if it exists (for local development)
try:
    with open('.env', 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ[key] = value
except FileNotFoundError:
    pass

FIXED_USER_ID = '62c1d2ca-88e6-490f-9051-20926c1dd8c4'

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fetchgram-dev-secret-change-me-in-production-2024')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production' or bool(os.environ.get('VERCEL'))
CORS(app, supports_credentials=True)



# ============== COOKIE EXTRACTOR CONFIGURATION ==============
COOKIE_EXTRACTOR_URL = os.environ.get('COOKIE_EXTRACTOR_URL', 'https://profilecookieextractor.onrender.com')


# ============== VIDEO URL GETTER SERVICE ==============
IG_VIDEO_URL_GETTER = os.environ.get('IG_VIDEO_URL_GETTER', 'https://igvideourl.onrender.com')



# ============== NEON POSTGRESQL SETUP ==============

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    try:
        if DATABASE_URL:
            conn = psycopg2.connect(DATABASE_URL)
            return conn
        else:
            app.logger.error("DATABASE_URL not set")
            return None
    except Exception as e:
        app.logger.error(f"Database connection error: {e}")
        return None















def init_db():
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        # User cookies table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_cookies (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id TEXT NOT NULL,
                cookie_data JSONB NOT NULL,
                username TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(user_id)
            );
        """)
        
        # Scraped reels table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scraped_reels (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                usernames TEXT[] NOT NULL,
                results JSONB NOT NULL,
                status TEXT DEFAULT 'completed',
                total_profiles INTEGER DEFAULT 0,
                total_reels INTEGER DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(user_id, job_id)
            );
        """)
        
        # Pipelines table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pipelines (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT NOT NULL,
                profile_username TEXT NOT NULL,
                facebook_account_id TEXT NOT NULL,
                facebook_page_name TEXT,
                daily_limit INTEGER DEFAULT 2,
                is_active BOOLEAN DEFAULT TRUE,
                last_run TIMESTAMP WITH TIME ZONE,
                total_posted INTEGER DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)
        
        # Posted reels table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS posted_reels (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                pipeline_id UUID REFERENCES pipelines(id) ON DELETE CASCADE,
                reel_url TEXT NOT NULL,
                direct_video_url TEXT,
                caption TEXT,
                facebook_post_id TEXT,
                facebook_post_url TEXT,
                posted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                status TEXT DEFAULT 'success',
                error_message TEXT,
                UNIQUE(pipeline_id, reel_url)
            );
        """)
        
        # Pipeline runs log
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                pipeline_id UUID REFERENCES pipelines(id) ON DELETE CASCADE,
                run_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                reels_posted INTEGER DEFAULT 0,
                reels_failed INTEGER DEFAULT 0,
                status TEXT DEFAULT 'completed',
                error_message TEXT
            );
        """)
        
        # Reel cache table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS reel_cache (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                reel_url TEXT NOT NULL UNIQUE,
                direct_url TEXT NOT NULL,
                caption TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)
        
        # Sync status table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sync_status (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username TEXT NOT NULL UNIQUE,
                status TEXT DEFAULT 'idle',
                total_reels INTEGER DEFAULT 0,
                captions_fetched INTEGER DEFAULT 0,
                captions_skipped INTEGER DEFAULT 0,
                errors INTEGER DEFAULT 0,
                started_at TIMESTAMP WITH TIME ZONE,
                completed_at TIMESTAMP WITH TIME ZONE,
                last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                job_id TEXT
            );
        """)
        
        # Scheduled posts table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_posts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                reel_url TEXT NOT NULL,
                direct_video_url TEXT NOT NULL,
                caption TEXT,
                pipeline_id UUID REFERENCES pipelines(id) ON DELETE CASCADE,
                scheduled_time TIMESTAMP WITH TIME ZONE NOT NULL,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                posted_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)
        
        # Pending posts table (backward compat)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pending_posts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                reel_url TEXT NOT NULL UNIQUE,
                direct_video_url TEXT NOT NULL,
                pipeline_id UUID REFERENCES pipelines(id) ON DELETE CASCADE,
                profile_username TEXT NOT NULL,
                facebook_account_id TEXT NOT NULL,
                caption TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                status TEXT DEFAULT 'pending',
                attempts INTEGER DEFAULT 0,
                error_message TEXT,
                facebook_post_id TEXT,
                facebook_post_url TEXT,
                wakeup_sent BOOLEAN DEFAULT FALSE,
                real_fetch_attempts INTEGER DEFAULT 0,
                webhook_received BOOLEAN DEFAULT FALSE
            );
        """)
        
        # ========== ZERNIO KEYS TABLE ==========
        cur.execute("""
            CREATE TABLE IF NOT EXISTS zernio_keys (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT NOT NULL,
                api_key TEXT NOT NULL UNIQUE,
                facebook_account_id TEXT NOT NULL,
                facebook_page_name TEXT,
                daily_limit INTEGER DEFAULT 50,
                usage_count INTEGER DEFAULT 0,
                last_used TIMESTAMP WITH TIME ZONE,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)
        
        # ========== APP SETTINGS TABLE ==========
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                setting_key TEXT NOT NULL UNIQUE,
                setting_value TEXT,
                setting_type TEXT DEFAULT 'string',
                description TEXT,
                is_encrypted BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)
        
        # Insert default settings
        cur.execute("""
            INSERT INTO app_settings (setting_key, setting_value, description) VALUES
                ('caption_service_url', 'https://copytxt-caption-automation.onrender.com/api/caption', 'Caption service endpoint'),
                ('zernio_base_url', 'https://zernio.com/api/v1', 'Zernio API base URL'),
                ('buffer_base_url', 'https://api.buffer.com', 'Buffer GraphQL API URL'),
                ('scraper_base_url', 'https://ig-reels-scraper.onrender.com', 'Instagram scraper service URL'),
                ('max_reels_per_scrape', '50', 'Maximum reels to scrape per profile'),
                ('max_scrolls_per_scrape', '200', 'Maximum scrolls per profile'),
                ('enable_auto_sync', 'true', 'Auto-sync captions after scrape')
            ON CONFLICT (setting_key) DO NOTHING;
        """)
        
        # ========== BUFFER KEYS TABLE (Twitter + TikTok) ==========
        cur.execute("""
            CREATE TABLE IF NOT EXISTS buffer_keys (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT NOT NULL,
                api_key TEXT NOT NULL UNIQUE,
                organization_id TEXT,
                organization_name TEXT,
                daily_limit INTEGER DEFAULT 50,
                usage_count INTEGER DEFAULT 0,
                last_used TIMESTAMP WITH TIME ZONE,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)
        
        # ========== BUFFER CHANNELS TABLE ==========
        cur.execute("""
            CREATE TABLE IF NOT EXISTS buffer_channels (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                buffer_key_id UUID REFERENCES buffer_keys(id) ON DELETE CASCADE,
                channel_id TEXT NOT NULL,
                name TEXT,
                display_name TEXT,
                service TEXT NOT NULL,
                avatar TEXT,
                is_disconnected BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(buffer_key_id, channel_id)
            );
        """)
        
        # ============================================================
        # ENSURE ALL COLUMNS EXIST (protects against tables created
        # by earlier schema versions)
        # ============================================================
        
        # posted_reels
        cur.execute("ALTER TABLE posted_reels ADD COLUMN IF NOT EXISTS direct_video_url TEXT;")
        cur.execute("ALTER TABLE posted_reels ADD COLUMN IF NOT EXISTS caption TEXT;")
        cur.execute("ALTER TABLE posted_reels ADD COLUMN IF NOT EXISTS platform TEXT DEFAULT 'facebook';")
        cur.execute("ALTER TABLE posted_reels ADD COLUMN IF NOT EXISTS external_post_url TEXT;")
        
        # pending_posts
        cur.execute("ALTER TABLE pending_posts ADD COLUMN IF NOT EXISTS wakeup_sent BOOLEAN DEFAULT FALSE;")
        cur.execute("ALTER TABLE pending_posts ADD COLUMN IF NOT EXISTS real_fetch_attempts INTEGER DEFAULT 0;")
        cur.execute("ALTER TABLE pending_posts ADD COLUMN IF NOT EXISTS webhook_received BOOLEAN DEFAULT FALSE;")
        
        # pipelines
        cur.execute("ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS zernio_key_id UUID REFERENCES zernio_keys(id);")
        cur.execute("ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS platform TEXT DEFAULT 'facebook';")
        cur.execute("ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS buffer_key_id UUID REFERENCES buffer_keys(id);")
        cur.execute("ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS buffer_channel_id TEXT;")
        cur.execute("ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS buffer_channel_name TEXT;")
        
        # buffer_keys — protects against an earlier minimal schema
        cur.execute("ALTER TABLE buffer_keys ADD COLUMN IF NOT EXISTS organization_id TEXT;")
        cur.execute("ALTER TABLE buffer_keys ADD COLUMN IF NOT EXISTS organization_name TEXT;")
        cur.execute("ALTER TABLE buffer_keys ADD COLUMN IF NOT EXISTS daily_limit INTEGER DEFAULT 50;")
        cur.execute("ALTER TABLE buffer_keys ADD COLUMN IF NOT EXISTS usage_count INTEGER DEFAULT 0;")
        cur.execute("ALTER TABLE buffer_keys ADD COLUMN IF NOT EXISTS last_used TIMESTAMP WITH TIME ZONE;")
        cur.execute("ALTER TABLE buffer_keys ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;")
        cur.execute("ALTER TABLE buffer_keys ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();")
        cur.execute("ALTER TABLE buffer_keys ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();")
        
        # buffer_channels — same protection
        cur.execute("ALTER TABLE buffer_channels ADD COLUMN IF NOT EXISTS buffer_key_id UUID REFERENCES buffer_keys(id) ON DELETE CASCADE;")
        cur.execute("ALTER TABLE buffer_channels ADD COLUMN IF NOT EXISTS name TEXT;")
        cur.execute("ALTER TABLE buffer_channels ADD COLUMN IF NOT EXISTS display_name TEXT;")
        cur.execute("ALTER TABLE buffer_channels ADD COLUMN IF NOT EXISTS service TEXT;")
        cur.execute("ALTER TABLE buffer_channels ADD COLUMN IF NOT EXISTS avatar TEXT;")
        cur.execute("ALTER TABLE buffer_channels ADD COLUMN IF NOT EXISTS is_disconnected BOOLEAN DEFAULT FALSE;")
        cur.execute("ALTER TABLE buffer_channels ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();")
        cur.execute("ALTER TABLE buffer_channels ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();")
        
        # ============================================================
        # FIX: Ensure UNIQUE(buffer_key_id, channel_id) constraint
        # exists on buffer_channels — required for ON CONFLICT
        # ============================================================
        
        # Remove duplicate rows that would block the unique constraint
        cur.execute("""
            DELETE FROM buffer_channels a
            USING buffer_channels b
            WHERE a.id > b.id
              AND a.buffer_key_id IS NOT DISTINCT FROM b.buffer_key_id
              AND a.channel_id = b.channel_id;
        """)
        
        # Add the constraint if it doesn't already exist
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conrelid = 'buffer_channels'::regclass
                      AND contype = 'u'
                      AND conname = 'buffer_channels_buffer_key_id_channel_id_key'
                ) THEN
                    ALTER TABLE buffer_channels
                        ADD CONSTRAINT buffer_channels_buffer_key_id_channel_id_key
                        UNIQUE (buffer_key_id, channel_id);
                END IF;
            END
            $$;
        """)
        
        # ============================================================
        # INDEXES
        # ============================================================
        
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scraped_reels_user_id ON scraped_reels(user_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scraped_reels_created_at ON scraped_reels(created_at DESC);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_user_cookies_user_id ON user_cookies(user_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_posted_reels_pipeline_id ON posted_reels(pipeline_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_posted_reels_posted_at ON posted_reels(posted_at);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pipelines_is_active ON pipelines(is_active);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pipeline_runs_pipeline_id ON pipeline_runs(pipeline_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_reel_cache_reel_url ON reel_cache(reel_url);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_reel_cache_created_at ON reel_cache(created_at);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sync_status_username ON sync_status(username);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sync_status_status ON sync_status(status);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_posts_scheduled_time ON scheduled_posts(scheduled_time);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_posts_status ON scheduled_posts(status);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_posts_pipeline_id ON scheduled_posts(pipeline_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_posts_processing ON scheduled_posts(status, updated_at) WHERE status = 'processing';")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_posts_due ON scheduled_posts(status, scheduled_time);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pending_posts_reel_url ON pending_posts(reel_url);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pending_posts_status ON pending_posts(status);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pending_posts_created_at ON pending_posts(created_at DESC);")
        
        # Zernio indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_zernio_keys_api_key ON zernio_keys(api_key);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_zernio_keys_is_active ON zernio_keys(is_active);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pipelines_zernio_key_id ON pipelines(zernio_key_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_app_settings_setting_key ON app_settings(setting_key);")
        
        # Buffer indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_buffer_keys_api_key ON buffer_keys(api_key);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_buffer_keys_is_active ON buffer_keys(is_active);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_buffer_keys_organization_id ON buffer_keys(organization_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_buffer_channels_key_id ON buffer_channels(buffer_key_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_buffer_channels_channel_id ON buffer_channels(channel_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_buffer_channels_service ON buffer_channels(service);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_buffer_channels_disconnected ON buffer_channels(is_disconnected) WHERE is_disconnected = FALSE;")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pipelines_platform ON pipelines(platform);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pipelines_buffer_key_id ON pipelines(buffer_key_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_posted_reels_platform ON posted_reels(platform);")
        
        conn.commit()
        app.logger.info(
            "✅ Database tables ready — Buffer keys, Zernio keys, app settings, "
            "and platform-aware pipelines all present"
        )
    except Exception as e:
        app.logger.error(f"❌ Database init error: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        cur.close()
        conn.close()




















# Initialize database on startup
init_db()

# ============== APP SETTINGS MANAGER ==============

APP_SETTINGS_CACHE = {}
SETTINGS_LAST_LOAD = None

def load_app_settings():
    """Load all app settings from database."""
    global APP_SETTINGS_CACHE, SETTINGS_LAST_LOAD
    
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT setting_key, setting_value, setting_type 
            FROM app_settings
            ORDER BY setting_key
        """)
        settings = cur.fetchall()
        
        for setting in settings:
            key = setting['setting_key']
            value = setting['setting_value']
            setting_type = setting['setting_type']
            
            # Parse based on type
            if setting_type == 'json':
                try:
                    APP_SETTINGS_CACHE[key] = json.loads(value) if value else None
                except:
                    APP_SETTINGS_CACHE[key] = value
            elif setting_type == 'array':
                try:
                    APP_SETTINGS_CACHE[key] = json.loads(value) if value else []
                except:
                    APP_SETTINGS_CACHE[key] = value.split(',') if value else []
            elif setting_type == 'boolean':
                APP_SETTINGS_CACHE[key] = value.lower() in ('true', '1', 'yes') if value else False
            else:
                APP_SETTINGS_CACHE[key] = value
        
        SETTINGS_LAST_LOAD = datetime.utcnow()
        cur.close()
        conn.close()
        app.logger.info(f"✅ Loaded {len(settings)} app settings")
        
    except Exception as e:
        app.logger.error(f"Error loading settings: {e}")

def get_setting(key, default=None):
    """Get a setting value."""
    # Reload if cache is old (5 minutes)
    if SETTINGS_LAST_LOAD and (datetime.utcnow() - SETTINGS_LAST_LOAD).total_seconds() > 300:
        load_app_settings()
    
    return APP_SETTINGS_CACHE.get(key, default)

def update_setting(key, value):
    """Update a setting value."""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO app_settings (setting_key, setting_value, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (setting_key) DO UPDATE SET
                setting_value = EXCLUDED.setting_value,
                updated_at = NOW()
        """, (key, str(value)))
        conn.commit()
        
        # Update cache
        APP_SETTINGS_CACHE[key] = value
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        app.logger.error(f"Error updating setting {key}: {e}")
        return False

# Load settings on startup
load_app_settings()

# ============== ZERNIO KEY MANAGER ==============

ZERNIO_KEYS = {}  # Cache for keys
ZERNIO_KEY_USAGE = {}  # Track usage per key

def load_zernio_keys():
    """Load all active Zernio keys from database."""
    global ZERNIO_KEYS, ZERNIO_KEY_USAGE
    
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, name, api_key, facebook_account_id, facebook_page_name, 
                   daily_limit, usage_count, is_active
            FROM zernio_keys
            WHERE is_active = TRUE
        """)
        keys = cur.fetchall()
        
        ZERNIO_KEYS = {}
        ZERNIO_KEY_USAGE = {}
        
        for key in keys:
            ZERNIO_KEYS[str(key['id'])] = dict(key)
            ZERNIO_KEY_USAGE[str(key['id'])] = {
                'today': 0,
                'last_reset': datetime.utcnow().date()
            }
        
        cur.close()
        conn.close()
        app.logger.info(f"✅ Loaded {len(keys)} Zernio keys")
        return keys
    except Exception as e:
        app.logger.error(f"Error loading Zernio keys: {e}")
        return []

def get_best_zernio_key():
    """
    Get the best available Zernio key based on usage.
    Returns the least used key that hasn't hit daily limit.
    """
    global ZERNIO_KEY_USAGE
    
    # Reset daily usage if new day
    today = datetime.utcnow().date()
    for key_id in ZERNIO_KEY_USAGE:
        if ZERNIO_KEY_USAGE[key_id]['last_reset'] != today:
            ZERNIO_KEY_USAGE[key_id]['today'] = 0
            ZERNIO_KEY_USAGE[key_id]['last_reset'] = today
    
    # Find keys with capacity
    available_keys = []
    for key_id, key_data in ZERNIO_KEYS.items():
        usage = ZERNIO_KEY_USAGE.get(key_id, {'today': 0, 'last_reset': today})
        if usage['today'] < key_data.get('daily_limit', 50):
            available_keys.append({
                'key_id': key_id,
                'usage': usage['today'],
                'limit': key_data.get('daily_limit', 50),
                'remaining': key_data.get('daily_limit', 50) - usage['today']
            })
    
    if not available_keys:
        return None
    
    # Return key with most remaining capacity
    best_key = max(available_keys, key=lambda x: x['remaining'])
    return ZERNIO_KEYS[best_key['key_id']]

def get_zernio_key_by_id(key_id):
    """Get a specific Zernio key by ID."""
    return ZERNIO_KEYS.get(str(key_id))

def increment_key_usage(key_id):
    """Increment usage count for a key."""
    if str(key_id) in ZERNIO_KEY_USAGE:
        ZERNIO_KEY_USAGE[str(key_id)]['today'] += 1
    
    # Also update database
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                UPDATE zernio_keys 
                SET usage_count = usage_count + 1,
                    last_used = NOW(),
                    updated_at = NOW()
                WHERE id = %s
            """, (key_id,))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            app.logger.error(f"Error updating key usage: {e}")

def get_key_usage_status(key_id):
    """Get usage status for a key."""
    if str(key_id) in ZERNIO_KEY_USAGE:
        usage = ZERNIO_KEY_USAGE[str(key_id)]
        key_data = ZERNIO_KEYS.get(str(key_id), {})
        today = datetime.utcnow().date()
        
        if usage['last_reset'] != today:
            usage['today'] = 0
            usage['last_reset'] = today
        
        return {
            'used_today': usage['today'],
            'daily_limit': key_data.get('daily_limit', 50),
            'remaining': key_data.get('daily_limit', 50) - usage['today']
        }
    return None

# Load Zernio keys on startup
load_zernio_keys()








# ============== BUFFER API CLIENT + KEY MANAGER ==============

BUFFER_API_URL = "https://api.buffer.com"

BUFFER_KEYS = {}          # {key_id_str: key_dict}
BUFFER_KEY_USAGE = {}     # {key_id_str: {'today': int, 'last_reset': date}}
BUFFER_CHANNELS = {}      # {key_id_str: [channel_dict, ...]}


def buffer_graphql(api_key, query, variables=None):
    """
    Send a GraphQL request to Buffer.

    Returns a dict with either:
      - {"data": {...}}      on success
      - {"error": "..."}     on failure
    """
    if not api_key:
        return {"error": "No Buffer API key provided"}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {"query": query, "variables": variables or {}}

    try:
        res = requests.post(BUFFER_API_URL, json=payload, headers=headers, timeout=60)
        json_data = res.json()
    except requests.exceptions.Timeout:
        return {"error": "Buffer API timeout"}
    except requests.exceptions.ConnectionError as e:
        return {"error": f"Buffer connection error: {e}"}
    except Exception as e:
        return {"error": f"Buffer request failed: {e}"}

    if "errors" in json_data:
        messages = "; ".join(
            e.get("message", "Unknown error") for e in json_data["errors"]
        )
        return {"error": messages}

    return {"data": json_data.get("data", {})}


def buffer_get_organizations(api_key):
    """Return the first organization for this Buffer key."""
    result = buffer_graphql(api_key, """
        query {
          account {
            id
            organizations { id name }
          }
        }
    """)
    if "error" in result:
        return None, result["error"]

    orgs = (result["data"].get("account") or {}).get("organizations") or []
    if not orgs:
        return None, "No organizations found for this Buffer key"

    return orgs[0], None


def buffer_fetch_channels(api_key, org_id):
    """Fetch all channels for a Buffer organization."""
    result = buffer_graphql(api_key, """
        query GetChannels($input: ChannelsInput!) {
          channels(input: $input) {
            id
            name
            displayName
            service
            avatar
            isDisconnected
          }
        }
    """, {"input": {"organizationId": org_id}})

    if "error" in result:
        return None, result["error"]

    return result["data"].get("channels") or [], None


def load_buffer_keys():
    """Load all active Buffer keys from the database."""
    global BUFFER_KEYS, BUFFER_KEY_USAGE, BUFFER_CHANNELS

    conn = get_db_connection()
    if not conn:
        return []

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, name, api_key, organization_id, organization_name,
                   daily_limit, usage_count, is_active
            FROM buffer_keys
            WHERE is_active = TRUE
        """)
        keys = cur.fetchall()

        BUFFER_KEYS = {}
        BUFFER_KEY_USAGE = {}
        BUFFER_CHANNELS = {}

        for key in keys:
            kid = str(key["id"])
            BUFFER_KEYS[kid] = dict(key)
            BUFFER_KEY_USAGE[kid] = {
                "today": 0,
                "last_reset": datetime.utcnow().date(),
            }
            BUFFER_CHANNELS[kid] = []

        # Load channels per key
        for kid in BUFFER_KEYS:
            cur.execute("""
                SELECT channel_id, name, display_name, service, avatar, is_disconnected
                FROM buffer_channels
                WHERE buffer_key_id = %s AND is_disconnected = FALSE
            """, (kid,))
            channels = cur.fetchall()
            BUFFER_CHANNELS[kid] = [dict(c) for c in channels]

        cur.close()
        conn.close()
        app.logger.info(f"✅ Loaded {len(keys)} Buffer keys")
        return keys

    except Exception as e:
        app.logger.error(f"Error loading Buffer keys: {e}")
        return []


def get_buffer_key_by_id(key_id):
    return BUFFER_KEYS.get(str(key_id))


def get_buffer_channels_for_key(key_id, service=None):
    """Get channels for a Buffer key, optionally filtered by service (twitter/tiktok)."""
    channels = BUFFER_CHANNELS.get(str(key_id), [])
    if service:
        return [c for c in channels if c.get("service") == service]
    return channels


def increment_buffer_key_usage(key_id):
    kid = str(key_id)
    if kid in BUFFER_KEY_USAGE:
        BUFFER_KEY_USAGE[kid]["today"] += 1

    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                UPDATE buffer_keys
                SET usage_count = usage_count + 1,
                    last_used = NOW(),
                    updated_at = NOW()
                WHERE id = %s
            """, (kid,))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            app.logger.error(f"Error updating Buffer key usage: {e}")


load_buffer_keys()
















def get_direct_video_url_from_service(instagram_url, pipeline_id=None, post_id=None, profile_username=None):
    """Get a direct video URL, handling Render cold starts synchronously."""
    service_root = (IG_VIDEO_URL_GETTER or '').rstrip('/')
    download_endpoint = f"{service_root}/api/download"
    health_endpoint = f"{service_root}/api/health"
    max_attempts = 4
    retry_delays = (5, 10, 20)

    payload = {"url": instagram_url}
    if pipeline_id:
        payload["pipeline_id"] = pipeline_id
    if post_id:
        payload["post_id"] = post_id
    if profile_username:
        payload["profile_username"] = profile_username

    last_error = None
    for attempt in range(max_attempts):
        attempt_no = attempt + 1
        app.logger.info(
            f"📥 [Video {attempt_no}/{max_attempts}] Waking/checking video service: {service_root}"
        )
        try:
            health_response = requests.get(
                health_endpoint, timeout=45,
                headers={"User-Agent": "FetchGram/1.0"}
            )
            app.logger.info(f"💓 Video service health response: {health_response.status_code}")
        except requests.exceptions.Timeout:
            app.logger.warning("⏰ Video health check timed out; trying download API")
        except requests.exceptions.RequestException as e:
            app.logger.warning(f"⚠️ Video health check failed: {e}; trying download API")
        except Exception as e:
            app.logger.warning(f"⚠️ Video health check error: {e}; trying download API")

        try:
            app.logger.info(
                f"📞 [Video {attempt_no}/{max_attempts}] Requesting video URL for {instagram_url[:60]}..."
            )
            response = requests.post(
                download_endpoint,
                json=payload,
                timeout=90,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code in (502, 503, 504):
                last_error = f"HTTP {response.status_code}"
                app.logger.warning(
                    f"⚠️ Video service gateway error {response.status_code}; Render may still be waking up."
                )
            elif response.status_code != 200:
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                app.logger.warning(f"⚠️ Video service returned {response.status_code}: {response.text[:200]}")
            else:
                try:
                    data = response.json()
                except ValueError as e:
                    last_error = f"Invalid JSON response: {e}"
                    app.logger.warning("⚠️ Video service returned invalid JSON")
                else:
                    if data.get('success'):
                        video_data = data.get('data') or {}
                        download_url = (
                            video_data.get('downloadUrl')
                            or video_data.get('directDownloadUrl')
                            or data.get('downloadUrl')
                            or data.get('directDownloadUrl')
                        )
                        if download_url:
                            app.logger.info(f"✅ VIDEO READY before caption step: {download_url[:60]}...")
                            return download_url
                        last_error = "Video service returned success without a download URL"
                        app.logger.warning(f"⚠️ {last_error}")
                    else:
                        last_error = str(data.get('error') or 'Video service returned success=false')
                        app.logger.warning(f"⚠️ Video service error: {last_error}")

        except requests.exceptions.Timeout:
            last_error = "Video service request timed out"
            app.logger.warning(
                f"⏰ [Video {attempt_no}/{max_attempts}] Video request timed out; Render may still be waking up."
            )
        except requests.exceptions.ConnectionError as e:
            last_error = f"Video connection error: {e}"
            app.logger.warning(f"🔌 [Video {attempt_no}/{max_attempts}] Connection error: {e}")
        except requests.exceptions.RequestException as e:
            last_error = f"Video request error: {e}"
            app.logger.warning(f"⚠️ [Video {attempt_no}/{max_attempts}] Request error: {e}")
        except Exception as e:
            last_error = str(e)
            app.logger.error(f"❌ [Video {attempt_no}/{max_attempts}] Unexpected video error: {e}")

        if attempt < max_attempts - 1:
            wait_time = retry_delays[attempt]
            app.logger.info(f"⏳ Video service may be waking up. Waiting {wait_time}s before retry...")
            time.sleep(wait_time)

    app.logger.error(f"❌ VIDEO NOT READY after {max_attempts} attempts. Last error: {last_error}")
    return None








def get_direct_video_url(url, media_id=None, pipeline_id=None, post_id=None, profile_username=None):
    """
    Get a FRESH direct video URL from the video service.

    No cache. Every call hits the video service and returns the URL it
    provides. fdown.vn signed URLs expire within hours, so the only safe
    source is a fresh call.

    Returns None if the service could not produce a URL. The caller is
    expected to retry on the next run rather than publish a dead link.
    """
    video_url = get_direct_video_url_from_service(
        url,
        pipeline_id=pipeline_id,
        post_id=post_id,
        profile_username=profile_username
    )

    if video_url:
        app.logger.info(f"✅ Fresh video URL from service: {video_url[:50]}...")
        return video_url

    app.logger.error(
        f"❌ Video service did not return a URL for: {url[:50]}... "
        f"(no cache fallback configured)"
    )
    return None





def store_video_url_with_context(reel_url, video_url, pipeline_id=None, post_id=None, profile_username=None):
    """
    Store video URL in database with pipeline context for autonomy.
    This ensures the video URL is associated with the correct pipeline and post.
    """
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        
        # 1. Store in reel_cache
        cur.execute("""
            INSERT INTO reel_cache (reel_url, direct_url, caption, created_at)
            VALUES (%s, %s, '', NOW())
            ON CONFLICT (reel_url) DO UPDATE SET 
                direct_url = EXCLUDED.direct_url,
                created_at = NOW()
        """, (reel_url, video_url))
        conn.commit()
        app.logger.info(f"💾 Video URL stored in reel_cache for: {reel_url[:50]}...")
        
        # 2. If we have post_id, update the scheduled_post
        if post_id:
            cur.execute("""
                UPDATE scheduled_posts 
                SET direct_video_url = %s, updated_at = NOW()
                WHERE id = %s AND status IN ('pending', 'processing')
                RETURNING id
            """, (video_url, post_id))
            updated = cur.fetchone()
            if updated:
                app.logger.info(f"✅ Updated scheduled_post {post_id} with video URL")
                
                # Check if we have both video URL and caption
                cur.execute("""
                    SELECT caption FROM scheduled_posts WHERE id = %s
                """, (post_id,))
                result = cur.fetchone()
                if result and result[0]:
                    app.logger.info(f"✅ Caption already exists! Processing post {post_id}...")
                    # Process the post (caption already exists)
                    cur.execute("""
                        SELECT 
                            sp.id as scheduled_id,
                            sp.reel_url,
                            sp.direct_video_url,
                            sp.caption,
                            sp.pipeline_id,
                            p.id as pipeline_id,
                            p.name as pipeline_name,
                            p.profile_username,
                            p.facebook_account_id,
                            p.zernio_key_id
                        FROM scheduled_posts sp
                        JOIN pipelines p ON sp.pipeline_id = p.id
                        WHERE sp.id = %s
                    """, (post_id,))
                    post = cur.fetchone()
                    if post and post['caption']:
                        # IMPORTANT: scheduler owns publishing. Do not start a
                        # second background publisher here; doing so can race the
                        # scheduler and create duplicate Facebook posts.
                        app.logger.info(
                            f"⏸️ Caption/video ready for post {post_id}; scheduler will publish it."
                        )
        
        # 3. If we have pipeline_id but no post_id, update by pipeline
        elif pipeline_id:
            cur.execute("""
                UPDATE scheduled_posts 
                SET direct_video_url = %s, updated_at = NOW()
                WHERE reel_url = %s AND pipeline_id = %s AND status IN ('pending', 'processing')
                RETURNING id
            """, (video_url, reel_url, pipeline_id))
            updated = cur.fetchone()
            if updated:
                app.logger.info(f"✅ Updated scheduled_post for pipeline {pipeline_id} with video URL")
                
                # Check if we have both video URL and caption
                cur.execute("""
                    SELECT 
                        sp.id as scheduled_id,
                        sp.reel_url,
                        sp.direct_video_url,
                        sp.caption,
                        sp.pipeline_id,
                        p.id as pipeline_id,
                        p.name as pipeline_name,
                        p.profile_username,
                        p.facebook_account_id,
                        p.zernio_key_id
                    FROM scheduled_posts sp
                    JOIN pipelines p ON sp.pipeline_id = p.id
                    WHERE sp.reel_url = %s AND sp.pipeline_id = %s AND sp.status = 'pending'
                """, (reel_url, pipeline_id))
                post = cur.fetchone()
                if post and post['caption']:
                    app.logger.info(
                        f"⏸️ Caption exists for {reel_url}; scheduler will publish it."
                    )
        
        # 4. If we have profile_username, try to find the pipeline
        elif profile_username:
            cur.execute("""
                SELECT id FROM pipelines 
                WHERE profile_username = %s AND is_active = TRUE
                LIMIT 1
            """, (profile_username,))
            pipeline = cur.fetchone()
            if pipeline:
                pipeline_id = pipeline[0]
                cur.execute("""
                    UPDATE scheduled_posts 
                    SET direct_video_url = %s, updated_at = NOW()
                    WHERE reel_url = %s AND pipeline_id = %s AND status IN ('pending', 'processing')
                    RETURNING id
                """, (video_url, reel_url, pipeline_id))
                updated = cur.fetchone()
                if updated:
                    app.logger.info(f"✅ Updated scheduled_post for profile @{profile_username} with video URL")
        
        conn.commit()
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        app.logger.error(f"❌ Error storing video URL with context: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
        return False















def get_video_with_captions(reel_url, pipeline_id=None, post_id=None, profile_username=None):
    """
    Get video URL and caption using the Instagram video URL getter service.
    Now supports autonomous pipeline and post tracking.
    """
    try:
        app.logger.info(f"📥 Fetching video from service: {IG_VIDEO_URL_GETTER}")
        app.logger.info(f"   Pipeline ID: {pipeline_id or 'None'}")
        app.logger.info(f"   Post ID: {post_id or 'None'}")
        app.logger.info(f"   Profile: {profile_username or 'None'}")
        
        # Build payload with all identifiers
        payload = {"url": reel_url}
        if pipeline_id:
            payload["pipeline_id"] = pipeline_id
        if post_id:
            payload["post_id"] = post_id
        if profile_username:
            payload["profile_username"] = profile_username
        
        response = requests.post(
            f"{IG_VIDEO_URL_GETTER}/api/download",
            json=payload,
            timeout=60,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                video_data = data.get('data', {})
                download_url = video_data.get('downloadUrl') or video_data.get('directDownloadUrl')
                
                if download_url:
                    caption = video_data.get('caption', '') or ''
                    thumbnail = video_data.get('thumbnail') or video_data.get('thumbnailUrl')
                    
                    app.logger.info(f"✅ Video URL fetched from service")
                    
                    # Store with context
                    if pipeline_id or post_id:
                        store_video_url_with_context(
                            reel_url, 
                            download_url, 
                            pipeline_id=pipeline_id, 
                            post_id=post_id,
                            profile_username=profile_username
                        )
                    
                    return download_url, caption, thumbnail
                else:
                    app.logger.warning(f"⚠️ No download URL in response")
                    return None, None, None
            else:
                app.logger.warning(f"⚠️ Service error: {data.get('error')}")
                return None, None, None
        else:
            app.logger.error(f"❌ Service returned {response.status_code}")
            return None, None, None
            
    except requests.exceptions.Timeout:
        app.logger.error(f"⏰ Service timeout")
        return None, None, None
    except Exception as e:
        app.logger.error(f"❌ Error: {e}")
        return None, None, None


def get_direct_url_with_caption_cache(reel_url, pipeline_id=None, post_id=None, profile_username=None):
    """Get direct URL with caption from cache, with pipeline context."""
    conn = get_db_connection()
    if not conn:
        video_url, caption, _ = get_video_with_captions(
            reel_url, 
            pipeline_id=pipeline_id, 
            post_id=post_id,
            profile_username=profile_username
        )
        return video_url, caption
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT direct_url, caption FROM reel_cache 
            WHERE reel_url = %s AND created_at > NOW() - INTERVAL '7 days'
        """, (reel_url,))
        result = cur.fetchone()
        if result and result[0]:
            app.logger.info(f"✅ Cache hit for: {reel_url[:50]}...")
            return result[0], result[1] or ''
        
        direct_url, caption, _ = get_video_with_captions(
            reel_url,
            pipeline_id=pipeline_id,
            post_id=post_id,
            profile_username=profile_username
        )
        if direct_url:
            cur.execute("""
                INSERT INTO reel_cache (reel_url, direct_url, caption, created_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (reel_url) DO UPDATE SET 
                    direct_url = EXCLUDED.direct_url,
                    caption = EXCLUDED.caption,
                    created_at = NOW()
            """, (reel_url, direct_url, caption or ''))
            conn.commit()
            app.logger.info(f"✅ Cached direct URL and caption for: {reel_url[:50]}...")
        return direct_url, caption
    except Exception as e:
        app.logger.error(f"Error getting cached direct URL: {e}")
        video_url, caption, _ = get_video_with_captions(
            reel_url,
            pipeline_id=pipeline_id,
            post_id=post_id,
            profile_username=profile_username
        )
        return video_url, caption
    finally:
        cur.close()
        conn.close()


def download_video_file(url, media_id=None):
    job_dir = os.path.join('/tmp', f"igdl_{uuid.uuid4().hex[:8]}")
    os.makedirs(job_dir, exist_ok=True)
    outtmpl = os.path.join(job_dir, "%(id)s.%(ext)s")
    opts = base_ydl_opts({"outtmpl": outtmpl})
    if media_id:
        opts["playlist_items"] = None
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise Exception(clean_error(str(e)))
    except Exception as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise Exception("Download failed: " + str(e))
    entries = info.get("entries") if "entries" in info else [info]
    entries = [e for e in entries if e]
    target = None
    if media_id:
        target = next((e for e in entries if e.get("id") == media_id), None)
    if target is None and entries:
        target = entries[0]
    if target is None:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise Exception("No video found to download.")
    filepath = target.get("requested_downloads", [{}])[0].get("filepath") or os.path.join(
        job_dir, f"{target.get('id')}.{target.get('ext', 'mp4')}"
    )
    if not os.path.exists(filepath):
        shutil.rmtree(job_dir, ignore_errors=True)
        raise Exception("File was fetched but couldn't be located.")
    return filepath, job_dir, target


def base_ydl_opts(extra=None):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": "best",
        "nocheckcertificate": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        },
    }

    cookie_file = get_cookie_file()
    if cookie_file and os.path.exists(cookie_file):
        opts["cookiefile"] = cookie_file
        app.logger.info(f"Using cookies from: {cookie_file}")

    if extra:
        opts.update(extra)
    return opts


def clean_error(msg: str) -> str:
    msg = msg.replace("ERROR: ", "").strip()
    if "Private" in msg or "login" in msg.lower():
        return "This post is private or requires login — it can't be downloaded."
    if "Video unavailable" in msg:
        return "The video is unavailable. It may have been removed or is restricted."
    if "rate limited" in msg.lower():
        return "Too many requests. Please wait a moment and try again."
    if "cookies" in msg.lower() or "cookie" in msg.lower():
        return "Authentication required. Please upload your cookies.json file."
    if len(msg) > 160:
        return "Couldn't process that link. Double-check it's a public post and try again."
    return msg


def store_caption_in_database(reel_url, caption, profile_username):
    """Store caption in database for future use."""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO reel_cache (reel_url, direct_url, caption, created_at)
            VALUES (%s, '', %s, NOW())
            ON CONFLICT (reel_url) DO UPDATE SET 
                caption = EXCLUDED.caption,
                created_at = NOW()
        """, (reel_url, caption))
        conn.commit()
        
        if profile_username:
            cur.execute("""
                SELECT id, results FROM scraped_reels 
                WHERE EXISTS (
                    SELECT 1 FROM jsonb_array_elements(results) AS elem
                    WHERE elem->>'username' = %s
                )
                ORDER BY created_at DESC LIMIT 1
            """, (profile_username,))
            result = cur.fetchone()
            if result:
                results = result[1]
                if isinstance(results, str):
                    results = json.loads(results)
                for profile_idx, profile in enumerate(results):
                    if profile.get('username') == profile_username:
                        for reel_idx, reel in enumerate(profile.get('reels', [])):
                            if isinstance(reel, dict) and reel.get('url') == reel_url:
                                results[profile_idx]['reels'][reel_idx]['caption'] = caption
                                break
                        break
                cur.execute("""
                    UPDATE scraped_reels SET results = %s, updated_at = NOW()
                    WHERE id = %s
                """, (json.dumps(results), result[0]))
                conn.commit()
        
        cur.close()
        conn.close()
        app.logger.info(f"💾 Caption stored for: {reel_url[:50]}...")
    except Exception as e:
        app.logger.error(f"Error storing caption: {e}")


# ============== CAPTION SERVICE WITH WAKE-UP MECHANISM ==============

def get_caption_service_url():
    """Get caption service URL from settings."""
    return get_setting('caption_service_url', 'https://copytxt-caption-automation.onrender.com/api/caption')




def fetch_caption_from_service(reel_url, timeout=30, pipeline_id=None,
                                profile_username=None, post_id=None):
    """
    Fetch a Reel caption synchronously from the caption service.

    The caption service returns the caption in the HTTP response, so this
    function waits for that response and never relies on a webhook or
    background thread.
    """
    caption_service_url = get_caption_service_url()
    max_attempts = 4  # initial request + up to 3 retries
    retry_delays = (3, 6, 12)

    # Optional health check to wake a sleeping Render service.
    try:
        health_url = caption_service_url.replace('/api/caption', '/api/health')
        app.logger.info("💤 Pinging caption service health...")
        response = requests.get(
            health_url,
            timeout=10,
            headers={"User-Agent": "FetchGram/1.0"}
        )
        app.logger.info(
            f"✅ Caption service health check returned {response.status_code}"
        )
    except Exception as e:
        app.logger.info(f"⚠️ Health check ignored: {e}")

    last_error = None

    for attempt in range(max_attempts):
        attempt_no = attempt + 1

        try:
            app.logger.info(
                f"📞 [Attempt {attempt_no}/{max_attempts}] Fetching caption "
                f"(timeout={timeout}s) for: {reel_url[:50]}..."
            )

            # IMPORTANT: synchronous request. No async/webhook fields.
            payload = {"url": reel_url}

            response = requests.post(
                caption_service_url,
                json=payload,
                timeout=timeout,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 404:
                app.logger.warning(
                    f"⚠️ [Attempt {attempt_no}] Caption service returned 404; "
                    "not retrying."
                )
                return None

            if response.status_code in (502, 503, 504):
                last_error = f"HTTP {response.status_code}"
                app.logger.warning(
                    f"⚠️ [Attempt {attempt_no}] Gateway error: "
                    f"{response.status_code}"
                )
            elif response.status_code != 200:
                last_error = f"HTTP {response.status_code}"
                app.logger.warning(
                    f"⚠️ [Attempt {attempt_no}] Service returned "
                    f"{response.status_code}: {response.text[:200]}"
                )
            else:
                try:
                    data = response.json()
                except ValueError as e:
                    last_error = f"Invalid JSON response: {e}"
                    app.logger.warning(
                        f"⚠️ [Attempt {attempt_no}] Invalid JSON from caption service"
                    )
                else:
                    if data.get("success") is False:
                        error_msg = str(data.get("error", "Unknown error"))
                        last_error = error_msg
                        app.logger.warning(
                            f"⚠️ [Attempt {attempt_no}] Caption service error: "
                            f"{error_msg}"
                        )
                    else:
                        caption = data.get("caption")
                        if isinstance(caption, str) and caption.strip():
                            source = data.get("source", "unknown")
                            app.logger.info(
                                f"✅ [Attempt {attempt_no}] Got caption "
                                f"({len(caption)} chars, source: {source})"
                            )
                            return caption.strip()

                        last_error = "Caption was empty"
                        app.logger.warning(
                            f"⚠️ [Attempt {attempt_no}] Service returned empty caption"
                        )

        except requests.exceptions.Timeout:
            last_error = f"Timeout after {timeout}s"
            app.logger.warning(
                f"⏰ [Attempt {attempt_no}/{max_attempts}] "
                f"Caption service timed out after {timeout}s"
            )
        except requests.exceptions.ConnectionError as e:
            last_error = f"Connection error: {e}"
            app.logger.warning(
                f"🔌 [Attempt {attempt_no}/{max_attempts}] "
                f"Caption service connection error: {e}"
            )
        except Exception as e:
            last_error = str(e)
            app.logger.error(
                f"❌ [Attempt {attempt_no}/{max_attempts}] "
                f"Caption service error: {e}"
            )

        if attempt < max_attempts - 1:
            wait_time = retry_delays[attempt]
            app.logger.info(
                f"⏳ Waiting {wait_time}s before caption retry..."
            )
            time.sleep(wait_time)

    app.logger.error(
        f"❌ Caption fetch failed after {max_attempts} attempts. "
        f"Last error: {last_error}"
    )
    return None


def cache_direct_url(reel_url, direct_url, caption=''):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO reel_cache (reel_url, direct_url, caption, created_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (reel_url) DO UPDATE SET 
                direct_url = EXCLUDED.direct_url,
                caption = EXCLUDED.caption,
                created_at = NOW()
        """, (reel_url, direct_url, caption))
        conn.commit()
        app.logger.info(f"✅ Cached CDN URL for: {reel_url[:50]}...")
        return True
    except Exception as e:
        app.logger.error(f"Cache error: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def get_direct_url_from_cache_only(reel_url):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute("SELECT direct_url FROM reel_cache WHERE reel_url = %s AND created_at > NOW() - INTERVAL '30 days'", (reel_url,))
        result = cur.fetchone()
        if result and result[0]:
            app.logger.info(f"✅ Cache hit for: {reel_url[:50]}...")
            return result[0]
        return None
    except Exception as e:
        app.logger.error(f"Cache lookup error: {e}")
        return None
    finally:
        cur.close()
        conn.close()











# ============== RANDOM TIME GENERATOR ==============

def generate_random_post_times(num_posts, start_hour=0, end_hour=23):
    """
    Generate random post times spread throughout the ENTIRE day.
    
    Args:
        num_posts: Number of posts to schedule
        start_hour: Earliest hour to post (default: 0 = 12:00 AM)
        end_hour: Latest hour to post (default: 23 = 11:00 PM)
    
    Returns:
        List of random datetime objects
    """
    if num_posts == 0:
        return []
    
    # If only 1 post, pick random time between start and end
    if num_posts == 1:
        random_hour = random.randint(start_hour, end_hour)
        random_minute = random.randint(0, 59)
        random_second = random.randint(0, 59)
        random_time = datetime.utcnow().replace(
            hour=random_hour,
            minute=random_minute,
            second=random_second,
            microsecond=0
        )
        if random_time < datetime.utcnow():
            random_time += timedelta(days=1)
        return [random_time]
    
    # Multiple posts - distribute randomly across the entire day
    total_minutes = (end_hour - start_hour + 1) * 60
    
    # Generate random times ensuring minimum spacing
    min_spacing = 45
    max_attempts = 100
    
    valid_times = []
    for attempt in range(max_attempts):
        minutes = sorted([random.randint(0, total_minutes - 1) for _ in range(num_posts)])
        valid = True
        for i in range(1, len(minutes)):
            if minutes[i] - minutes[i-1] < min_spacing:
                valid = False
                break
        if valid and num_posts > 1:
            if minutes[-1] - minutes[0] < min_spacing * (num_posts - 1):
                valid = False
        if valid:
            valid_times = minutes
            break
    
    if not valid_times:
        spacing = total_minutes // num_posts
        valid_times = [i * spacing + random.randint(-spacing//3, spacing//3) for i in range(num_posts)]
        valid_times = sorted([max(0, min(total_minutes - 1, t)) for t in valid_times])
    
    times = []
    base_time = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    for minute in valid_times:
        hour = minute // 60
        minute_of_hour = minute % 60
        post_time = base_time.replace(
            hour=hour,
            minute=minute_of_hour,
            second=0,
            microsecond=0
        )
        post_time += timedelta(seconds=random.randint(0, 3599))
        while post_time < datetime.utcnow():
            post_time += timedelta(days=1)
        times.append(post_time)
    
    return sorted(times)

# ============== CAPTION FETCH TRACKING ==============
CAPTION_FETCH_STATUS = {}

# ============== CAPTION SERVICE INTEGRATION ==============

# ============== CAPTION SERVICE WITH WAKE-UP MECHANISM ==============




def get_zernio_base_url():
    """Get Zernio base URL from settings."""
    return get_setting('zernio_base_url', 'https://zernio.com/api/v1')

def get_scraper_base_url():
    """Get scraper service URL from settings."""
    return get_setting('scraper_base_url', 'https://ig-reels-scraper.onrender.com')

def fetch_captions_batch(reel_urls):
    if not reel_urls:
        return {}
    try:
        caption_service_url = get_caption_service_url()
        response = requests.post(
            f"{caption_service_url}/batch",
            json={"urls": reel_urls},
            timeout=60,
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                results = {}
                for item in data.get('results', []):
                    if item.get('success'):
                        results[item['url']] = item.get('caption', '')
                return results
        return {}
    except Exception as e:
        app.logger.error(f"Caption service error: {e}")
        return {}


def process_reels_with_captions(reels):
    urls_to_fetch = []
    processed_reels = []
    for reel in reels:
        if isinstance(reel, str):
            urls_to_fetch.append(reel)
            processed_reels.append({"url": reel, "caption": ""})
        elif isinstance(reel, dict):
            url = reel.get('url')
            caption = reel.get('caption', '')
            if url:
                if caption and caption.strip():
                    processed_reels.append(reel)
                else:
                    urls_to_fetch.append(url)
                    processed_reels.append({"url": url, "caption": ""})
            else:
                processed_reels.append(reel)
        else:
            processed_reels.append({"url": str(reel), "caption": ""})
    
    if urls_to_fetch:
        app.logger.info(f"📝 Fetching {len(urls_to_fetch)} captions...")
        captions_map = fetch_captions_batch(urls_to_fetch)
        for reel in processed_reels:
            if reel.get('url') in captions_map:
                reel['caption'] = captions_map[reel['url']] or ''
    return processed_reels

# ============== SYNC STATUS FUNCTIONS ==============

def update_sync_status(username, status, total_reels=0, captions_fetched=0, captions_skipped=0, errors=0, job_id=None):
    conn = get_db_connection()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sync_status (username, status, total_reels, captions_fetched, captions_skipped, errors, job_id, last_updated, started_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (username) DO UPDATE SET
                status = EXCLUDED.status,
                total_reels = EXCLUDED.total_reels,
                captions_fetched = EXCLUDED.captions_fetched,
                captions_skipped = EXCLUDED.captions_skipped,
                errors = EXCLUDED.errors,
                job_id = EXCLUDED.job_id,
                last_updated = NOW(),
                started_at = CASE WHEN sync_status.status = 'idle' OR sync_status.started_at IS NULL THEN NOW() ELSE sync_status.started_at END,
                completed_at = CASE WHEN EXCLUDED.status IN ('completed', 'error', 'partial') THEN NOW() ELSE NULL END
        """, (username, status, total_reels, captions_fetched, captions_skipped, errors, job_id))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        app.logger.error(f"Failed to update sync status: {e}")

def get_sync_status(username):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT username, status, total_reels, captions_fetched, captions_skipped, errors,
                   started_at, completed_at, last_updated, job_id
            FROM sync_status WHERE username = %s
        """, (username,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result
    except Exception as e:
        app.logger.error(f"Failed to get sync status: {e}")
        return None

# ============== BACKGROUND SYNC FUNCTION ==============

def sync_captions_background(username):
    import threading
    job_id = str(uuid.uuid4())
    
    def run_sync():
        with app.app_context():
            try:
                app.logger.info(f"[Job {job_id}] 🔥 Starting sync for @{username}")
                update_sync_status(username, 'syncing', 0, 0, 0, 0, job_id)
                
                conn = get_db_connection()
                if not conn:
                    update_sync_status(username, 'error', 0, 0, 0, 1, job_id)
                    return
                
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("""
                    SELECT id, results FROM scraped_reels 
                    WHERE EXISTS (
                        SELECT 1 FROM jsonb_array_elements(results) AS elem
                        WHERE elem->>'username' = %s
                    )
                    ORDER BY created_at DESC LIMIT 1
                """, (username,))
                
                result = cur.fetchone()
                if not result:
                    app.logger.error(f"[Job {job_id}] No data for @{username}")
                    update_sync_status(username, 'error', 0, 0, 0, 1, job_id)
                    cur.close()
                    conn.close()
                    return
                
                results = result['results']
                total_reels = 0
                captions_fetched = 0
                captions_skipped = 0
                errors = 0
                updated = False
                urls_to_fetch = []
                reel_positions = []
                
                for profile_idx, profile in enumerate(results):
                    if profile.get('username') == username:
                        reels = profile.get('reels', [])
                        total_reels = len(reels)
                        app.logger.info(f"[Job {job_id}] 📹 Found {total_reels} reels for @{username}")
                        update_sync_status(username, 'syncing', total_reels, 0, 0, 0, job_id)
                        
                        for reel_idx, reel in enumerate(reels):
                            if isinstance(reel, dict):
                                reel_url = reel.get('url')
                                existing_caption = reel.get('caption', '')
                                if existing_caption and existing_caption.strip():
                                    captions_skipped += 1
                                    continue
                                if reel_url:
                                    urls_to_fetch.append(reel_url)
                                    reel_positions.append((profile_idx, reel_idx))
                            else:
                                reel_url = str(reel)
                                urls_to_fetch.append(reel_url)
                                reel_positions.append((profile_idx, reel_idx))
                        break
                
                app.logger.info(f"[Job {job_id}] 📤 {len(urls_to_fetch)} URLs need captions")
                
                for idx, (reel_url, (profile_idx, reel_idx)) in enumerate(zip(urls_to_fetch, reel_positions)):
                    try:
                        caption_service_url = get_caption_service_url()
                        app.logger.info(f"[Job {job_id}] 📞 [{idx+1}/{len(urls_to_fetch)}] Calling caption service...")
                        response = requests.post(
                            caption_service_url,
                            json={"url": reel_url},
                            timeout=30,
                            headers={"Content-Type": "application/json"}
                        )
                        if response.status_code == 200:
                            data = response.json()
                            if data.get('success'):
                                caption = data.get('caption', '')
                                if caption:
                                    results[profile_idx]['reels'][reel_idx]['caption'] = caption
                                    captions_fetched += 1
                                    updated = True
                                    app.logger.info(f"[Job {job_id}] ✅ Got caption ({len(caption)} chars)")
                                else:
                                    errors += 1
                            else:
                                errors += 1
                        else:
                            app.logger.error(f"[Job {job_id}] ❌ Service error: {response.status_code}")
                            errors += 1
                    except Exception as e:
                        app.logger.error(f"[Job {job_id}] ❌ Service exception: {e}")
                        errors += 1
                    
                    time.sleep(1)
                    if (captions_fetched + errors) % 2 == 0 or idx == len(urls_to_fetch) - 1:
                        update_sync_status(username, 'syncing', total_reels, captions_fetched, captions_skipped, errors, job_id)
                
                if updated:
                    cur.execute("""
                        UPDATE scraped_reels SET results = %s, updated_at = NOW()
                        WHERE id = %s
                    """, (json.dumps(results), result['id']))
                    conn.commit()
                    app.logger.info(f"[Job {job_id}] 💾 Saved {captions_fetched} captions to database")
                    
                    for profile in results:
                        for reel in profile.get('reels', []):
                            if isinstance(reel, dict):
                                reel_url = reel.get('url')
                                caption = reel.get('caption', '')
                                if reel_url and caption:
                                    cur.execute("""
                                        INSERT INTO reel_cache (reel_url, direct_url, caption, created_at)
                                        VALUES (%s, '', %s, NOW())
                                        ON CONFLICT (reel_url) DO UPDATE SET 
                                            caption = EXCLUDED.caption, created_at = NOW()
                                    """, (reel_url, caption))
                    conn.commit()
                
                final_status = 'completed' if errors == 0 else 'partial'
                update_sync_status(username, final_status, total_reels, captions_fetched, captions_skipped, errors, job_id)
                app.logger.info(f"[Job {job_id}] ✅ Done: {captions_fetched} fetched, {errors} errors")
                
                cur.close()
                conn.close()
            except Exception as e:
                app.logger.error(f"[Job {job_id}] ❌ Error: {e}")
                import traceback
                app.logger.error(traceback.format_exc())
                update_sync_status(username, 'error', 0, 0, 0, 1, job_id)
    
    thread = threading.Thread(target=run_sync)
    thread.daemon = True
    thread.start()
    return job_id

# ============== COOKIE STORAGE FUNCTIONS ==============

def get_user_id():
    user_id = FIXED_USER_ID
    session['user_id'] = user_id
    return user_id

def save_cookies_to_db(cookies_data, username):
    user_id = get_user_id()
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_cookies (user_id, cookie_data, username, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (user_id) DO UPDATE SET 
                cookie_data = EXCLUDED.cookie_data,
                username = EXCLUDED.username,
                updated_at = NOW()
        """, (user_id, json.dumps(cookies_data), username))
        conn.commit()
        app.logger.info(f"Cookies saved to Neon DB for user: {user_id}")
        return True
    except Exception as e:
        app.logger.error(f"Database save error: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_cookies_from_db():
    user_id = get_user_id()
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT cookie_data, username, updated_at FROM user_cookies WHERE user_id = %s", (user_id,))
        result = cur.fetchone()
        if result:
            return {
                'cookie_data': result['cookie_data'],
                'username': result['username'],
                'updated_at': result['updated_at']
            }
        return None
    except Exception as e:
        app.logger.error(f"Database get error: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def clear_cookies_from_db():
    user_id = get_user_id()
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM user_cookies WHERE user_id = %s", (user_id,))
        conn.commit()
        app.logger.info(f"Cookies cleared from Neon DB for user: {user_id}")
        return True
    except Exception as e:
        app.logger.error(f"Database clear error: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_existing_reel_urls(username):
    conn = get_db_connection()
    if not conn:
        return set()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT results FROM scraped_reels 
            WHERE EXISTS (
                SELECT 1 FROM jsonb_array_elements(results) AS elem
                WHERE elem->>'username' = %s
            )
            ORDER BY created_at DESC LIMIT 1
        """, (username,))
        result = cur.fetchone()
        if not result:
            return set()
        results = result[0]
        existing_urls = set()
        for profile in results:
            if profile.get('username') == username:
                reels = profile.get('reels', [])
                for reel in reels:
                    if isinstance(reel, dict):
                        url = reel.get('url')
                        if url:
                            existing_urls.add(url)
                    elif isinstance(reel, str):
                        existing_urls.add(reel)
                break
        return existing_urls
    except Exception as e:
        app.logger.error(f"Error getting existing URLs: {e}")
        return set()
    finally:
        cur.close()
        conn.close()

# ============== ENCRYPTION FUNCTIONS ==============

def get_encryption_key():
    env_key = os.environ.get('ENCRYPTION_KEY')
    if env_key:
        try:
            return base64.urlsafe_b64decode(env_key)
        except Exception:
            return env_key.encode() if isinstance(env_key, str) else env_key

    key_file = os.path.join('/tmp', 'encryption_key.key')
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            return f.read()

    salt = b'fetchgram_salt_2024_v2'
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(app.secret_key.encode()))
    try:
        with open(key_file, 'wb') as f:
            f.write(key)
    except Exception:
        pass
    return key

def encrypt_credentials(identifier, password):
    try:
        key = get_encryption_key()
        f = Fernet(key)

        if isinstance(password, str) and password.startswith('['):
            try:
                data = json.loads(password)
                data_dict = {'type': 'cookies', 'data': data, 'timestamp': time.time()}
            except Exception:
                data_dict = {'type': 'credentials', 'identifier': identifier, 'password': password, 'timestamp': time.time()}
        elif isinstance(password, (list, dict)):
            data_dict = {'type': 'cookies', 'data': password, 'timestamp': time.time()}
        else:
            data_dict = {'type': 'credentials', 'identifier': identifier, 'password': password, 'timestamp': time.time()}

        encrypted = f.encrypt(json.dumps(data_dict).encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    except Exception as e:
        app.logger.error(f"Encryption failed: {e}")
        return None

def decrypt_credentials(encrypted_data):
    try:
        key = get_encryption_key()
        f = Fernet(key)
        decoded = base64.urlsafe_b64decode(encrypted_data)
        decrypted = f.decrypt(decoded)
        data = json.loads(decrypted)

        if time.time() - data.get('timestamp', 0) > 30 * 24 * 60 * 60:
            return None

        if data.get('type') == 'cookies':
            return data.get('data', []), 'cookies'
        else:
            return data.get('identifier'), data.get('password')
    except Exception as e:
        app.logger.error(f"Decryption failed: {e}")
        return None

def write_netscape_cookies(cookie_data, filepath):
    with open(filepath, 'w') as f:
        f.write("# Netscape HTTP Cookie File\n")
        for cookie in cookie_data:
            if not isinstance(cookie, dict):
                continue
            domain = cookie.get('domain', '')
            flag = 'TRUE' if cookie.get('hostOnly') is not True else 'FALSE'
            path = cookie.get('path', '/')
            secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'
            expiry = cookie.get('expirationDate')
            if expiry is None:
                expiry = cookie.get('expiry', 0)
            try:
                expiry = str(int(expiry) if expiry else 0)
            except (TypeError, ValueError):
                expiry = '0'
            name = cookie.get('name', '')
            value = cookie.get('value', '')
            if not name or not domain:
                continue
            f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")

# ============== IG URL HELPERS ==============

IG_URL_RE = re.compile(r"^https?://(www\.)?instagram\.com/", re.IGNORECASE)

def is_valid_instagram_url(url: str) -> bool:
    return bool(url) and bool(IG_URL_RE.match(url.strip()))

# ============== YT-DLP FUNCTIONS ==============

def get_cookie_file():
    """Get cookie file with automatic retry from Render service"""
    # Try to get cookies from database first
    db_cookies = get_cookies_from_db()
    if db_cookies:
        cookie_data = db_cookies.get('cookie_data', [])
        if cookie_data:
            # Check if cookies have sessionid
            has_session = any(c.get('name') == 'sessionid' for c in cookie_data)
            if has_session:
                username = db_cookies.get('username', 'default')
                safe_user = re.sub(r'[^a-zA-Z0-9_-]', '_', str(username))[:40]
                cookie_file = os.path.join('/tmp', f'instagram_cookies_{safe_user}.txt')
                # ✅ Always write fresh file
                write_netscape_cookies(cookie_data, cookie_file)
                app.logger.info(f"Using cookies from database → {cookie_file}")
                return cookie_file
    
    # Try environment variable cookies
    cookies_json_env = os.environ.get('COOKIES_JSON')
    if cookies_json_env:
        try:
            cookies_data = json.loads(cookies_json_env)
            cookie_file = os.path.join('/tmp', 'cookies_netscape.txt')
            write_netscape_cookies(cookies_data, cookie_file)
            return cookie_file
        except Exception as e:
            app.logger.error(f"Failed to parse COOKIES_JSON: {e}")
    
    # Try local cookies.json file
    if os.path.exists('cookies.json'):
        try:
            with open('cookies.json', 'r') as f:
                cookies_data = json.load(f)
            cookie_file = os.path.join('/tmp', 'cookies_netscape.txt')
            write_netscape_cookies(cookies_data, cookie_file)
            return cookie_file
        except Exception as e:
            app.logger.error(f"Failed to load cookies.json: {e}")
    
    # No cookies found, try to extract from Render service
    app.logger.info("🔄 No cookies found, attempting to extract from Render service...")
    if extract_cookies_from_render_service():
        # Try again after extraction
        db_cookies = get_cookies_from_db()
        if db_cookies:
            cookie_data = db_cookies.get('cookie_data', [])
            if cookie_data:
                username = db_cookies.get('username', 'default')
                safe_user = re.sub(r'[^a-zA-Z0-9_-]', '_', str(username))[:40]
                cookie_file = os.path.join('/tmp', f'instagram_cookies_{safe_user}.txt')
                write_netscape_cookies(cookie_data, cookie_file)
                app.logger.info(f"✅ Using cookies from database after extraction → {cookie_file}")
                return cookie_file
    
    return None






# ============== COOKIE EXTRACTION FROM RENDER SERVICE ==============

def extract_cookies_from_render_service():
    """Call the Render cookie extractor service to get fresh cookies"""
    try:
        app.logger.info(f"🍪 Calling Render cookie extractor service at {COOKIE_EXTRACTOR_URL}...")
        
        response = requests.post(
            f"{COOKIE_EXTRACTOR_URL}/api/extract",
            timeout=30,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code != 200:
            app.logger.error(f"❌ Render service returned {response.status_code}")
            return False
        
        data = response.json()
        
        if not data.get('success'):
            app.logger.error(f"❌ Render service failed: {data.get('error')}")
            return False
        
        cookies = data.get('cookies', [])
        if not cookies:
            app.logger.error("❌ No cookies returned from service")
            return False
        
        # Save to database
        username = None
        for cookie in cookies:
            if cookie.get('name') == 'ds_user_id':
                username = cookie.get('value')
                break
        
        success = save_cookies_to_db(cookies, username or 'Instagram User')
        if not success:
            app.logger.error("❌ Failed to save cookies to database")
            return False
        
        # ✅ FIX: Write BOTH formats - JSON and Netscape
        try:
            # JSON format
            cookie_file_path = os.path.join('/tmp', 'cookies.json')
            with open(cookie_file_path, 'w') as f:
                json.dump(cookies, f, indent=2)
            app.logger.info(f"✅ Saved cookies to {cookie_file_path}")
            
            # ✅ Netscape format for yt-dlp
            netscape_file = os.path.join('/tmp', 'cookies_netscape.txt')
            write_netscape_cookies(cookies, netscape_file)
            app.logger.info(f"✅ Saved Netscape cookies to {netscape_file}")
            
            # ✅ Also update the Instagram-specific cookie file
            safe_user = re.sub(r'[^a-zA-Z0-9_-]', '_', str(username or 'default'))[:40]
            instagram_cookie_file = os.path.join('/tmp', f'instagram_cookies_{safe_user}.txt')
            write_netscape_cookies(cookies, instagram_cookie_file)
            app.logger.info(f"✅ Saved Instagram cookies to {instagram_cookie_file}")
            
        except Exception as e:
            app.logger.warning(f"⚠️ Could not save cookies to file: {e}")
        
        app.logger.info(f"✅ Extracted {len(cookies)} cookies from Render service")
        return True
        
    except requests.exceptions.Timeout:
        app.logger.error("❌ Render service timeout")
        return False
    except requests.exceptions.ConnectionError:
        app.logger.error("❌ Render service connection error")
        return False
    except Exception as e:
        app.logger.error(f"❌ Error: {e}")
        return False






# ============== BROWSERLESS REFRESH FUNCTIONS ==============

BROWSERLESS_TOKEN = os.environ.get('BROWSERLESS_API_KEY', '2V9phNVcUGlxvJJ9154e14b2c71b8c81d6e0f2f23bcfaf323')
BROWSERLESS_ORIGIN = 'https://production-sfo.browserless.io'
BROWSERLESS_PROFILE = os.environ.get('BROWSERLESS_PROFILE', 'instagram-login')

def refresh_browserless_profile():
    """
    Refresh the Browserless profile by calling the Render service.
    The Render service handles the Browserless refresh with the correct payload.
    """
    app.logger.info("🔄 Refreshing Browserless profile via Render service...")
    
    try:
        # ✅ Call the Render service's /api/refresh endpoint
        # The Render service already knows the correct payload format
        response = requests.post(
            f"{COOKIE_EXTRACTOR_URL}/api/refresh",
            timeout=60,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                app.logger.info("✅ Browserless profile refreshed successfully via Render service")
                
                # Get cookies from the response and save them
                cookies = data.get('cookies', [])
                if cookies:
                    username = None
                    for cookie in cookies:
                        if cookie.get('name') == 'ds_user_id':
                            username = cookie.get('value')
                            break
                    
                    save_cookies_to_db(cookies, username or 'Instagram User')
                    write_netscape_cookies(cookies, '/tmp/cookies_netscape.txt')
                    
                    cookie_file_path = os.path.join('/tmp', 'cookies.json')
                    with open(cookie_file_path, 'w') as f:
                        json.dump(cookies, f, indent=2)
                    
                    app.logger.info(f"✅ Saved {len(cookies)} cookies after refresh")
                
                return {
                    "success": True,
                    "message": data.get('message', 'Profile refreshed successfully'),
                    "cookies": cookies,
                    "cookies_count": len(cookies)
                }
            else:
                error_msg = data.get('error', 'Unknown error')
                app.logger.error(f"❌ Render service refresh failed: {error_msg}")
                return {"success": False, "error": error_msg}
        else:
            app.logger.error(f"❌ Render service returned {response.status_code}")
            return {"success": False, "error": f"Render service returned {response.status_code}"}
            
    except requests.exceptions.Timeout:
        app.logger.error("❌ Render service timeout")
        return {"success": False, "error": "Render service timeout"}
    except requests.exceptions.ConnectionError:
        app.logger.error("❌ Render service connection error")
        return {"success": False, "error": "Render service connection error"}
    except Exception as e:
        app.logger.error(f"❌ Refresh error: {e}")
        return {"success": False, "error": str(e)}


def create_browserless_profile(cookies):
    """
    Create a new Browserless profile with the provided cookies.
    """
    try:
        create_url = f"{BROWSERLESS_ORIGIN}/profile/create?token={BROWSERLESS_TOKEN}"
        
        formatted_cookies = []
        for cookie in cookies:
            formatted_cookies.append({
                "name": cookie.get('name', ''),
                "value": cookie.get('value', ''),
                "domain": cookie.get('domain', '.instagram.com'),
                "path": cookie.get('path', '/'),
                "expires": cookie.get('expirationDate', -1),
                "httpOnly": cookie.get('httpOnly', False),
                "secure": cookie.get('secure', False),
                "session": cookie.get('session', True)
            })
        
        create_payload = {
            "name": BROWSERLESS_PROFILE,
            "state": {
                "cookies": formatted_cookies
            }
        }
        
        response = requests.post(
            create_url,
            json=create_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200 or response.status_code == 201:
            app.logger.info(f"✅ Browserless profile created: {BROWSERLESS_PROFILE}")
            return {
                "success": True,
                "message": f"Profile '{BROWSERLESS_PROFILE}' created with {len(cookies)} cookies"
            }
        else:
            app.logger.error(f"❌ Profile creation failed: {response.status_code}")
            return {"success": False, "error": f"Profile creation failed: {response.status_code}"}
            
    except Exception as e:
        app.logger.error(f"❌ Profile creation error: {e}")
        return {"success": False, "error": str(e)}











# ============== BLUESKY FUNCTIONS ==============

def create_bluesky_session(identifier, password):
    try:
        response = requests.post(
            "https://bsky.social/xrpc/com.atproto.server.createSession",
            json={"identifier": identifier, "password": password},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to authenticate with Bluesky: {str(e)}")

def upload_bluesky_blob(session_data, file_data, mime_type):
    try:
        response = requests.post(
            "https://bsky.social/xrpc/com.atproto.repo.uploadBlob",
            headers={
                "Authorization": f"Bearer {session_data['accessJwt']}",
                "Content-Type": mime_type
            },
            data=file_data,
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to upload blob to Bluesky: {str(e)}")

def upload_video_to_bluesky(session_data, video_url, text, thumbnail_url=None):
    try:
        app.logger.info(f"Downloading video from: {video_url}")
        video_response = requests.get(video_url, stream=True, timeout=120)
        video_response.raise_for_status()
        content_type = video_response.headers.get("content-type", "video/mp4")
        if not content_type.startswith("video/"):
            content_type = "video/mp4"
        app.logger.info("Uploading video to Bluesky...")
        blob_response = upload_bluesky_blob(session_data, video_response.content, content_type)
        did = session_data["did"]
        record = {
            "$type": "app.bsky.feed.post",
            "text": text or "Instagram video",
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "embed": {
                "$type": "app.bsky.embed.video",
                "video": blob_response["blob"],
                "aspectRatio": {"width": 720, "height": 1280}
            }
        }
        app.logger.info("Creating Bluesky post...")
        response = requests.post(
            "https://bsky.social/xrpc/com.atproto.repo.createRecord",
            json={"repo": did, "collection": "app.bsky.feed.post", "record": record},
            headers={"Authorization": f"Bearer {session_data['accessJwt']}"},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise Exception(f"Failed to upload video to Bluesky: {str(e)}")

def post_to_bluesky(video_url, text, thumbnail_url=None, identifier=None, password=None):
    try:
        if not identifier or not password:
            encrypted = session.get('bluesky_encrypted')
            if encrypted:
                decrypted = decrypt_credentials(encrypted)
                if decrypted:
                    identifier, password = decrypted
            if not identifier or not password:
                identifier = session.get('bluesky_identifier')
                password = session.get('bluesky_password')
        if not identifier or not password:
            raise Exception("Bluesky credentials not configured.")
        session_data = create_bluesky_session(identifier, password)
        result = upload_video_to_bluesky(session_data, video_url, text, thumbnail_url)
        uri_parts = result.get("uri", "").split("/")
        post_id = uri_parts[-1] if uri_parts else ""
        return {"success": True, "post_uri": result.get("uri"), "post_cid": result.get("cid"), "post_id": post_id, "message": "Video posted to Bluesky successfully!"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ============== ZERNIO (FACEBOOK) INTEGRATION ==============

def publish_to_facebook(video_url, text, account_id, publish_now=True, scheduled_time=None, key_id=None):
    """
    Publish to Facebook using a specific Zernio key or the best available.

    Returns a dict with one of these shapes:
      - Success:         {"post": {...}, "already_posted": False}
      - Already posted:  {"post": {"_id": <existingPostId>, ...}, "already_posted": True}
      - Failure:         {"error": "...", "status_code": <int>}
    """
    # Get the key to use
    zernio_base_url = get_zernio_base_url()

    if key_id and str(key_id) in ZERNIO_KEYS:
        key = ZERNIO_KEYS[str(key_id)]
    else:
        key = get_best_zernio_key()

    if not key:
        return {"error": "No available Zernio keys with remaining capacity"}

    app.logger.info(f"📤 Using Zernio key: {key['name']}")

    headers = {
        "Authorization": f"Bearer {key['api_key']}",
        "Content-Type": "application/json"
    }

    payload = {
        "content": text,
        "platforms": [
            {
                "platform": "facebook",
                "accountId": account_id or key['facebook_account_id']
            }
        ],
        "mediaItems": [
            {
                "type": "video",
                "url": video_url
            }
        ]
    }

    if publish_now:
        payload["publishNow"] = True
    elif scheduled_time:
        payload["scheduledFor"] = scheduled_time
        payload["timezone"] = "UTC"

    try:
        response = requests.post(
            f"{zernio_base_url}/posts",
            headers=headers,
            json=payload,
            timeout=120
        )

        # Increment usage (a request was made regardless of outcome)
        increment_key_usage(key['id'])

        # ---------- Happy path ----------
        if response.status_code in (200, 201):
            data = response.json()
            data.setdefault("already_posted", False)
            return data

        # ---------- Non-2xx: inspect the body for idempotency signals ----------
        try:
            err_body = response.json()
        except ValueError:
            err_body = {}

        err_text = (err_body.get("error") or response.text or "").lower()
        details = err_body.get("details") or {}
        existing_post_id = details.get("existingPostId")
        existing_post_url = (
            details.get("existingPostUrl")
            or details.get("publishedUrl")
        )

        # Zernio returns this when the same content was already
        # scheduled / publishing / posted to this account in the last 24h.
        is_duplicate = (
            bool(existing_post_id)
            or "already scheduled" in err_text
            or "already posted" in err_text
            or "within the last 24 hours" in err_text
        )

        if is_duplicate:
            app.logger.info(
                f"♻️ Facebook publish skipped — content already exists "
                f"(existingPostId={existing_post_id})"
            )
            return {
                "already_posted": True,
                "post": {
                    "_id": existing_post_id,
                    "platforms": [
                        {
                            "platform": "facebook",
                            "publishedUrl": existing_post_url
                        }
                    ]
                },
                "error": None
            }

        # ---------- Genuine hard failure ----------
        app.logger.warning(
            f"⚠️ Facebook publish hard failure "
            f"(status={response.status_code}): {response.text[:200]}"
        )
        return {"error": response.text, "status_code": response.status_code}

    except Exception as e:
        return {"error": str(e)}
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
# ============== BUFFER — TWITTER PUBLISHER ==============

def publish_to_twitter(video_url, text, channel_id, key_id, thumbnail_offset=1000):
    """
    Publish a tweet with a video via Buffer GraphQL.

    Returns:
        Success:        {"post": {...}, "already_posted": False, "external_url": "..."}
        Hard failure:   {"error": "...", "status_code": int}
    """
    key = get_buffer_key_by_id(key_id)
    if not key:
        return {"error": f"Buffer key {key_id} not found"}

    query = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post { id text status dueAt shareMode externalLink }
        }
        ... on MutationError { message }
      }
    }
    """

    variables = {
        "input": {
            "channelId": channel_id,
            "text": text[:280],  # Twitter hard limit
            "schedulingType": "automatic",
            "mode": "shareNow",
            "assets": [
                {
                    "video": {
                        "url": video_url,
                        "metadata": {"thumbnailOffset": int(thumbnail_offset or 1000)},
                    }
                }
            ],
        }
    }

    result = buffer_graphql(key["api_key"], query, variables)

    if "error" in result:
        app.logger.error(f"❌ Twitter publish error: {result['error']}")
        return {"error": result["error"], "status_code": 500}

    create_result = result["data"].get("createPost") or {}

    # Typed error
    if create_result.get("message"):
        msg = create_result["message"]
        # Detect the "duplicate" idempotency pattern
        is_dup = "already" in msg.lower() or "duplicate" in msg.lower()
        if is_dup:
            app.logger.info(f"♻️ Twitter dedup detected: {msg}")
            return {
                "already_posted": True,
                "post": {"_id": None, "platforms": [{"platform": "twitter", "publishedUrl": None}]},
                "external_url": None,
                "error": None,
            }
        app.logger.error(f"❌ Twitter MutationError: {msg}")
        return {"error": msg, "status_code": 400}

    post = create_result.get("post")
    if not post:
        return {"error": "Buffer returned no post object", "status_code": 500}

    increment_buffer_key_usage(key_id)

    return {
        "already_posted": False,
        "post": post,
        "external_url": post.get("externalLink"),
        "error": None,
    }


# ============== BUFFER — TIKTOK PUBLISHER ==============

def publish_to_tiktok(video_url, text, channel_id, key_id, thumbnail_offset=1000):
    """
    Publish a TikTok video via Buffer GraphQL.

    TikTok requires a video asset; text-only posts are not supported.
    The caption limit for TikTok is 2200 characters, but Buffer enforces
    its own limits per channel, so we let Buffer validate.
    """
    key = get_buffer_key_by_id(key_id)
    if not key:
        return {"error": f"Buffer key {key_id} not found"}

    query = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post { id text status dueAt shareMode externalLink }
        }
        ... on MutationError { message }
      }
    }
    """

    variables = {
        "input": {
            "channelId": channel_id,
            "text": text[:2200],  # TikTok caption limit
            "schedulingType": "automatic",
            "mode": "shareNow",
            "assets": [
                {
                    "video": {
                        "url": video_url,
                        "metadata": {"thumbnailOffset": int(thumbnail_offset or 1000)},
                    }
                }
            ],
        }
    }

    result = buffer_graphql(key["api_key"], query, variables)

    if "error" in result:
        app.logger.error(f"❌ TikTok publish error: {result['error']}")
        return {"error": result["error"], "status_code": 500}

    create_result = result["data"].get("createPost") or {}

    if create_result.get("message"):
        msg = create_result["message"]
        is_dup = "already" in msg.lower() or "duplicate" in msg.lower()
        if is_dup:
            app.logger.info(f"♻️ TikTok dedup detected: {msg}")
            return {
                "already_posted": True,
                "post": {"_id": None, "platforms": [{"platform": "tiktok", "publishedUrl": None}]},
                "external_url": None,
                "error": None,
            }
        app.logger.error(f"❌ TikTok MutationError: {msg}")
        return {"error": msg, "status_code": 400}

    post = create_result.get("post")
    if not post:
        return {"error": "Buffer returned no post object", "status_code": 500}

    increment_buffer_key_usage(key_id)

    return {
        "already_posted": False,
        "post": post,
        "external_url": post.get("externalLink"),
        "error": None,
    }
    
    
    
    
    
    
# ============== PLATFORM DISPATCHER ==============

def dispatch_publish(pipeline, video_url, caption, scheduled_post_id=None):
    """
    Route a publish request to the correct platform publisher.

    The `pipeline` dict must be a row from the pipelines table (or a dict
    with the same keys). Required keys depend on the platform:

      Facebook:  facebook_account_id, zernio_key_id
      Twitter:   buffer_channel_id,   buffer_key_id
      TikTok:    buffer_channel_id,   buffer_key_id

    Returns the same dict shape as publish_to_facebook:
      Success:         {"post": {...}, "already_posted": bool, "external_url": str|None}
      Hard failure:    {"error": "...", "status_code": int}
    """
    platform = (pipeline.get("platform") or "facebook").lower()

    app.logger.info(
        f"🚏 dispatch_publish → platform={platform} "
        f"(post_id={scheduled_post_id})"
    )

    # ---------- FACEBOOK (Zernio) ----------
    if platform == "facebook":
        account_id = pipeline.get("facebook_account_id")
        if not account_id:
            return {
                "error": "Missing facebook_account_id on pipeline",
                "status_code": 400,
            }
        return publish_to_facebook(
            video_url=video_url,
            text=caption,
            account_id=account_id,
            publish_now=True,
            key_id=pipeline.get("zernio_key_id"),
        )

    # ---------- TWITTER / X (Buffer) ----------
    if platform == "twitter":
        channel_id = pipeline.get("buffer_channel_id")
        key_id = pipeline.get("buffer_key_id")
        if not channel_id or not key_id:
            return {
                "error": (
                    "Missing buffer_channel_id or buffer_key_id on pipeline "
                    "for twitter platform"
                ),
                "status_code": 400,
            }
        return publish_to_twitter(
            video_url=video_url,
            text=caption,
            channel_id=channel_id,
            key_id=key_id,
        )

    # ---------- TIKTOK (Buffer) ----------
    if platform == "tiktok":
        channel_id = pipeline.get("buffer_channel_id")
        key_id = pipeline.get("buffer_key_id")
        if not channel_id or not key_id:
            return {
                "error": (
                    "Missing buffer_channel_id or buffer_key_id on pipeline "
                    "for tiktok platform"
                ),
                "status_code": 400,
            }
        return publish_to_tiktok(
            video_url=video_url,
            text=caption,
            channel_id=channel_id,
            key_id=key_id,
        )

    # ---------- UNKNOWN ----------
    return {
        "error": f"Unsupported platform: {platform}",
        "status_code": 400,
    }
    
    
    
    
    
    
    
    
    
    

def publish_video_to_all_accounts(video_url, text, publish_now=True, scheduled_time=None):
    results = {}
    try:
        zernio_base_url = get_zernio_base_url()
        
        # First, get the key to use
        key = get_best_zernio_key()
        if not key:
            return {"error": "No available Zernio keys"}
        
        headers = {
            "Authorization": f"Bearer {key['api_key']}",
            "Content-Type": "application/json"
        }
        response = requests.get(f"{zernio_base_url}/accounts", headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            accounts = data.get('accounts', [])
            for account in accounts:
                if account.get('platform') == 'facebook':
                    account_id = account.get('_id')
                    account_name = account.get('displayName', 'Unknown')
                    result = publish_to_facebook(
                        video_url=video_url,
                        text=text,
                        account_id=account_id,
                        publish_now=publish_now,
                        scheduled_time=scheduled_time,
                        key_id=key['id']
                    )
                    results[account_id] = {"account_name": account_name, "result": result}
    except Exception as e:
        app.logger.error(f"Error getting Zernio accounts: {e}")
    return results

# ============== DUAL REQUEST CAPTION FETCH ==============




def get_caption_fetch_status(reel_url):
    status = CAPTION_FETCH_STATUS.get(reel_url)
    if status:
        return status
    return {'status': 'not_found', 'message': 'No caption fetch job found for this URL'}

# ============== PENDING POST FUNCTIONS (KEPT FOR BACKWARD COMPATIBILITY) ==============

def create_pending_post(reel_url, direct_video_url, pipeline_id, profile_username, facebook_account_id):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO pending_posts (
                reel_url, direct_video_url, pipeline_id, 
                profile_username, facebook_account_id, status
            )
            VALUES (%s, %s, %s, %s, %s, 'pending')
            ON CONFLICT (reel_url) DO UPDATE SET
                direct_video_url = EXCLUDED.direct_video_url,
                status = 'pending',
                updated_at = NOW()
            RETURNING id
        """, (reel_url, direct_video_url, pipeline_id, profile_username, facebook_account_id))
        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        app.logger.info(f"📝 Created pending post for: {reel_url[:50]}...")
        return result[0] if result else None
    except Exception as e:
        app.logger.error(f"Failed to create pending post: {e}")
        return None

def get_pending_post(reel_url):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT * FROM pending_posts 
            WHERE reel_url = %s AND status IN ('pending', 'processing')
            ORDER BY created_at DESC LIMIT 1
        """, (reel_url,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result
    except Exception as e:
        app.logger.error(f"Failed to get pending post: {e}")
        return None

def update_pending_post_status(post_id, status, error_message=None, facebook_post_id=None, facebook_post_url=None):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE pending_posts 
            SET status = %s,
                attempts = attempts + 1,
                error_message = COALESCE(%s, error_message),
                facebook_post_id = COALESCE(%s, facebook_post_id),
                facebook_post_url = COALESCE(%s, facebook_post_url),
                updated_at = NOW()
            WHERE id = %s
        """, (status, error_message, facebook_post_id, facebook_post_url, post_id))
        conn.commit()
        cur.close()
        conn.close()
        app.logger.info(f"📝 Updated pending post {post_id} status to: {status}")
        return True
    except Exception as e:
        app.logger.error(f"Failed to update pending post: {e}")
        return False

def process_pending_post(post):
    try:
        app.logger.info(f"📤 Processing pending post for: {post['reel_url'][:50]}...")
        update_pending_post_status(post['id'], 'processing')

        caption = get_caption_for_reel(
            post['reel_url'], post['profile_username'], post['pipeline_id']
        )
        if not caption or not caption.strip():
            app.logger.error(f"❌ No caption available for: {post['reel_url'][:50]}...")
            update_pending_post_status(post['id'], 'failed', 'No caption available')
            return False

        # Get the pipeline's zernio_key_id if set
        conn = get_db_connection()
        key_id = None
        if conn:
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT zernio_key_id FROM pipelines WHERE id = %s",
                    (post['pipeline_id'],)
                )
                result = cur.fetchone()
                if result and result[0]:
                    key_id = result[0]
                cur.close()
                conn.close()
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass

        result = publish_to_facebook(
            video_url=post['direct_video_url'],
            text=caption,
            account_id=post['facebook_account_id'],
            publish_now=True,
            key_id=key_id
        )

        # ---------- Success or idempotent "already posted" ----------
        if result and not result.get('error'):
            already_posted = result.get('already_posted', False)

            post_id = result.get('post', {}).get('_id') or result.get('post_id')
            post_url = None
            for platform in result.get('post', {}).get('platforms', []):
                if platform.get('platform') == 'facebook':
                    post_url = platform.get('publishedUrl')
                    break

            mark_reel_as_posted(
                pipeline_id=post['pipeline_id'],
                reel_url=post['reel_url'],
                direct_video_url=post['direct_video_url'],
                caption=caption,
                facebook_post_id=post_id,
                facebook_post_url=post_url,
                status='success',
                error_message='Already posted (dedup)' if already_posted else None
            )
            update_pipeline_stats(post['pipeline_id'], 0, 0)
            update_pending_post_status(post['id'], 'completed', None, post_id, post_url)

            if already_posted:
                app.logger.info(
                    f"♻️ Pending post already existed on Facebook "
                    f"(existingPostId={post_id}): {post['reel_url'][:50]}..."
                )
            else:
                app.logger.info(
                    f"✅ Pending post completed and stats updated: "
                    f"{post['reel_url'][:50]}..."
                )
            return True

        # ---------- Genuine failure ----------
        error_msg = result.get('error', 'Unknown error') if result else 'Unknown error'
        update_pending_post_status(post['id'], 'failed', str(error_msg))
        mark_reel_as_posted(
            pipeline_id=post['pipeline_id'],
            reel_url=post['reel_url'],
            direct_video_url=post['direct_video_url'],
            caption=caption if caption else '',
            status='failed',
            error_message=str(error_msg)
        )
        update_pipeline_stats(post['pipeline_id'], 0, 0)
        app.logger.error(
            f"❌ Pending post failed: {post['reel_url'][:50]}... - {error_msg}"
        )
        return False

    except Exception as e:
        app.logger.error(f"❌ Error processing pending post: {e}")
        update_pending_post_status(post['id'], 'failed', str(e))
        try:
            mark_reel_as_posted(
                pipeline_id=post['pipeline_id'],
                reel_url=post['reel_url'],
                direct_video_url=post['direct_video_url'],
                caption='',
                status='failed',
                error_message=str(e)
            )
            update_pipeline_stats(post['pipeline_id'], 0, 0)
        except Exception:
            pass
        return False
    
    
    
    
    
    
    
    
    
    
def get_caption_for_reel(reel_url, profile_username, pipeline_id, max_retries=3):
    """
    Get a Reel caption.

    Order:
      1. scraped_reels
      2. posted_reels
      3. reel_cache
      4. synchronous caption service

    Database connections are closed before the network request so a slow
    caption service cannot hold a database connection open.
    """
    # 1. Check scraped_reels.
    conn = get_db_connection()
    if conn:
        cur = None
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT results
                FROM scraped_reels
                WHERE EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(results) AS elem
                    WHERE elem->>'username' = %s
                )
                ORDER BY created_at DESC
                LIMIT 1
            """, (profile_username,))

            result = cur.fetchone()
            if result:
                results = result[0]
                if isinstance(results, str):
                    results = json.loads(results)

                if isinstance(results, list):
                    for profile in results:
                        if not isinstance(profile, dict):
                            continue
                        if profile.get('username') != profile_username:
                            continue

                        for reel in profile.get('reels', []):
                            if (
                                isinstance(reel, dict)
                                and reel.get('url') == reel_url
                            ):
                                caption = reel.get('caption', '')
                                if isinstance(caption, str) and caption.strip():
                                    app.logger.info(
                                        "✅ Found caption in scraped_reels"
                                    )
                                    return caption.strip()
                                break
                        break
        except Exception as e:
            app.logger.warning(
                f"⚠️ scraped_reels caption lookup failed: {e}"
            )
        finally:
            if cur is not None:
                try:
                    cur.close()
                except Exception:
                    pass
            try:
                conn.close()
            except Exception:
                pass

    # 2. Check posted_reels.
    conn = get_db_connection()
    if conn:
        cur = None
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT caption
                FROM posted_reels
                WHERE pipeline_id = %s AND reel_url = %s
                LIMIT 1
                """,
                (pipeline_id, reel_url)
            )
            result = cur.fetchone()
            if result and isinstance(result[0], str) and result[0].strip():
                app.logger.info("✅ Found caption in posted_reels")
                return result[0].strip()
        except Exception as e:
            app.logger.warning(
                f"⚠️ posted_reels caption lookup failed: {e}"
            )
        finally:
            if cur is not None:
                try:
                    cur.close()
                except Exception:
                    pass
            try:
                conn.close()
            except Exception:
                pass

    # 3. Check reel_cache.
    conn = get_db_connection()
    if conn:
        cur = None
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT caption
                FROM reel_cache
                WHERE reel_url = %s
                LIMIT 1
                """,
                (reel_url,)
            )
            result = cur.fetchone()
            if result and isinstance(result[0], str) and result[0].strip():
                app.logger.info("✅ Found caption in reel_cache")
                return result[0].strip()
        except Exception as e:
            app.logger.warning(
                f"⚠️ reel_cache caption lookup failed: {e}"
            )
        finally:
            if cur is not None:
                try:
                    cur.close()
                except Exception:
                    pass
            try:
                conn.close()
            except Exception:
                pass

    # 4. Database has no caption. The database connections above are already
    # closed before making the network request.
    app.logger.info(
        "🔥 Caption not in DB - fetching from caption service..."
    )

    caption = fetch_caption_from_service(
        reel_url=reel_url,
        timeout=60,
        pipeline_id=pipeline_id,
        profile_username=profile_username
    )

    if caption and caption.strip():
        store_caption_in_database(
            reel_url,
            caption.strip(),
            profile_username
        )
        app.logger.info(
            f"✅ Caption fetched from service and stored "
            f"({len(caption.strip())} chars)"
        )
        return caption.strip()

    app.logger.warning(
        f"❌ No caption returned by caption service for: "
        f"{reel_url[:50]}..."
    )
    return None






# ============== PIPELINE FUNCTIONS ==============

def get_unposted_reels(profile_username, pipeline_id, limit=10):
    """Get ALL unposted reels for a profile (with whatever captions they have)."""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT results FROM scraped_reels 
            WHERE EXISTS (
                SELECT 1 FROM jsonb_array_elements(results) AS elem
                WHERE elem->>'username' = %s
            )
            ORDER BY created_at DESC LIMIT 1
        """, (profile_username,))
        
        result = cur.fetchone()
        if not result:
            return []
        
        results = result[0]
        profile_reels = []
        for item in results:
            if item.get('username') == profile_username:
                profile_reels = item.get('reels', [])
                break
        
        cur.execute("SELECT reel_url FROM posted_reels WHERE pipeline_id = %s", (pipeline_id,))
        posted_urls = {row[0] for row in cur.fetchall()}
        
        unposted = []
        for reel in profile_reels:
            if isinstance(reel, str):
                if reel not in posted_urls:
                    unposted.append({"url": reel, "caption": ""})
            elif isinstance(reel, dict):
                reel_url = reel.get('url')
                if reel_url and reel_url not in posted_urls:
                    unposted.append({
                        "url": reel_url,
                        "caption": reel.get('caption', '')
                    })
            else:
                reel_url = str(reel)
                if reel_url not in posted_urls:
                    unposted.append({"url": reel_url, "caption": ""})
        
        return unposted[:limit]
        
    except Exception as e:
        app.logger.error(f"Error getting unposted reels: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def mark_reel_as_posted(pipeline_id, reel_url, direct_video_url=None, caption=None, 
                        facebook_post_id=None, facebook_post_url=None, 
                        status='success', error_message=None):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO posted_reels (
                pipeline_id, reel_url, direct_video_url, caption,
                facebook_post_id, facebook_post_url, status, error_message
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (pipeline_id, reel_url) DO UPDATE SET
                direct_video_url = EXCLUDED.direct_video_url,
                caption = EXCLUDED.caption,
                facebook_post_id = EXCLUDED.facebook_post_id,
                facebook_post_url = EXCLUDED.facebook_post_url,
                status = EXCLUDED.status,
                error_message = EXCLUDED.error_message,
                posted_at = NOW()
        """, (pipeline_id, reel_url, direct_video_url, caption, 
              facebook_post_id, facebook_post_url, status, error_message))
        if status == 'success':
            cur.execute("SELECT COUNT(*) FROM posted_reels WHERE pipeline_id = %s AND status = 'success'", (pipeline_id,))
            total_posted = cur.fetchone()[0]
            cur.execute("""
                UPDATE pipelines SET total_posted = %s, last_run = NOW(), updated_at = NOW()
                WHERE id = %s
            """, (total_posted, pipeline_id))
            app.logger.info(f"📊 Updated pipeline {pipeline_id} total_posted to: {total_posted}")
        conn.commit()
        app.logger.info(f"✅ Marked reel as posted: {reel_url[:50]}... (status: {status})")
        return True
    except Exception as e:
        app.logger.error(f"Error marking reel as posted: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def update_pipeline_stats(pipeline_id, posted_count, failed_count):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM posted_reels WHERE pipeline_id = %s AND status = 'success'", (pipeline_id,))
        total_posted = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM posted_reels WHERE pipeline_id = %s AND status = 'failed'", (pipeline_id,))
        total_failed = cur.fetchone()[0]
        cur.execute("""
            UPDATE pipelines SET total_posted = %s, last_run = NOW(), updated_at = NOW()
            WHERE id = %s
        """, (total_posted, pipeline_id))
        conn.commit()
        app.logger.info(f"📊 Pipeline {pipeline_id} stats synced: {total_posted} posted, {total_failed} failed")
        return True
    except Exception as e:
        app.logger.error(f"Error updating pipeline stats: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def log_pipeline_run(pipeline_id, posted_count, failed_count, status='completed', error_message=None):
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO pipeline_runs (pipeline_id, reels_posted, reels_failed, status, error_message)
            VALUES (%s, %s, %s, %s, %s)
        """, (pipeline_id, posted_count, failed_count, status, error_message))
        conn.commit()
        return True
    except Exception as e:
        app.logger.error(f"Error logging pipeline run: {e}")
        return False
    finally:
        cur.close()
        conn.close()



# ============== UPDATED RUN_PIPELINE - PURE SCHEDULING ==============











































# ============== DUPLICATE-PUBLISH PROTECTION ==============

PROCESSING_TIMEOUT_MINUTES = int(os.environ.get('POST_PROCESSING_TIMEOUT_MINUTES', '60'))


def _post_lock_key(pipeline_id, reel_url):
    """Return a stable PostgreSQL advisory-lock key for one pipeline/reel."""
    return f"{pipeline_id}:{reel_url}"[:2000]


def claim_scheduled_post(post_id):
    """
    Atomically claim one scheduled post.

    Only a row currently in pending state can be claimed. This prevents two
    scheduler requests/workers from both publishing the same scheduled row.
    """
    conn = get_db_connection()
    if not conn:
        return None
    cur = None
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            UPDATE scheduled_posts
            SET status = 'processing', updated_at = NOW(), error_message = NULL
            WHERE id = %s
              AND status = 'pending'
              AND scheduled_time <= NOW()
            RETURNING *
        """, (post_id,))
        row = cur.fetchone()
        conn.commit()
        if row:
            app.logger.info(f"🔒 CLAIMED scheduled post {post_id}")
        else:
            app.logger.info(f"⏭️ Post {post_id} was already claimed/handled")
        return row
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        app.logger.error(f"❌ Failed to claim scheduled post {post_id}: {e}")
        return None
    finally:
        if cur:
            cur.close()
        conn.close()


def claim_due_posts(limit=5, pipeline_id=None):
    """
    Atomically claim due pending posts using PostgreSQL row locks.

    FOR UPDATE SKIP LOCKED makes concurrent scheduler requests safe.
    """
    conn = get_db_connection()
    if not conn:
        return []
    cur = None
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        if pipeline_id:
            cur.execute("""
                SELECT * FROM scheduled_posts
                WHERE pipeline_id = %s
                  AND status = 'pending'
                  AND scheduled_time <= NOW()
                ORDER BY scheduled_time ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            """, (pipeline_id, limit))
        else:
            cur.execute("""
                SELECT * FROM scheduled_posts
                WHERE status = 'pending'
                  AND scheduled_time <= NOW()
                ORDER BY scheduled_time ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            """, (limit,))

        posts = cur.fetchall()
        if not posts:
            conn.commit()
            return []

        ids = [post['id'] for post in posts]
        cur.execute("""
            UPDATE scheduled_posts
            SET status = 'processing', updated_at = NOW(), error_message = NULL
            WHERE id = ANY(%s::uuid[])
            RETURNING *
        """, (ids,))
        claimed = cur.fetchall()
        conn.commit()
        app.logger.info(f"🔒 Atomically claimed {len(claimed)} scheduled post(s)")
        return claimed
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        app.logger.error(f"❌ Failed to claim due posts: {e}")
        return []
    finally:
        if cur:
            cur.close()
        conn.close()


def mark_processing_post_retryable(post_id, error_message=None):
    """Return a processing post to pending so a later scheduler run can retry."""
    conn = get_db_connection()
    if not conn:
        return False
    cur = None
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE scheduled_posts
            SET status = 'pending',
                error_message = %s,
                updated_at = NOW()
            WHERE id = %s AND status = 'processing'
        """, (error_message, post_id))
        conn.commit()
        return cur.rowcount == 1
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        app.logger.error(f"❌ Failed returning post {post_id} to pending: {e}")
        return False
    finally:
        if cur:
            cur.close()
        conn.close()


def recover_stale_processing_posts():
    """
    Recover jobs left in processing after a crash/restart.
    The timeout is intentionally conservative so an active long-running post
    is not immediately released.
    """
    conn = get_db_connection()
    if not conn:
        return 0
    cur = None
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE scheduled_posts
            SET status = 'pending',
                error_message = 'Recovered stale processing job',
                updated_at = NOW()
            WHERE status = 'processing'
              AND updated_at < NOW() - (%s * INTERVAL '1 minute')
              AND scheduled_time <= NOW()
        """, (PROCESSING_TIMEOUT_MINUTES,))
        recovered = cur.rowcount
        conn.commit()
        if recovered:
            app.logger.warning(f"♻️ Recovered {recovered} stale processing post(s)")
        return recovered
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        app.logger.error(f"❌ Failed recovering stale posts: {e}")
        return 0
    finally:
        if cur:
            cur.close()
        conn.close()


def get_successfully_posted(pipeline_id, reel_url):
    """Return existing posted_reels record for this exact pipeline/reel."""
    conn = get_db_connection()
    if not conn:
        return None
    cur = None
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT * FROM posted_reels
            WHERE pipeline_id = %s
              AND reel_url = %s
              AND status = 'success'
            LIMIT 1
        """, (pipeline_id, reel_url))
        return cur.fetchone()
    except Exception as e:
        app.logger.error(f"❌ Posted lookup failed: {e}")
        return None
    finally:
        if cur:
            cur.close()
        conn.close()


def finalize_duplicate_scheduled_post(post_id, message='Duplicate prevented — reel already posted'):
    """Mark a scheduled row as posted without publishing it again."""
    conn = get_db_connection()
    if not conn:
        return False
    cur = None
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE scheduled_posts
            SET status = 'posted',
                posted_at = COALESCE(posted_at, NOW()),
                error_message = %s,
                updated_at = NOW()
            WHERE id = %s
              AND status = 'processing'
        """, (message, post_id))
        conn.commit()
        return cur.rowcount == 1
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        app.logger.error(f"❌ Failed finalizing duplicate post {post_id}: {e}")
        return False
    finally:
        if cur:
            cur.close()
        conn.close()


def set_scheduled_post_status(post_id, status, error_message=None):
    """Internal DB helper for scheduler workers. Do not call the Flask route directly."""
    conn = get_db_connection()
    if not conn:
        return False
    cur = None
    try:
        cur = conn.cursor()
        if status == 'posted':
            cur.execute("""
                UPDATE scheduled_posts
                SET status = %s,
                    posted_at = COALESCE(posted_at, NOW()),
                    error_message = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (status, error_message, post_id))
        else:
            cur.execute("""
                UPDATE scheduled_posts
                SET status = %s,
                    error_message = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (status, error_message, post_id))
        changed = cur.rowcount == 1
        conn.commit()
        if changed:
            app.logger.info(f"📝 Scheduled post {post_id} -> {status}")
        else:
            app.logger.warning(f"⚠️ Scheduled post {post_id} not found while setting status={status}")
        return changed
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        app.logger.error(f"❌ Failed setting scheduled post {post_id} -> {status}: {e}")
        return False
    finally:
        if cur:
            cur.close()
        conn.close()


# ============== UPDATED RUN_PIPELINE - WITH PIPELINE & POST TRACKING ==============

def acquire_global_publisher_lock():
    """Acquire a session-level advisory lock used to serialize external Facebook publishes."""
    conn = get_db_connection()
    if not conn:
        return None, None, False
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s, 0))",
            ("facebook-global-publisher-lock",)
        )
        acquired = bool(cur.fetchone()[0])
        if not acquired:
            cur.close()
            conn.close()
            return None, None, False
        return conn, cur, True
    except Exception as e:
        app.logger.error(f"❌ Failed acquiring global publisher lock: {e}")
        try:
            if cur: cur.close()
        except Exception: pass
        try: conn.close()
        except Exception: pass
        return None, None, False


def release_global_publisher_lock(conn, cur):
    if not conn:
        return
    try:
        if cur:
            cur.execute(
                "SELECT pg_advisory_unlock(hashtextextended(%s, 0))",
                ("facebook-global-publisher-lock",)
            )
            conn.commit()
    except Exception as e:
        app.logger.warning(f"⚠️ Failed releasing global publisher lock: {e}")
    finally:
        try:
            if cur: cur.close()
        except Exception: pass
        try: conn.close()
        except Exception: pass


def run_pipeline(pipeline_id):
    """Run due posts strictly one-at-a-time with DB claim + duplicate protection."""
    recover_stale_processing_posts()

    conn = get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}
    cur = None
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM pipelines WHERE id = %s", (pipeline_id,))
        pipeline = cur.fetchone()
    finally:
        if cur:
            cur.close()
        conn.close()

    if not pipeline:
        return {"error": "Pipeline not found"}
    if not pipeline['is_active']:
        return {"error": "Pipeline is inactive"}

    due_posts = claim_due_posts(limit=5, pipeline_id=pipeline_id)
    if not due_posts:
        log_pipeline_run(pipeline_id, 0, 0, 'completed')
        return {"message": "No due posts", "posted": 0, "failed": 0, "total": 0}

    posted_count = 0
    failed_count = 0

    # ← CHANGED: show which platform this pipeline publishes to
    pipeline_platform = (pipeline.get('platform') or 'facebook').lower()

    for claimed in due_posts:
        scheduled_post_id = claimed['id']
        reel_url = claimed.get('reel_url')
        if not reel_url:
            set_scheduled_post_status(scheduled_post_id, 'failed', 'Missing reel URL')
            failed_count += 1
            continue

        # DB-level advisory lock protects against different scheduled rows for
        # the same reel being published concurrently.
        lock_conn = get_db_connection()
        lock_cur = None
        lock_acquired = False
        if not lock_conn:
            app.logger.error(f"❌ Could not acquire DB lock connection for post {scheduled_post_id}")
            mark_processing_post_retryable(
                scheduled_post_id,
                'Database connection unavailable while acquiring duplicate lock'
            )
            failed_count += 1
            continue
        try:
            lock_cur = lock_conn.cursor()
            lock_cur.execute(
                "SELECT pg_try_advisory_lock(hashtextextended(%s, 0))",
                (_post_lock_key(pipeline_id, reel_url),)
            )
            lock_acquired = bool(lock_cur.fetchone()[0])

            if not lock_acquired:
                app.logger.warning(
                    f"⏭️ Duplicate lock busy; returning post {scheduled_post_id} to pending"
                )
                mark_processing_post_retryable(
                    scheduled_post_id,
                    'Another worker is processing this reel'
                )
                continue

            # Check again after acquiring the lock. This catches duplicate
            # scheduled rows that have different scheduled_post IDs.
            existing = get_successfully_posted(pipeline_id, reel_url)
            if existing:
                # ← CHANGED: message no longer says "Facebook" specifically
                app.logger.warning(
                    f"♻️ DUPLICATE BLOCKED before {pipeline_platform} publish: {reel_url[:70]}..."
                )
                finalize_duplicate_scheduled_post(
                    scheduled_post_id,
                    f"Duplicate prevented; existing {pipeline_platform} post "
                    f"{existing.get('facebook_post_id') or 'already exists'}"
                )
                posted_count += 1
                continue

            try:
                # ← CHANGED: log shows the correct platform
                app.logger.info(
                    f"\n{'=' * 70}\n"
                    f"🎬 PIPELINE {pipeline_id} | PLATFORM {pipeline_platform.upper()} "
                    f"| POST {scheduled_post_id}\n"
                    f"🔒 CLAIMED + LOCKED\n"
                    f"1️⃣ VIDEO FIRST (fresh): {reel_url[:70]}\n"
                    f"{'=' * 70}"
                )

                direct_video_url = get_direct_video_url(
                    reel_url,
                    pipeline_id=pipeline_id,
                    post_id=scheduled_post_id,
                    profile_username=pipeline.get('profile_username')
                )

                if not direct_video_url:
                    app.logger.warning(
                        f"🛑 VIDEO NOT READY for {reel_url[:60]} — retrying later"
                    )
                    mark_processing_post_retryable(
                        scheduled_post_id,
                        'Video URL not ready; retry on next scheduler run'
                    )
                    continue

                update_conn = get_db_connection()
                if update_conn:
                    update_cur = None
                    try:
                        update_cur = update_conn.cursor()
                        update_cur.execute("""
                            UPDATE scheduled_posts
                            SET direct_video_url = %s, updated_at = NOW()
                            WHERE id = %s AND status = 'processing'
                        """, (direct_video_url, scheduled_post_id))
                        update_conn.commit()
                    except Exception as e:
                        update_conn.rollback()
                        app.logger.warning(f"⚠️ Failed saving video URL: {e}")
                    finally:
                        if update_cur:
                            update_cur.close()
                        update_conn.close()

                caption = claimed.get('caption') or ''
                if not caption.strip():
                    caption = get_caption_for_reel(
                        reel_url=reel_url,
                        profile_username=pipeline.get('profile_username'),
                        pipeline_id=pipeline_id
                    )

                if not caption or not caption.strip():
                    app.logger.warning(
                        f"🛑 CAPTION NOT READY for {reel_url[:60]} — retrying later"
                    )
                    mark_processing_post_retryable(
                        scheduled_post_id,
                        'Caption not ready; retry on next scheduler run'
                    )
                    continue

                caption = caption.strip()

                caption_conn = get_db_connection()
                if caption_conn:
                    caption_cur = None
                    try:
                        caption_cur = caption_conn.cursor()
                        caption_cur.execute("""
                            UPDATE scheduled_posts
                            SET caption = %s, direct_video_url = %s, updated_at = NOW()
                            WHERE id = %s AND status = 'processing'
                        """, (caption, direct_video_url, scheduled_post_id))
                        caption_conn.commit()
                    except Exception as e:
                        caption_conn.rollback()
                        app.logger.warning(f"⚠️ Failed saving caption: {e}")
                    finally:
                        if caption_cur:
                            caption_cur.close()
                        caption_conn.close()

                # Final duplicate check immediately before external publish.
                existing = get_successfully_posted(pipeline_id, reel_url)
                if existing:
                    # ← CHANGED: message no longer says "Facebook" specifically
                    app.logger.warning(
                        f"♻️ DUPLICATE BLOCKED immediately before {pipeline_platform} publish: "
                        f"{reel_url[:70]}..."
                    )
                    finalize_duplicate_scheduled_post(
                        scheduled_post_id,
                        f"Duplicate prevented; existing {pipeline_platform} post "
                        f"{existing.get('facebook_post_id') or 'already exists'}"
                    )
                    posted_count += 1
                    continue

                # ← CHANGED: log uses the pipeline's platform
                app.logger.info(f"3️⃣ {pipeline_platform.upper()} — acquiring global publisher lock")
                publish_lock_conn, publish_lock_cur, publish_lock_acquired = acquire_global_publisher_lock()
                if not publish_lock_acquired:
                    app.logger.info("⏳ Another post is currently being published; returning this post to pending")
                    mark_processing_post_retryable(
                        scheduled_post_id,
                        'Another publish is currently in progress'
                    )
                    continue

                try:
                    # ← CHANGED: dispatch to the correct publisher based on platform
                    app.logger.info(f"3️⃣ {pipeline_platform.upper()} — publishing exactly once")
                    result = dispatch_publish(
                        pipeline=pipeline,
                        video_url=direct_video_url,
                        caption=caption,
                        scheduled_post_id=scheduled_post_id
                    )
                finally:
                    release_global_publisher_lock(publish_lock_conn, publish_lock_cur)

                if result and not result.get('error'):
                    already_posted = result.get('already_posted', False)

                    # ← CHANGED: handles both Facebook (post._id) and
                    # Buffer (post.id) response shapes, and both URL fields
                    # (platforms[].publishedUrl for FB, external_url for Buffer).
                    post_result_id = (
                        result.get('post', {}).get('_id')
                        or result.get('post', {}).get('id')
                        or result.get('post_id')
                    )

                    post_url = result.get('external_url')  # Buffer returns this
                    if not post_url:
                        # Facebook shape
                        for platform in result.get('post', {}).get('platforms', []):
                            if platform.get('platform') == 'facebook':
                                post_url = platform.get('publishedUrl')
                                break

                    mark_reel_as_posted(
                        pipeline_id=pipeline_id,
                        reel_url=reel_url,
                        direct_video_url=direct_video_url,
                        caption=caption,
                        facebook_post_id=post_result_id,
                        facebook_post_url=post_url,
                        status='success',
                        error_message='Already posted (dedup)' if already_posted else None
                    )
                    set_scheduled_post_status(scheduled_post_id, 'posted')
                    posted_count += 1

                    app.logger.info(
                        f"{'♻️ DEDUPLICATED' if already_posted else '🎉 POSTED'} "
                        f"to {pipeline_platform}: {reel_url[:70]}..."
                    )
                else:
                    error_msg = result.get('error', 'Unknown error') if result else 'Unknown error'
                    # ← CHANGED: log shows the correct platform
                    app.logger.error(f"❌ {pipeline_platform} publish failed: {error_msg}")
                    mark_reel_as_posted(
                        pipeline_id=pipeline_id,
                        reel_url=reel_url,
                        direct_video_url=direct_video_url,
                        caption=caption,
                        status='failed',
                        error_message=str(error_msg)
                    )
                    set_scheduled_post_status(scheduled_post_id, 'failed', str(error_msg))
                    failed_count += 1

            except Exception as e:
                app.logger.error(f"❌ Error processing scheduled post {scheduled_post_id}: {e}")
                app.logger.exception(e)
                # A failed worker should be retryable unless the row was already
                # finalized by another safe path.
                mark_processing_post_retryable(scheduled_post_id, str(e))
                failed_count += 1

        finally:
            if lock_acquired and lock_cur:
                try:
                    lock_cur.execute(
                        "SELECT pg_advisory_unlock(hashtextextended(%s, 0))",
                        (_post_lock_key(pipeline_id, reel_url),)
                    )
                    lock_conn.commit()
                except Exception as e:
                    app.logger.warning(f"⚠️ Failed releasing duplicate lock: {e}")
            if lock_cur:
                lock_cur.close()
            lock_conn.close()

    try:
        update_pipeline_stats(pipeline_id, 0, 0)
    except Exception as e:
        app.logger.warning(f"⚠️ Failed updating pipeline stats: {e}")

    run_status = 'completed' if failed_count == 0 else 'partial'
    log_pipeline_run(pipeline_id, posted_count, failed_count, run_status)
    return {
        "message": "Pipeline completed with atomic claiming and duplicate protection",
        "posted": posted_count,
        "failed": failed_count,
        "total": len(due_posts)
    }


def run_all_active_pipelines():
    """
    Process due posts for ALL active pipelines.
    Like scheduler/process but for all pipelines.
    """
    conn = get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, name, profile_username FROM pipelines WHERE is_active = TRUE")
        pipelines = cur.fetchall()
        cur.close()
        
        app.logger.info(f"🔄 Running all active pipelines: {len(pipelines)} found")
        
        results = []
        total_posted = 0
        total_failed = 0
        
        for pipeline in pipelines:
            app.logger.info(f"📋 Processing pipeline: {pipeline['name']} (@{pipeline['profile_username']})")
            result = run_pipeline(pipeline['id'])
            results.append({
                "pipeline_id": pipeline['id'],
                "pipeline_name": pipeline['name'],
                "profile_username": pipeline['profile_username'],
                "result": result
            })
            if result.get('posted'):
                total_posted += result['posted']
            if result.get('failed'):
                total_failed += result['failed']
        
        app.logger.info(f"✅ All pipelines processed: {total_posted} posted, {total_failed} failed")
        
        return {
            "message": f"Processed {total_posted} due posts, {total_failed} failed across {len(pipelines)} pipelines",
            "total_posted": total_posted,
            "total_failed": total_failed,
            "total_pipelines": len(pipelines),
            "results": results
        }
    except Exception as e:
        app.logger.error(f"Error running all pipelines: {e}")
        return {"error": str(e)}
    finally:
        conn.close()


# ============== ROUTES ==============

@app.route("/")
def index():
    return render_template("index.html")

# ============== COOKIE ROUTES ==============

@app.route("/api/cookies/upload", methods=["POST"])
def upload_cookies():
    if 'cookies_file' not in request.files:
        return jsonify({"error": "No file uploaded", "status": "error"}), 400
    file = request.files['cookies_file']
    if file.filename == '':
        return jsonify({"error": "No file selected", "status": "error"}), 400
    if not file.filename.endswith('.json'):
        return jsonify({"error": "File must be a JSON file", "status": "error"}), 400
    try:
        content = file.read().decode('utf-8')
        cookies_data = json.loads(content)
        if not isinstance(cookies_data, list):
            return jsonify({"error": "Invalid cookie format - expected an array", "status": "error"}), 400
        has_session = any(isinstance(c, dict) and c.get('name') in ('sessionid', 'ds_user_id') for c in cookies_data)
        if not has_session:
            return jsonify({"error": "No session cookies found. Make sure you're logged into Instagram.", "status": "error"}), 400
        username = None
        for cookie in cookies_data:
            if isinstance(cookie, dict) and cookie.get('name') == 'ds_user':
                username = cookie.get('value')
                break
            if isinstance(cookie, dict) and cookie.get('name') == 'sessionid':
                value = cookie.get('value', '')
                if '%3A' in value:
                    username = value.split('%3A')[0]
                elif ':' in value:
                    username = value.split(':')[0]
                break
        user_id = get_user_id()
        success = save_cookies_to_db(cookies_data, username or 'Instagram User')
        if not success:
            return jsonify({"error": "Failed to save cookies to database", "status": "error"}), 500
        session['instagram_username'] = username or 'Instagram User'
        session['instagram_saved'] = True
        response = jsonify({"status": "success", "message": "Cookies uploaded and saved to database!", "username": username or 'Instagram User'})
        response.set_cookie('user_id', user_id, max_age=30*24*60*60, path='/', secure=os.environ.get('FLASK_ENV') == 'production' or bool(os.environ.get('VERCEL')), httponly=True, samesite='Lax')
        return response
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON file", "status": "error"}), 400
    except Exception as e:
        app.logger.error(f"Cookie upload error: {e}")
        return jsonify({"error": f"Failed to process cookies: {str(e)}", "status": "error"}), 500

@app.route("/api/instagram/cookies_status", methods=["GET"])
def instagram_cookies_status():
    db_cookies = get_cookies_from_db()
    if db_cookies:
        return jsonify({"status": "success", "has_cookies": True, "username": db_cookies.get('username', 'Instagram User'), "message": "Cookies are saved in database"})
    return jsonify({"status": "success", "has_cookies": False, "message": "No saved cookies found"})

@app.route("/api/cookies/clear", methods=["POST"])
def clear_cookies():
    clear_cookies_from_db()
    session.pop('instagram_username', None)
    session.pop('instagram_saved', None)
    for file in ['cookies_netscape.txt', 'instagram_cookies_persistent.txt']:
        path = os.path.join('/tmp', file)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
    return jsonify({"status": "success", "message": "Cookies cleared successfully"})

# ============== SCRAPE PROXY ==============

@app.route("/api/scrape/proxy", methods=["POST"])
def scrape_proxy():
    data = request.get_json(silent=True) or {}
    usernames = data.get("usernames", [])
    max_reels = data.get("maxReels", 50)
    fetch_captions = data.get("fetch_captions", True)
    
    app.logger.info(f"📝 Scraping usernames: {usernames}")
    app.logger.info(f"📝 Max reels: {max_reels}")
    
    cookies = None
    db_cookies = get_cookies_from_db()
    
    if db_cookies:
        cookies = db_cookies.get('cookie_data', [])
        app.logger.info(f"Proxy: Retrieved {len(cookies)} cookies from Neon DB")
        # Check if cookies have sessionid
        has_session = any(c.get('name') == 'sessionid' for c in cookies)
        if has_session:
            app.logger.info("✅ Cookies have valid sessionid")
        else:
            app.logger.warning("⚠️ Cookies found but no sessionid - may be invalid")
            cookies = None  # Force re-extraction
    
    # ✅ If no valid cookies in DB, try to extract from Render service
    if not cookies:
        app.logger.info("🔄 No valid cookies found. Attempting to extract from Render service...")
        
        try:
            extraction_success = extract_cookies_from_render_service()
            
            if extraction_success:
                # Try again after extraction
                db_cookies = get_cookies_from_db()
                if db_cookies:
                    cookies = db_cookies.get('cookie_data', [])
                    app.logger.info(f"✅ Retrieved {len(cookies)} cookies after extraction")
                    
                    # Verify sessionid exists
                    has_session = any(c.get('name') == 'sessionid' for c in cookies)
                    if has_session:
                        app.logger.info("✅ Extraction successful - valid cookies obtained")
                    else:
                        app.logger.warning("⚠️ Extraction returned cookies but no sessionid")
                        cookies = None
            else:
                app.logger.warning("⚠️ Failed to extract cookies from Render service")
        except Exception as e:
            app.logger.error(f"❌ Extraction error: {e}")
    
    # Try environment variable as final fallback
    if not cookies:
        cookies_json_env = os.environ.get('COOKIES_JSON')
        if cookies_json_env:
            try:
                cookies = json.loads(cookies_json_env)
                app.logger.info(f"Proxy: Retrieved {len(cookies)} cookies from env")
                has_session = any(c.get('name') == 'sessionid' for c in cookies)
                if not has_session:
                    app.logger.warning("⚠️ Environment cookies have no sessionid")
                    cookies = None
            except:
                pass
    
    if not cookies:
        return jsonify({
            "status": "error", 
            "error": "No Instagram cookies found. Please click 'Extract from Browserless' button first.",
            "requires_cookies": True
        }), 400
    
    # ✅ Verify cookies have sessionid before proceeding
    has_session = any(c.get('name') == 'sessionid' for c in cookies)
    if not has_session:
        return jsonify({
            "status": "error",
            "error": "Invalid cookies - no sessionid found. Please re-extract.",
            "requires_cookies": True
        }), 400
    
    data['cookies'] = cookies
    
    try:
        existing_urls = {}
        for username in usernames:
            existing_urls[username] = get_existing_reel_urls(username)
            app.logger.info(f"📊 @{username}: {len(existing_urls[username])} existing reels")
        
        scraper_base_url = get_scraper_base_url()
        response = requests.post(
            f'{scraper_base_url}/api/scrape/start', 
            json=data, 
            headers={'Content-Type': 'application/json'}, 
            timeout=60
        )
        app.logger.info(f"Proxy: Render responded with status {response.status_code}")
        
        if response.status_code == 200:
            result_data = response.json()
            results = result_data.get('results', [])
            new_results = []
            total_new_reels = 0
            
            for profile in results:
                username = profile.get('username')
                if not username:
                    continue
                existing = existing_urls.get(username, set())
                reels = profile.get('reels', [])
                new_reels = []
                
                for reel in reels:
                    if isinstance(reel, str):
                        if reel not in existing:
                            new_reels.append(reel)
                            existing.add(reel)
                    elif isinstance(reel, dict):
                        url = reel.get('url')
                        if url and url not in existing:
                            new_reels.append(reel)
                            existing.add(url)
                
                if new_reels:
                    profile['reels'] = new_reels
                    new_results.append(profile)
                    total_new_reels += len(new_reels)
                    app.logger.info(f"✅ @{username}: {len(new_reels)} new reels found")
                else:
                    app.logger.info(f"ℹ️ @{username}: No new reels found")
            
            if new_results:
                with app.test_request_context():
                    store_scraped_data()
                    app.logger.info(f"✅ Stored {total_new_reels} new reels for {len(new_results)} profiles")
                
                if fetch_captions:
                    app.logger.info(f"📝 Auto-fetching captions for {total_new_reels} new reels...")
                    all_reel_urls = []
                    for profile in new_results:
                        reels = profile.get('reels', [])
                        for reel in reels:
                            if isinstance(reel, str):
                                all_reel_urls.append(reel)
                            elif isinstance(reel, dict):
                                url = reel.get('url')
                                if url:
                                    all_reel_urls.append(url)
                    
                    if all_reel_urls:
                        captions_map = fetch_captions_batch(all_reel_urls)
                        for profile in new_results:
                            reels = profile.get('reels', [])
                            processed_reels = []
                            for reel in reels:
                                if isinstance(reel, str):
                                    reel_url = reel
                                    caption = captions_map.get(reel_url, '')
                                    processed_reels.append({"url": reel_url, "caption": caption or ''})
                                elif isinstance(reel, dict):
                                    reel_url = reel.get('url')
                                    if reel_url:
                                        caption = captions_map.get(reel_url, '')
                                        processed_reels.append({"url": reel_url, "caption": caption or ''})
                                    else:
                                        processed_reels.append(reel)
                                else:
                                    processed_reels.append(reel)
                            profile['reels'] = processed_reels
                        app.logger.info(f"✅ Added captions to {len(all_reel_urls)} new reels")
                
                extracted_usernames = [p.get('username') for p in new_results if p.get('username')]
                return jsonify({
                    "status": "success", 
                    "job_id": result_data.get('job_id') or str(uuid.uuid4()), 
                    "usernames": extracted_usernames, 
                    "message": f"Found {total_new_reels} new reels across {len(new_results)} profiles", 
                    "results": new_results, 
                    "auto_sync": False, 
                    "new_reels": total_new_reels, 
                    "profiles_with_new": len(new_results)
                }), 200
            else:
                return jsonify({
                    "status": "success", 
                    "message": "No new reels found for the requested profiles", 
                    "usernames": usernames, 
                    "results": []
                }), 200
        
        return jsonify(response.json()), response.status_code
        
    except requests.exceptions.Timeout:
        return jsonify({"status": "error", "error": "Render service timed out. Please try again."}), 504
    except requests.exceptions.ConnectionError:
        return jsonify({"status": "error", "error": "Could not connect to Render service. Please try again later."}), 503
    except Exception as e:
        app.logger.error(f"Proxy error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

# ============== SCRAPED DATA STORAGE ==============

def store_scraped_data_internal(job_id, results, usernames, status='completed'):
    if not results:
        return False
    user_id = get_user_id()
    conn = get_db_connection()
    if not conn:
        return False
    try:
        total_profiles = len(results)
        total_reels = 0
        for profile in results:
            if profile.get('reels'):
                total_reels += len(profile.get('reels', []))
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO scraped_reels (user_id, job_id, usernames, results, status, total_profiles, total_reels, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (user_id, job_id) DO UPDATE SET 
                results = EXCLUDED.results, usernames = EXCLUDED.usernames,
                status = EXCLUDED.status, total_profiles = EXCLUDED.total_profiles,
                total_reels = EXCLUDED.total_reels, updated_at = NOW()
        """, (user_id, job_id or f"job_{datetime.utcnow().isoformat()}", usernames, json.dumps(results), status, total_profiles, total_reels))
        conn.commit()
        app.logger.info(f"Stored {total_profiles} profiles from job {job_id}")
        return True
    except Exception as e:
        app.logger.error(f"Database store error: {e}")
        return False
    finally:
        cur.close()
        conn.close()

@app.route("/api/scraped/store", methods=["POST"])
def store_scraped_data():
    data = request.get_json(silent=True) or {}
    results = data.get("results", [])
    job_id = data.get("job_id")
    if not results:
        return jsonify({"error": "No results provided"}), 400
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        user_id = get_user_id()
        all_usernames = []
        processed_results = []
        for profile in results:
            username = profile.get('username')
            if username:
                all_usernames.append(username)
            existing_urls = get_existing_reel_urls(username)
            new_reels = profile.get('reels', [])
            merged_reels = []
            existing_reels_dict = {}
            if existing_urls:
                cur = conn.cursor()
                cur.execute("""
                    SELECT results FROM scraped_reels 
                    WHERE EXISTS (
                        SELECT 1 FROM jsonb_array_elements(results) AS elem
                        WHERE elem->>'username' = %s
                    )
                    ORDER BY created_at DESC LIMIT 1
                """, (username,))
                result = cur.fetchone()
                cur.close()
                if result:
                    existing_results = result[0]
                    for p in existing_results:
                        if p.get('username') == username:
                            for reel in p.get('reels', []):
                                if isinstance(reel, dict):
                                    url = reel.get('url')
                                    if url:
                                        existing_reels_dict[url] = reel
                                elif isinstance(reel, str):
                                    existing_reels_dict[reel] = {"url": reel, "caption": ""}
                            break
            for url, reel_data in existing_reels_dict.items():
                merged_reels.append(reel_data)
            for reel in new_reels:
                if isinstance(reel, dict):
                    url = reel.get('url')
                    if url and url not in existing_reels_dict:
                        merged_reels.append(reel)
                        existing_reels_dict[url] = reel
                elif isinstance(reel, str):
                    if reel not in existing_reels_dict:
                        merged_reels.append({"url": reel, "caption": ""})
                        existing_reels_dict[reel] = {"url": reel, "caption": ""}
            merged_profile = {"username": username, "reels": merged_reels, "status": profile.get('status', 'ok')}
            processed_results.append(merged_profile)
        total_reels = sum(len(p.get('reels', [])) for p in processed_results)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO scraped_reels (user_id, job_id, usernames, results, status, total_profiles, total_reels, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (user_id, job_id) DO UPDATE SET 
                results = EXCLUDED.results, usernames = EXCLUDED.usernames,
                status = EXCLUDED.status, total_profiles = EXCLUDED.total_profiles,
                total_reels = EXCLUDED.total_reels, updated_at = NOW()
        """, (user_id, job_id or f"job_{datetime.utcnow().isoformat()}", all_usernames, json.dumps(processed_results), 'completed', len(processed_results), total_reels))
        conn.commit()
        app.logger.info(f"✅ Merged: {len(processed_results)} profiles with {total_reels} total reels")
        return jsonify({"status": "success", "message": f"Merged {len(processed_results)} profiles with {total_reels} total reels", "profiles": len(processed_results), "reels": total_reels})
    except Exception as e:
        app.logger.error(f"Storage error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

# ============== SCRAPED DATA ROUTES ==============

@app.route("/api/scraped/latest", methods=["GET"])
def get_scraped_data():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT results, total_profiles, total_reels, usernames, created_at FROM scraped_reels ORDER BY created_at DESC")
        all_results = cur.fetchall()
        if all_results:
            combined_results = []
            seen_usernames = set()
            total_profiles = 0
            total_reels = 0
            for entry in all_results:
                results = entry['results']
                if results and isinstance(results, list):
                    for profile in results:
                        username = profile.get('username')
                        if username:
                            if username not in seen_usernames:
                                seen_usernames.add(username)
                                combined_results.append({'username': username, 'reels': profile.get('reels', []), 'status': profile.get('status', 'ok')})
                                total_profiles += 1
                                total_reels += len(profile.get('reels', []))
                            else:
                                for existing in combined_results:
                                    if existing.get('username') == username:
                                        existing_reels = existing.get('reels', [])
                                        new_reels = profile.get('reels', [])
                                        for reel in new_reels:
                                            if reel not in existing_reels:
                                                existing_reels.append(reel)
                                        total_reels += len(new_reels)
                                        break
            combined_results.sort(key=lambda x: len(x.get('reels', [])), reverse=True)
            all_usernames = []
            cur.execute("SELECT DISTINCT unnest(usernames) as username FROM scraped_reels WHERE usernames IS NOT NULL AND array_length(usernames, 1) > 0")
            username_rows = cur.fetchall()
            for row in username_rows:
                if row['username']:
                    all_usernames.append(row['username'])
            return jsonify({"status": "success", "results": combined_results, "total_profiles": len(combined_results), "total_reels": total_reels, "usernames": list(seen_usernames), "all_usernames": all_usernames, "job_count": len(all_results), "message": f"Loaded {len(combined_results)} unique profiles with {total_reels} total reels"})
        else:
            return jsonify({"status": "success", "results": [], "message": "No scraped data found in database"})
    except Exception as e:
        app.logger.error(f"Database error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route("/api/scraped/delete", methods=["POST"])
def delete_scraped_by_username():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    if not username:
        return jsonify({"error": "Username is required"}), 400
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM scraped_reels WHERE EXISTS (SELECT 1 FROM jsonb_array_elements(results) AS r WHERE r->>'username' = %s)", (username,))
        jobs_count = cur.fetchone()[0]
        app.logger.info(f"📊 Found {jobs_count} jobs containing username: {username}")
        cur.execute("DELETE FROM scraped_reels WHERE EXISTS (SELECT 1 FROM jsonb_array_elements(results) AS r WHERE r->>'username' = %s)", (username,))
        deleted_count = cur.rowcount
        conn.commit()
        app.logger.info(f"✅ PERMANENTLY DELETED {deleted_count} jobs for username: {username}")
        return jsonify({"status": "success", "message": f"Permanently deleted {deleted_count} jobs for @{username}", "deleted_count": deleted_count, "jobs_found": jobs_count})
    except Exception as e:
        app.logger.error(f"❌ Delete error: {e}")
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

# ============== VIDEO DOWNLOAD ROUTES ==============

@app.route("/api/fetch", methods=["POST"])
def fetch_info():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "Paste an Instagram link first."}), 400
    if not is_valid_instagram_url(url):
        return jsonify({"error": "That doesn't look like an instagram.com link."}), 400
    try:
        with yt_dlp.YoutubeDL(base_ydl_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        return jsonify({"error": clean_error(str(e))}), 422
    except Exception as e:
        return jsonify({"error": clean_error(str(e))}), 422
    entries = info.get("entries") if "entries" in info else [info]
    entries = [e for e in entries if e]
    items = []
    for e in entries:
        items.append({"id": e.get("id"), "title": (e.get("title") or e.get("description") or "Instagram video").strip()[:140], "thumbnail": e.get("thumbnail"), "duration": e.get("duration"), "uploader": e.get("uploader") or e.get("uploader_id"), "ext": e.get("ext", "mp4")})
    if not items:
        return jsonify({"error": "No downloadable video found at that link."}), 422
    return jsonify({"items": items, "source_url": url})

@app.route("/api/download", methods=["GET"])
def download_video():
    url = (request.args.get("url") or "").strip()
    media_id = (request.args.get("id") or "").strip()
    if not is_valid_instagram_url(url):
        return jsonify({"error": "Invalid or missing url."}), 400
    try:
        direct_url = get_direct_video_url(url, media_id)
        if direct_url:
            return jsonify({"download_url": direct_url})
    except Exception as e:
        app.logger.warning(f"Direct URL failed: {e}")
    try:
        filepath, job_dir, target = download_video_file(url, media_id)
        download_name = f"{target.get('id', 'instagram_video')}.{target.get('ext', 'mp4')}"
        @after_this_request
        def cleanup(response):
            shutil.rmtree(job_dir, ignore_errors=True)
            return response
        return send_file(filepath, as_attachment=True, download_name=download_name)
    except Exception as e:
        return jsonify({"error": str(e)}), 500







# ============== DOWNLOAD JOBS TRACKING ==============
DOWNLOAD_JOBS = {}  # Track async download jobs

def send_download_webhook(job_id, instagram_url, video_url, media_id, action, error, caption=None):
    """Send webhook notification for async download"""
    try:
        job_data = DOWNLOAD_JOBS.get(job_id, {})
        webhook_url = job_data.get('webhook_url')
        
        if not webhook_url:
            app.logger.warning(f"⚠️ [ASYNC Job {job_id}] No webhook URL provided")
            return
        
        payload = {
            "job_id": job_id,
            "url": instagram_url,
            "media_id": media_id,
            "action": action,
            "status": "completed" if video_url else "failed",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if video_url:
            payload["video_url"] = video_url
            payload["download_url"] = video_url
            payload["video_info"] = {
                "id": media_id or 'instagram_video',
                "title": caption or "Instagram video",
                "thumbnail": None,
                "ext": "mp4"
            }
            if caption:
                payload["caption"] = caption
            app.logger.info(f"✅ [ASYNC Job {job_id}] Sending success webhook to: {webhook_url[:50]}...")
        else:
            payload["error"] = error or "Failed to get video URL"
            payload["status"] = "failed"
            app.logger.info(f"❌ [ASYNC Job {job_id}] Sending failure webhook to: {webhook_url[:50]}...")
        
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=30,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            app.logger.info(f"✅ [ASYNC Job {job_id}] Webhook sent successfully")
        else:
            app.logger.warning(f"⚠️ [ASYNC Job {job_id}] Webhook returned {response.status_code}")
            
    except Exception as e:
        app.logger.error(f"❌ [ASYNC Job {job_id}] Failed to send webhook: {e}")














@app.route("/api/commands/download", methods=["POST"])
def api_download():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    media_id = data.get("media_id", "").strip()
    action = data.get("action", "url_only")
    webhook_url = data.get("webhook_url")  # Optional webhook for async response

    if not url:
        return jsonify({"error": "Missing 'url' parameter"}), 400
    if not is_valid_instagram_url(url):
        return jsonify({"error": "Invalid Instagram URL"}), 400

    # ============================================================
    # STEP 1: RETRY LOGIC FOR SERVICE CALLS (shared helper)
    # ============================================================
    def call_service_with_retry(url, max_retries=3, timeout=30):
        """Call the video URL service with retry logic."""
        last_error = None

        for attempt in range(max_retries):
            try:
                app.logger.info(
                    f"📥 [Attempt {attempt + 1}/{max_retries}] "
                    f"Calling video URL service..."
                )

                response = requests.post(
                    f"{IG_VIDEO_URL_GETTER}/api/download",
                    json={"url": url},
                    timeout=timeout,
                    headers={"Content-Type": "application/json"}
                )

                if response.status_code == 200:
                    return response, None
                elif response.status_code == 500:
                    app.logger.warning(
                        f"⚠️ [Attempt {attempt + 1}] Service returned 500, retrying..."
                    )
                    last_error = f"Service returned 500 (attempt {attempt + 1})"
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # 1, 2, 4 seconds
                        app.logger.info(f"⏳ Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                    continue
                else:
                    return response, None

            except requests.exceptions.Timeout:
                last_error = f"Timeout (attempt {attempt + 1})"
                app.logger.warning(f"⏰ [Attempt {attempt + 1}] Timeout, retrying...")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    app.logger.info(f"⏳ Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                continue

            except requests.exceptions.ConnectionError as e:
                last_error = f"Connection error: {str(e)}"
                app.logger.warning(
                    f"🔌 [Attempt {attempt + 1}] Connection error, retrying..."
                )
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    app.logger.info(f"⏳ Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                continue

            except Exception as e:
                last_error = str(e)
                app.logger.error(f"❌ [Attempt {attempt + 1}] Error: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    app.logger.info(f"⏳ Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                continue

        return None, last_error

    # ============================================================
    # STEP 2: ALWAYS FETCH FRESH — NEVER TRUST THE CACHE FIRST
    # Fast path: 10s timeout, 2 retries.
    # ============================================================
    app.logger.info(
        f"📥 [FAST] Fetching FRESH video URL from service "
        f"(10s timeout, 2 retries) for: {url[:50]}..."
    )

    response, error = call_service_with_retry(url, max_retries=2, timeout=10)

    if response and response.status_code == 200:
        service_data = response.json()

        if service_data.get('success'):
            video_data = service_data.get('data', {})
            download_url = (
                video_data.get('downloadUrl')
                or video_data.get('directDownloadUrl')
            )
            caption = video_data.get('caption', '') or ''

            if download_url:
                app.logger.info(f"✅ [FAST] Got FRESH video URL: {download_url[:50]}...")

                # Store it in the cache purely as an audit trail — nothing
                # in the publish path reads it back as a source of truth.
                cache_direct_url(url, download_url, caption)

                video_info = {
                    "id": media_id or video_data.get('id', 'instagram_video'),
                    "title": video_data.get('filename', caption or 'Instagram video'),
                    "duration": None,
                    "uploader": None,
                    "thumbnail": (
                        video_data.get('thumbnail')
                        or video_data.get('thumbnailUrl')
                    ),
                    "ext": "mp4"
                }

                session['current_video_url'] = download_url
                session['current_video_title'] = video_info.get('title')
                session['current_video_thumbnail'] = video_info.get('thumbnail')

                response_data = {
                    "status": "success",
                    "url": url,
                    "media_id": media_id,
                    "action": action,
                    "download_url": download_url,
                    "video_info": video_info,
                    "from_cache": False,
                    "timestamp": datetime.utcnow().isoformat()
                }
                if caption:
                    response_data["caption"] = caption

                return jsonify(response_data)

    # ============================================================
    # STEP 3: ASYNC MODE — if a webhook was provided, use it
    # ============================================================
    if webhook_url:
        app.logger.info(f"📤 [ASYNC] Download request with webhook for: {url[:50]}...")
        app.logger.info(f"   Fast path failed: {error or 'Service unavailable'}")

        # Generate a job ID for tracking
        job_id = str(uuid.uuid4())

        # Store the request status
        DOWNLOAD_JOBS[job_id] = {
            'url': url,
            'status': 'processing',
            'created_at': datetime.utcnow().isoformat(),
            'webhook_url': webhook_url,
            'media_id': media_id,
            'action': action
        }

        # Start the video fetch in a background thread with retries
        import threading

        def process_async_download():
            def run_async():
                with app.app_context():
                    try:
                        app.logger.info(
                            f"📥 [ASYNC Job {job_id}] Fetching real video URL "
                            f"for: {url[:50]}..."
                        )

                        # Use retry logic in background (3 retries, 60s timeout)
                        response, error = call_service_with_retry(
                            url, max_retries=3, timeout=60
                        )

                        if response and response.status_code == 200:
                            service_data = response.json()
                            if service_data.get('success'):
                                video_data = service_data.get('data', {})
                                download_url = (
                                    video_data.get('downloadUrl')
                                    or video_data.get('directDownloadUrl')
                                )
                                caption = video_data.get('caption', '') or ''

                                if download_url:
                                    app.logger.info(
                                        f"✅ [ASYNC Job {job_id}] Got REAL video URL: "
                                        f"{download_url[:50]}..."
                                    )

                                    cache_direct_url(url, download_url, caption or '')

                                    DOWNLOAD_JOBS[job_id]['video_url'] = download_url
                                    DOWNLOAD_JOBS[job_id]['caption'] = caption
                                    DOWNLOAD_JOBS[job_id]['status'] = 'completed'
                                    DOWNLOAD_JOBS[job_id]['completed_at'] = (
                                        datetime.utcnow().isoformat()
                                    )

                                    send_download_webhook(
                                        job_id, url, download_url,
                                        media_id, action, None, caption
                                    )
                                    return

                        # If we get here, all retries failed
                        app.logger.error(
                            f"❌ [ASYNC Job {job_id}] All retries failed: {error}"
                        )
                        DOWNLOAD_JOBS[job_id]['status'] = 'failed'
                        DOWNLOAD_JOBS[job_id]['error'] = error or 'All retries failed'
                        DOWNLOAD_JOBS[job_id]['completed_at'] = (
                            datetime.utcnow().isoformat()
                        )
                        send_download_webhook(
                            job_id, url, None, media_id, action,
                            error or 'All retries failed', None
                        )

                    except Exception as e:
                        app.logger.error(f"❌ [ASYNC Job {job_id}] Error: {e}")
                        import traceback
                        app.logger.error(traceback.format_exc())
                        DOWNLOAD_JOBS[job_id]['status'] = 'failed'
                        DOWNLOAD_JOBS[job_id]['error'] = str(e)
                        DOWNLOAD_JOBS[job_id]['completed_at'] = (
                            datetime.utcnow().isoformat()
                        )
                        send_download_webhook(
                            job_id, url, None, media_id, action, str(e), None
                        )

            thread = threading.Thread(target=run_async)
            thread.daemon = True
            thread.start()

        process_async_download()

        # Return job ID - webhook will send REAL URL when ready
        return jsonify({
            "status": "accepted",
            "job_id": job_id,
            "message": (
                "Download request accepted. You will receive the real "
                "video URL via webhook when ready."
            ),
            "action": action,
            "webhook_url": webhook_url,
            "timestamp": datetime.utcnow().isoformat()
        }), 202

    # ============================================================
    # STEP 4: SYNC MODE (no webhook) — wait with full retries
    # ============================================================
    try:
        app.logger.info(f"📥 [SYNC] Download request for: {url[:50]}...")

        # Use retry logic with full timeout (3 retries, 60s timeout)
        response, error = call_service_with_retry(url, max_retries=3, timeout=60)

        if response and response.status_code == 200:
            service_data = response.json()

            if service_data.get('success'):
                video_data = service_data.get('data', {})
                download_url = (
                    video_data.get('downloadUrl')
                    or video_data.get('directDownloadUrl')
                )
                caption = video_data.get('caption', '') or ''

                if download_url:
                    app.logger.info(
                        f"✅ [SYNC] Got REAL video URL: {download_url[:50]}..."
                    )

                    cache_direct_url(url, download_url, caption)

                    video_info = {
                        "id": media_id or video_data.get('id', 'instagram_video'),
                        "title": video_data.get('filename', caption or 'Instagram video'),
                        "duration": None,
                        "uploader": None,
                        "thumbnail": (
                            video_data.get('thumbnail')
                            or video_data.get('thumbnailUrl')
                        ),
                        "ext": "mp4"
                    }

                    session['current_video_url'] = download_url
                    session['current_video_title'] = video_info.get('title')
                    session['current_video_thumbnail'] = video_info.get('thumbnail')

                    response_data = {
                        "status": "success",
                        "url": url,
                        "media_id": media_id,
                        "action": action,
                        "download_url": download_url,
                        "video_info": video_info,
                        "from_cache": False,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    if caption:
                        response_data["caption"] = caption

                    return jsonify(response_data)
                else:
                    app.logger.warning(
                        "⚠️ [SYNC] No download URL in service response"
                    )
                    return jsonify({
                        "error": "No video URL found in service response"
                    }), 404
            else:
                error_msg = service_data.get('error', 'Service error')
                app.logger.warning(f"⚠️ [SYNC] Service error: {error_msg}")
                return jsonify({"error": error_msg}), 500
        else:
            app.logger.error(f"❌ [SYNC] All retries failed: {error}")
            return jsonify({
                "error": f"Service unavailable after retries: {error}"
            }), 503

    except Exception as e:
        app.logger.error(f"❌ [SYNC] Download error: {e}")
        return jsonify({"error": clean_error(str(e))}), 500









    
    
    
    
    
    
    
    
    
    
    
    

# ============== BLUESKY ROUTES ==============

@app.route("/api/bluesky/save_credentials", methods=["POST"])
def save_bluesky_credentials():
    data = request.get_json(silent=True) or {}
    identifier = data.get("identifier", "").strip()
    password = data.get("password", "").strip()
    remember = data.get("remember", True)
    if not identifier or not password:
        return jsonify({"error": "Missing identifier or password"}), 400
    try:
        session_data = create_bluesky_session(identifier, password)
        if remember:
            encrypted = encrypt_credentials(identifier, password)
            if encrypted:
                session.permanent = True
                session['bluesky_encrypted'] = encrypted
                session['bluesky_identifier'] = identifier
                session.pop('bluesky_password', None)
                session['bluesky_handle'] = session_data.get('handle', identifier)
                session['bluesky_did'] = session_data.get('did')
                session['bluesky_saved'] = True
        return jsonify({"status": "success", "message": "Credentials saved successfully!", "handle": session_data.get('handle'), "did": session_data.get('did'), "remembered": remember})
    except Exception as e:
        return jsonify({"error": str(e)}), 401

@app.route("/api/bluesky/credentials_status", methods=["GET"])
def bluesky_credentials_status():
    encrypted = session.get('bluesky_encrypted')
    identifier = session.get('bluesky_identifier')
    if encrypted:
        decrypted = decrypt_credentials(encrypted)
        if decrypted:
            return jsonify({"status": "success", "has_credentials": True, "identifier": identifier or decrypted[0], "handle": session.get('bluesky_handle', identifier or decrypted[0]), "message": "Credentials are saved and valid"})
    return jsonify({"status": "success", "has_credentials": False, "message": "No saved credentials found"})

@app.route("/api/bluesky/clear_credentials", methods=["POST"])
def clear_bluesky_credentials():
    session.pop('bluesky_encrypted', None)
    session.pop('bluesky_identifier', None)
    session.pop('bluesky_password', None)
    session.pop('bluesky_handle', None)
    session.pop('bluesky_did', None)
    session.pop('bluesky_saved', None)
    return jsonify({"status": "success", "message": "Credentials cleared successfully"})

@app.route("/api/bluesky/post", methods=["POST"])
def bluesky_post():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    text = data.get("text", "Check out this video! 🎬").strip()
    identifier = data.get("identifier", "").strip()
    password = data.get("password", "").strip()
    remember = data.get("remember", True)
    if not url and session.get('current_video_url'):
        url = session.get('current_video_url')
        text = text or session.get('current_video_title', 'Instagram video')
    if not url:
        return jsonify({"error": "No video URL provided. Please fetch a video first."}), 400
    thumbnail_url = session.get('current_video_thumbnail')
    if identifier and password:
        try:
            test_session = create_bluesky_session(identifier, password)
            if remember:
                encrypted = encrypt_credentials(identifier, password)
                if encrypted:
                    session.permanent = True
                    session['bluesky_encrypted'] = encrypted
                    session['bluesky_identifier'] = identifier
                    session.pop('bluesky_password', None)
                    session['bluesky_handle'] = test_session.get('handle', identifier)
                    session['bluesky_did'] = test_session.get('did')
                    session['bluesky_saved'] = True
        except Exception as e:
            return jsonify({"error": f"Invalid credentials: {str(e)}"}), 401
    try:
        result = post_to_bluesky(video_url=url, text=text, thumbnail_url=thumbnail_url, identifier=identifier or None, password=password or None)
        if result["success"]:
            return jsonify({"status": "success", "post_uri": result.get("post_uri"), "post_cid": result.get("post_cid"), "post_id": result.get("post_id"), "message": result.get("message"), "video_url": url, "saved": bool(session.get('bluesky_saved'))})
        else:
            return jsonify({"status": "error", "error": result.get("error")}), 500
    except Exception as e:
        return jsonify({"error": clean_error(str(e))}), 500

# ============== ZERNIO (FACEBOOK) ROUTES ==============

@app.route('/api/zernio/publish', methods=['POST'])
def zernio_publish():
    data = request.get_json(silent=True) or {}
    video_url = data.get('video_url')
    text = data.get('text', 'Check out this video! 🎬')
    account_id = data.get('account_id')
    publish_now = data.get('publish_now', True)
    scheduled_time = data.get('scheduled_time')
    key_id = data.get('key_id')  # Optional: specific key to use
    
    if not video_url:
        return jsonify({"error": "video_url is required"}), 400
    
    if account_id:
        result = publish_to_facebook(
            video_url=video_url,
            text=text,
            account_id=account_id,
            publish_now=publish_now,
            scheduled_time=scheduled_time,
            key_id=key_id
        )
        return jsonify(result)
    
    results = publish_video_to_all_accounts(
        video_url=video_url,
        text=text,
        publish_now=publish_now,
        scheduled_time=scheduled_time
    )
    return jsonify({"status": "success", "message": f"Published to {len(results)} accounts", "results": results})

@app.route('/api/zernio/status', methods=['GET'])
def zernio_status():
    try:
        # Try to get accounts with the best available key
        key = get_best_zernio_key()
        if not key:
            return jsonify({"status": "error", "message": "No Zernio keys available"}), 503
        
        zernio_base_url = get_zernio_base_url()
        headers = {"Authorization": f"Bearer {key['api_key']}", "Content-Type": "application/json"}
        response = requests.get(f"{zernio_base_url}/accounts", headers=headers, timeout=30)
        return jsonify({"status": "connected" if response.status_code == 200 else "error", "status_code": response.status_code, "message": "Zernio API is accessible" if response.status_code == 200 else "Failed to connect"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500







@app.route("/api/debug/zernio-memory", methods=["GET"])
def debug_zernio_memory():
    masked = {}
    for key_id, key_data in ZERNIO_KEYS.items():
        d = dict(key_data)
        api_key = d.get('api_key', '')
        if api_key and len(api_key) > 12:
            d['api_key'] = api_key[:8] + '...' + api_key[-4:]
        masked[key_id] = d
 
    return jsonify({
        "status": "success",
        "note": "This is IN-MEMORY state on this specific lambda instance, not the database.",
        "zernio_keys_in_memory": masked,
        "zernio_key_usage_in_memory": {
            k: {**v, 'last_reset': str(v.get('last_reset'))}
            for k, v in ZERNIO_KEY_USAGE.items()
        },
        "total_keys_in_memory": len(ZERNIO_KEYS)
    })







@app.route('/api/zernio/accounts', methods=['GET'])
def zernio_list_accounts():
    """List ALL connected Zernio Facebook accounts from ALL keys."""
    try:
        # ✅ Get ALL keys, not just the best one
        if not ZERNIO_KEYS:
            return jsonify({
                "status": "error", 
                "message": "No Zernio keys available. Please add a key first.", 
                "accounts": []
            }), 503
        
        all_facebook_accounts = []
        zernio_base_url = get_zernio_base_url()
        
        # ✅ Loop through ALL keys
        for key_id, key_data in ZERNIO_KEYS.items():
            try:
                headers = {
                    "Authorization": f"Bearer {key_data['api_key']}", 
                    "Content-Type": "application/json"
                }
                
                app.logger.info(f"🔑 Fetching accounts with key: {key_data['name']}")
                
                response = requests.get(f"{zernio_base_url}/accounts", headers=headers, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    accounts = data.get('accounts', [])
                    
                    for account in accounts:
                        if account.get('platform') == 'facebook':
                            all_facebook_accounts.append({
                                "id": account.get('_id'),
                                "name": account.get('displayName', 'Unknown'),
                                "page_id": account.get('profileData', {}).get('id', 'N/A'),
                                "username": account.get('username', 'N/A'),
                                "status": account.get('platformStatus', 'unknown'),
                                "key_id": key_id,           # ✅ Add key ID
                                "key_name": key_data['name'] # ✅ Add key name
                            })
                    
                    app.logger.info(f"✅ Found {len(accounts)} total accounts for key: {key_data['name']}")
                else:
                    app.logger.warning(f"⚠️ Key {key_data['name']} returned {response.status_code}")
                    
            except requests.exceptions.Timeout:
                app.logger.warning(f"⏰ Timeout for key: {key_data['name']}")
            except requests.exceptions.ConnectionError as e:
                app.logger.warning(f"🔌 Connection error for key {key_data['name']}: {e}")
            except Exception as e:
                app.logger.warning(f"❌ Error fetching accounts for key {key_data['name']}: {e}")
        
        app.logger.info(f"✅ Found {len(all_facebook_accounts)} total Facebook accounts across all keys")
        
        return jsonify({
            "status": "success", 
            "accounts": all_facebook_accounts, 
            "total": len(all_facebook_accounts),
            "keys_processed": len(ZERNIO_KEYS)
        })
        
    except Exception as e:
        app.logger.error(f"❌ Error fetching Zernio accounts: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({"status": "error", "message": str(e), "accounts": []}), 500

# ============== ZERNIO KEYS API ==============

@app.route('/api/zernio/keys', methods=['GET'])
def get_zernio_keys():
    """Get all Zernio keys with their Facebook accounts."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT 
                id,
                name,
                api_key,
                facebook_account_id,
                facebook_page_name,
                daily_limit,
                usage_count,
                last_used,
                is_active,
                created_at
            FROM zernio_keys
            ORDER BY created_at DESC
        """)
        keys = cur.fetchall()
        
        zernio_base_url = get_zernio_base_url()
        
        for key in keys:
            # Mask API key
            if key['api_key'] and len(key['api_key']) > 10:
                key['api_key_masked'] = key['api_key'][:8] + '...' + key['api_key'][-4:]
            else:
                key['api_key_masked'] = '***'
            
            # ⭐ FETCH ALL Facebook accounts for this key from the API
            key['accounts'] = []
            key['account_count'] = 0
            
            try:
                headers = {
                    "Authorization": f"Bearer {key['api_key']}",
                    "Content-Type": "application/json"
                }
                
                app.logger.info(f"🔍 Fetching accounts for key: {key['name']}")
                response = requests.get(f"{zernio_base_url}/accounts", headers=headers, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    accounts = data.get('accounts', [])
                    
                    facebook_accounts = []
                    for account in accounts:
                        if account.get('platform') == 'facebook':
                            facebook_accounts.append({
                                "id": account.get('_id'),
                                "name": account.get('displayName', 'Unknown'),
                                "page_id": account.get('profileData', {}).get('id', 'N/A'),
                                "status": account.get('platformStatus', 'unknown')
                            })
                    
                    key['accounts'] = facebook_accounts
                    key['account_count'] = len(facebook_accounts)
                    app.logger.info(f"✅ Found {len(facebook_accounts)} accounts for key: {key['name']}")
                else:
                    app.logger.warning(f"⚠️ API returned {response.status_code} for key {key['name']}")
                    key['accounts'] = []
                    key['account_count'] = 0
                    
            except requests.exceptions.Timeout:
                app.logger.warning(f"⏰ Timeout fetching accounts for key {key['name']}")
                key['accounts'] = []
                key['account_count'] = 0
            except requests.exceptions.ConnectionError as e:
                app.logger.warning(f"🔌 Connection error for key {key['name']}: {e}")
                key['accounts'] = []
                key['account_count'] = 0
            except Exception as e:
                app.logger.warning(f"❌ Error fetching accounts for key {key['name']}: {e}")
                key['accounts'] = []
                key['account_count'] = 0
        
        return jsonify({
            "status": "success",
            "keys": keys,
            "total": len(keys)
        })
        
    except Exception as e:
        app.logger.error(f"❌ Error in get_zernio_keys: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/zernio/keys', methods=['POST'])
def create_zernio_key():
    """Add a new Zernio key - auto-discovers accounts."""
    data = request.get_json(silent=True) or {}
    
    api_key = data.get('api_key')
    name = data.get('name')
    daily_limit = data.get('daily_limit', 50)
    
    if not api_key:
        return jsonify({"error": "API key is required"}), 400
    
    # 🔥 FIX: Auto-generate incrementing name if not provided or if it's "Key 1"
    if not name or name == "Key 1":
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            # Count existing keys
            cur.execute("SELECT COUNT(*) FROM zernio_keys")
            count = cur.fetchone()[0]
            cur.close()
            conn.close()
            name = f"Key {count + 1}"
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        # First, validate the key and fetch accounts
        zernio_base_url = get_zernio_base_url()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        app.logger.info(f"🔍 Validating key: {api_key[:10]}...")
        
        response = requests.get(f"{zernio_base_url}/accounts", headers=headers, timeout=30)
        
        if response.status_code != 200:
            return jsonify({
                "error": f"Invalid API key or unable to connect. Status: {response.status_code}"
            }), 400
        
        data = response.json()
        accounts = data.get('accounts', [])
        
        facebook_accounts = []
        for account in accounts:
            if account.get('platform') == 'facebook':
                facebook_accounts.append({
                    "id": account.get('_id'),
                    "name": account.get('displayName', 'Unknown'),
                    "page_id": account.get('profileData', {}).get('id', 'N/A'),
                    "status": account.get('platformStatus', 'unknown')
                })
        
        if not facebook_accounts:
            return jsonify({
                "error": "No Facebook accounts found for this API key. Please check your key."
            }), 400
        
        app.logger.info(f"✅ Found {len(facebook_accounts)} Facebook accounts")
        
        # Use the first Facebook account as the default
        first_account = facebook_accounts[0]
        
        # Save the key
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO zernio_keys (
                name, api_key, facebook_account_id, facebook_page_name, daily_limit
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (name, api_key, first_account['id'], first_account['name'], daily_limit))
        
        key_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        # Reload keys
        load_zernio_keys()
        
        return jsonify({
            "status": "success",
            "message": f"Zernio key '{name}' added with {len(facebook_accounts)} Facebook accounts",
            "key_id": key_id,
            "accounts_found": len(facebook_accounts),
            "accounts": facebook_accounts
        })
        
    except requests.exceptions.Timeout:
        return jsonify({"error": "Connection timeout - please check your key"}), 400
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Could not connect to Zernio API"}), 400
    except Exception as e:
        app.logger.error(f"Error adding key: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/zernio/keys/<key_id>', methods=['PUT'])
def update_zernio_key(key_id):
    """Update a Zernio key."""
    data = request.get_json(silent=True) or {}
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        updates = []
        params = []
        
        if 'name' in data:
            updates.append("name = %s"); params.append(data['name'])
        if 'api_key' in data:
            updates.append("api_key = %s"); params.append(data['api_key'])
        if 'facebook_account_id' in data:
            updates.append("facebook_account_id = %s"); params.append(data['facebook_account_id'])
        if 'facebook_page_name' in data:
            updates.append("facebook_page_name = %s"); params.append(data['facebook_page_name'])
        if 'daily_limit' in data:
            updates.append("daily_limit = %s"); params.append(data['daily_limit'])
        if 'is_active' in data:
            updates.append("is_active = %s"); params.append(data['is_active'])
        
        if not updates:
            return jsonify({"error": "No fields to update"}), 400
        
        updates.append("updated_at = NOW()")
        params.append(key_id)
        
        cur = conn.cursor()
        cur.execute(f"UPDATE zernio_keys SET {', '.join(updates)} WHERE id = %s", params)
        conn.commit()
        cur.close()
        conn.close()
        
        # Reload keys
        load_zernio_keys()
        
        return jsonify({"status": "success", "message": "Key updated"})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/zernio/keys/<key_id>', methods=['DELETE'])
def delete_zernio_key(key_id):
    """Delete a Zernio key."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM zernio_keys WHERE id = %s RETURNING id", (key_id,))
        deleted = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        if deleted:
            # Reload keys
            load_zernio_keys()
            return jsonify({"status": "success", "message": "Key deleted"})
        else:
            return jsonify({"error": "Key not found"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/zernio/keys/<key_id>/stats', methods=['GET'])
def get_key_stats(key_id):
    """Get detailed stats for a Zernio key."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT 
                id,
                name,
                daily_limit,
                usage_count,
                last_used,
                is_active,
                created_at
            FROM zernio_keys
            WHERE id = %s
        """, (key_id,))
        key = cur.fetchone()
        
        if not key:
            return jsonify({"error": "Key not found"}), 404
        
        # Get today's usage
        today = datetime.utcnow().date()
        key_id_str = str(key_id)
        if key_id_str in ZERNIO_KEY_USAGE and ZERNIO_KEY_USAGE[key_id_str]['last_reset'] == today:
            key['today_usage'] = ZERNIO_KEY_USAGE[key_id_str]['today']
        else:
            key['today_usage'] = 0
        
        key['remaining'] = key['daily_limit'] - key['today_usage']
        
        # Get pipeline usage
        cur.execute("""
            SELECT 
                p.name as pipeline_name,
                p.profile_username,
                COUNT(pr.id) as posts_count
            FROM pipelines p
            LEFT JOIN posted_reels pr ON p.id = pr.pipeline_id
            WHERE p.zernio_key_id = %s
            AND pr.posted_at > NOW() - INTERVAL '30 days'
            GROUP BY p.id
        """, (key_id,))
        key['pipeline_usage'] = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({"status": "success", "key": key})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


















# ============== BUFFER KEYS API ==============

@app.route('/api/buffer/keys', methods=['GET'])
def get_buffer_keys():
    """Get all Buffer keys with their cached channels."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, name, api_key, organization_id, organization_name,
                   daily_limit, usage_count, last_used, is_active, created_at
            FROM buffer_keys
            ORDER BY created_at DESC
        """)
        keys = cur.fetchall()

        for key in keys:
            api_key = key["api_key"] or ""
            key["api_key_masked"] = (
                api_key[:8] + "..." + api_key[-4:]
            ) if len(api_key) > 12 else "***"

            cur.execute("""
                SELECT channel_id, name, display_name, service, avatar, is_disconnected
                FROM buffer_channels
                WHERE buffer_key_id = %s
                ORDER BY service, display_name
            """, (key["id"],))
            channels = cur.fetchall()

            key["channels"] = [dict(c) for c in channels]
            key["channel_count"] = len(channels)
            key["twitter_count"] = sum(
                1 for c in channels
                if c["service"] == "twitter" and not c["is_disconnected"]
            )
            key["tiktok_count"] = sum(
                1 for c in channels
                if c["service"] == "tiktok" and not c["is_disconnected"]
            )

        return jsonify({"status": "success", "keys": keys, "total": len(keys)})

    except Exception as e:
        app.logger.error(f"Error in get_buffer_keys: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@app.route('/api/buffer/validate-key', methods=['POST'])
def validate_buffer_key():
    """Validate a Buffer key and return organization + channels."""
    data = request.get_json(silent=True) or {}
    api_key = (data.get("api_key") or "").strip()

    if not api_key:
        return jsonify({"valid": False, "message": "API key required"}), 400

    org, err = buffer_get_organizations(api_key)
    if err:
        return jsonify({"valid": False, "message": err}), 400

    channels, err = buffer_fetch_channels(api_key, org["id"])
    if err:
        return jsonify({"valid": False, "message": err}), 400

    twitter = [
        c for c in channels
        if c.get("service") == "twitter" and not c.get("isDisconnected")
    ]
    tiktok = [
        c for c in channels
        if c.get("service") == "tiktok" and not c.get("isDisconnected")
    ]

    return jsonify({
        "valid": True,
        "organization": org,
        "channels": channels,
        "twitter_count": len(twitter),
        "tiktok_count": len(tiktok),
    })


@app.route('/api/buffer/keys', methods=['POST'])
def create_buffer_key():
    """Add a new Buffer key and auto-discover channels."""
    data = request.get_json(silent=True) or {}
    api_key = (data.get("api_key") or "").strip()
    name = (data.get("name") or "").strip()
    daily_limit = data.get("daily_limit", 50)

    if not api_key:
        return jsonify({"error": "API key is required"}), 400

    # Validate first
    org, err = buffer_get_organizations(api_key)
    if err:
        return jsonify({"error": f"Invalid Buffer key: {err}"}), 400

    channels, err = buffer_fetch_channels(api_key, org["id"])
    if err:
        return jsonify({"error": f"Failed to fetch channels: {err}"}), 400

    # Auto-name if not provided
    if not name:
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM buffer_keys")
                count = cur.fetchone()[0]
                cur.close()
                conn.close()
                name = f"Buffer Key {count + 1}"
            except Exception:
                name = "Buffer Key"

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO buffer_keys (name, api_key, organization_id, organization_name, daily_limit)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (name, api_key, org["id"], org.get("name"), daily_limit))
        key_id = cur.fetchone()[0]

        for c in channels:
            cur.execute("""
                INSERT INTO buffer_channels
                    (buffer_key_id, channel_id, name, display_name, service, avatar, is_disconnected)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (buffer_key_id, channel_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    display_name = EXCLUDED.display_name,
                    service = EXCLUDED.service,
                    avatar = EXCLUDED.avatar,
                    is_disconnected = EXCLUDED.is_disconnected,
                    updated_at = NOW()
            """, (
                key_id,
                c["id"], c.get("name"), c.get("displayName"),
                c.get("service"), c.get("avatar"), bool(c.get("isDisconnected")),
            ))

        conn.commit()
        cur.close()
        conn.close()

        load_buffer_keys()

        twitter = sum(1 for c in channels if c.get("service") == "twitter")
        tiktok = sum(1 for c in channels if c.get("service") == "tiktok")

        return jsonify({
            "status": "success",
            "message": f"Buffer key '{name}' added",
            "key_id": str(key_id),
            "channel_count": len(channels),
            "twitter_count": twitter,
            "tiktok_count": tiktok,
        })

    except Exception as e:
        app.logger.error(f"Error creating Buffer key: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/buffer/keys/<key_id>', methods=['PUT'])
def update_buffer_key(key_id):
    data = request.get_json(silent=True) or {}
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        updates = []
        params = []

        for field in ("name", "api_key", "daily_limit", "is_active"):
            if field in data:
                updates.append(f"{field} = %s")
                params.append(data[field])

        if not updates:
            return jsonify({"error": "No fields to update"}), 400

        updates.append("updated_at = NOW()")
        params.append(key_id)

        cur = conn.cursor()
        cur.execute(f"UPDATE buffer_keys SET {', '.join(updates)} WHERE id = %s", params)
        conn.commit()
        cur.close()
        conn.close()

        load_buffer_keys()
        return jsonify({"status": "success", "message": "Buffer key updated"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/buffer/keys/<key_id>', methods=['DELETE'])
def delete_buffer_key(key_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM buffer_keys WHERE id = %s RETURNING id", (key_id,))
        deleted = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        if deleted:
            load_buffer_keys()
            return jsonify({"status": "success", "message": "Buffer key deleted"})
        return jsonify({"error": "Buffer key not found"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/buffer/keys/<key_id>/refresh-channels', methods=['POST'])
def refresh_buffer_channels(key_id):
    """Re-fetch channels from Buffer for a key."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT api_key, organization_id FROM buffer_keys WHERE id = %s", (key_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Buffer key not found"}), 404

        channels, err = buffer_fetch_channels(row["api_key"], row["organization_id"])
        if err:
            return jsonify({"error": err}), 400

        for c in channels:
            cur.execute("""
                INSERT INTO buffer_channels
                    (buffer_key_id, channel_id, name, display_name, service, avatar, is_disconnected)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (buffer_key_id, channel_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    display_name = EXCLUDED.display_name,
                    service = EXCLUDED.service,
                    avatar = EXCLUDED.avatar,
                    is_disconnected = EXCLUDED.is_disconnected,
                    updated_at = NOW()
            """, (
                key_id,
                c["id"], c.get("name"), c.get("displayName"),
                c.get("service"), c.get("avatar"), bool(c.get("isDisconnected")),
            ))

        conn.commit()
        cur.close()
        conn.close()

        load_buffer_keys()
        return jsonify({"status": "success", "channel_count": len(channels)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/buffer/channels', methods=['GET'])
def get_buffer_channels():
    """
    Return channels grouped by service.
    Query param: ?service=twitter or ?service=tiktok
    """
    service_filter = request.args.get("service")
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT bc.*, bk.id AS key_id, bk.name AS key_name
            FROM buffer_channels bc
            JOIN buffer_keys bk ON bc.buffer_key_id = bk.id
            WHERE bk.is_active = TRUE AND bc.is_disconnected = FALSE
        """
        params = []
        if service_filter:
            query += " AND bc.service = %s"
            params.append(service_filter)
        query += " ORDER BY bc.service, bc.display_name"

        cur.execute(query, params)
        rows = cur.fetchall()

        channels = [{
            "id": r["channel_id"],
            "name": r["name"],
            "display_name": r["display_name"],
            "service": r["service"],
            "avatar": r["avatar"],
            "key_id": str(r["key_id"]),
            "key_name": r["key_name"],
        } for r in rows]

        return jsonify({"status": "success", "channels": channels, "total": len(channels)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()



















# ============== SYNC STATUS ROUTE ==============

@app.route("/api/sync-status/<username>", methods=["GET"])
def get_sync_status_endpoint(username):
    status = get_sync_status(username)
    if status:
        total = status['total_reels'] or 1
        progress = min(100, int((status['captions_fetched'] / total) * 100)) if total > 0 else 0
        return jsonify({"status": "success", "sync": {"username": status['username'], "status": status['status'], "total_reels": status['total_reels'], "captions_fetched": status['captions_fetched'], "captions_skipped": status['captions_skipped'], "errors": status['errors'], "progress": progress, "started_at": status['started_at'], "completed_at": status['completed_at'], "last_updated": status['last_updated']}})
    else:
        return jsonify({"status": "success", "sync": None, "message": "No sync status found for this username"})

@app.route("/api/sync-captions", methods=["POST"])
def sync_captions():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    if not username:
        return jsonify({"error": "Username is required"}), 400
    app.logger.info(f"📝 Syncing captions for @{username}")
    job_id = sync_captions_background(username)
    return jsonify({"status": "accepted", "job_id": job_id, "message": f"Caption sync started for @{username}. Check /api/sync-status/{username} for progress.", "username": username}), 202






# ============== EXTRACT COOKIES FROM RENDER SERVICE ==============

COOKIE_EXTRACTOR_URL = os.environ.get('COOKIE_EXTRACTOR_URL', 'https://profilecookieextractor.onrender.com')






# ============== COOKIE EXTRACTION ROUTES ==============

@app.route("/api/cookies/extract-from-render", methods=["POST"])
def extract_cookies_from_render_endpoint():
    """Call the Render cookie extractor service to get fresh cookies"""
    success = extract_cookies_from_render_service()
    if success:
        db_cookies = get_cookies_from_db()
        username = db_cookies.get('username', 'Instagram User') if db_cookies else 'Instagram User'
        return jsonify({
            "success": True,
            "message": "Cookies extracted successfully from Render service",
            "username": username
        })
    else:
        return jsonify({
            "success": False,
            "error": "Failed to extract cookies from Render service"
        }), 500

@app.route("/api/cookies/extract-from-render/status", methods=["GET"])
def cookie_extractor_status():
    """Check if the Render cookie service is available"""
    try:
        response = requests.get(
            f"{COOKIE_EXTRACTOR_URL}/health",
            timeout=5
        )
        return jsonify({
            "available": response.status_code == 200,
            "status_code": response.status_code,
            "url": COOKIE_EXTRACTOR_URL
        })
    except Exception as e:
        return jsonify({
            "available": False,
            "error": str(e),
            "url": COOKIE_EXTRACTOR_URL
        })







# ============== CAPTION WEBHOOK ==============

@app.route("/api/webhook/caption", methods=["POST"])
def webhook_caption():
    """
    Webhook endpoint for caption service to send back captions.
    When caption is received, process the pending scheduled post.
    """
    data = request.get_json(silent=True) or {}
    
    reel_url = data.get('reel_url')
    caption = data.get('caption')
    job_id = data.get('job_id')
    status = data.get('status', 'completed')
    error = data.get('error')
    profile_username = data.get('profile_username')
    pipeline_id = data.get('pipeline_id')
    post_id = data.get('post_id')
    
    app.logger.info(f"📥 [Job {job_id}] Webhook received for: {reel_url[:50] if reel_url else 'unknown'}...")
    app.logger.info(f"   Caption: {caption[:50] if caption else 'None'}...")
    app.logger.info(f"   Status: {status}")
    app.logger.info(f"   Post ID: {post_id}")
    app.logger.info(f"   Pipeline ID: {pipeline_id}")
    
    if not reel_url:
        return jsonify({"status": "error", "message": "reel_url required"}), 400
    
    if reel_url in CAPTION_FETCH_STATUS:
        CAPTION_FETCH_STATUS[reel_url]['status'] = status
        CAPTION_FETCH_STATUS[reel_url]['message'] = 'Webhook received'
        CAPTION_FETCH_STATUS[reel_url]['completed_at'] = datetime.utcnow().isoformat()
        CAPTION_FETCH_STATUS[reel_url]['webhook_received'] = True
        if caption:
            CAPTION_FETCH_STATUS[reel_url]['caption'] = caption[:200]
            CAPTION_FETCH_STATUS[reel_url]['caption_length'] = len(caption)
    
    if status == 'completed' and caption:
        try:
            conn = get_db_connection()
            if conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                # Store in reel_cache
                cur.execute("""
                    INSERT INTO reel_cache (reel_url, direct_url, caption, created_at)
                    VALUES (%s, '', %s, NOW())
                    ON CONFLICT (reel_url) DO UPDATE SET 
                        caption = EXCLUDED.caption, created_at = NOW()
                """, (reel_url, caption))
                
                # Store in scraped_reels if possible
                if profile_username:
                    cur.execute("""
                        SELECT id, results FROM scraped_reels 
                        WHERE EXISTS (
                            SELECT 1 FROM jsonb_array_elements(results) AS elem
                            WHERE elem->>'username' = %s
                        )
                        ORDER BY created_at DESC LIMIT 1
                    """, (profile_username,))
                    result = cur.fetchone()
                    if result:
                        row_id = result['id']
                        results = result['results']
                        updated = False
                        if isinstance(results, str):
                            results = json.loads(results)
                        for profile_idx, profile in enumerate(results):
                            if profile.get('username') == profile_username:
                                reels = profile.get('reels', [])
                                for reel_idx, reel in enumerate(reels):
                                    if isinstance(reel, dict):
                                        if reel.get('url') == reel_url:
                                            results[profile_idx]['reels'][reel_idx]['caption'] = caption
                                            updated = True
                                            break
                                break
                        if updated:
                            cur.execute("""
                                UPDATE scraped_reels SET results = %s, updated_at = NOW()
                                WHERE id = %s
                            """, (json.dumps(results), row_id))
                            conn.commit()
                            app.logger.info(f"💾 [Job {job_id}] Caption stored in scraped_reels")
                
                # Store in posted_reels if already posted
                cur.execute("""
                    UPDATE posted_reels 
                    SET caption = %s 
                    WHERE reel_url = %s AND (caption IS NULL OR caption = '')
                """, (caption, reel_url))
                conn.commit()
                
                # PROCESS SCHEDULED POST - NEW FLOW
                if post_id:
                    app.logger.info(f"🔥 [Job {job_id}] Processing scheduled post {post_id} with caption")
                    
                    cur.execute("""
                        UPDATE scheduled_posts 
                        SET caption = %s, updated_at = NOW()
                        WHERE id = %s AND status = 'processing'
                        RETURNING id
                    """, (caption, post_id))
                    
                    updated = cur.fetchone()
                    if updated:
                        # ✅ FIX: Use aliases to avoid ID conflict
                        # ← CHANGED: added p.platform, p.buffer_key_id, p.buffer_channel_id
                        cur.execute("""
                            SELECT 
                                sp.id as scheduled_id,
                                sp.reel_url,
                                sp.direct_video_url,
                                sp.caption,
                                sp.pipeline_id,
                                sp.scheduled_time,
                                sp.status,
                                sp.error_message,
                                sp.posted_at,
                                sp.created_at,
                                sp.updated_at,
                                p.id as pipeline_id,
                                p.name as pipeline_name,
                                p.profile_username,
                                p.facebook_account_id,
                                p.zernio_key_id,
                                p.platform,
                                p.buffer_key_id,
                                p.buffer_channel_id
                            FROM scheduled_posts sp
                            JOIN pipelines p ON sp.pipeline_id = p.id
                            WHERE sp.id = %s
                        """, (post_id,))
                        post = cur.fetchone()
                        
                        if post:
                            process_post_with_caption(post, caption)
                        else:
                            app.logger.warning(f"⚠️ [Job {job_id}] Post {post_id} not found")
                    else:
                        app.logger.warning(f"⚠️ [Job {job_id}] Post {post_id} not in 'processing' status")
                
                # Fallback: Find scheduled post by reel_url and pipeline_id
                elif pipeline_id:
                    app.logger.info(f"🔍 [Job {job_id}] Finding scheduled post by URL: {reel_url[:50]}...")
                    cur.execute("""
                        SELECT id FROM scheduled_posts 
                        WHERE reel_url = %s AND pipeline_id = %s AND status = 'processing'
                        ORDER BY created_at DESC LIMIT 1
                    """, (reel_url, pipeline_id))
                    result = cur.fetchone()
                    
                    if result:
                        found_post_id = result['id']
                        app.logger.info(f"🔥 [Job {job_id}] Found scheduled post {found_post_id} for caption")
                        
                        cur.execute("""
                            UPDATE scheduled_posts 
                            SET caption = %s, updated_at = NOW()
                            WHERE id = %s
                        """, (caption, found_post_id))
                        conn.commit()
                        
                        # ✅ FIX: Use aliases to avoid ID conflict
                        # ← CHANGED: added p.platform, p.buffer_key_id, p.buffer_channel_id
                        cur.execute("""
                            SELECT 
                                sp.id as scheduled_id,
                                sp.reel_url,
                                sp.direct_video_url,
                                sp.caption,
                                sp.pipeline_id,
                                sp.scheduled_time,
                                sp.status,
                                sp.error_message,
                                sp.posted_at,
                                sp.created_at,
                                sp.updated_at,
                                p.id as pipeline_id,
                                p.name as pipeline_name,
                                p.profile_username,
                                p.facebook_account_id,
                                p.zernio_key_id,
                                p.platform,
                                p.buffer_key_id,
                                p.buffer_channel_id
                            FROM scheduled_posts sp
                            JOIN pipelines p ON sp.pipeline_id = p.id
                            WHERE sp.id = %s
                        """, (found_post_id,))
                        post = cur.fetchone()
                        
                        if post:
                            process_post_with_caption(post, caption)
                
                # Backward compatibility: Check pending_posts
                else:
                    app.logger.info(f"🔍 [Job {job_id}] Checking for pending post: {reel_url[:50]}...")
                    pending = get_pending_post(reel_url)
                    if pending:
                        app.logger.info(f"🔥 [Job {job_id}] Found pending post! Processing...")
                        success = process_pending_post(pending)
                        if success:
                            app.logger.info(f"✅ [Job {job_id}] Pending post processed successfully!")
                        else:
                            app.logger.error(f"❌ [Job {job_id}] Failed to process pending post")
                            cur.execute("""
                                UPDATE pending_posts SET status = 'failed', error_message = 'Processing failed', updated_at = NOW()
                                WHERE reel_url = %s AND status IN ('pending', 'processing')
                            """, (reel_url,))
                            conn.commit()
                    else:
                        app.logger.info(f"ℹ️ [Job {job_id}] No pending post found")
                        
                        cur.execute("SELECT COUNT(*) FROM posted_reels WHERE reel_url = %s AND status = 'success'", (reel_url,))
                        already_posted = cur.fetchone()['count'] > 0
                        if already_posted:
                            app.logger.info(f"✅ [Job {job_id}] Reel already posted")
                            cur.execute("""
                                UPDATE pending_posts SET status = 'completed', caption = %s, webhook_received = TRUE, updated_at = NOW()
                                WHERE reel_url = %s AND status IN ('pending', 'processing')
                            """, (caption, reel_url))
                            conn.commit()
                        else:
                            app.logger.info(f"ℹ️ [Job {job_id}] No pending post, caption stored for future use")
                            cur.execute("""
                                UPDATE pending_posts SET caption = %s, webhook_received = TRUE, updated_at = NOW()
                                WHERE reel_url = %s
                            """, (caption, reel_url))
                            conn.commit()
                
                cur.close()
                conn.close()
                
                return jsonify({
                    "status": "success", 
                    "message": "Caption stored and post processed", 
                    "job_id": job_id,
                    "post_id": post_id
                })
                
        except Exception as e:
            app.logger.error(f"❌ [Job {job_id}] Failed to store caption: {e}")
            import traceback
            app.logger.error(traceback.format_exc())
            return jsonify({
                "status": "error", 
                "message": f"Failed to store caption: {str(e)}", 
                "job_id": job_id
            }), 500
            
    elif status == 'failed':
        app.logger.warning(f"⚠️ [Job {job_id}] Caption fetch failed: {error}")
        if reel_url in CAPTION_FETCH_STATUS:
            CAPTION_FETCH_STATUS[reel_url]['error'] = error
        
        if post_id:
            try:
                conn = get_db_connection()
                if conn:
                    cur = conn.cursor()
                    cur.execute("""
                        UPDATE scheduled_posts 
                        SET status = 'failed', error_message = %s, updated_at = NOW()
                        WHERE id = %s AND status = 'processing'
                    """, (error or 'Caption fetch failed', post_id))
                    conn.commit()
                    cur.close()
                    conn.close()
                    app.logger.info(f"✅ [Job {job_id}] Marked scheduled post {post_id} as failed")
            except Exception as e:
                app.logger.error(f"❌ [Job {job_id}] Failed to mark scheduled post as failed: {e}")
        
        try:
            conn = get_db_connection()
            if conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE pending_posts SET status = 'failed', error_message = %s, updated_at = NOW()
                    WHERE reel_url = %s AND status IN ('pending', 'processing')
                """, (error or 'Caption fetch failed', reel_url))
                conn.commit()
                cur.close()
                conn.close()
                app.logger.info(f"✅ [Job {job_id}] Marked pending post as failed")
        except Exception as e:
            app.logger.error(f"❌ [Job {job_id}] Failed to mark pending post as failed: {e}")
    
    return jsonify({"status": "success", "message": "Webhook received", "job_id": job_id})


# ============== PROCESS POST WITH CAPTION (NEW FLOW) ==============

def process_post_with_caption(post, caption):
    """
    Process a scheduled post that now has a caption.
    Publishes to the correct platform based on post['platform'].
    """
    try:
        # ✅ Use the correct IDs from aliases
        scheduled_id = post.get('scheduled_id')  # This is the SCHEDULED post ID
        pipeline_id = post.get('pipeline_id')    # This is the PIPELINE ID

        # ← CHANGED: read the platform (defaults to facebook for legacy rows)
        pipeline_platform = (post.get('platform') or 'facebook').lower()

        app.logger.info(f"📤 Processing post with caption")
        app.logger.info(f"   Scheduled ID: {scheduled_id}")
        app.logger.info(f"   Pipeline ID:  {pipeline_id}")
        app.logger.info(f"   Platform:     {pipeline_platform}")

        if not scheduled_id:
            app.logger.error("❌ No scheduled_id found in post")
            return

        # This legacy/webhook path must never publish a row already claimed by
        # the main scheduler. Only transition pending -> processing here.
        claim_conn = get_db_connection()
        claim_cur = None
        claimed_here = False
        try:
            claim_cur = claim_conn.cursor()
            claim_cur.execute("""
                UPDATE scheduled_posts
                SET status = 'processing', updated_at = NOW()
                WHERE id = %s AND status = 'pending'
                RETURNING id
            """, (scheduled_id,))
            claimed_here = bool(claim_cur.fetchone())
            claim_conn.commit()
        except Exception:
            try: claim_conn.rollback()
            except Exception: pass
        finally:
            if claim_cur: claim_cur.close()
            claim_conn.close()

        if not claimed_here:
            app.logger.info(
                f"⏭️ Legacy caption publisher skipped {scheduled_id}: already claimed/handled."
            )
            return

        # ============================================================
        # STEP 1: ALWAYS fetch a FRESH video URL — no cache, no DB.
        # The URL stored on the scheduled post may be an expired
        # fdown.vn signed link from a previous run.
        # ============================================================
        app.logger.info(
            f"📥 Fetching FRESH video URL for post {scheduled_id}..."
        )
        direct_video_url = get_direct_video_url(
            post['reel_url'],
            pipeline_id=pipeline_id,
            post_id=scheduled_id,
            profile_username=post.get('profile_username')
        )

        if not direct_video_url:
            app.logger.error(
                f"❌ No fresh video URL for post {scheduled_id} — "
                f"leaving it pending for retry"
            )
            # Do NOT mark as failed. The post remains in whatever
            # status it had so a later run can retry with a live URL.
            return

        app.logger.info(f"🎬✅ Fresh video URL: {direct_video_url[:60]}...")

        # ============================================================
        # STEP 2: Publish via the platform dispatcher
        # ============================================================
        app.logger.info(
            f"📤 Publishing to {pipeline_platform} "
            f"(key: {post.get('zernio_key_id') or post.get('buffer_key_id')})"
        )

        # ← CHANGED: dispatch_publish reads post['platform'] and picks the right publisher.
        # The `post` dict must contain the same keys a pipeline row would:
        #   facebook:  facebook_account_id, zernio_key_id
        #   twitter:   buffer_channel_id,   buffer_key_id
        #   tiktok:    buffer_channel_id,   buffer_key_id
        result = dispatch_publish(
            pipeline=post,
            video_url=direct_video_url,
            caption=caption,
            scheduled_post_id=scheduled_id
        )

        conn = get_db_connection()
        if not conn:
            app.logger.error("❌ No database connection")
            return

        cur = conn.cursor()

        # ---------- Success OR idempotent "already posted" ----------
        if result and not result.get('error'):
            already_posted = result.get('already_posted', False)

            # ← CHANGED: Facebook returns post._id; Buffer returns post.id
            post_result_id = (
                result.get('post', {}).get('_id')
                or result.get('post', {}).get('id')
                or result.get('post_id')
            )

            # ← CHANGED: Buffer returns external_url at the top level.
            # Fall back to Facebook's platforms[].publishedUrl shape.
            post_url = result.get('external_url')
            if not post_url:
                for platform in result.get('post', {}).get('platforms', []):
                    if platform.get('platform') == 'facebook':
                        post_url = platform.get('publishedUrl')
                        break

            mark_reel_as_posted(
                pipeline_id=pipeline_id,
                reel_url=post['reel_url'],
                direct_video_url=direct_video_url,
                caption=caption,
                facebook_post_id=post_result_id,
                facebook_post_url=post_url,
                status='success',
                error_message=(
                    'Already posted (dedup)' if already_posted else None
                )
            )

            # ✅ CRITICAL: Update scheduled_posts using scheduled_id
            cur.execute("""
                UPDATE scheduled_posts
                SET status = 'posted', posted_at = NOW(), updated_at = NOW()
                WHERE id = %s
            """, (scheduled_id,))
            conn.commit()

            if already_posted:
                # ← CHANGED: log shows the correct platform
                app.logger.info(
                    f"♻️ Post {scheduled_id} already existed on "
                    f"{pipeline_platform} (existingPostId={post_result_id})"
                )
            else:
                app.logger.info(
                    f"✅ Post {scheduled_id} published to "
                    f"{pipeline_platform} and marked as posted!"
                )

        # ---------- Genuine failure ----------
        else:
            error_msg = (
                result.get('error', 'Unknown error')
                if result else 'Unknown error'
            )
            # ← CHANGED: log shows the correct platform
            app.logger.error(
                f"❌ {pipeline_platform} publish failed: {error_msg}"
            )

            mark_reel_as_posted(
                pipeline_id=pipeline_id,
                reel_url=post['reel_url'],
                direct_video_url=direct_video_url,
                caption=caption,
                status='failed',
                error_message=str(error_msg)
            )

            cur.execute("""
                UPDATE scheduled_posts
                SET status = 'failed', error_message = %s, updated_at = NOW()
                WHERE id = %s
            """, (str(error_msg), scheduled_id))
            conn.commit()

        update_pipeline_stats(pipeline_id, 0, 0)
        cur.close()
        conn.close()

    except Exception as e:
        app.logger.error(f"❌ Error processing post from webhook: {e}")
        import traceback
        app.logger.error(traceback.format_exc())

# ============== CAPTION STATUS ROUTES ==============

@app.route("/api/caption-status/<path:reel_url>", methods=["GET"])
def get_caption_status(reel_url):
    decoded_url = re.sub(r'^/(.+)$', r'\1', reel_url)
    status = get_caption_fetch_status(decoded_url)
    return jsonify({"status": "success", "reel_url": decoded_url, "fetch_status": status})

@app.route("/api/caption-status-dual/<path:reel_url>", methods=["GET"])
def get_caption_status_dual(reel_url):
    decoded_url = re.sub(r'^/(.+)$', r'\1', reel_url)
    status = CAPTION_FETCH_STATUS.get(decoded_url, {})
    return jsonify({"status": "success", "reel_url": decoded_url, "fetch_status": status, "dual_request_details": {"wake_up_sent": status.get('wake_up_sent', False), "real_fetch_attempts": status.get('real_fetch_attempts', 0), "webhook_received": status.get('webhook_received', False), "retry_count": status.get('retry_count', 0)}})

@app.route("/api/caption-status", methods=["GET"])
def get_all_caption_status():
    return jsonify({"status": "success", "total": len(CAPTION_FETCH_STATUS), "statuses": CAPTION_FETCH_STATUS})

# ============== PIPELINE API ROUTES ==============

@app.route('/api/pipelines', methods=['GET'])
def get_pipelines():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        # ✅ Set isolation level to READ COMMITTED to avoid deadlocks
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED)
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # ✅ FIX 1: Get pipelines first WITHOUT LEFT JOIN
        cur.execute("""
            SELECT 
                p.id,
                p.name,
                p.profile_username,
                p.facebook_account_id,
                p.facebook_page_name,
                p.daily_limit,
                p.is_active,
                p.last_run,
                p.total_posted,
                p.created_at,
                p.updated_at,
                p.zernio_key_id
            FROM pipelines p
            ORDER BY p.created_at DESC
        """)
        pipelines = cur.fetchall()
        
        # ✅ FIX 2: Get counts separately for each pipeline
        for pipeline in pipelines:
            pipeline_id = pipeline['id']
            
            # Get posted_reels counts with simple queries
            cur.execute("""
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'success') as success_count,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed_count,
                    MAX(posted_at) as last_post_time
                FROM posted_reels 
                WHERE pipeline_id = %s
            """, (pipeline_id,))
            stats = cur.fetchone()
            
            pipeline['success_count'] = stats['success_count'] or 0
            pipeline['failed_count'] = stats['failed_count'] or 0
            pipeline['last_post_time'] = stats['last_post_time']
            pipeline['total_posted_count'] = stats['success_count'] or 0
            
            # Get scheduled_posts counts
            cur.execute("""
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
                    COUNT(*) FILTER (WHERE status = 'processing') as processing_count,
                    COUNT(*) FILTER (WHERE status = 'posted') as posted_count,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed_count,
                    COUNT(*) as total_scheduled
                FROM scheduled_posts 
                WHERE pipeline_id = %s
            """, (pipeline_id,))
            scheduled_counts = cur.fetchone()
            
            # Get pending_posts counts (backward compatibility)
            cur.execute("""
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
                    COUNT(*) FILTER (WHERE status = 'processing') as processing_count,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed_count
                FROM pending_posts 
                WHERE pipeline_id = %s
            """, (pipeline_id,))
            pending_counts = cur.fetchone()
            
            # Combine counts from both tables
            total_pending = (scheduled_counts['pending_count'] or 0) + (pending_counts['pending_count'] or 0)
            total_processing = (scheduled_counts['processing_count'] or 0) + (pending_counts['processing_count'] or 0)
            total_failed = (scheduled_counts['failed_count'] or 0) + (pending_counts['failed_count'] or 0)
            total_posted = (scheduled_counts['posted_count'] or 0)
            
            pipeline['pending_posts'] = total_pending
            pipeline['processing_posts'] = total_processing
            pipeline['posted_posts'] = total_posted
            pipeline['failed_posts'] = total_failed
            pipeline['total_scheduled'] = scheduled_counts['total_scheduled'] or 0
        
        cur.close()
        conn.close()
        
        return jsonify({"status": "success", "pipelines": pipelines})
        
    except psycopg2.errors.DeadlockDetected:
        app.logger.warning("⚠️ Deadlock detected in get_pipelines, retrying...")
        conn.rollback()
        # Retry once
        try:
            return get_pipelines()
        except Exception as retry_e:
            return jsonify({"error": f"Deadlock retry failed: {str(retry_e)}"}), 500
    except Exception as e:
        app.logger.error(f"Error fetching pipelines: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            conn.close()
        except:
            pass

@app.route('/api/pipelines', methods=['POST'])
def create_pipeline():
    data = request.get_json(silent=True) or {}
    name = data.get('name')
    profile_username = data.get('profile_username')
    daily_limit = data.get('daily_limit', 2)

    # ← CHANGED: platform-first validation
    platform = (data.get('platform') or 'facebook').strip().lower()

    # Facebook-specific fields
    facebook_account_id = data.get('facebook_account_id')
    zernio_key_id = data.get('zernio_key_id')

    # ← CHANGED: Buffer-specific fields (Twitter / TikTok)
    buffer_key_id = data.get('buffer_key_id')
    buffer_channel_id = data.get('buffer_channel_id')
    buffer_channel_name = data.get('buffer_channel_name')

    # ← CHANGED: name + profile_username required for all platforms
    if not name or not profile_username:
        return jsonify({
            "error": "name and profile_username are required"
        }), 400

    # ← CHANGED: per-platform validation
    if platform == 'facebook':
        if not facebook_account_id:
            return jsonify({
                "error": "facebook_account_id is required for facebook platform"
            }), 400
    elif platform in ('twitter', 'tiktok'):
        if not buffer_key_id or not buffer_channel_id:
            return jsonify({
                "error": (
                    f"buffer_key_id and buffer_channel_id are required "
                    f"for {platform} platform"
                )
            }), 400
    else:
        return jsonify({
            "error": f"Unsupported platform: {platform}"
        }), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO pipelines (
                id, name, profile_username, facebook_account_id, daily_limit,
                is_active, zernio_key_id, platform,
                buffer_key_id, buffer_channel_id, buffer_channel_name
            )
            VALUES (
                gen_random_uuid(), %s, %s, %s, %s,
                TRUE, %s, %s,
                %s, %s, %s
            )
            RETURNING id
        """, (
            name,
            profile_username,
            facebook_account_id or '',   # ← keep NOT NULL constraint happy for buffer pipelines
            daily_limit,
            zernio_key_id,
            platform,
            buffer_key_id,
            buffer_channel_id,
            buffer_channel_name,
        ))
        pipeline_id = cur.fetchone()[0]
        conn.commit()

        app.logger.info(
            f"✅ Created {platform} pipeline '{name}' "
            f"(profile=@{profile_username}, id={pipeline_id})"
        )

        return jsonify({
            "status": "success",
            "message": f"{platform} pipeline created",
            "pipeline_id": pipeline_id,
            "platform": platform,
        })
    except Exception as e:
        app.logger.error(f"❌ create_pipeline error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@app.route('/api/pipelines/<pipeline_id>', methods=['PUT'])
def update_pipeline(pipeline_id):
    data = request.get_json(silent=True) or {}
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        updates = []
        params = []

        # Existing fields
        if 'name' in data:
            updates.append("name = %s"); params.append(data['name'])
        if 'profile_username' in data:
            updates.append("profile_username = %s"); params.append(data['profile_username'])
        if 'facebook_account_id' in data:
            updates.append("facebook_account_id = %s"); params.append(data['facebook_account_id'])
        if 'daily_limit' in data:
            updates.append("daily_limit = %s"); params.append(data['daily_limit'])
        if 'is_active' in data:
            updates.append("is_active = %s"); params.append(data['is_active'])
        if 'zernio_key_id' in data:
            updates.append("zernio_key_id = %s"); params.append(data['zernio_key_id'])

        # ← CHANGED: Buffer + platform fields
        if 'platform' in data:
            updates.append("platform = %s"); params.append(data['platform'])
        if 'buffer_key_id' in data:
            updates.append("buffer_key_id = %s"); params.append(data['buffer_key_id'])
        if 'buffer_channel_id' in data:
            updates.append("buffer_channel_id = %s"); params.append(data['buffer_channel_id'])
        if 'buffer_channel_name' in data:
            updates.append("buffer_channel_name = %s"); params.append(data['buffer_channel_name'])

        if not updates:
            return jsonify({"error": "No fields to update"}), 400

        updates.append("updated_at = NOW()")
        params.append(pipeline_id)

        cur = conn.cursor()
        cur.execute(f"UPDATE pipelines SET {', '.join(updates)} WHERE id = %s", params)
        conn.commit()

        app.logger.info(f"✏️ Updated pipeline {pipeline_id}: {updates}")

        return jsonify({"status": "success", "message": "Pipeline updated"})
    except Exception as e:
        app.logger.error(f"❌ update_pipeline error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/pipelines/<pipeline_id>/run', methods=['POST'])
def run_pipeline_endpoint(pipeline_id):
    result = run_pipeline(pipeline_id)
    if result.get('error'):
        return jsonify(result), 500
    return jsonify(result)

@app.route('/api/pipelines/run-all', methods=['POST'])
def run_all_pipelines_endpoint():
    result = run_all_active_pipelines()
    if result.get('error'):
        return jsonify(result), 500
    return jsonify(result)

@app.route('/api/pipelines/<pipeline_id>/reset', methods=['POST'])
def reset_pipeline(pipeline_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM posted_reels WHERE pipeline_id = %s", (pipeline_id,))
        cur.execute("UPDATE pipelines SET total_posted = 0, updated_at = NOW() WHERE id = %s", (pipeline_id,))
        conn.commit()
        return jsonify({"status": "success", "message": "Pipeline reset - all reels marked as unposted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/pipelines/<pipeline_id>/pending', methods=['GET'])
def get_pending_posts(pipeline_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, reel_url, direct_video_url, pipeline_id, profile_username,
                   facebook_account_id, caption, created_at, updated_at, status,
                   attempts, error_message, facebook_post_id, facebook_post_url,
                   wakeup_sent, real_fetch_attempts, webhook_received
            FROM pending_posts WHERE pipeline_id = %s ORDER BY created_at DESC
        """, (pipeline_id,))
        pending = cur.fetchall()
        return jsonify({"status": "success", "pending": pending, "count": len(pending)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/pipelines/<pipeline_id>/posted', methods=['GET'])
def get_posted_reels(pipeline_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT reel_url, direct_video_url, caption, facebook_post_id,
                   facebook_post_url, posted_at, status, error_message
            FROM posted_reels WHERE pipeline_id = %s ORDER BY posted_at DESC LIMIT 50
        """, (pipeline_id,))
        posted = cur.fetchall()
        return jsonify({"status": "success", "posted": posted, "count": len(posted)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

# ============== GET SINGLE PIPELINE ==============

@app.route('/api/pipelines/<pipeline_id>', methods=['GET'])
def get_pipeline(pipeline_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT p.*, COUNT(pr.id) as total_posted_count,
                   SUM(CASE WHEN pr.status = 'success' THEN 1 ELSE 0 END) as success_count,
                   SUM(CASE WHEN pr.status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                   MAX(pr.posted_at) as last_post_time
            FROM pipelines p
            LEFT JOIN posted_reels pr ON p.id = pr.pipeline_id
            WHERE p.id = %s GROUP BY p.id
        """, (pipeline_id,))
        pipeline = cur.fetchone()
        if not pipeline:
            return jsonify({"error": "Pipeline not found"}), 404
        cur.execute("SELECT COUNT(*) as pending_count FROM pending_posts WHERE pipeline_id = %s AND status IN ('pending', 'processing')", (pipeline_id,))
        pending = cur.fetchone()
        pipeline['pending_posts'] = pending['pending_count'] if pending else 0
        return jsonify({"status": "success", "pipeline": pipeline})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

# ============== DELETE PIPELINE ==============

@app.route('/api/pipelines/<pipeline_id>', methods=['DELETE'])
def delete_pipeline(pipeline_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM pipelines WHERE id = %s", (pipeline_id,))
        pipeline = cur.fetchone()
        if not pipeline:
            return jsonify({"error": "Pipeline not found"}), 404
        pipeline_name = pipeline[1]
        cur.execute("DELETE FROM pending_posts WHERE pipeline_id = %s", (pipeline_id,))
        pending_deleted = cur.rowcount
        cur.execute("DELETE FROM posted_reels WHERE pipeline_id = %s", (pipeline_id,))
        posted_deleted = cur.rowcount
        cur.execute("DELETE FROM pipeline_runs WHERE pipeline_id = %s", (pipeline_id,))
        runs_deleted = cur.rowcount
        cur.execute("DELETE FROM pipelines WHERE id = %s", (pipeline_id,))
        conn.commit()
        app.logger.info(f"🗑️ Deleted pipeline '{pipeline_name}' (ID: {pipeline_id}) with {pending_deleted} pending, {posted_deleted} posted reels, and {runs_deleted} runs")
        return jsonify({"status": "success", "message": f"Pipeline '{pipeline_name}' deleted successfully", "deleted": {"pipeline_id": pipeline_id, "pipeline_name": pipeline_name, "pending_posts_deleted": pending_deleted, "posted_reels_deleted": posted_deleted, "runs_deleted": runs_deleted}})
    except Exception as e:
        app.logger.error(f"Delete pipeline error: {e}")
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

# ============== PROCESS REELS ==============

@app.route("/api/process-reels", methods=["POST"])
def process_reels():
    data = request.get_json(silent=True) or {}
    reel_urls = data.get("reels")
    job_id = data.get("job_id")
    chunk = data.get("chunk", 1)
    total_chunks = data.get("total_chunks", 1)
    if not reel_urls or not isinstance(reel_urls, list):
        return jsonify({"error": "Missing or invalid 'reels' list"}), 400
    app.logger.info(f"📥 [Job {job_id}] Received chunk {chunk}/{total_chunks} with {len(reel_urls)} reels")
    if len(reel_urls) == 0:
        return jsonify({"status": "success", "message": "No reels to process", "job_id": job_id, "count": 0})
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        cur = conn.cursor()
        stored_count = 0
        for reel_url in reel_urls:
            try:
                cur.execute("""
                    INSERT INTO reel_cache (reel_url, direct_url, caption, created_at)
                    VALUES (%s, '', '', NOW())
                    ON CONFLICT (reel_url) DO UPDATE SET created_at = NOW()
                """, (reel_url,))
                stored_count += 1
            except Exception as e:
                app.logger.warning(f"⚠️ Failed to store reel: {reel_url[:50]}... - {e}")
        conn.commit()
        cur.close()
        conn.close()
        app.logger.info(f"✅ [Job {job_id}] Stored {stored_count}/{len(reel_urls)} reels (chunk {chunk}/{total_chunks})")
        if chunk == total_chunks:
            app.logger.info(f"🎉 [Job {job_id}] All {total_chunks} chunks received! Total reels: {len(reel_urls) * total_chunks}")
        return jsonify({"status": "success", "message": f"Stored {stored_count} reels", "job_id": job_id, "chunk": chunk, "total_chunks": total_chunks, "stored": stored_count, "total": len(reel_urls)})
    except Exception as e:
        app.logger.error(f"❌ [Job {job_id}] Error processing reels: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({"status": "error", "error": str(e), "job_id": job_id}), 500

# ============== SCHEDULED POSTS ROUTES ==============

@app.route('/api/scheduled-posts', methods=['GET'])
def get_all_scheduled_posts():
    """Get all scheduled posts with filters."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        status_filter = request.args.get('status', 'all')
        pipeline_id = request.args.get('pipeline_id')
        limit = request.args.get('limit', 50, type=int)
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        query = """
            SELECT 
                sp.id,
                sp.reel_url,
                sp.direct_video_url,
                sp.caption,
                sp.scheduled_time,
                sp.status,
                sp.created_at,
                sp.posted_at,
                sp.error_message,
                p.name as pipeline_name,
                p.profile_username
            FROM scheduled_posts sp
            LEFT JOIN pipelines p ON sp.pipeline_id = p.id
            WHERE 1=1
        """
        params = []
        
        if status_filter != 'all':
            query += " AND sp.status = %s"
            params.append(status_filter)
        
        if pipeline_id:
            query += " AND sp.pipeline_id = %s"
            params.append(pipeline_id)
        
        query += " ORDER BY sp.scheduled_time ASC LIMIT %s"
        params.append(limit)
        
        cur.execute(query, params)
        scheduled_posts = cur.fetchall()
        
        # Get counts by status
        cur.execute("""
            SELECT 
                status,
                COUNT(*) as count
            FROM scheduled_posts
            GROUP BY status
        """)
        counts = cur.fetchall()
        count_dict = {c['status']: c['count'] for c in counts}
        
        return jsonify({
            "status": "success",
            "scheduled_posts": scheduled_posts,
            "counts": {
                "total": sum(count_dict.values()),
                "pending": count_dict.get('pending', 0),
                "posted": count_dict.get('posted', 0),
                "failed": count_dict.get('failed', 0)
            },
            "total": len(scheduled_posts)
        })
        
    except Exception as e:
        app.logger.error(f"Error fetching scheduled posts: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/scheduled-posts/<post_id>', methods=['DELETE'])
def delete_scheduled_post(post_id):
    """Delete a scheduled post."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM scheduled_posts WHERE id = %s RETURNING id", (post_id,))
        deleted = cur.fetchone()
        conn.commit()
        
        if deleted:
            return jsonify({"status": "success", "message": "Post deleted"})
        else:
            return jsonify({"error": "Post not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/scheduled-posts/<post_id>', methods=['PUT'])
def update_scheduled_post(post_id):
    """Update a scheduled post (reschedule or change status)."""
    data = request.get_json(silent=True) or {}
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        updates = []
        params = []
        
        if 'scheduled_time' in data:
            updates.append("scheduled_time = %s")
            params.append(data['scheduled_time'])
        
        if 'status' in data:
            updates.append("status = %s")
            params.append(data['status'])
        
        if not updates:
            return jsonify({"error": "No fields to update"}), 400
        
        updates.append("updated_at = NOW()")
        params.append(post_id)
        
        cur.execute(f"""
            UPDATE scheduled_posts 
            SET {', '.join(updates)}
            WHERE id = %s
            RETURNING id
        """, params)
        
        updated = cur.fetchone()
        conn.commit()
        
        if updated:
            return jsonify({"status": "success", "message": "Post updated"})
        else:
            return jsonify({"error": "Post not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

# ============== SCHEDULER ENDPOINTS ==============

@app.route("/api/scheduler/process", methods=["POST"])
def process_scheduled_posts():
    """Global scheduler. Posts are atomically claimed and processed sequentially."""
    try:
        recover_stale_processing_posts()
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        cur = None
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT id FROM pipelines WHERE is_active = TRUE ORDER BY created_at ASC")
            pipeline_ids = [row['id'] for row in cur.fetchall()]
        finally:
            if cur:
                cur.close()
            conn.close()

        results = []
        total_posted = 0
        total_failed = 0

        for pipeline_id in pipeline_ids:
            result = run_pipeline(pipeline_id)
            results.append({"pipeline_id": pipeline_id, "result": result})
            total_posted += int(result.get('posted', 0) or 0)
            total_failed += int(result.get('failed', 0) or 0)

        return jsonify({
            "status": "success",
            "message": "Scheduler completed with duplicate protection",
            "posted": total_posted,
            "failed": total_failed,
            "results": results
        })
    except Exception as e:
        app.logger.exception("❌ Scheduler error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/scheduler/daily", methods=["POST"])
def daily_scheduler():
    """
    Daily scheduler - runs at midnight (12:00 AM).
    Schedules posts for all active pipelines with random times throughout the ENTIRE day (12 AM - 11 PM).
    Captions will be fetched during posting.
    """
    app.logger.info("🕐 Running daily scheduler at midnight...")
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # ============================================================
        # STEP 1: Get all active pipelines
        # ============================================================
        cur.execute("""
            SELECT 
                id, 
                name, 
                profile_username, 
                facebook_account_id,
                daily_limit,
                is_active,
                zernio_key_id
            FROM pipelines 
            WHERE is_active = TRUE
            ORDER BY name
        """)
        pipelines = cur.fetchall()
        
        if not pipelines:
            app.logger.info("ℹ️ No active pipelines found")
            cur.close()
            conn.close()
            return jsonify({
                "status": "success",
                "message": "No active pipelines found",
                "total_pipelines": 0,
                "total_scheduled": 0
            })
        
        app.logger.info(f"📊 Found {len(pipelines)} active pipelines")
        
        total_scheduled = 0
        total_failed = 0
        results = []
        
        # ============================================================
        # STEP 2: Process each pipeline
        # ============================================================
        for pipeline in pipelines:
            pipeline_id = pipeline['id']
            pipeline_name = pipeline['name']
            profile_username = pipeline['profile_username']
            daily_limit = pipeline['daily_limit'] or 2
            
            app.logger.info(f"📋 Processing pipeline: {pipeline_name} (daily_limit: {daily_limit})")
            
            try:
                # Get unposted reels for this pipeline
                unposted = get_unposted_reels(profile_username, pipeline_id, limit=100)
                
                if not unposted:
                    app.logger.info(f"ℹ️ No unposted reels for pipeline: {pipeline_name}")
                    results.append({
                        "pipeline_id": pipeline_id,
                        "pipeline_name": pipeline_name,
                        "scheduled": 0,
                        "available": 0,
                        "message": "No unposted reels available"
                    })
                    continue
                
                # Filter out already scheduled reels (pending posts)
                cur.execute("""
                    SELECT reel_url FROM scheduled_posts 
                    WHERE pipeline_id = %s AND status IN ('pending', 'processing')
                """, (pipeline_id,))
                already_scheduled = {row['reel_url'] for row in cur.fetchall()}
                
                available_reels = [r for r in unposted if r.get('url') not in already_scheduled]
                
                if not available_reels:
                    app.logger.info(f"ℹ️ All reels already scheduled for pipeline: {pipeline_name}")
                    results.append({
                        "pipeline_id": pipeline_id,
                        "pipeline_name": pipeline_name,
                        "scheduled": 0,
                        "available": len(unposted),
                        "message": "All reels already scheduled"
                    })
                    continue
                
                # Determine how many to schedule (up to daily_limit)
                schedule_count = min(daily_limit, len(available_reels))
                
                app.logger.info(f"📝 Scheduling {schedule_count} posts for pipeline: {pipeline_name}")
                
                # ============================================================
                # STEP 3: Generate random times throughout the ENTIRE day (12 AM - 11 PM)
                # WITH RANDOM MINUTES AND SECONDS
                # ============================================================
                times = generate_random_post_times(schedule_count, start_hour=0, end_hour=23)
                
                # ============================================================
                # STEP 4: Create scheduled posts with random times
                # ============================================================
                scheduled_count = 0
                failed_count = 0
                
                for i, reel in enumerate(available_reels[:schedule_count]):
                    try:
                        # Get the random time for this post
                        if i < len(times):
                            scheduled_time = times[i]
                        else:
                            # Fallback: generate a random time (any hour, minute, second)
                            random_hour = random.randint(0, 23)
                            random_minute = random.randint(0, 59)
                            random_second = random.randint(0, 59)
                            scheduled_time = datetime.utcnow().replace(
                                hour=random_hour,
                                minute=random_minute,
                                second=random_second,
                                microsecond=0
                            )
                            # Ensure future time (add a day if needed)
                            if scheduled_time < datetime.utcnow():
                                scheduled_time += timedelta(days=1)
                        
                        reel_url = reel.get('url') if isinstance(reel, dict) else reel
                        caption = reel.get('caption', '') if isinstance(reel, dict) else ''
                        
                        # Get direct video URL from cache if available
                        direct_video_url = get_direct_url_from_cache_only(reel_url) or ''
                        
                        # Check if already scheduled (double-check)
                        cur.execute(
                            "SELECT id FROM scheduled_posts WHERE reel_url = %s AND pipeline_id = %s AND status = 'pending'",
                            (reel_url, pipeline_id)
                        )
                        existing = cur.fetchone()
                        
                        if existing:
                            app.logger.warning(f"⚠️ Reel already scheduled: {reel_url[:50]}...")
                            continue
                        
                        # Insert the scheduled post with the random time
                        cur.execute("""
                            INSERT INTO scheduled_posts (
                                reel_url,
                                direct_video_url,
                                caption,
                                pipeline_id,
                                scheduled_time,
                                status,
                                created_at,
                                updated_at
                            )
                            VALUES (%s, %s, %s, %s, %s, 'pending', NOW(), NOW())
                            RETURNING id
                        """, (
                            reel_url,
                            direct_video_url,
                            caption,
                            pipeline_id,
                            scheduled_time.isoformat()
                        ))
                        
                        scheduled_count += 1
                        
                        # Log the scheduled time in 12-hour format with minutes
                        time_str = scheduled_time.strftime('%I:%M %p')
                        app.logger.info(f"✅ Scheduled: {reel_url[:50]}... at {time_str}")
                        
                    except Exception as e:
                        app.logger.error(f"❌ Failed to schedule post: {e}")
                        failed_count += 1
                
                total_scheduled += scheduled_count
                total_failed += failed_count
                
                results.append({
                    "pipeline_id": pipeline_id,
                    "pipeline_name": pipeline_name,
                    "scheduled": scheduled_count,
                    "failed": failed_count,
                    "available": len(available_reels),
                    "daily_limit": daily_limit
                })
                
                app.logger.info(f"✅ Pipeline {pipeline_name}: scheduled {scheduled_count}, failed {failed_count}")
                
            except Exception as e:
                app.logger.error(f"❌ Error processing pipeline {pipeline_name}: {e}")
                import traceback
                app.logger.error(traceback.format_exc())
                results.append({
                    "pipeline_id": pipeline_id,
                    "pipeline_name": pipeline_name,
                    "scheduled": 0,
                    "error": str(e)
                })
                total_failed += 1
        
        # ============================================================
        # STEP 5: Clean up old scheduled posts
        # ============================================================
        try:
            cur.execute("""
                UPDATE scheduled_posts 
                SET status = 'failed', 
                    error_message = 'Expired - not posted within 48 hours',
                    updated_at = NOW()
                WHERE status = 'pending' 
                AND scheduled_time < NOW() - INTERVAL '48 hours'
            """)
            conn.commit()
            expired_count = cur.rowcount
            app.logger.info(f"🧹 Cleaned up {expired_count} expired scheduled posts")
        except Exception as e:
            app.logger.error(f"Cleanup error: {e}")
        
        cur.close()
        conn.close()
        
        # ============================================================
        # STEP 6: Process any due posts (including newly scheduled ones)
        # ============================================================
        process_result = run_all_active_pipelines()
        
        # ============================================================
        # STEP 7: Return summary
        # ============================================================
        return jsonify({
            "status": "success",
            "message": f"Daily scheduler completed: {total_scheduled} posts scheduled, {total_failed} failed",
            "total_pipelines": len(pipelines),
            "total_scheduled": total_scheduled,
            "total_failed": total_failed,
            "results": results,
            "process_result": process_result,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f"❌ Daily scheduler error: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            conn.close()
        except:
            pass


# ============================================================
# RANDOM TIME GENERATOR - FULL 24-HOUR DAY WITH RANDOM MINUTES
# ============================================================

def generate_random_post_times(num_posts, start_hour=0, end_hour=23):
    """
    Generate random post times spread throughout the ENTIRE day (12 AM - 11 PM).
    Each post gets random minutes and seconds for natural distribution.
    
    Args:
        num_posts: Number of posts to schedule
        start_hour: Earliest hour to post (default: 0 = 12:00 AM)
        end_hour: Latest hour to post (default: 23 = 11:00 PM)
    
    Returns:
        List of random datetime objects (UTC) with random minutes and seconds
    """
    if num_posts == 0:
        return []
    
    # If only 1 post, pick random time with random minutes and seconds
    if num_posts == 1:
        random_hour = random.randint(start_hour, end_hour)
        random_minute = random.randint(0, 59)
        random_second = random.randint(0, 59)
        random_time = datetime.utcnow().replace(
            hour=random_hour,
            minute=random_minute,
            second=random_second,
            microsecond=0
        )
        # Ensure time is in the future (add a day if needed)
        if random_time < datetime.utcnow():
            random_time += timedelta(days=1)
        return [random_time]
    
    # Multiple posts - distribute randomly across the entire 24-hour day
    total_minutes = 24 * 60  # Full 24 hours
    
    # Generate random times ensuring minimum spacing (45 minutes)
    min_spacing = 45
    max_attempts = 100
    
    valid_times = []
    for attempt in range(max_attempts):
        # Generate random minutes with random offsets
        minutes = sorted([random.randint(0, total_minutes - 1) for _ in range(num_posts)])
        valid = True
        for i in range(1, len(minutes)):
            if minutes[i] - minutes[i-1] < min_spacing:
                valid = False
                break
        if valid and num_posts > 1:
            if minutes[-1] - minutes[0] < min_spacing * (num_posts - 1):
                valid = False
        if valid:
            valid_times = minutes
            break
    
    # If no valid times found, use even spacing with random offset
    if not valid_times:
        spacing = total_minutes // num_posts
        valid_times = [i * spacing + random.randint(-spacing//3, spacing//3) for i in range(num_posts)]
        valid_times = sorted([max(0, min(total_minutes - 1, t)) for t in valid_times])
    
    # Convert minutes to datetime objects with random seconds
    times = []
    base_time = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    for minute in valid_times:
        hour = minute // 60
        minute_of_hour = minute % 60
        random_second = random.randint(0, 59)
        
        post_time = base_time.replace(
            hour=hour,
            minute=minute_of_hour,
            second=random_second,
            microsecond=0
        )
        
        # Ensure time is in the future (add a day if needed)
        while post_time < datetime.utcnow():
            post_time += timedelta(days=1)
        
        times.append(post_time)
    
    # Sort times and return
    return sorted(times)
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        

# ============== DEBUG ROUTES ==============

@app.route("/api/debug/cookies", methods=["GET"])
def debug_cookies():
    cookie_file = get_cookie_file()
    if cookie_file and os.path.exists(cookie_file):
        with open(cookie_file, 'r') as f:
            first_lines = f.readlines()[:10]
        return jsonify({"cookie_file_exists": True, "cookie_file_path": cookie_file, "sample_cookies": first_lines, "has_session_cookie": any("sessionid" in line for line in first_lines), "username": session.get('instagram_username') or 'Unknown', "has_encrypted": bool(session.get('instagram_encrypted')), "session_permanent": session.permanent})
    return jsonify({"cookie_file_exists": False, "message": "No cookie file found", "has_encrypted": bool(session.get('instagram_encrypted')), "session_permanent": session.permanent})

@app.route("/api/debug/session", methods=["GET"])
def debug_session():
    db_cookies = get_cookies_from_db()
    return jsonify({"session_keys": list(session.keys()), "session_size": len(str(dict(session))), "instagram_username": session.get('instagram_username'), "instagram_saved": session.get('instagram_saved', False), "session_permanent": session.permanent, "db_cookies": db_cookies is not None, "db_username": db_cookies.get('username') if db_cookies else None, "user_id_from_cookie": request.cookies.get('user_id'), "user_id_from_session": session.get('user_id'), "note": "Large cookie data is stored in database, not session"})

@app.route("/api/init", methods=["GET"])
def init_session():
    user_id = FIXED_USER_ID
    session['user_id'] = user_id
    db_cookies = get_cookies_from_db()
    if db_cookies:
        session['instagram_username'] = db_cookies.get('username', 'Instagram User')
        session['instagram_saved'] = True
    return jsonify({"status": "success", "user_id": user_id, "has_cookies": bool(db_cookies)})

@app.route("/api/session/clear-large", methods=["POST"])
def clear_large_session():
    session.pop('instagram_encrypted', None)
    session.pop('cookies_data', None)
    session.pop('username', None)
    session.pop('cookie_file', None)
    return jsonify({"status": "success", "message": "Large session data cleared. Session size should now be under 4KB.", "new_session_size": len(str(dict(session)))})

@app.route("/api/commands/status", methods=["GET"])
def api_status():
    cookie_status = "configured" if get_cookie_file() else "not configured"
    return jsonify({"status": "running", "version": "1.5.0", "cookies": cookie_status, "zernio_connected": bool(get_best_zernio_key()), "zernio_keys": len(ZERNIO_KEYS), "download_history_count": 0, "recent_downloads": []})

@app.route("/api/pending-posts", methods=["GET"])
def get_all_pending_posts():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT pp.*, p.name as pipeline_name
            FROM pending_posts pp
            LEFT JOIN pipelines p ON pp.pipeline_id = p.id
            WHERE pp.status IN ('pending', 'processing')
            ORDER BY pp.created_at DESC
        """)
        pending = cur.fetchall()
        return jsonify({"status": "success", "pending": pending, "count": len(pending)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

# ============== KEEP-ALIVE ENDPOINTS ==============

@app.route("/api/keep-alive", methods=["GET"])
def keep_alive():
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat(), "message": "I'm alive!"})

@app.route("/api/pipelines/<pipeline_id>/sync-stats", methods=["POST"])
def sync_pipeline_stats(pipeline_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM posted_reels WHERE pipeline_id = %s AND status = 'success'", (pipeline_id,))
        actual_count = cur.fetchone()[0]
        cur.execute("UPDATE pipelines SET total_posted = %s, updated_at = NOW() WHERE id = %s", (actual_count, pipeline_id))
        conn.commit()
        return jsonify({"status": "success", "pipeline_id": pipeline_id, "total_posted": actual_count, "message": f"Pipeline stats synced: {actual_count} total posted"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

# ============== APP SETTINGS ROUTES ==============

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get all app settings."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT setting_key, setting_value, setting_type, description, updated_at
            FROM app_settings
            ORDER BY setting_key
        """)
        settings = cur.fetchall()
        
        return jsonify({
            "status": "success",
            "settings": settings
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/settings/<key>', methods=['GET'])
def get_setting_endpoint(key):
    """Get a single setting."""
    value = get_setting(key)
    if value is None:
        return jsonify({"error": "Setting not found"}), 404
    
    return jsonify({
        "status": "success",
        "key": key,
        "value": value
    })







# ============== VALIDATE ZERNIO KEY ==============

@app.route('/api/zernio/validate-key', methods=['POST'])
def validate_zernio_key():
    """Validate a Zernio API key and return associated accounts."""
    data = request.get_json(silent=True) or {}
    api_key = data.get('api_key')
    
    if not api_key:
        return jsonify({"valid": False, "message": "API key required"}), 400
    
    try:
        zernio_base_url = get_zernio_base_url()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Try to fetch accounts with this key
        response = requests.get(f"{zernio_base_url}/accounts", headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            accounts = data.get('accounts', [])
            
            facebook_accounts = []
            for account in accounts:
                if account.get('platform') == 'facebook':
                    facebook_accounts.append({
                        "id": account.get('_id'),
                        "name": account.get('displayName', 'Unknown'),
                        "page_id": account.get('profileData', {}).get('id', 'N/A'),
                        "status": account.get('platformStatus', 'unknown')
                    })
            
            # Get the first Facebook account for auto-fill
            first_account = facebook_accounts[0] if facebook_accounts else None
            
            # Try to get key info from the response
            key_name = data.get('key_name') or data.get('name') or f"Key {len(facebook_accounts)} accounts"
            
            return jsonify({
                "valid": True,
                "accounts": facebook_accounts,
                "account_count": len(facebook_accounts),
                "name": key_name,
                "first_account": first_account
            })
        else:
            return jsonify({
                "valid": False,
                "message": f"Invalid API key or unable to connect. Status: {response.status_code}"
            }), 400
            
    except requests.exceptions.Timeout:
        return jsonify({"valid": False, "message": "Connection timeout - please check your key"}), 400
    except requests.exceptions.ConnectionError:
        return jsonify({"valid": False, "message": "Could not connect to Zernio API"}), 400
    except Exception as e:
        return jsonify({"valid": False, "message": str(e)}), 400








# ============== MANUAL SCHEDULER ROUTES ==============

@app.route('/api/scheduler/manual', methods=['POST'])
def manual_schedule():
    """
    Manually schedule specific reels at specific times.
    
    Request body:
    {
        "pipeline_id": "uuid",
        "schedules": [
            {"reel_url": "https://...", "scheduled_time": "2026-09-08T14:30:00Z", "caption": "optional"}
        ]
    }
    """
    data = request.get_json(silent=True) or {}
    pipeline_id = data.get('pipeline_id')
    schedules = data.get('schedules', [])
    
    if not pipeline_id:
        return jsonify({"error": "pipeline_id is required"}), 400
    
    if not schedules or len(schedules) == 0:
        return jsonify({"error": "schedules array is required"}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Verify pipeline exists
        cur.execute("SELECT id, profile_username FROM pipelines WHERE id = %s", (pipeline_id,))
        pipeline = cur.fetchone()
        if not pipeline:
            return jsonify({"error": "Pipeline not found"}), 404
        
        scheduled_count = 0
        failed_count = 0
        results = []
        
        for schedule in schedules:
            reel_url = schedule.get('reel_url', '').strip()
            scheduled_time_str = schedule.get('scheduled_time')
            caption = schedule.get('caption', '')
            
            if not reel_url or not scheduled_time_str:
                results.append({"reel_url": reel_url, "success": False, "error": "Missing reel_url or scheduled_time"})
                failed_count += 1
                continue
            
            try:
                # Parse scheduled time (supports ISO format)
                scheduled_time = datetime.fromisoformat(scheduled_time_str.replace('Z', '+00:00'))
            except ValueError:
                results.append({"reel_url": reel_url, "success": False, "error": "Invalid scheduled_time format"})
                failed_count += 1
                continue
            
            # Check if reel is already scheduled
            cur.execute(
                "SELECT id FROM scheduled_posts WHERE reel_url = %s AND status = 'pending'",
                (reel_url,)
            )
            existing = cur.fetchone()
            
            if existing:
                # Update existing
                cur.execute("""
                    UPDATE scheduled_posts 
                    SET scheduled_time = %s, caption = %s, updated_at = NOW()
                    WHERE id = %s
                """, (scheduled_time, caption, existing['id']))
                results.append({
                    "reel_url": reel_url,
                    "success": True,
                    "scheduled_time": scheduled_time.isoformat(),
                    "action": "updated"
                })
            else:
                # Insert new
                direct_video_url = get_direct_url_from_cache_only(reel_url) or ''
                
                cur.execute("""
                    INSERT INTO scheduled_posts (
                        reel_url, direct_video_url, caption, pipeline_id, scheduled_time
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (reel_url, direct_video_url, caption, pipeline_id, scheduled_time))
                
                results.append({
                    "reel_url": reel_url,
                    "success": True,
                    "scheduled_time": scheduled_time.isoformat(),
                    "action": "created",
                    "id": cur.fetchone()['id']
                })
            
            scheduled_count += 1
            conn.commit()
        
        return jsonify({
            "status": "success",
            "message": f"Scheduled {scheduled_count} posts, {failed_count} failed",
            "scheduled": scheduled_count,
            "failed": failed_count,
            "results": results
        })
        
    except Exception as e:
        app.logger.error(f"Manual scheduling error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@app.route('/api/scheduler/unposted-reels/<pipeline_id>', methods=['GET'])
def get_unposted_reels_for_scheduler(pipeline_id):
    """Get all unposted reels for a pipeline (for manual scheduling)."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get pipeline
        cur.execute("SELECT * FROM pipelines WHERE id = %s", (pipeline_id,))
        pipeline = cur.fetchone()
        if not pipeline:
            return jsonify({"error": "Pipeline not found"}), 404
        
        # Get unposted reels
        unposted = get_unposted_reels(
            pipeline['profile_username'],
            pipeline_id,
            limit=200  # Get all
        )
        
        # Get already scheduled pending posts
        cur.execute("""
            SELECT reel_url, scheduled_time, caption 
            FROM scheduled_posts 
            WHERE pipeline_id = %s AND status = 'pending'
            ORDER BY scheduled_time ASC
        """, (pipeline_id,))
        scheduled = cur.fetchall()
        scheduled_urls = {s['reel_url']: s for s in scheduled}
        
        # Enrich unposted with scheduled info
        result_reels = []
        for reel in unposted:
            reel_url = reel.get('url') if isinstance(reel, dict) else reel
            caption = reel.get('caption', '') if isinstance(reel, dict) else ''
            
            is_scheduled = reel_url in scheduled_urls
            scheduled_info = scheduled_urls.get(reel_url) if is_scheduled else None
            
            # Format scheduled time in 12-hour format for display
            scheduled_display = None
            if scheduled_info and scheduled_info['scheduled_time']:
                dt = scheduled_info['scheduled_time']
                if isinstance(dt, str):
                    dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
                hour12 = dt.hour % 12
                if hour12 == 0:
                    hour12 = 12
                ampm = "AM" if dt.hour < 12 else "PM"
                scheduled_display = f"{hour12}:{dt.minute:02d} {ampm}"
            
            result_reels.append({
                "url": reel_url,
                "caption": caption,
                "is_scheduled": is_scheduled,
                "scheduled_time": scheduled_info['scheduled_time'].isoformat() if scheduled_info else None,
                "scheduled_time_display": scheduled_display,
                "scheduled_caption": scheduled_info.get('caption', '') if scheduled_info else None
            })
        
        return jsonify({
            "status": "success",
            "pipeline": {
                "id": pipeline['id'],
                "name": pipeline['name'],
                "profile_username": pipeline['profile_username']
            },
            "reels": result_reels,
            "total": len(result_reels),
            "scheduled_count": len(scheduled)
        })
        
    except Exception as e:
        app.logger.error(f"Error getting unposted reels: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@app.route('/api/scheduler/generate-random-times', methods=['POST'])
def generate_random_times():
    """Generate random scheduled times for a given number of posts (12-hour format)."""
    data = request.get_json(silent=True) or {}
    num_posts = data.get('num_posts', 1)
    start_hour = data.get('start_hour', 8)  # 8 AM default
    end_hour = data.get('end_hour', 22)     # 10 PM default
    
    if num_posts < 1 or num_posts > 100:
        return jsonify({"error": "num_posts must be between 1 and 100"}), 400
    
    # Generate random times using existing function
    times = generate_random_post_times(num_posts, start_hour, end_hour)
    
    # Format times in 12-hour format for display
    formatted_times = []
    for t in times:
        # Convert to 12-hour format
        hour12 = t.hour % 12
        if hour12 == 0:
            hour12 = 12
        ampm = "AM" if t.hour < 12 else "PM"
        formatted_times.append({
            "iso": t.isoformat(),
            "display": f"{hour12}:{t.minute:02d} {ampm}",
            "hour": t.hour,
            "minute": t.minute
        })
    
    return jsonify({
        "status": "success",
        "times": [t["iso"] for t in formatted_times],
        "display_times": [t["display"] for t in formatted_times],
        "count": len(times)
    })






@app.route("/api/cookies/sync", methods=["POST"])
def sync_cookies_from_render():
    """
    Receive cookies from the Render cookie extractor service.
    """
    data = request.get_json(silent=True) or {}
    cookies = data.get('cookies', [])
    username = data.get('username', 'Instagram User')
    
    if not cookies:
        return jsonify({"error": "No cookies provided"}), 400
    
    try:
        # Save cookies to database
        success = save_cookies_to_db(cookies, username)
        if success:
            app.logger.info(f"✅ Synced {len(cookies)} cookies from Render service for user: {username}")
            
            # Also write to file for immediate use
            cookie_file_path = os.path.join('/tmp', 'cookies.json')
            with open(cookie_file_path, 'w') as f:
                json.dump(cookies, f, indent=2)
            
            # Write Netscape format for yt-dlp
            write_netscape_cookies(cookies, '/tmp/cookies_netscape.txt')
            
            # Write Instagram-specific cookie file
            safe_user = re.sub(r'[^a-zA-Z0-9_-]', '_', str(username or 'default'))[:40]
            instagram_cookie_file = os.path.join('/tmp', f'instagram_cookies_{safe_user}.txt')
            write_netscape_cookies(cookies, instagram_cookie_file)
            
            return jsonify({
                "status": "success",
                "message": f"Synced {len(cookies)} cookies",
                "cookies_count": len(cookies)
            })
        else:
            return jsonify({"error": "Failed to save cookies to database"}), 500
            
    except Exception as e:
        app.logger.error(f"Error syncing cookies: {e}")
        return jsonify({"error": str(e)}), 500












@app.route('/api/settings', methods=['POST', 'PUT'])
def update_setting_endpoint():
    """Update a setting."""
    data = request.get_json(silent=True) or {}
    key = data.get('key')
    value = data.get('value')
    setting_type = data.get('setting_type', 'string')
    description = data.get('description', '')
    
    if not key:
        return jsonify({"error": "key is required"}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO app_settings (setting_key, setting_value, setting_type, description, updated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (setting_key) DO UPDATE SET
                setting_value = EXCLUDED.setting_value,
                setting_type = EXCLUDED.setting_type,
                description = EXCLUDED.description,
                updated_at = NOW()
        """, (key, str(value), setting_type, description))
        conn.commit()
        
        # Update cache
        APP_SETTINGS_CACHE[key] = value
        
        cur.close()
        conn.close()
        
        return jsonify({
            "status": "success",
            "message": f"Setting '{key}' updated",
            "key": key,
            "value": value
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============== AFTER REQUEST ==============

@app.after_request
def after_request(response):
    response.set_cookie('user_id', FIXED_USER_ID, max_age=30*24*60*60, path='/', secure=os.environ.get('FLASK_ENV') == 'production' or bool(os.environ.get('VERCEL')), httponly=True, samesite='Lax')
    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
