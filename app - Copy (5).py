import os
import re
import uuid
import shutil
import tempfile
import json
import time
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
        
        # Add columns if they don't exist
        cur.execute("ALTER TABLE posted_reels ADD COLUMN IF NOT EXISTS direct_video_url TEXT;")
        cur.execute("ALTER TABLE posted_reels ADD COLUMN IF NOT EXISTS caption TEXT;")
        
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
        
        # Pending posts table (kept for backward compatibility but not used in new flow)
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
        
        # Add columns if they don't exist
        cur.execute("ALTER TABLE pending_posts ADD COLUMN IF NOT EXISTS wakeup_sent BOOLEAN DEFAULT FALSE;")
        cur.execute("ALTER TABLE pending_posts ADD COLUMN IF NOT EXISTS real_fetch_attempts INTEGER DEFAULT 0;")
        cur.execute("ALTER TABLE pending_posts ADD COLUMN IF NOT EXISTS webhook_received BOOLEAN DEFAULT FALSE;")
        
        # ========== NEW: ZERNIO KEYS TABLE ==========
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
        
        # Add zernio_key_id to pipelines
        cur.execute("ALTER TABLE pipelines ADD COLUMN IF NOT EXISTS zernio_key_id UUID REFERENCES zernio_keys(id);")
        
        # ========== NEW: APP SETTINGS TABLE ==========
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
                ('scraper_base_url', 'https://ig-reels-scraper.onrender.com', 'Instagram scraper service URL'),
                ('max_reels_per_scrape', '50', 'Maximum reels to scrape per profile'),
                ('max_scrolls_per_scrape', '200', 'Maximum scrolls per profile'),
                ('enable_auto_sync', 'true', 'Auto-sync captions after scrape')
            ON CONFLICT (setting_key) DO NOTHING;
        """)
        
        # Create indexes
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
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pending_posts_reel_url ON pending_posts(reel_url);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pending_posts_status ON pending_posts(status);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pending_posts_created_at ON pending_posts(created_at DESC);")
        
        # ========== NEW INDEXES ==========
        cur.execute("CREATE INDEX IF NOT EXISTS idx_zernio_keys_api_key ON zernio_keys(api_key);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_zernio_keys_is_active ON zernio_keys(is_active);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_pipelines_zernio_key_id ON pipelines(zernio_key_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_app_settings_setting_key ON app_settings(setting_key);")
        
        conn.commit()
        app.logger.info("✅ Database tables ready with all columns (including Zernio keys and app settings)")
    except Exception as e:
        app.logger.error(f"❌ Database init error: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
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

def get_caption_service_url():
    """Get caption service URL from settings."""
    return get_setting('caption_service_url', 'https://copytxt-caption-automation.onrender.com/api/caption')

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

def fetch_caption_from_service(reel_url):
    """Fetch a single caption from the caption service - called during posting."""
    try:
        app.logger.info(f"📞 Fetching caption NOW for: {reel_url[:50]}...")
        caption_service_url = get_caption_service_url()
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
                app.logger.info(f"✅ Caption fetched: {caption[:50] if caption else 'Empty'}...")
                return caption
        return None
    except Exception as e:
        app.logger.error(f"Caption service error for {reel_url}: {e}")
        return None

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
    db_cookies = get_cookies_from_db()
    if db_cookies:
        cookie_data = db_cookies.get('cookie_data', [])
        if cookie_data:
            username = db_cookies.get('username', 'default')
            safe_user = re.sub(r'[^a-zA-Z0-9_-]', '_', str(username))[:40]
            cookie_file = os.path.join('/tmp', f'instagram_cookies_{safe_user}.txt')
            write_netscape_cookies(cookie_data, cookie_file)
            app.logger.info(f"Using cookies from database → {cookie_file}")
            return cookie_file
    
    cookies_json_env = os.environ.get('COOKIES_JSON')
    if cookies_json_env:
        try:
            cookies_data = json.loads(cookies_json_env)
            cookie_file = os.path.join('/tmp', 'cookies_netscape.txt')
            write_netscape_cookies(cookies_data, cookie_file)
            return cookie_file
        except Exception as e:
            app.logger.error(f"Failed to parse COOKIES_JSON: {e}")
    return None

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

def get_video_with_captions(reel_url):
    try:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "best[ext=mp4]/best",
            "nocheckcertificate": True,
            "http_headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            "extract_flat": False,
            "writeinfo": True
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(reel_url, download=False)
            caption = info.get('description') or info.get('title') or ''
            caption = caption.strip()
            if len(caption) > 5000:
                caption = caption[:4997] + "..."
            entries = info.get("entries") if "entries" in info else [info]
            entries = [e for e in entries if e]
            target = entries[0] if entries else None
            if not target:
                return None, None, None
            thumbnail = target.get('thumbnail') or info.get('thumbnail')
            formats = target.get("formats", [])
            if not formats:
                video_url = target.get("url") or target.get("webpage_url")
            else:
                video_url = None
                for fmt in formats:
                    if fmt.get("ext") == "mp4" and fmt.get("acodec") != "none" and fmt.get("vcodec") != "none":
                        video_url = fmt.get("url")
                        break
                if not video_url:
                    video_url = formats[0].get("url") if formats else None
            return video_url, caption, thumbnail
    except Exception as e:
        app.logger.error(f"Error extracting video with captions: {e}")
        return None, None, None

def get_direct_video_url(url, media_id=None):
    opts = base_ydl_opts({"format": "best[ext=mp4]/best"})
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            entries = info.get("entries") if "entries" in info else [info]
            entries = [e for e in entries if e]
            target = None
            if media_id:
                target = next((e for e in entries if e.get("id") == media_id), None)
            else:
                target = entries[0] if entries else None
            if not target:
                return None
            formats = target.get("formats", [])
            if not formats:
                return target.get("url") or target.get("webpage_url")
            for fmt in formats:
                if fmt.get("ext") == "mp4" and fmt.get("acodec") != "none" and fmt.get("vcodec") != "none":
                    return fmt.get("url")
            return formats[0].get("url") if formats else None
    except Exception as e:
        app.logger.error(f"Error getting direct video URL: {e}")
        return None

def get_direct_url_with_caption_cache(reel_url):
    conn = get_db_connection()
    if not conn:
        video_url, caption, _ = get_video_with_captions(reel_url)
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
        direct_url, caption, _ = get_video_with_captions(reel_url)
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
        video_url, caption, _ = get_video_with_captions(reel_url)
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
    
    Args:
        video_url: URL of the video to publish
        text: Caption text
        account_id: Zernio Facebook account ID
        publish_now: If True, publish immediately
        scheduled_time: ISO format datetime string
        key_id: Specific key to use (optional)
    
    Returns:
        dict: Response from Zernio API
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
        
        # Increment usage
        increment_key_usage(key['id'])
        
        if response.status_code in [200, 201]:
            return response.json()
        else:
            return {"error": response.text, "status_code": response.status_code}
    except Exception as e:
        return {"error": str(e)}

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

def trigger_caption_fetch_with_dual_requests(reel_url, pipeline_id, profile_username):
    import threading
    import uuid
    from datetime import datetime
    import time
    
    job_id = str(uuid.uuid4())
    app.logger.info(f"📤 [Job {job_id}] Triggering dual caption fetch for: {reel_url[:50]}...")
    
    CAPTION_FETCH_STATUS[reel_url] = {
        'status': 'pending',
        'job_id': job_id,
        'pipeline_id': pipeline_id,
        'profile_username': profile_username,
        'message': 'Dual request queued (wake-up + real fetch)',
        'timestamp': datetime.utcnow().isoformat(),
        'request_1_sent': False,
        'request_2_sent': False,
        'request_1_status': None,
        'request_2_status': None,
        'retry_count': 0
    }
    
    def send_request_1():
        try:
            caption_service_url = get_caption_service_url()
            app.logger.info(f"📞 [Job {job_id}] Request 1 (WAKE-UP) sent...")
            response = requests.post(
                caption_service_url,
                json={
                    "url": reel_url,
                    "job_id": job_id,
                    "pipeline_id": pipeline_id,
                    "profile_username": profile_username,
                    "webhook_url": f"https://fetchgram-one.vercel.app/api/webhook/caption",
                    "request_type": "wakeup"
                },
                timeout=3,
                headers={"Content-Type": "application/json"}
            )
            app.logger.info(f"⏰ [Job {job_id}] Request 1 completed: {response.status_code}")
            CAPTION_FETCH_STATUS[reel_url]['request_1_sent'] = True
            CAPTION_FETCH_STATUS[reel_url]['request_1_status'] = response.status_code
        except requests.exceptions.Timeout:
            app.logger.info(f"⏰ [Job {job_id}] Request 1 timed out (expected)")
            CAPTION_FETCH_STATUS[reel_url]['request_1_sent'] = True
            CAPTION_FETCH_STATUS[reel_url]['request_1_status'] = 'timeout'
        except Exception as e:
            app.logger.error(f"❌ [Job {job_id}] Request 1 error: {e}")
            CAPTION_FETCH_STATUS[reel_url]['request_1_sent'] = True
            CAPTION_FETCH_STATUS[reel_url]['request_1_status'] = str(e)
    
    def send_request_2():
        try:
            caption_service_url = get_caption_service_url()
            app.logger.info(f"⏳ [Job {job_id}] Waiting 60 seconds before request 2...")
            time.sleep(60)
            app.logger.info(f"📞 [Job {job_id}] Request 2 (REAL FETCH) sent...")
            response = requests.post(
                caption_service_url,
                json={
                    "url": reel_url,
                    "job_id": job_id,
                    "pipeline_id": pipeline_id,
                    "profile_username": profile_username,
                    "webhook_url": f"https://fetchgram-one.vercel.app/api/webhook/caption",
                    "request_type": "real_fetch"
                },
                timeout=60,
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 200:
                app.logger.info(f"✅ [Job {job_id}] Request 2 completed successfully!")
                CAPTION_FETCH_STATUS[reel_url]['request_2_sent'] = True
                CAPTION_FETCH_STATUS[reel_url]['request_2_status'] = response.status_code
                CAPTION_FETCH_STATUS[reel_url]['status'] = 'processing'
                CAPTION_FETCH_STATUS[reel_url]['message'] = 'Caption service processing (request 2)'
            else:
                app.logger.error(f"❌ [Job {job_id}] Request 2 failed: {response.status_code}")
                CAPTION_FETCH_STATUS[reel_url]['request_2_sent'] = True
                CAPTION_FETCH_STATUS[reel_url]['request_2_status'] = response.status_code
                CAPTION_FETCH_STATUS[reel_url]['status'] = 'failed'
                CAPTION_FETCH_STATUS[reel_url]['message'] = f'Request 2 failed: {response.status_code}'
        except requests.exceptions.Timeout:
            app.logger.error(f"❌ [Job {job_id}] Request 2 timed out")
            CAPTION_FETCH_STATUS[reel_url]['request_2_sent'] = True
            CAPTION_FETCH_STATUS[reel_url]['request_2_status'] = 'timeout'
            CAPTION_FETCH_STATUS[reel_url]['status'] = 'failed'
            CAPTION_FETCH_STATUS[reel_url]['message'] = 'Request 2 timed out'
        except Exception as e:
            app.logger.error(f"❌ [Job {job_id}] Request 2 error: {e}")
            CAPTION_FETCH_STATUS[reel_url]['request_2_sent'] = True
            CAPTION_FETCH_STATUS[reel_url]['request_2_status'] = str(e)
            CAPTION_FETCH_STATUS[reel_url]['status'] = 'failed'
            CAPTION_FETCH_STATUS[reel_url]['message'] = f'Request 2 error: {str(e)}'
    
    thread1 = threading.Thread(target=send_request_1)
    thread1.daemon = True
    thread1.start()
    thread2 = threading.Thread(target=send_request_2)
    thread2.daemon = True
    thread2.start()
    
    return {
        'status': 'accepted',
        'job_id': job_id,
        'message': 'Dual requests sent (wake-up + real fetch in 60s)',
        'details': {
            'request_1': 'Wake-up request sent (timeout: 3s)',
            'request_2': 'Real fetch scheduled in 60s (timeout: 60s)'
        }
    }

def trigger_caption_fetch_with_dual_requests_and_retry(reel_url, pipeline_id, profile_username, max_retries=3):
    import threading
    import uuid
    from datetime import datetime
    import time
    
    job_id = str(uuid.uuid4())
    app.logger.info(f"📤 [Job {job_id}] Starting DUAL+RETRY caption fetch for: {reel_url[:50]}...")
    
    CAPTION_FETCH_STATUS[reel_url] = {
        'status': 'pending',
        'job_id': job_id,
        'pipeline_id': pipeline_id,
        'profile_username': profile_username,
        'message': 'Dual+Retry request queued',
        'timestamp': datetime.utcnow().isoformat(),
        'wake_up_sent': False,
        'real_fetch_attempts': 0,
        'real_fetch_status': None,
        'webhook_received': False,
        'retry_count': 0
    }
    
    def send_wakeup():
        try:
            caption_service_url = get_caption_service_url()
            app.logger.info(f"💤 [Job {job_id}] Sending wake-up request...")
            requests.post(
                caption_service_url,
                json={
                    "url": reel_url,
                    "job_id": job_id,
                    "pipeline_id": pipeline_id,
                    "profile_username": profile_username,
                    "webhook_url": f"https://fetchgram-one.vercel.app/api/webhook/caption",
                    "request_type": "wakeup"
                },
                timeout=2,
                headers={"Content-Type": "application/json"}
            )
            app.logger.info(f"✅ [Job {job_id}] Wake-up request sent")
            CAPTION_FETCH_STATUS[reel_url]['wake_up_sent'] = True
            conn = get_db_connection()
            if conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE pending_posts SET wakeup_sent = TRUE 
                    WHERE reel_url = %s AND status IN ('pending', 'processing')
                """, (reel_url,))
                conn.commit()
                cur.close()
                conn.close()
        except Exception as e:
            app.logger.info(f"⏰ [Job {job_id}] Wake-up request timed out (expected)")
            CAPTION_FETCH_STATUS[reel_url]['wake_up_sent'] = True
    
    def send_real_fetch_with_retry():
        caption_service_url = get_caption_service_url()
        app.logger.info(f"⏳ [Job {job_id}] Waiting 60 seconds for Render to wake up...")
        time.sleep(60)
        max_attempts = max_retries
        base_delay = 5
        
        for attempt in range(max_attempts):
            try:
                app.logger.info(f"📞 [Job {job_id}] Real fetch attempt {attempt + 1}/{max_attempts}...")
                CAPTION_FETCH_STATUS[reel_url]['real_fetch_attempts'] = attempt + 1
                CAPTION_FETCH_STATUS[reel_url]['message'] = f'Real fetch attempt {attempt + 1}'
                response = requests.post(
                    caption_service_url,
                    json={
                        "url": reel_url,
                        "job_id": job_id,
                        "pipeline_id": pipeline_id,
                        "profile_username": profile_username,
                        "webhook_url": f"https://fetchgram-one.vercel.app/api/webhook/caption",
                        "request_type": "real_fetch",
                        "attempt": attempt + 1
                    },
                    timeout=45,
                    headers={"Content-Type": "application/json"}
                )
                if response.status_code == 200:
                    app.logger.info(f"✅ [Job {job_id}] Real fetch successful! (attempt {attempt + 1})")
                    CAPTION_FETCH_STATUS[reel_url]['real_fetch_status'] = 'success'
                    CAPTION_FETCH_STATUS[reel_url]['status'] = 'processing'
                    CAPTION_FETCH_STATUS[reel_url]['message'] = 'Caption service processing'
                    conn = get_db_connection()
                    if conn:
                        cur = conn.cursor()
                        cur.execute("""
                            UPDATE pending_posts SET real_fetch_attempts = %s
                            WHERE reel_url = %s AND status IN ('pending', 'processing')
                        """, (attempt + 1, reel_url))
                        conn.commit()
                        cur.close()
                        conn.close()
                    return
                elif response.status_code in [502, 503, 504]:
                    app.logger.warning(f"⚠️ [Job {job_id}] Gateway error (attempt {attempt + 1})")
                    if attempt < max_attempts - 1:
                        delay = base_delay * (2 ** attempt)
                        app.logger.info(f"⏳ [Job {job_id}] Retrying in {delay}s...")
                        time.sleep(delay)
                        continue
                    else:
                        app.logger.error(f"❌ [Job {job_id}] All attempts failed (gateway errors)")
                        CAPTION_FETCH_STATUS[reel_url]['real_fetch_status'] = 'failed'
                        CAPTION_FETCH_STATUS[reel_url]['status'] = 'failed'
                        CAPTION_FETCH_STATUS[reel_url]['message'] = 'Gateway errors after all attempts'
                        return
                else:
                    app.logger.error(f"❌ [Job {job_id}] Real fetch failed: {response.status_code}")
                    CAPTION_FETCH_STATUS[reel_url]['real_fetch_status'] = 'failed'
                    CAPTION_FETCH_STATUS[reel_url]['status'] = 'failed'
                    CAPTION_FETCH_STATUS[reel_url]['message'] = f'Error {response.status_code}'
                    return
            except requests.exceptions.Timeout:
                app.logger.warning(f"⚠️ [Job {job_id}] Timeout (attempt {attempt + 1})")
                if attempt < max_attempts - 1:
                    delay = base_delay * (2 ** attempt)
                    app.logger.info(f"⏳ [Job {job_id}] Retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    app.logger.error(f"❌ [Job {job_id}] All attempts failed (timeouts)")
                    CAPTION_FETCH_STATUS[reel_url]['real_fetch_status'] = 'failed'
                    CAPTION_FETCH_STATUS[reel_url]['status'] = 'failed'
                    CAPTION_FETCH_STATUS[reel_url]['message'] = 'Timeout after all attempts'
                    return
            except Exception as e:
                app.logger.error(f"❌ [Job {job_id}] Real fetch error: {e}")
                if attempt < max_attempts - 1:
                    delay = base_delay * (2 ** attempt)
                    app.logger.info(f"⏳ [Job {job_id}] Retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    CAPTION_FETCH_STATUS[reel_url]['real_fetch_status'] = 'failed'
                    CAPTION_FETCH_STATUS[reel_url]['status'] = 'failed'
                    CAPTION_FETCH_STATUS[reel_url]['message'] = str(e)
                    return
        
        if CAPTION_FETCH_STATUS[reel_url]['status'] != 'processing':
            CAPTION_FETCH_STATUS[reel_url]['status'] = 'failed'
            CAPTION_FETCH_STATUS[reel_url]['message'] = 'All retry attempts exhausted'
    
    thread_wakeup = threading.Thread(target=send_wakeup)
    thread_wakeup.daemon = True
    thread_wakeup.start()
    thread_real = threading.Thread(target=send_real_fetch_with_retry)
    thread_real.daemon = True
    thread_real.start()
    
    return {
        'status': 'accepted',
        'job_id': job_id,
        'message': 'Dual+Retry caption fetch started',
        'timeline': {
            'request_1': 'Wake-up sent immediately',
            'request_2': 'Real fetch after 60s (with retries)',
            'max_retries': max_retries
        }
    }

def trigger_caption_fetch_async(reel_url, pipeline_id, profile_username):
    return trigger_caption_fetch_with_dual_requests_and_retry(reel_url, pipeline_id, profile_username)

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
        caption = get_caption_for_reel(post['reel_url'], post['profile_username'], post['pipeline_id'])
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
                cur.execute("SELECT zernio_key_id FROM pipelines WHERE id = %s", (post['pipeline_id'],))
                result = cur.fetchone()
                if result and result[0]:
                    key_id = result[0]
                cur.close()
                conn.close()
            except:
                pass
        
        result = publish_to_facebook(
            video_url=post['direct_video_url'],
            text=caption,
            account_id=post['facebook_account_id'],
            publish_now=True,
            key_id=key_id
        )
        if result and not result.get('error'):
            post_id = result.get('post', {}).get('_id') or result.get('post_id')
            post_url = None
            platforms = result.get('post', {}).get('platforms', [])
            for platform in platforms:
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
                status='success'
            )
            update_pipeline_stats(post['pipeline_id'], 0, 0)
            update_pending_post_status(post['id'], 'completed', None, post_id, post_url)
            app.logger.info(f"✅ Pending post completed and stats updated: {post['reel_url'][:50]}...")
            return True
        else:
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
            app.logger.error(f"❌ Pending post failed: {post['reel_url'][:50]}... - {error_msg}")
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
        except:
            pass
        return False

def get_caption_for_reel(reel_url, profile_username, pipeline_id):
    conn = get_db_connection()
    if not conn:
        return None
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
        if result:
            results = result[0]
            if isinstance(results, str):
                results = json.loads(results)
            for profile in results:
                if profile.get('username') == profile_username:
                    for reel in profile.get('reels', []):
                        if isinstance(reel, dict) and reel.get('url') == reel_url:
                            caption = reel.get('caption', '')
                            if caption and caption.strip():
                                return caption
        cur.execute("SELECT caption FROM posted_reels WHERE pipeline_id = %s AND reel_url = %s", (pipeline_id, reel_url))
        result = cur.fetchone()
        if result and result[0] and result[0].strip():
            return result[0]
        cur.execute("SELECT caption FROM reel_cache WHERE reel_url = %s", (reel_url,))
        result = cur.fetchone()
        if result and result[0] and result[0].strip():
            return result[0]
        return None
    except Exception as e:
        app.logger.error(f"Error getting caption: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def store_caption_in_database(reel_url, caption, profile_username):
    """Store caption in database for future use."""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cur = conn.cursor()
        
        # Store in reel_cache
        cur.execute("""
            INSERT INTO reel_cache (reel_url, direct_url, caption, created_at)
            VALUES (%s, '', %s, NOW())
            ON CONFLICT (reel_url) DO UPDATE SET 
                caption = EXCLUDED.caption,
                created_at = NOW()
        """, (reel_url, caption))
        conn.commit()
        
        # Update scraped_reels if possible
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

# ============== UPDATED RUN_PIPELINE - PURE SCHEDULING ==============

def run_pipeline(pipeline_id):
    """Pure scheduling - find unposted reels and schedule them at random times."""
    conn = get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM pipelines WHERE id = %s", (pipeline_id,))
        pipeline = cur.fetchone()
        cur.close()
        
        if not pipeline:
            return {"error": "Pipeline not found"}
        if not pipeline['is_active']:
            return {"error": "Pipeline is inactive"}
        
        unposted = get_unposted_reels(
            pipeline['profile_username'], 
            pipeline['id'], 
            pipeline['daily_limit']
        )
        
        if not unposted:
            log_pipeline_run(pipeline['id'], 0, 0, 'completed', 'No unposted reels found')
            return {"message": "No unposted reels to schedule", "scheduled": 0}
        
        # Generate random post times
        num_posts = len(unposted)
        post_times = generate_random_post_times(num_posts, start_hour=0, end_hour=23)
        
        scheduled_count = 0
        failed_count = 0
        
        for idx, reel in enumerate(unposted):
            try:
                reel_url = reel['url']
                caption = reel.get('caption', '') or ''
                
                app.logger.info(f"📝 Scheduling: {reel_url[:50]}...")
                
                # ✅ DON'T fetch video URL here - leave empty
                # The video URL will be fetched during posting
                direct_video_url = ''
                
                scheduled_time = post_times[idx] if idx < len(post_times) else None
                if not scheduled_time:
                    hours_from_now = random.randint(1, 24)
                    scheduled_time = datetime.utcnow() + timedelta(hours=hours_from_now)
                    scheduled_time = scheduled_time.replace(minute=random.randint(0, 59), second=random.randint(0, 59))
                
                cur = conn.cursor()
                
                # Check if reel already exists
                cur.execute("SELECT id FROM scheduled_posts WHERE reel_url = %s", (reel_url,))
                existing = cur.fetchone()
                
                if existing:
                    # Update existing record - KEEP existing direct_video_url if any
                    cur.execute("""
                        UPDATE scheduled_posts 
                        SET caption = %s,
                            pipeline_id = %s,
                            scheduled_time = %s,
                            updated_at = NOW()
                        WHERE reel_url = %s
                    """, (caption, pipeline['id'], scheduled_time, reel_url))
                else:
                    # Insert new record with empty direct_video_url
                    cur.execute("""
                        INSERT INTO scheduled_posts (
                            reel_url, direct_video_url, caption, pipeline_id, scheduled_time
                        )
                        VALUES (%s, %s, %s, %s, %s)
                    """, (reel_url, '', caption, pipeline['id'], scheduled_time))
                
                conn.commit()
                cur.close()
                scheduled_count += 1
                time_str = scheduled_time.strftime('%Y-%m-%d %I:%M:%S %p UTC')
                app.logger.info(f"📅 Scheduled post at {time_str}: {reel_url[:50]}...")
                    
            except Exception as e:
                app.logger.error(f"Error scheduling reel: {e}")
                failed_count += 1
        
        update_pipeline_stats(pipeline['id'], scheduled_count, failed_count)
        log_pipeline_run(pipeline['id'], scheduled_count, failed_count, 'completed' if failed_count == 0 else 'partial')
        
        return {
            "message": f"Scheduled {scheduled_count} posts at random times, {failed_count} failed",
            "scheduled": scheduled_count,
            "failed": failed_count,
            "total": len(unposted)
        }
    except Exception as e:
        app.logger.error(f"Pipeline execution error: {e}")
        log_pipeline_run(pipeline_id, 0, 0, 'error', str(e))
        return {"error": str(e)}
    finally:
        conn.close()

def run_all_active_pipelines():
    conn = get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id FROM pipelines WHERE is_active = TRUE")
        pipelines = cur.fetchall()
        cur.close()
        results = []
        for pipeline in pipelines:
            result = run_pipeline(pipeline['id'])
            results.append({"pipeline_id": pipeline['id'], "result": result})
        return {"message": f"Ran {len(pipelines)} pipelines", "results": results}
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()

def ensure_caption_for_reel(reel_url, profile_username, pipeline_id):
    conn = get_db_connection()
    if not conn:
        return None
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
        if result:
            results = result[0]
            for profile in results:
                if profile.get('username') == profile_username:
                    reels = profile.get('reels', [])
                    for reel in reels:
                        if isinstance(reel, dict):
                            if reel.get('url') == reel_url:
                                caption = reel.get('caption', '')
                                if caption and caption.strip():
                                    app.logger.info(f"📝 Found caption in scraped_reels")
                                    return caption
        cur.execute("SELECT caption FROM posted_reels WHERE pipeline_id = %s AND reel_url = %s", (pipeline_id, reel_url))
        result = cur.fetchone()
        if result and result[0] and result[0].strip():
            app.logger.info(f"📝 Found caption in posted_reels")
            return result[0]
        app.logger.info(f"🔥 Caption not found, triggering dual fetch for: {reel_url[:50]}...")
        trigger_caption_fetch_with_dual_requests_and_retry(reel_url, pipeline_id, profile_username)
        return None
    except Exception as e:
        app.logger.error(f"Error ensuring caption: {e}")
        return None
    finally:
        cur.close()
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
    if not cookies:
        cookies_json_env = os.environ.get('COOKIES_JSON')
        if cookies_json_env:
            try:
                cookies = json.loads(cookies_json_env)
                app.logger.info(f"Proxy: Retrieved {len(cookies)} cookies from env")
            except:
                pass
    if not cookies:
        return jsonify({"status": "error", "error": "No Instagram cookies found. Please upload your cookies.json file first."}), 400
    data['cookies'] = cookies
    try:
        existing_urls = {}
        for username in usernames:
            existing_urls[username] = get_existing_reel_urls(username)
            app.logger.info(f"📊 @{username}: {len(existing_urls[username])} existing reels")
        scraper_base_url = get_scraper_base_url()
        response = requests.post(f'{scraper_base_url}/api/scrape/start', json=data, headers={'Content-Type': 'application/json'}, timeout=60)
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
                return jsonify({"status": "success", "job_id": result_data.get('job_id') or str(uuid.uuid4()), "usernames": extracted_usernames, "message": f"Found {total_new_reels} new reels across {len(new_results)} profiles", "results": new_results, "auto_sync": False, "new_reels": total_new_reels, "profiles_with_new": len(new_results)}), 200
            else:
                return jsonify({"status": "success", "message": "No new reels found for the requested profiles", "usernames": usernames, "results": []}), 200
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

@app.route("/api/commands/download", methods=["POST"])
def api_download():
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    media_id = data.get("media_id", "").strip()
    action = data.get("action", "url_only")
    if not url:
        return jsonify({"error": "Missing 'url' parameter"}), 400
    if not is_valid_instagram_url(url):
        return jsonify({"error": "Invalid Instagram URL"}), 400
    try:
        response = {"status": "success", "url": url, "media_id": media_id, "action": action, "timestamp": datetime.utcnow().isoformat()}
        with yt_dlp.YoutubeDL(base_ydl_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
        entries = info.get("entries") if "entries" in info else [info]
        entries = [e for e in entries if e]
        if not entries:
            return jsonify({"error": "No videos found"}), 422
        target = entries[0]
        if media_id:
            target = next((e for e in entries if e.get("id") == media_id), None) or target
        video_info = {"id": target.get("id"), "title": target.get("title", "Instagram video"), "duration": target.get("duration"), "uploader": target.get("uploader") or target.get("uploader_id"), "thumbnail": target.get("thumbnail"), "ext": target.get("ext", "mp4")}
        response["video_info"] = video_info
        session['current_video_url'] = get_direct_video_url(url, media_id)
        session['current_video_title'] = video_info.get('title')
        session['current_video_thumbnail'] = video_info.get('thumbnail')
        if action == "url_only":
            direct_url = get_direct_video_url(url, media_id)
            if direct_url:
                response["download_url"] = direct_url
            else:
                response["download_url"] = f"/api/download?url={url}&id={media_id}"
                response["warning"] = "Direct URL not available, using streaming fallback"
        elif action == "download":
            filepath, job_dir, target = download_video_file(url, media_id)
            download_name = f"{target.get('id', 'instagram_video')}.{target.get('ext', 'mp4')}"
            @after_this_request
            def cleanup(response_obj):
                shutil.rmtree(job_dir, ignore_errors=True)
                return response_obj
            return send_file(filepath, as_attachment=True, download_name=download_name)
        else:
            return jsonify({"error": f"Unknown action: {action}"}), 400
        return jsonify(response)
    except Exception as e:
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
    """List all connected Zernio Facebook accounts - uses the BEST available key."""
    try:
        # Get the best available key
        key = get_best_zernio_key()
        if not key:
            return jsonify({
                "status": "error", 
                "message": "No Zernio keys available. Please add a key first.", 
                "accounts": []
            }), 503
        
        # Use the key's actual API key
        zernio_base_url = get_zernio_base_url()
        headers = {
            "Authorization": f"Bearer {key['api_key']}", 
            "Content-Type": "application/json"
        }
        
        app.logger.info(f"🔑 Fetching accounts with key: {key['name']}")
        
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
                        "username": account.get('username', 'N/A'),
                        "status": account.get('platformStatus', 'unknown')
                    })
            
            app.logger.info(f"✅ Found {len(facebook_accounts)} Facebook accounts for key: {key['name']}")
            
            return jsonify({
                "status": "success", 
                "accounts": facebook_accounts, 
                "total": len(facebook_accounts),
                "key_name": key['name'],
                "key_id": key['id']
            })
        else:
            app.logger.error(f"❌ Zernio API error: {response.status_code} - {response.text[:200]}")
            return jsonify({
                "status": "error", 
                "message": f"Zernio API returned {response.status_code}", 
                "accounts": []
            }), 500
            
    except requests.exceptions.Timeout:
        app.logger.error("❌ Zernio API timeout")
        return jsonify({"status": "error", "message": "Connection timeout", "accounts": []}), 500
    except requests.exceptions.ConnectionError as e:
        app.logger.error(f"❌ Zernio connection error: {e}")
        return jsonify({"status": "error", "message": str(e), "accounts": []}), 500
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
    
    if not name:
        name = f"Key {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
    
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

# ============== CAPTION WEBHOOK ==============

@app.route("/api/webhook/caption", methods=["POST"])
def webhook_caption():
    data = request.get_json(silent=True) or {}
    reel_url = data.get('reel_url')
    caption = data.get('caption')
    job_id = data.get('job_id')
    status = data.get('status', 'completed')
    error = data.get('error')
    profile_username = data.get('profile_username')
    pipeline_id = data.get('pipeline_id')
    app.logger.info(f"📥 [Job {job_id}] Webhook received for: {reel_url[:50] if reel_url else 'unknown'}...")
    app.logger.info(f"   Caption: {caption[:50] if caption else 'None'}...")
    app.logger.info(f"   Status: {status}")
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
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO reel_cache (reel_url, direct_url, caption, created_at)
                    VALUES (%s, '', %s, NOW())
                    ON CONFLICT (reel_url) DO UPDATE SET 
                        caption = EXCLUDED.caption, created_at = NOW()
                """, (reel_url, caption))
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
                        row_id = result[0]
                        results = result[1]
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
                cur.execute("UPDATE posted_reels SET caption = %s WHERE reel_url = %s AND (caption IS NULL OR caption = '')", (caption, reel_url))
                conn.commit()
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
                    already_posted = cur.fetchone()[0] > 0
                    if already_posted:
                        app.logger.info(f"✅ [Job {job_id}] Reel already posted, updating pending_posts to completed")
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
                cur.execute("""
                    UPDATE pending_posts SET webhook_received = TRUE, updated_at = NOW()
                    WHERE reel_url = %s AND status IN ('pending', 'processing')
                """, (reel_url,))
                conn.commit()
                cur.close()
                conn.close()
                return jsonify({"status": "success", "message": "Caption stored and pending post processed", "job_id": job_id, "pending_processed": bool(pending) if 'pending' in locals() else False})
        except Exception as e:
            app.logger.error(f"❌ [Job {job_id}] Failed to store caption: {e}")
            import traceback
            app.logger.error(traceback.format_exc())
            return jsonify({"status": "error", "message": f"Failed to store caption: {str(e)}", "job_id": job_id}), 500
    elif status == 'failed':
        app.logger.warning(f"⚠️ [Job {job_id}] Caption fetch failed: {error}")
        if reel_url in CAPTION_FETCH_STATUS:
            CAPTION_FETCH_STATUS[reel_url]['error'] = error
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
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT p.*, COUNT(pr.id) as total_posted_count,
                   SUM(CASE WHEN pr.status = 'success' THEN 1 ELSE 0 END) as success_count,
                   SUM(CASE WHEN pr.status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                   MAX(pr.posted_at) as last_post_time
            FROM pipelines p
            LEFT JOIN posted_reels pr ON p.id = pr.pipeline_id
            GROUP BY p.id ORDER BY p.created_at DESC
        """)
        pipelines = cur.fetchall()
        for pipeline in pipelines:
            cur.execute("SELECT COUNT(*) as pending_count FROM pending_posts WHERE pipeline_id = %s AND status IN ('pending', 'processing')", (pipeline['id'],))
            pending = cur.fetchone()
            pipeline['pending_posts'] = pending['pending_count'] if pending else 0
        return jsonify({"status": "success", "pipelines": pipelines})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/pipelines', methods=['POST'])
def create_pipeline():
    data = request.get_json(silent=True) or {}
    name = data.get('name')
    profile_username = data.get('profile_username')
    facebook_account_id = data.get('facebook_account_id')
    daily_limit = data.get('daily_limit', 2)
    zernio_key_id = data.get('zernio_key_id')  # Optional: assign a specific key
    
    if not name or not profile_username or not facebook_account_id:
        return jsonify({"error": "name, profile_username, and facebook_account_id are required"}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO pipelines (id, name, profile_username, facebook_account_id, daily_limit, is_active, zernio_key_id)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, TRUE, %s) RETURNING id
        """, (name, profile_username, facebook_account_id, daily_limit, zernio_key_id))
        pipeline_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({"status": "success", "message": "Pipeline created", "pipeline_id": pipeline_id})
    except Exception as e:
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
        if not updates:
            return jsonify({"error": "No fields to update"}), 400
        updates.append("updated_at = NOW()")
        params.append(pipeline_id)
        cur = conn.cursor()
        cur.execute(f"UPDATE pipelines SET {', '.join(updates)} WHERE id = %s", params)
        conn.commit()
        return jsonify({"status": "success", "message": "Pipeline updated"})
    except Exception as e:
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
    """Process scheduled posts - fetches video URL and caption DURING posting."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT * FROM scheduled_posts 
            WHERE status = 'pending' 
            AND scheduled_time <= NOW()
            ORDER BY scheduled_time ASC
            LIMIT 5
        """)
        
        due_posts = cur.fetchall()
        
        if not due_posts:
            return jsonify({"status": "success", "message": "No posts due", "posted": 0})
        
        posted_count = 0
        failed_count = 0
        
        for post in due_posts:
            try:
                app.logger.info(f"📤 Processing due post: {post['reel_url'][:50]}...")
                
                cur.execute("SELECT * FROM pipelines WHERE id = %s", (post['pipeline_id'],))
                pipeline = cur.fetchone()
                
                if not pipeline:
                    app.logger.error(f"❌ Pipeline not found for post: {post['id']}")
                    continue
                
                # 🔥 Step 1: Get video URL NOW
                direct_video_url = post.get('direct_video_url', '')
                
                if not direct_video_url:
                    app.logger.info(f"📥 Fetching video URL NOW for: {post['reel_url'][:50]}...")
                    direct_video_url = get_direct_video_url(post['reel_url'])
                    
                    if direct_video_url:
                        cache_direct_url(post['reel_url'], direct_video_url, '')
                        cur.execute("""
                            UPDATE scheduled_posts 
                            SET direct_video_url = %s, updated_at = NOW()
                            WHERE id = %s
                        """, (direct_video_url, post['id']))
                        conn.commit()
                        app.logger.info(f"✅ Video URL fetched: {direct_video_url[:50]}...")
                    else:
                        # Try cache as fallback
                        direct_video_url = get_direct_url_from_cache_only(post['reel_url'])
                        if direct_video_url:
                            app.logger.info(f"✅ Found video URL in cache: {direct_video_url[:50]}...")
                            cur.execute("""
                                UPDATE scheduled_posts 
                                SET direct_video_url = %s, updated_at = NOW()
                                WHERE id = %s
                            """, (direct_video_url, post['id']))
                            conn.commit()
                
                if not direct_video_url:
                    app.logger.warning(f"⚠️ No video URL for: {post['reel_url'][:50]}... - will retry")
                    continue
                
                # 🔥 Step 2: Get caption
                caption = post.get('caption', '')
                if not caption or not caption.strip():
                    caption = get_caption_for_reel(post['reel_url'], pipeline['profile_username'], post['pipeline_id'])
                
                if not caption or not caption.strip():
                    app.logger.info(f"📝 Fetching caption NOW for: {post['reel_url'][:50]}...")
                    caption = fetch_caption_from_service(post['reel_url'])
                    if caption:
                        store_caption_in_database(post['reel_url'], caption, pipeline['profile_username'])
                
                # 🔥 Step 3: Post to Facebook
                if caption and caption.strip() and direct_video_url:
                    key_id = pipeline.get('zernio_key_id')
                    
                    result = publish_to_facebook(
                        video_url=direct_video_url,
                        text=caption,
                        account_id=pipeline['facebook_account_id'],
                        publish_now=True,
                        key_id=key_id
                    )
                    
                    if result and not result.get('error'):
                        mark_reel_as_posted(...)
                        posted_count += 1
                    else:
                        failed_count += 1
                else:
                    app.logger.warning(f"⚠️ Missing data for: {post['reel_url'][:50]}...")
                    
            except Exception as e:
                app.logger.error(f"❌ Error processing scheduled post: {e}")
                failed_count += 1
        
        return jsonify({"status": "success", "posted": posted_count, "failed": failed_count})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route("/api/scheduler/daily", methods=["POST"])
def daily_scheduler():
    """
    Daily scheduler - runs at midnight (12:00 AM).
    🔥 Pure scheduling - no pending posts, just schedule all unposted reels.
    Captions will be fetched during posting.
    """
    app.logger.info("🕐 Running daily scheduler at midnight...")
    
    # Run all active pipelines to schedule posts
    result = run_all_active_pipelines()
    
    # Clean up old scheduled posts
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE scheduled_posts 
                SET status = 'failed', error_message = 'Expired - not posted within 48 hours'
                WHERE status = 'pending' 
                AND scheduled_time < NOW() - INTERVAL '48 hours'
            """)
            conn.commit()
            cur.close()
            conn.close()
            app.logger.info(f"🧹 Cleaned up old scheduled posts")
    except Exception as e:
        app.logger.error(f"Cleanup error: {e}")
    
    return jsonify({
        "status": "success",
        "message": "Daily scheduler completed at midnight",
        "result": result
    })

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