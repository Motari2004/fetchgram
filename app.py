import os
import re
import uuid
import shutil
import tempfile
import json
import time
import base64
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
    pass  # .env file not found, use environment variables

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
    """Get a connection to the Neon PostgreSQL database."""
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
    """Initialize the database tables if they don't exist."""
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
        cur.execute("""
            ALTER TABLE posted_reels ADD COLUMN IF NOT EXISTS direct_video_url TEXT;
        """)
        cur.execute("""
            ALTER TABLE posted_reels ADD COLUMN IF NOT EXISTS caption TEXT;
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
        
        # Create indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_scraped_reels_user_id 
            ON scraped_reels(user_id);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_scraped_reels_created_at 
            ON scraped_reels(created_at DESC);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_cookies_user_id 
            ON user_cookies(user_id);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_posted_reels_pipeline_id 
            ON posted_reels(pipeline_id);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_posted_reels_posted_at 
            ON posted_reels(posted_at);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_pipelines_is_active 
            ON pipelines(is_active);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_pipeline_runs_pipeline_id 
            ON pipeline_runs(pipeline_id);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_reel_cache_reel_url 
            ON reel_cache(reel_url);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_reel_cache_created_at 
            ON reel_cache(created_at);
        """)
        
        conn.commit()
        app.logger.info("Database tables ready")
    except Exception as e:
        app.logger.error(f"Database init error: {e}")
    finally:
        cur.close()
        conn.close()

# Initialize database on startup
init_db()

# ============== CAPTION SERVICE INTEGRATION ==============

CAPTION_SERVICE_URL = os.environ.get('CAPTION_SERVICE_URL', 'https://copytxt-caption-automation.onrender.com/api/caption')

def fetch_captions_batch(reel_urls):
    """Fetch captions from the caption service."""
    if not reel_urls:
        return {}
    
    try:
        response = requests.post(
            f"{CAPTION_SERVICE_URL}/batch",
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
    """Process reels - fetch captions for those without them."""
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

# ============== COOKIE STORAGE FUNCTIONS ==============

def get_user_id():
    """Get or create a persistent user ID."""
    user_id = FIXED_USER_ID
    session['user_id'] = user_id
    return user_id

def save_cookies_to_db(cookies_data, username):
    """Save cookies to Neon PostgreSQL."""
    user_id = get_user_id()
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO user_cookies (user_id, cookie_data, username, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (user_id) 
            DO UPDATE SET 
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
    """Get cookies from Neon PostgreSQL."""
    user_id = get_user_id()
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT cookie_data, username, updated_at 
            FROM user_cookies 
            WHERE user_id = %s
        """, (user_id,))
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
    """Clear cookies from Neon PostgreSQL."""
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

# ============== ENCRYPTION FUNCTIONS ==============

def get_encryption_key():
    """Generate or retrieve a stable encryption key for credentials."""
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
    """Encrypt credentials or cookie data. Returns base64 string or None."""
    try:
        key = get_encryption_key()
        f = Fernet(key)

        if isinstance(password, str) and password.startswith('['):
            try:
                data = json.loads(password)
                data_dict = {
                    'type': 'cookies',
                    'data': data,
                    'timestamp': time.time()
                }
            except Exception:
                data_dict = {
                    'type': 'credentials',
                    'identifier': identifier,
                    'password': password,
                    'timestamp': time.time()
                }
        elif isinstance(password, (list, dict)):
            data_dict = {
                'type': 'cookies',
                'data': password,
                'timestamp': time.time()
            }
        else:
            data_dict = {
                'type': 'credentials',
                'identifier': identifier,
                'password': password,
                'timestamp': time.time()
            }

        encrypted = f.encrypt(json.dumps(data_dict).encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    except Exception as e:
        app.logger.error(f"Encryption failed: {e}")
        return None

def decrypt_credentials(encrypted_data):
    """Decrypt credentials. Returns (data, type) or None."""
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
    """Write a list of cookie dicts to a Netscape cookie file."""
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
    """Get cookies from session, database, or file."""
    db_cookies = get_cookies_from_db()
    if db_cookies:
        cookie_data = db_cookies.get('cookie_data', [])
        if cookie_data:
            username = db_cookies.get('username', 'default')
            safe_user = re.sub(r'[^a-zA-Z0-9_-]', '_', str(username))[:40]
            cookie_file = os.path.join('/tmp', f'instagram_cookies_{safe_user}.txt')
            write_netscape_cookies(cookie_data, cookie_file)
            session['cookie_file'] = cookie_file
            app.logger.info(f"Using cookies from database → {cookie_file}")
            return cookie_file
    
    cookie_file = session.get('cookie_file')
    if cookie_file and os.path.exists(cookie_file):
        app.logger.info(f"Using cookies from session: {cookie_file}")
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
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
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
    """
    Extract both direct video URL and caption from Instagram reel.
    Returns: (direct_url, caption, thumbnail)
    """
    try:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "best[ext=mp4]/best",
            "nocheckcertificate": True,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            "extract_flat": False,
            "writeinfo": True
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(reel_url, download=False)
            
            # Extract caption/description
            caption = info.get('description') or info.get('title') or ''
            
            # Clean up caption
            caption = caption.strip()
            if len(caption) > 5000:
                caption = caption[:4997] + "..."
            
            # Get direct video URL
            entries = info.get("entries") if "entries" in info else [info]
            entries = [e for e in entries if e]
            target = entries[0] if entries else None
            if not target:
                return None, None, None
            
            # Get thumbnail
            thumbnail = target.get('thumbnail') or info.get('thumbnail')
            
            # Get direct video URL
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
    """Extract direct video URL from Instagram URL."""
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
    """
    Get direct video URL and caption with caching.
    Returns: (direct_url, caption)
    """
    conn = get_db_connection()
    if not conn:
        video_url, caption, _ = get_video_with_captions(reel_url)
        return video_url, caption
    
    try:
        # Check cache first
        cur = conn.cursor()
        cur.execute("""
            SELECT direct_url, caption FROM reel_cache 
            WHERE reel_url = %s AND created_at > NOW() - INTERVAL '7 days'
        """, (reel_url,))
        result = cur.fetchone()
        
        if result and result[0]:
            app.logger.info(f"✅ Cache hit for: {reel_url[:50]}...")
            return result[0], result[1] or ''
        
        # Get direct URL and caption using yt-dlp
        app.logger.info(f"⏳ Fetching direct URL and caption for: {reel_url[:50]}...")
        direct_url, caption, _ = get_video_with_captions(reel_url)
        
        if direct_url:
            # Cache it
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
    """Download video file and return filepath."""
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
                "aspectRatio": {
                    "width": 720,
                    "height": 1280
                }
            }
        }

        app.logger.info("Creating Bluesky post...")
        response = requests.post(
            "https://bsky.social/xrpc/com.atproto.repo.createRecord",
            json={
                "repo": did,
                "collection": "app.bsky.feed.post",
                "record": record
            },
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

        return {
            "success": True,
            "post_uri": result.get("uri"),
            "post_cid": result.get("cid"),
            "post_id": post_id,
            "message": "Video posted to Bluesky successfully!"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# ============== ZERNIO (FACEBOOK) INTEGRATION ==============

ZERNIO_API_KEY = os.environ.get('ZERNIO_API_KEY', 'sk_48ad5dd4a9d9bd8e2561633862dc1708b3fb2013645023fde617921bd065a037')
ZERNIO_BASE_URL = "https://zernio.com/api/v1"

def publish_to_facebook(video_url, text, account_id, publish_now=True, scheduled_time=None):
    """
    Publish a video to Facebook via Zernio
    
    Args:
        video_url: URL of the video to publish (should be direct video URL)
        text: Caption text
        account_id: Zernio Facebook account ID
        publish_now: If True, publish immediately. If False and scheduled_time provided, schedule.
        scheduled_time: ISO format datetime string (e.g., "2026-09-03T10:00:00Z")
    
    Returns:
        dict: Response from Zernio API
    """
    headers = {
        "Authorization": f"Bearer {ZERNIO_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "content": text,
        "platforms": [
            {
                "platform": "facebook",
                "accountId": account_id
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
            f"{ZERNIO_BASE_URL}/posts",
            headers=headers,
            json=payload,
            timeout=120
        )
        
        if response.status_code in [200, 201]:
            return response.json()
        else:
            return {"error": response.text, "status_code": response.status_code}
    except Exception as e:
        return {"error": str(e)}

def publish_video_to_all_accounts(video_url, text, publish_now=True, scheduled_time=None):
    """Publish a video to all connected Facebook accounts"""
    results = {}
    
    # Get accounts from Zernio API dynamically
    try:
        headers = {
            "Authorization": f"Bearer {ZERNIO_API_KEY}",
            "Content-Type": "application/json"
        }
        response = requests.get(f"{ZERNIO_BASE_URL}/accounts", headers=headers, timeout=30)
        
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
                        scheduled_time=scheduled_time
                    )
                    results[account_id] = {
                        "account_name": account_name,
                        "result": result
                    }
    except Exception as e:
        app.logger.error(f"Error getting Zernio accounts: {e}")
    
    return results

# ============== PIPELINE FUNCTIONS ==============

def get_unposted_reels(profile_username, pipeline_id, limit=10):
    """Get unposted reels with captions for a profile."""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cur = conn.cursor()
        
        # Get reels from scraped data
        cur.execute("""
            SELECT 
                results
            FROM scraped_reels 
            WHERE EXISTS (
                SELECT 1 FROM jsonb_array_elements(results) AS elem
                WHERE elem->>'username' = %s
            )
            ORDER BY created_at DESC
            LIMIT 1
        """, (profile_username,))
        
        result = cur.fetchone()
        if not result:
            return []
        
        # Extract reels for this profile
        results = result[0]  # results JSONB
        profile_reels = []
        for item in results:
            if item.get('username') == profile_username:
                profile_reels = item.get('reels', [])
                break
        
        # Get already posted reels
        cur.execute("""
            SELECT reel_url FROM posted_reels 
            WHERE pipeline_id = %s
        """, (pipeline_id,))
        posted_urls = {row[0] for row in cur.fetchall()}
        
        # Filter unposted reels
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
    """Mark a reel as posted with caption."""
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
        
        conn.commit()
        return True
    except Exception as e:
        app.logger.error(f"Error marking reel as posted: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def update_pipeline_stats(pipeline_id, posted_count, failed_count):
    """Update pipeline statistics"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE pipelines 
            SET total_posted = total_posted + %s,
                last_run = NOW(),
                updated_at = NOW()
            WHERE id = %s
        """, (posted_count, pipeline_id))
        conn.commit()
        return True
    except Exception as e:
        app.logger.error(f"Error updating pipeline stats: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def log_pipeline_run(pipeline_id, posted_count, failed_count, status='completed', error_message=None):
    """Log a pipeline run"""
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

def run_pipeline(pipeline_id):
    """Execute a single pipeline using ONLY stored captions."""
    conn = get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        # Get pipeline configuration
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM pipelines WHERE id = %s", (pipeline_id,))
        pipeline = cur.fetchone()
        cur.close()
        
        if not pipeline:
            return {"error": "Pipeline not found"}
        
        if not pipeline['is_active']:
            return {"error": "Pipeline is inactive"}
        
        # Get unposted reels with captions
        unposted = get_unposted_reels(
            pipeline['profile_username'], 
            pipeline['id'], 
            pipeline['daily_limit']
        )
        
        if not unposted:
            log_pipeline_run(pipeline['id'], 0, 0, 'completed', 'No unposted reels found')
            return {"message": "No unposted reels to post", "posted": 0}
        
        posted_count = 0
        failed_count = 0
        
        # Post each reel
        for reel in unposted:
            try:
                reel_url = reel['url']
                caption = reel.get('caption', '')
                
                # 🔥 FIX: If no caption in DB, use fallback - DON'T fetch!
                if not caption or caption.strip() == '':
                    caption = f"🎬 New reel from @{pipeline['profile_username']}!"
                    app.logger.info(f"📝 Using fallback caption for: {reel_url[:50]}...")
                
                # Truncate caption if too long
                if len(caption) > 5000:
                    caption = caption[:4997] + "..."
                
                # 🔥 FIX: Get direct URL from cache ONLY - don't fetch if not cached
                direct_video_url = get_direct_url_from_cache_only(reel_url)
                
                if not direct_video_url:
                    app.logger.error(f"❌ No cached direct URL for: {reel_url}")
                    mark_reel_as_posted(
                        pipeline_id=pipeline['id'],
                        reel_url=reel_url,
                        caption=caption,
                        status='failed',
                        error_message='No cached direct video URL found. Please pre-fetch URLs.'
                    )
                    failed_count += 1
                    continue
                
                app.logger.info(f"✅ Using cached direct URL for: {reel_url[:50]}...")
                
                # Post to Facebook using the caption
                result = publish_to_facebook(
                    video_url=direct_video_url,
                    text=caption,
                    account_id=pipeline['facebook_account_id'],
                    publish_now=True
                )
                
                if result and not result.get('error'):
                    # Success
                    post_id = result.get('post', {}).get('_id') or result.get('post_id')
                    post_url = None
                    
                    platforms = result.get('post', {}).get('platforms', [])
                    for platform in platforms:
                        if platform.get('platform') == 'facebook':
                            post_url = platform.get('publishedUrl')
                            break
                    
                    mark_reel_as_posted(
                        pipeline_id=pipeline['id'],
                        reel_url=reel_url,
                        direct_video_url=direct_video_url,
                        caption=caption,
                        facebook_post_id=post_id,
                        facebook_post_url=post_url,
                        status='success'
                    )
                    posted_count += 1
                    app.logger.info(f"✅ Successfully posted: {reel_url[:50]}...")
                else:
                    # Failed
                    error_msg = result.get('error', 'Unknown error') if result else 'Unknown error'
                    mark_reel_as_posted(
                        pipeline_id=pipeline['id'],
                        reel_url=reel_url,
                        direct_video_url=direct_video_url,
                        caption=caption,
                        status='failed',
                        error_message=str(error_msg)
                    )
                    failed_count += 1
                    app.logger.error(f"❌ Failed to post: {reel_url[:50]}... - {error_msg}")
                    
            except Exception as e:
                app.logger.error(f"Error posting reel: {e}")
                mark_reel_as_posted(
                    pipeline_id=pipeline['id'],
                    reel_url=reel.get('url', 'unknown'),
                    caption=reel.get('caption', ''),
                    status='failed',
                    error_message=str(e)
                )
                failed_count += 1
        
        # Update pipeline stats
        update_pipeline_stats(pipeline['id'], posted_count, failed_count)
        
        # Log the run
        log_pipeline_run(pipeline['id'], posted_count, failed_count, 
                        'completed' if failed_count == 0 else 'partial')
        
        return {
            "message": f"Posted {posted_count} reels, {failed_count} failed",
            "posted": posted_count,
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
    """Run all active pipelines"""
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
            results.append({
                "pipeline_id": pipeline['id'],
                "result": result
            })
        
        return {
            "message": f"Ran {len(pipelines)} pipelines",
            "results": results
        }
        
    except Exception as e:
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
    """Upload cookies.json file (saves to Neon PostgreSQL)."""
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

        has_session = any(
            isinstance(c, dict) and c.get('name') in ('sessionid', 'ds_user_id')
            for c in cookies_data
        )
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

        encrypted = encrypt_credentials(json.dumps(cookies_data), "instagram_cookies")
        if encrypted:
            session['instagram_encrypted'] = encrypted
            session['instagram_username'] = username or 'Instagram User'
            session['instagram_saved'] = True

        session['cookies_data'] = cookies_data
        session['username'] = username or 'Instagram User'

        response = jsonify({
            "status": "success",
            "message": "Cookies uploaded and saved to database!",
            "username": username or 'Instagram User'
        })
        
        response.set_cookie(
            'user_id',
            user_id,
            max_age=30*24*60*60,
            path='/',
            secure=os.environ.get('FLASK_ENV') == 'production' or bool(os.environ.get('VERCEL')),
            httponly=True,
            samesite='Lax'
        )
        
        return response

    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON file", "status": "error"}), 400
    except Exception as e:
        app.logger.error(f"Cookie upload error: {e}")
        return jsonify({"error": f"Failed to process cookies: {str(e)}", "status": "error"}), 500

@app.route("/api/instagram/cookies_status", methods=["GET"])
def instagram_cookies_status():
    """Check if Instagram cookies are saved."""
    db_cookies = get_cookies_from_db()
    if db_cookies:
        return jsonify({
            "status": "success",
            "has_cookies": True,
            "username": db_cookies.get('username', 'Instagram User'),
            "message": "Cookies are saved in database"
        })
    
    encrypted = session.get('instagram_encrypted')
    if encrypted:
        try:
            decrypted = decrypt_credentials(encrypted)
            if decrypted:
                return jsonify({
                    "status": "success",
                    "has_cookies": True,
                    "username": session.get('instagram_username', 'Instagram User'),
                    "message": "Cookies are saved in session"
                })
        except Exception:
            pass
    
    return jsonify({
        "status": "success",
        "has_cookies": False,
        "message": "No saved cookies found"
    })

@app.route("/api/cookies/clear", methods=["POST"])
def clear_cookies():
    """Clear uploaded cookies from Neon PostgreSQL and session."""
    clear_cookies_from_db()
    
    session.pop('instagram_encrypted', None)
    session.pop('instagram_username', None)
    session.pop('instagram_saved', None)
    session.pop('cookies_data', None)
    session.pop('username', None)
    session.pop('cookie_file', None)

    for file in ['cookies_netscape.txt', 'instagram_cookies_persistent.txt']:
        path = os.path.join('/tmp', file)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    return jsonify({
        "status": "success",
        "message": "Cookies cleared successfully"
    })

# ============== SCRAPE PROXY ==============

@app.route("/api/scrape/proxy", methods=["POST"])
def scrape_proxy():
    """Proxy endpoint that retrieves cookies and fetches captions."""
    data = request.get_json(silent=True) or {}
    usernames = data.get("usernames", [])
    fetch_captions = data.get("fetch_captions", True)
    
    app.logger.info(f"📝 Scraping usernames: {usernames}")
    app.logger.info(f"📝 Fetch captions: {fetch_captions}")
    
    cookies = None
    db_cookies = get_cookies_from_db()
    if db_cookies:
        cookies = db_cookies.get('cookie_data', [])
        app.logger.info(f"Proxy: Retrieved {len(cookies)} cookies from Neon DB")
    
    if not cookies:
        encrypted = session.get('instagram_encrypted')
        if encrypted:
            try:
                decrypted = decrypt_credentials(encrypted)
                if decrypted:
                    cookie_data = decrypted[0]
                    if isinstance(cookie_data, str) and cookie_data.startswith('['):
                        cookie_data = json.loads(cookie_data)
                    elif isinstance(cookie_data, dict):
                        cookie_data = cookie_data.get('data', [])
                    cookies = cookie_data
                    app.logger.info(f"Proxy: Retrieved {len(cookies)} cookies from session")
            except Exception as e:
                app.logger.error(f"Failed to decrypt cookies: {e}")
    
    if not cookies:
        cookies = session.get('cookies_data')
        if cookies:
            app.logger.info(f"Proxy: Retrieved {len(cookies)} cookies from session data")
    
    if not cookies:
        return jsonify({
            "status": "error",
            "error": "No Instagram cookies found. Please upload your cookies.json file first."
        }), 400
    
    data['cookies'] = cookies
    
    try:
        response = requests.post(
            'https://ig-reels-scraper.onrender.com/api/scrape/start',
            json=data,
            headers={'Content-Type': 'application/json'},
            timeout=60
        )
        
        app.logger.info(f"Proxy: Render responded with status {response.status_code}")
        
        if response.status_code == 200:
            result_data = response.json()
            if result_data.get('job_id') and result_data.get('results'):
                results = result_data.get('results', [])
                
                # 🔥 NEW: Process captions on Vercel side
                if fetch_captions:
                    app.logger.info("📝 Processing captions on Vercel...")
                    for profile in results:
                        if isinstance(profile, dict):
                            reels = profile.get('reels', [])
                            if reels:
                                profile['reels'] = process_reels_with_captions(reels)
                                with_captions = sum(1 for r in profile['reels'] if r.get('caption') and r['caption'].strip())
                                app.logger.info(f"  @{profile.get('username')}: {with_captions}/{len(reels)} captions")
                
                extracted_usernames = []
                for profile in results:
                    if isinstance(profile, dict):
                        username = profile.get('username')
                        if username:
                            extracted_usernames.append(username)
                
                # Store with captions
                with app.test_request_context():
                    store_scraped_data()
                    app.logger.info(f"✅ Auto-stored scraped data for job {result_data.get('job_id')}")
        
        return jsonify(response.json()), response.status_code
        
    except requests.exceptions.Timeout:
        return jsonify({
            "status": "error",
            "error": "Render service timed out. Please try again."
        }), 504
    except requests.exceptions.ConnectionError:
        return jsonify({
            "status": "error",
            "error": "Could not connect to Render service. Please try again later."
        }), 503
    except Exception as e:
        app.logger.error(f"Proxy error: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

# ============== SCRAPED DATA STORAGE (DATABASE) ==============

def store_scraped_data_internal(job_id, results, usernames, status='completed'):
    """Internal function to store scraped data in database."""
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
            ON CONFLICT (user_id, job_id) 
            DO UPDATE SET 
                results = EXCLUDED.results,
                usernames = EXCLUDED.usernames,
                status = EXCLUDED.status,
                total_profiles = EXCLUDED.total_profiles,
                total_reels = EXCLUDED.total_reels,
                updated_at = NOW()
        """, (
            user_id, 
            job_id or f"job_{datetime.utcnow().isoformat()}", 
            usernames,
            json.dumps(results),
            status,
            total_profiles,
            total_reels
        ))
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
    """Store scraped data from Render into PostgreSQL with usernames and captions."""
    data = request.get_json(silent=True) or {}
    results = data.get("results", [])
    job_id = data.get("job_id")
    usernames = data.get("usernames", [])
    
    if not results:
        return jsonify({"error": "No results provided"}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        if not usernames:
            usernames = []
            for profile in results:
                if isinstance(profile, dict):
                    username = profile.get('username')
                    if username:
                        usernames.append(username)
        
        # Process results - PRESERVE captions
        processed_results = []
        for profile in results:
            if isinstance(profile, dict):
                processed_profile = profile.copy()
                reels = profile.get('reels', [])
                processed_reels = []
                for reel in reels:
                    if isinstance(reel, str):
                        processed_reels.append({
                            "url": reel,
                            "caption": ""
                        })
                    elif isinstance(reel, dict):
                        processed_reels.append({
                            "url": reel.get('url', ''),
                            "caption": reel.get('caption', '')
                        })
                    else:
                        processed_reels.append({
                            "url": str(reel),
                            "caption": ""
                        })
                processed_profile['reels'] = processed_reels
                processed_results.append(processed_profile)
            else:
                processed_results.append(profile)
        
        total_profiles = len(processed_results)
        total_reels = 0
        for profile in processed_results:
            reels = profile.get('reels', [])
            total_reels += len(reels)
        
        user_id = get_user_id()
        
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO scraped_reels (user_id, job_id, usernames, results, status, total_profiles, total_reels, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (user_id, job_id) 
            DO UPDATE SET 
                results = EXCLUDED.results,
                usernames = EXCLUDED.usernames,
                status = EXCLUDED.status,
                total_profiles = EXCLUDED.total_profiles,
                total_reels = EXCLUDED.total_reels,
                updated_at = NOW()
        """, (
            user_id,
            job_id or f"job_{datetime.utcnow().isoformat()}", 
            usernames,
            json.dumps(processed_results),
            'completed',
            total_profiles,
            total_reels
        ))
        conn.commit()
        
        app.logger.info(f"✅ Stored {total_profiles} profiles with {total_reels} total reels")
        
        return jsonify({
            "status": "success",
            "message": f"Stored {total_profiles} profiles with {total_reels} total reels",
            "count": total_profiles,
            "reels_count": total_reels,
            "usernames": usernames,
            "job_id": job_id
        })
        
    except Exception as e:
        app.logger.error(f"Database store error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

# ============== REST OF ROUTES (unchanged) ==============

@app.route("/api/scraped/latest", methods=["GET"])
def get_scraped_data():
    """Get ALL scraped data from PostgreSQL - show all profiles from all jobs."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT 
                results,
                total_profiles,
                total_reels,
                usernames,
                created_at
            FROM scraped_reels 
            ORDER BY created_at DESC
        """)
        
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
                                combined_results.append({
                                    'username': username,
                                    'reels': profile.get('reels', []),
                                    'status': profile.get('status', 'ok')
                                })
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
            
            return jsonify({
                "status": "success",
                "results": combined_results,
                "total_profiles": len(combined_results),
                "total_reels": total_reels,
                "usernames": list(seen_usernames),
                "all_usernames": all_usernames,
                "job_count": len(all_results),
                "message": f"Loaded {len(combined_results)} unique profiles with {total_reels} total reels"
            })
        else:
            return jsonify({
                "status": "success",
                "results": [],
                "message": "No scraped data found in database"
            })
            
    except Exception as e:
        app.logger.error(f"Database error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route("/api/scraped/delete", methods=["POST"])
def delete_scraped_by_username():
    """Delete scraped data for a specific username - PERMANENT DELETE from database."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    
    if not username:
        return jsonify({"error": "Username is required"}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT COUNT(*) FROM scraped_reels 
            WHERE EXISTS (
                SELECT 1 FROM jsonb_array_elements(results) AS r 
                WHERE r->>'username' = %s
            )
        """, (username,))
        jobs_count = cur.fetchone()[0]
        
        app.logger.info(f"📊 Found {jobs_count} jobs containing username: {username}")
        
        cur.execute("""
            DELETE FROM scraped_reels 
            WHERE EXISTS (
                SELECT 1 FROM jsonb_array_elements(results) AS r 
                WHERE r->>'username' = %s
            )
        """, (username,))
        
        deleted_count = cur.rowcount
        conn.commit()
        
        app.logger.info(f"✅ PERMANENTLY DELETED {deleted_count} jobs for username: {username}")
        
        return jsonify({
            "status": "success",
            "message": f"Permanently deleted {deleted_count} jobs for @{username}",
            "deleted_count": deleted_count,
            "jobs_found": jobs_count
        })
        
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
        items.append({
            "id": e.get("id"),
            "title": (e.get("title") or e.get("description") or "Instagram video").strip()[:140],
            "thumbnail": e.get("thumbnail"),
            "duration": e.get("duration"),
            "uploader": e.get("uploader") or e.get("uploader_id"),
            "ext": e.get("ext", "mp4"),
        })

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
        response = {
            "status": "success",
            "url": url,
            "media_id": media_id,
            "action": action,
            "timestamp": datetime.utcnow().isoformat()
        }

        with yt_dlp.YoutubeDL(base_ydl_opts()) as ydl:
            info = ydl.extract_info(url, download=False)

        entries = info.get("entries") if "entries" in info else [info]
        entries = [e for e in entries if e]

        if not entries:
            return jsonify({"error": "No videos found"}), 422

        target = entries[0]
        if media_id:
            target = next((e for e in entries if e.get("id") == media_id), None) or target

        video_info = {
            "id": target.get("id"),
            "title": target.get("title", "Instagram video"),
            "duration": target.get("duration"),
            "uploader": target.get("uploader") or target.get("uploader_id"),
            "thumbnail": target.get("thumbnail"),
            "ext": target.get("ext", "mp4")
        }
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

        return jsonify({
            "status": "success",
            "message": "Credentials saved successfully!",
            "handle": session_data.get('handle'),
            "did": session_data.get('did'),
            "remembered": remember
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 401

@app.route("/api/bluesky/credentials_status", methods=["GET"])
def bluesky_credentials_status():
    encrypted = session.get('bluesky_encrypted')
    identifier = session.get('bluesky_identifier')

    if encrypted:
        decrypted = decrypt_credentials(encrypted)
        if decrypted:
            return jsonify({
                "status": "success",
                "has_credentials": True,
                "identifier": identifier or decrypted[0],
                "handle": session.get('bluesky_handle', identifier or decrypted[0]),
                "message": "Credentials are saved and valid"
            })

    return jsonify({
        "status": "success",
        "has_credentials": False,
        "message": "No saved credentials found"
    })

@app.route("/api/bluesky/clear_credentials", methods=["POST"])
def clear_bluesky_credentials():
    session.pop('bluesky_encrypted', None)
    session.pop('bluesky_identifier', None)
    session.pop('bluesky_password', None)
    session.pop('bluesky_handle', None)
    session.pop('bluesky_did', None)
    session.pop('bluesky_saved', None)
    return jsonify({
        "status": "success",
        "message": "Credentials cleared successfully"
    })

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
        result = post_to_bluesky(
            video_url=url,
            text=text,
            thumbnail_url=thumbnail_url,
            identifier=identifier or None,
            password=password or None
        )

        if result["success"]:
            return jsonify({
                "status": "success",
                "post_uri": result.get("post_uri"),
                "post_cid": result.get("post_cid"),
                "post_id": result.get("post_id"),
                "message": result.get("message"),
                "video_url": url,
                "saved": bool(session.get('bluesky_saved'))
            })
        else:
            return jsonify({
                "status": "error",
                "error": result.get("error")
            }), 500

    except Exception as e:
        return jsonify({"error": clean_error(str(e))}), 500

# ============== ZERNIO (FACEBOOK) ROUTES ==============

@app.route('/api/zernio/publish', methods=['POST'])
def zernio_publish():
    """Publish a video to Facebook via Zernio"""
    data = request.get_json(silent=True) or {}
    
    video_url = data.get('video_url')
    text = data.get('text', 'Check out this video! 🎬')
    account_id = data.get('account_id')
    publish_now = data.get('publish_now', True)
    scheduled_time = data.get('scheduled_time')
    
    if not video_url:
        return jsonify({"error": "video_url is required"}), 400
    
    if account_id:
        result = publish_to_facebook(
            video_url=video_url,
            text=text,
            account_id=account_id,
            publish_now=publish_now,
            scheduled_time=scheduled_time
        )
        return jsonify(result)
    
    results = publish_video_to_all_accounts(
        video_url=video_url,
        text=text,
        publish_now=publish_now,
        scheduled_time=scheduled_time
    )
    
    return jsonify({
        "status": "success",
        "message": f"Published to {len(results)} accounts",
        "results": results
    })

@app.route('/api/zernio/status', methods=['GET'])
def zernio_status():
    """Check Zernio connection status"""
    try:
        headers = {
            "Authorization": f"Bearer {ZERNIO_API_KEY}",
            "Content-Type": "application/json"
        }
        response = requests.get(f"{ZERNIO_BASE_URL}/accounts", headers=headers, timeout=30)
        
        return jsonify({
            "status": "connected" if response.status_code == 200 else "error",
            "status_code": response.status_code,
            "message": "Zernio API is accessible" if response.status_code == 200 else "Failed to connect"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/zernio/accounts', methods=['GET'])
def zernio_list_accounts():
    """List all connected Zernio Facebook accounts (dynamic from API)"""
    try:
        headers = {
            "Authorization": f"Bearer {ZERNIO_API_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(f"{ZERNIO_BASE_URL}/accounts", headers=headers, timeout=30)
        
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
            
            return jsonify({
                "status": "success",
                "accounts": facebook_accounts,
                "total": len(facebook_accounts)
            })
        else:
            return jsonify({
                "status": "error",
                "message": f"Zernio API returned {response.status_code}",
                "accounts": []
            }), 500
            
    except Exception as e:
        app.logger.error(f"Error fetching Zernio accounts: {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "accounts": []
        }), 500

# ============== PIPELINE API ROUTES ==============

@app.route('/api/pipelines', methods=['GET'])
def get_pipelines():
    """Get all pipelines"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT 
                p.*,
                COUNT(pr.id) as total_posted_count,
                SUM(CASE WHEN pr.status = 'success' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN pr.status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                MAX(pr.posted_at) as last_post_time
            FROM pipelines p
            LEFT JOIN posted_reels pr ON p.id = pr.pipeline_id
            GROUP BY p.id
            ORDER BY p.created_at DESC
        """)
        pipelines = cur.fetchall()
        
        return jsonify({
            "status": "success",
            "pipelines": pipelines
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/pipelines', methods=['POST'])
def create_pipeline():
    """Create a new pipeline"""
    data = request.get_json(silent=True) or {}
    
    name = data.get('name')
    profile_username = data.get('profile_username')
    facebook_account_id = data.get('facebook_account_id')
    daily_limit = data.get('daily_limit', 2)
    
    if not name or not profile_username or not facebook_account_id:
        return jsonify({"error": "name, profile_username, and facebook_account_id are required"}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO pipelines (id, name, profile_username, facebook_account_id, daily_limit, is_active)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, TRUE)
            RETURNING id
        """, (name, profile_username, facebook_account_id, daily_limit))
        
        pipeline_id = cur.fetchone()[0]
        conn.commit()
        
        return jsonify({
            "status": "success",
            "message": "Pipeline created",
            "pipeline_id": pipeline_id
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/pipelines/<pipeline_id>', methods=['PUT'])
def update_pipeline(pipeline_id):
    """Update a pipeline"""
    data = request.get_json(silent=True) or {}
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        updates = []
        params = []
        
        if 'name' in data:
            updates.append("name = %s")
            params.append(data['name'])
        if 'profile_username' in data:
            updates.append("profile_username = %s")
            params.append(data['profile_username'])
        if 'facebook_account_id' in data:
            updates.append("facebook_account_id = %s")
            params.append(data['facebook_account_id'])
        if 'daily_limit' in data:
            updates.append("daily_limit = %s")
            params.append(data['daily_limit'])
        if 'is_active' in data:
            updates.append("is_active = %s")
            params.append(data['is_active'])
        
        if not updates:
            return jsonify({"error": "No fields to update"}), 400
        
        updates.append("updated_at = NOW()")
        params.append(pipeline_id)
        
        cur = conn.cursor()
        cur.execute(f"""
            UPDATE pipelines 
            SET {', '.join(updates)}
            WHERE id = %s
        """, params)
        conn.commit()
        
        return jsonify({
            "status": "success",
            "message": "Pipeline updated"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/pipelines/<pipeline_id>/run', methods=['POST'])
def run_pipeline_endpoint(pipeline_id):
    """Run a single pipeline"""
    result = run_pipeline(pipeline_id)
    if result.get('error'):
        return jsonify(result), 500
    return jsonify(result)

@app.route('/api/pipelines/run-all', methods=['POST'])
def run_all_pipelines_endpoint():
    """Run all active pipelines"""
    result = run_all_active_pipelines()
    if result.get('error'):
        return jsonify(result), 500
    return jsonify(result)

@app.route('/api/pipelines/<pipeline_id>/reset', methods=['POST'])
def reset_pipeline(pipeline_id):
    """Reset posted status for a pipeline (for testing)"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        # Delete posted records for this pipeline
        cur.execute("DELETE FROM posted_reels WHERE pipeline_id = %s", (pipeline_id,))
        # Reset pipeline stats
        cur.execute("""
            UPDATE pipelines 
            SET total_posted = 0,
                updated_at = NOW()
            WHERE id = %s
        """, (pipeline_id,))
        conn.commit()
        
        return jsonify({
            "status": "success",
            "message": "Pipeline reset - all reels marked as unposted"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/api/pipelines/<pipeline_id>/posted', methods=['GET'])
def get_posted_reels(pipeline_id):
    """Get posted reels for a pipeline with captions"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT 
                reel_url,
                direct_video_url,
                caption,
                facebook_post_id,
                facebook_post_url,
                posted_at,
                status,
                error_message
            FROM posted_reels
            WHERE pipeline_id = %s
            ORDER BY posted_at DESC
            LIMIT 50
        """, (pipeline_id,))
        posted = cur.fetchall()
        
        return jsonify({
            "status": "success",
            "posted": posted,
            "count": len(posted)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

# ============== GET SINGLE PIPELINE ==============

@app.route('/api/pipelines/<pipeline_id>', methods=['GET'])
def get_pipeline(pipeline_id):
    """Get a single pipeline by ID"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT 
                p.*,
                COUNT(pr.id) as total_posted_count,
                SUM(CASE WHEN pr.status = 'success' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN pr.status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                MAX(pr.posted_at) as last_post_time
            FROM pipelines p
            LEFT JOIN posted_reels pr ON p.id = pr.pipeline_id
            WHERE p.id = %s
            GROUP BY p.id
        """, (pipeline_id,))
        
        pipeline = cur.fetchone()
        
        if not pipeline:
            return jsonify({"error": "Pipeline not found"}), 404
        
        return jsonify({
            "status": "success",
            "pipeline": pipeline
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

# ============== DELETE PIPELINE ==============

@app.route('/api/pipelines/<pipeline_id>', methods=['DELETE'])
def delete_pipeline(pipeline_id):
    """Delete a pipeline and all its associated data."""
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor()
        
        # First, check if pipeline exists
        cur.execute("SELECT id, name FROM pipelines WHERE id = %s", (pipeline_id,))
        pipeline = cur.fetchone()
        
        if not pipeline:
            return jsonify({"error": "Pipeline not found"}), 404
        
        pipeline_name = pipeline[1]
        
        # Delete associated posted_reels (cascade will handle this if set)
        cur.execute("DELETE FROM posted_reels WHERE pipeline_id = %s", (pipeline_id,))
        posted_deleted = cur.rowcount
        
        # Delete associated pipeline_runs
        cur.execute("DELETE FROM pipeline_runs WHERE pipeline_id = %s", (pipeline_id,))
        runs_deleted = cur.rowcount
        
        # Delete the pipeline itself
        cur.execute("DELETE FROM pipelines WHERE id = %s", (pipeline_id,))
        
        conn.commit()
        
        app.logger.info(f"🗑️ Deleted pipeline '{pipeline_name}' (ID: {pipeline_id}) with {posted_deleted} posted reels and {runs_deleted} runs")
        
        return jsonify({
            "status": "success",
            "message": f"Pipeline '{pipeline_name}' deleted successfully",
            "deleted": {
                "pipeline_id": pipeline_id,
                "pipeline_name": pipeline_name,
                "posted_reels_deleted": posted_deleted,
                "runs_deleted": runs_deleted
            }
        })
        
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
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Invalid request body"}), 400

    reel_urls = data.get("reels")
    if not reel_urls or not isinstance(reel_urls, list):
        return jsonify({"error": "Missing or invalid 'reels' list"}), 400

    processed_results = []
    for reel_url in reel_urls:
        try:
            direct_url = get_direct_video_url(reel_url)
            if direct_url:
                processed_results.append({
                    "original_url": reel_url,
                    "download_url": direct_url,
                    "status": "success"
                })
            else:
                processed_results.append({
                    "original_url": reel_url,
                    "download_url": None,
                    "status": "failed",
                    "error": "Could not fetch direct URL"
                })
        except Exception as e:
            processed_results.append({
                "original_url": reel_url,
                "download_url": None,
                "status": "error",
                "error": str(e)
            })

    return jsonify({
        "status": "success",
        "processed_count": len(processed_results),
        "results": processed_results
    })

# ============== DEBUG ROUTES ==============

@app.route("/api/debug/cookies", methods=["GET"])
def debug_cookies():
    cookie_file = get_cookie_file()
    if cookie_file and os.path.exists(cookie_file):
        with open(cookie_file, 'r') as f:
            first_lines = f.readlines()[:10]

        return jsonify({
            "cookie_file_exists": True,
            "cookie_file_path": cookie_file,
            "sample_cookies": first_lines,
            "has_session_cookie": any("sessionid" in line for line in first_lines),
            "username": session.get('instagram_username') or session.get('username', 'Unknown'),
            "has_encrypted": bool(session.get('instagram_encrypted')),
            "session_permanent": session.permanent
        })
    return jsonify({
        "cookie_file_exists": False,
        "message": "No cookie file found",
        "has_encrypted": bool(session.get('instagram_encrypted')),
        "session_permanent": session.permanent
    })

@app.route("/api/debug/session", methods=["GET"])
def debug_session():
    """Debug endpoint to check session contents."""
    db_cookies = get_cookies_from_db()
    return jsonify({
        "session_keys": list(session.keys()),
        "has_instagram_encrypted": bool(session.get('instagram_encrypted')),
        "has_cookies_data": bool(session.get('cookies_data')),
        "instagram_username": session.get('instagram_username'),
        "username": session.get('username'),
        "session_permanent": session.permanent,
        "cookie_file": session.get('cookie_file'),
        "db_cookies": db_cookies is not None,
        "db_username": db_cookies.get('username') if db_cookies else None,
        "user_id_from_cookie": request.cookies.get('user_id'),
        "user_id_from_session": session.get('user_id')
    })

@app.route("/api/init", methods=["GET"])
def init_session():
    """Initialize session and return user_id."""
    user_id = FIXED_USER_ID
    session['user_id'] = user_id
    
    db_cookies = get_cookies_from_db()
    
    if db_cookies and not session.get('instagram_encrypted'):
        cookies_data = db_cookies.get('cookie_data', [])
        username = db_cookies.get('username', 'Instagram User')
        
        encrypted = encrypt_credentials(json.dumps(cookies_data), "instagram_cookies")
        if encrypted:
            session['instagram_encrypted'] = encrypted
            session['instagram_username'] = username
            session['instagram_saved'] = True
            session['cookies_data'] = cookies_data
            session['username'] = username
    
    return jsonify({
        "status": "success",
        "user_id": user_id,
        "has_cookies": True
    })


@app.route("/api/sync-captions", methods=["POST"])
def sync_captions():
    """
    Sync captions for a specific username.
    Fetches captions for ALL reels of that profile using the caption service.
    """
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    
    if not username:
        return jsonify({"error": "Username is required"}), 400
    
    app.logger.info(f"📝 Syncing captions for @{username}")
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get the latest scraped data for this username
        cur.execute("""
            SELECT id, results FROM scraped_reels 
            WHERE EXISTS (
                SELECT 1 FROM jsonb_array_elements(results) AS elem
                WHERE elem->>'username' = %s
            )
            ORDER BY created_at DESC
            LIMIT 1
        """, (username,))
        
        result = cur.fetchone()
        if not result:
            return jsonify({
                "error": f"No scraped data found for @{username}",
                "message": f"Please scrape @{username} first"
            }), 404
        
        results = result['results']
        updated = False
        total_reels = 0
        captions_fetched = 0
        captions_skipped = 0
        errors = 0
        
        # Process each profile
        for profile_idx, profile in enumerate(results):
            if profile.get('username') == username:
                reels = profile.get('reels', [])
                total_reels = len(reels)
                
                app.logger.info(f"📹 Processing {total_reels} reels for @{username}")
                
                # 🔥 FIX: Collect all URLs that need captions
                urls_to_fetch = []
                reel_indices = []
                
                for reel_idx, reel in enumerate(reels):
                    if isinstance(reel, dict):
                        reel_url = reel.get('url')
                        existing_caption = reel.get('caption', '')
                        if existing_caption and existing_caption.strip():
                            captions_skipped += 1
                            continue
                        if reel_url:
                            urls_to_fetch.append(reel_url)
                            reel_indices.append(reel_idx)
                    else:
                        # Convert string to dict
                        reel_url = str(reel)
                        urls_to_fetch.append(reel_url)
                        reel_indices.append(reel_idx)
                
                # 🔥 FIX: Fetch ALL captions in one batch
                if urls_to_fetch:
                    app.logger.info(f"📤 Fetching {len(urls_to_fetch)} captions in batch...")
                    
                    # Use the batch endpoint
                    try:
                        response = requests.post(
                            f"{CAPTION_SERVICE_URL}/batch",
                            json={"urls": urls_to_fetch},
                            timeout=60 * len(urls_to_fetch),  # 60 seconds per URL
                            headers={"Content-Type": "application/json"}
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            if data.get('success'):
                                captions_map = {}
                                for item in data.get('results', []):
                                    if item.get('success'):
                                        captions_map[item['url']] = item.get('caption', '')
                                
                                # Update each reel with its caption
                                for reel_idx, reel_url in zip(reel_indices, urls_to_fetch):
                                    caption = captions_map.get(reel_url, '')
                                    if caption:
                                        results[profile_idx]['reels'][reel_idx]['caption'] = caption
                                        captions_fetched += 1
                                        updated = True
                                    else:
                                        results[profile_idx]['reels'][reel_idx]['caption'] = ''
                                        errors += 1
                            else:
                                app.logger.error("Batch API returned error")
                                errors += len(urls_to_fetch)
                        else:
                            app.logger.error(f"Batch API error: {response.status_code}")
                            errors += len(urls_to_fetch)
                            
                    except requests.exceptions.Timeout:
                        app.logger.error("Batch API timeout")
                        errors += len(urls_to_fetch)
                    except Exception as e:
                        app.logger.error(f"Batch API error: {e}")
                        errors += len(urls_to_fetch)
                else:
                    app.logger.info("No URLs need caption fetching")
                
                break
        
        if updated:
            # Save back to database
            cur.execute("""
                UPDATE scraped_reels 
                SET results = %s, updated_at = NOW()
                WHERE id = %s
            """, (json.dumps(results), result['id']))
            conn.commit()
            
            # Also update reel_cache
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
                                    caption = EXCLUDED.caption,
                                    created_at = NOW()
                            """, (reel_url, caption))
            conn.commit()
            
            return jsonify({
                "status": "success",
                "message": f"Synced captions for @{username}",
                "total_reels": total_reels,
                "captions_fetched": captions_fetched,
                "captions_skipped": captions_skipped,
                "errors": errors,
                "username": username
            })
        else:
            return jsonify({
                "status": "success",
                "message": f"No new captions needed for @{username}",
                "total_reels": total_reels,
                "captions_fetched": 0,
                "captions_skipped": captions_skipped,
                "errors": errors,
                "username": username
            })
        
    except Exception as e:
        app.logger.error(f"Sync captions error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

def update_reel_cache(cur, results):
    """Helper function to update reel_cache with captions."""
    for profile in results:
        for reel in profile.get('reels', []):
            if isinstance(reel, dict):
                reel_url = reel.get('url')
                caption = reel.get('caption', '')
                if reel_url and caption:
                    cur.execute("""
                        UPDATE reel_cache 
                        SET caption = %s, created_at = NOW()
                        WHERE reel_url = %s
                    """, (caption, reel_url))
                    if cur.rowcount == 0:
                        # Not in cache, insert
                        cur.execute("""
                            INSERT INTO reel_cache (reel_url, direct_url, caption, created_at)
                            VALUES (%s, '', %s, NOW())
                            ON CONFLICT (reel_url) DO UPDATE SET 
                                caption = EXCLUDED.caption,
                                created_at = NOW()
                        """, (reel_url, caption))




@app.route("/api/commands/status", methods=["GET"])
def api_status():
    cookie_status = "configured" if get_cookie_file() else "not configured"
    return jsonify({
        "status": "running",
        "version": "1.3.0",
        "cookies": cookie_status,
        "zernio_connected": bool(ZERNIO_API_KEY),
        "download_history_count": 0,
        "recent_downloads": []
    })

# ============== AFTER REQUEST ==============

@app.after_request
def after_request(response):
    """Ensure user_id cookie is set on every response."""
    response.set_cookie(
        'user_id',
        FIXED_USER_ID,
        max_age=30*24*60*60,
        path='/',
        secure=os.environ.get('FLASK_ENV') == 'production' or bool(os.environ.get('VERCEL')),
        httponly=True,
        samesite='Lax'
    )
    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)