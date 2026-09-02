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


app = Flask(__name__)
# Use a stable secret key – set SECRET_KEY in environment for production
app.secret_key = os.environ.get('SECRET_KEY', 'fetchgram-dev-secret-change-me-in-production-2024')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
# Only force Secure cookies when running on HTTPS (Vercel etc.)
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production' or bool(os.environ.get('VERCEL'))
CORS(app, supports_credentials=True)


IG_URL_RE = re.compile(r"^https?://(www\.)?instagram\.com/", re.IGNORECASE)


# For Vercel / serverless – only /tmp is writable
DOWNLOAD_ROOT = os.path.join('/tmp', "igdl_downloads")
os.makedirs(DOWNLOAD_ROOT, exist_ok=True)

# Fallback for local development
if not os.path.exists(DOWNLOAD_ROOT):
    DOWNLOAD_ROOT = os.path.join(tempfile.gettempdir(), "igdl_downloads")
    os.makedirs(DOWNLOAD_ROOT, exist_ok=True)


# In-memory history (ephemeral on serverless)
download_history = []


def is_valid_instagram_url(url: str) -> bool:
    return bool(url) and bool(IG_URL_RE.match(url.strip()))


def get_encryption_key():
    """Generate or retrieve a stable encryption key for credentials."""
    # Prefer environment variable (required for multi-instance / Vercel)
    env_key = os.environ.get('ENCRYPTION_KEY')
    if env_key:
        try:
            return base64.urlsafe_b64decode(env_key)
        except Exception:
            # If user pasted the raw Fernet key string
            return env_key.encode() if isinstance(env_key, str) else env_key

    key_file = os.path.join('/tmp', 'encryption_key.key')
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            return f.read()

    # Derive a deterministic key from secret_key so it survives restarts
    # (as long as SECRET_KEY stays the same)
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
        pass  # /tmp may be read-only in some environments

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

        # Expire after 30 days
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


def get_cookie_file():
    """Get cookies from session (encrypted), env, or file. Always rewrites /tmp file."""
    # PRIORITY 1: Persistent encrypted Instagram cookies from session
    encrypted_instagram = session.get('instagram_encrypted')
    if encrypted_instagram:
        try:
            decrypted = decrypt_credentials(encrypted_instagram)
            if decrypted:
                cookie_data, dtype = decrypted
                if dtype == 'cookies':
                    if isinstance(cookie_data, str) and cookie_data.startswith('['):
                        cookie_data = json.loads(cookie_data)
                    elif isinstance(cookie_data, dict):
                        cookie_data = cookie_data.get('data', [])

                    username = session.get('instagram_username', 'default')
                    # Sanitise username for filename
                    safe_user = re.sub(r'[^a-zA-Z0-9_-]', '_', str(username))[:40]
                    cookie_file = os.path.join('/tmp', f'instagram_cookies_{safe_user}.txt')
                    write_netscape_cookies(cookie_data, cookie_file)
                    session['cookie_file'] = cookie_file
                    app.logger.info(f"Using persistent Instagram cookies from session → {cookie_file}")
                    return cookie_file
        except Exception as e:
            app.logger.error(f"Failed to decrypt Instagram cookies: {e}")

    # PRIORITY 2: Uploaded cookies already written this session
    cookie_file = session.get('cookie_file')
    if cookie_file and os.path.exists(cookie_file):
        app.logger.info(f"Using uploaded cookies from: {cookie_file}")
        return cookie_file

    # PRIORITY 3: Environment variable (Vercel / production)
    cookies_json_env = os.environ.get('COOKIES_JSON')
    if cookies_json_env:
        try:
            cookies_data = json.loads(cookies_json_env)
            cookie_file = os.path.join('/tmp', 'cookies_netscape.txt')
            write_netscape_cookies(cookies_data, cookie_file)
            app.logger.info(f"Converted COOKIES_JSON to Netscape format at: {cookie_file}")
            return cookie_file
        except Exception as e:
            app.logger.error(f"Failed to parse COOKIES_JSON: {e}")

    # PRIORITY 4: Local cookies.json
    cookie_json_path = os.path.join(os.getcwd(), 'cookies.json')
    if os.path.exists(cookie_json_path):
        try:
            with open(cookie_json_path, 'r') as f:
                cookies_data = json.load(f)
            cookie_file = os.path.join('/tmp', 'cookies_netscape.txt')
            write_netscape_cookies(cookies_data, cookie_file)
            app.logger.info(f"Converted cookies.json to Netscape format at: {cookie_file}")
            return cookie_file
        except Exception as e:
            app.logger.error(f"Failed to parse cookies.json: {e}")

    app.logger.warning("No cookies found")
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
    else:
        # Local fallback only
        try:
            opts["cookiesfrombrowser"] = ("chrome",)
            app.logger.info("Using browser cookies")
        except Exception as e:
            app.logger.warning(f"No cookies available: {e}")

    if extra:
        opts.update(extra)
    return opts


def get_direct_video_url(url, media_id=None):
    """Extract direct video URL without downloading."""
    opts = base_ydl_opts({
        "format": "best[ext=mp4]/best",
    })

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

        entries = info.get("entries") if "entries" in info else [info]
        entries = [e for e in entries if e]

        if media_id:
            target = next((e for e in entries if e.get("id") == media_id), None)
        else:
            target = entries[0] if entries else None

        if not target:
            return None

        formats = target.get("formats", [])
        if not formats:
            return target.get("url") or target.get("webpage_url")

        # Prefer mp4 with audio
        for fmt in formats:
            if fmt.get("ext") == "mp4" and fmt.get("acodec") != "none" and fmt.get("vcodec") != "none":
                return fmt.get("url")

        return formats[0].get("url") if formats else None


def download_video_file(url, media_id=None):
    """Download video file and return filepath."""
    job_dir = os.path.join(DOWNLOAD_ROOT, uuid.uuid4().hex)
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


# ============== BLUESKY AT PROTOCOL ==============


def create_bluesky_session(identifier, password):
    """Create a Bluesky session using AT Protocol"""
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
    """Upload a blob (image or video) to Bluesky"""
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
    """Upload a video to Bluesky using the direct URL"""
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
    """Main function to post a video to Bluesky"""
    try:
        if not identifier or not password:
            # Prefer encrypted storage
            encrypted = session.get('bluesky_encrypted')
            if encrypted:
                decrypted = decrypt_credentials(encrypted)
                if decrypted:
                    identifier, password = decrypted
            # Fallback to plain session (legacy)
            if not identifier or not password:
                identifier = session.get('bluesky_identifier')
                password = session.get('bluesky_password')

        if not identifier or not password:
            raise Exception("Bluesky credentials not configured. Please enter your Bluesky handle and password.")

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


# ============== ROUTES ==============


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/cookies/upload", methods=["POST"])
def upload_cookies():
    """Upload cookies.json file (one-shot, also saves persistently)."""
    if 'cookies_file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['cookies_file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if not file.filename.endswith('.json'):
        return jsonify({"error": "File must be a JSON file"}), 400

    try:
        content = file.read().decode('utf-8')
        cookies_data = json.loads(content)

        if not isinstance(cookies_data, list):
            return jsonify({"error": "Invalid cookie format - expected an array"}), 400

        has_session = any(
            isinstance(c, dict) and c.get('name') in ('sessionid', 'ds_user_id')
            for c in cookies_data
        )
        if not has_session:
            return jsonify({"error": "No session cookies found. Make sure you're logged into Instagram."}), 400

        # Extract username
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

        # Persist encrypted
        encrypted = encrypt_credentials(json.dumps(cookies_data), "instagram_cookies")
        if encrypted:
            session.permanent = True
            session['instagram_encrypted'] = encrypted
            session['instagram_username'] = username or 'Instagram User'
            session['instagram_saved'] = True

        # Also write file for immediate use
        cookie_id = uuid.uuid4().hex[:8]
        cookie_file = os.path.join('/tmp', f'uploaded_cookies_{cookie_id}.txt')
        write_netscape_cookies(cookies_data, cookie_file)
        session['cookie_file'] = cookie_file
        session['cookie_id'] = cookie_id
        session['username'] = username or 'Instagram User'

        return jsonify({
            "status": "success",
            "message": "Cookies uploaded and saved persistently!",
            "username": session['username'],
            "cookie_id": cookie_id
        })

    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON file"}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to process cookies: {str(e)}"}), 500


@app.route("/api/cookies/status", methods=["GET"])
def cookies_status():
    """Check if cookies are uploaded and valid."""
    cookie_file = get_cookie_file()
    if cookie_file and os.path.exists(cookie_file):
        return jsonify({
            "status": "success",
            "has_cookies": True,
            "username": session.get('instagram_username') or session.get('username', 'Instagram User'),
            "cookie_file": cookie_file
        })
    return jsonify({
        "status": "success",
        "has_cookies": False,
        "message": "No cookies uploaded"
    })


@app.route("/api/cookies/clear", methods=["POST"])
def clear_cookies():
    """Clear uploaded cookies."""
    cookie_file = session.get('cookie_file')
    if cookie_file and os.path.exists(cookie_file):
        try:
            os.remove(cookie_file)
        except Exception:
            pass

    cookie_id = session.get('cookie_id')
    if cookie_id:
        json_file = os.path.join('/tmp', f'uploaded_cookies_{cookie_id}.json')
        if os.path.exists(json_file):
            try:
                os.remove(json_file)
            except Exception:
                pass

    session.pop('cookie_file', None)
    session.pop('cookie_id', None)
    session.pop('username', None)
    session.pop('instagram_encrypted', None)
    session.pop('instagram_username', None)
    session.pop('instagram_saved', None)

    return jsonify({
        "status": "success",
        "message": "Cookies cleared successfully"
    })


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

    job_dir = os.path.join(DOWNLOAD_ROOT, uuid.uuid4().hex)
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
        return jsonify({"error": clean_error(str(e))}), 422
    except Exception as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": clean_error(str(e))}), 500

    entries = info.get("entries") if "entries" in info else [info]
    entries = [e for e in entries if e]
    target = None
    if media_id:
        target = next((e for e in entries if e.get("id") == media_id), None)
    if target is None and entries:
        target = entries[0]

    if target is None:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": "No video found to download."}), 422

    filepath = target.get("requested_downloads", [{}])[0].get("filepath") or os.path.join(
        job_dir, f"{target.get('id')}.{target.get('ext', 'mp4')}"
    )

    if not os.path.exists(filepath):
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"error": "File was fetched but couldn't be located."}), 500

    download_name = f"{target.get('id', 'instagram_video')}.{target.get('ext', 'mp4')}"

    @after_this_request
    def cleanup(response):
        shutil.rmtree(job_dir, ignore_errors=True)
        return response

    return send_file(filepath, as_attachment=True, download_name=download_name)


@app.route("/api/commands/download", methods=["POST"])
def api_download():
    """API endpoint to download Instagram video."""
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    media_id = (data.get("media_id") or "").strip()
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

        target = None
        if media_id:
            target = next((e for e in entries if e.get("id") == media_id), None)
        if target is None:
            target = entries[0]

        if not target:
            return jsonify({"error": "Video not found"}), 422

        video_info = {
            "id": target.get("id"),
            "title": target.get("title", "Instagram video"),
            "duration": target.get("duration"),
            "uploader": target.get("uploader") or target.get("uploader_id"),
            "thumbnail": target.get("thumbnail"),
            "ext": target.get("ext", "mp4")
        }
        response["video_info"] = video_info

        # Store current video in session for Bluesky
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

        download_history.append(response)
        if len(download_history) > 100:
            download_history.pop(0)

        return jsonify(response)

    except Exception as e:
        return jsonify({"error": clean_error(str(e))}), 500


@app.route("/api/commands/batch", methods=["POST"])
def api_batch_download():
    """Batch download multiple videos."""
    data = request.get_json(silent=True) or {}
    urls = data.get("urls", [])
    action = data.get("action", "url_only")

    if not urls:
        return jsonify({"error": "No URLs provided"}), 400

    results = []
    for url in urls:
        try:
            with yt_dlp.YoutubeDL(base_ydl_opts()) as ydl:
                info = ydl.extract_info(url, download=False)

            entries = info.get("entries") if "entries" in info else [info]
            entries = [e for e in entries if e]

            for entry in entries:
                results.append({
                    "url": url,
                    "id": entry.get("id"),
                    "title": entry.get("title", "Instagram video"),
                    "uploader": entry.get("uploader") or entry.get("uploader_id"),
                    "download_url": get_direct_video_url(url, entry.get("id"))
                })
        except Exception as e:
            results.append({
                "url": url,
                "error": str(e)
            })

    return jsonify({
        "status": "success",
        "total": len(results),
        "results": results,
        "timestamp": datetime.utcnow().isoformat()
    })


@app.route("/api/bluesky/save_credentials", methods=["POST"])
def save_bluesky_credentials():
    """Save Bluesky credentials securely and persistently."""
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
                session.permanent = True          # ← critical for 30-day persistence
                session['bluesky_encrypted'] = encrypted
                session['bluesky_identifier'] = identifier
                # Do NOT store plaintext password any more
                session.pop('bluesky_password', None)
                session['bluesky_handle'] = session_data.get('handle', identifier)
                session['bluesky_did'] = session_data.get('did')
                session['bluesky_saved'] = True

        return jsonify({
            "status": "success",
            "message": "Credentials saved successfully! They will persist for 30 days.",
            "handle": session_data.get('handle'),
            "did": session_data.get('did'),
            "remembered": remember
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 401


@app.route("/api/bluesky/credentials_status", methods=["GET"])
def bluesky_credentials_status():
    """Check if Bluesky credentials are saved."""
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

    if identifier and session.get('bluesky_password'):
        return jsonify({
            "status": "success",
            "has_credentials": True,
            "identifier": identifier,
            "handle": session.get('bluesky_handle', identifier),
            "message": "Credentials are saved"
        })

    return jsonify({
        "status": "success",
        "has_credentials": False,
        "message": "No saved credentials found"
    })


@app.route("/api/bluesky/clear_credentials", methods=["POST"])
def clear_bluesky_credentials():
    """Clear saved Bluesky credentials."""
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
    """Post a video to Bluesky."""
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


@app.route("/api/bluesky/auth", methods=["POST"])
def bluesky_auth():
    """Authenticate with Bluesky and return session info."""
    data = request.get_json(silent=True) or {}
    identifier = data.get("identifier", "").strip()
    password = data.get("password", "").strip()

    if not identifier or not password:
        return jsonify({"error": "Missing identifier or password"}), 400

    try:
        session_data = create_bluesky_session(identifier, password)
        return jsonify({
            "status": "success",
            "did": session_data.get("did"),
            "handle": session_data.get("handle"),
            "email": session_data.get("email"),
            "message": "Authentication successful!"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 401


@app.route("/api/bluesky/status", methods=["GET"])
def bluesky_status():
    """Check if Bluesky is configured."""
    has_credentials = bool(session.get('bluesky_encrypted')) or bool(
        os.environ.get("BLUESKY_IDENTIFIER") and
        os.environ.get("BLUESKY_PASSWORD")
    )
    return jsonify({
        "configured": has_credentials,
        "message": "Bluesky credentials are configured" if has_credentials else "Bluesky credentials are not configured."
    })


@app.route("/api/commands/status", methods=["GET"])
def api_status():
    """Get service status and download history."""
    cookie_status = "configured" if get_cookie_file() else "not configured"
    return jsonify({
        "status": "running",
        "version": "1.1.0",
        "cookies": cookie_status,
        "download_history_count": len(download_history),
        "recent_downloads": download_history[-10:]
    })


@app.route("/api/instagram/save_cookies", methods=["POST"])
def save_instagram_cookies():
    """Save Instagram cookies persistently (encrypted in session cookie)."""
    data = request.get_json(silent=True) or {}
    cookies_data = data.get("cookies", [])
    remember = data.get("remember", True)

    if not cookies_data:
        return jsonify({"error": "No cookies provided"}), 400

    try:
        if remember:
            cookies_json = json.dumps(cookies_data)
            encrypted = encrypt_credentials(cookies_json, "instagram_cookies")
            if encrypted:
                session.permanent = True          # ← critical for 30-day persistence
                session['instagram_encrypted'] = encrypted

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

                session['instagram_username'] = username or 'Instagram User'
                session['instagram_saved'] = True

                # Write file for immediate use this request
                cookie_file = os.path.join('/tmp', 'instagram_cookies_persistent.txt')
                write_netscape_cookies(cookies_data, cookie_file)
                session['cookie_file'] = cookie_file

                return jsonify({
                    "status": "success",
                    "message": "Cookies saved successfully! They will persist for 30 days.",
                    "username": username
                })

        return jsonify({"status": "error", "error": "Failed to save cookies"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/instagram/cookies_status", methods=["GET"])
def instagram_cookies_status():
    """Check if Instagram cookies are saved."""
    encrypted = session.get('instagram_encrypted')

    if encrypted:
        try:
            decrypted = decrypt_credentials(encrypted)
            if decrypted:
                return jsonify({
                    "status": "success",
                    "has_cookies": True,
                    "username": session.get('instagram_username', 'Instagram User'),
                    "message": "Cookies are saved and valid"
                })
        except Exception:
            pass

    return jsonify({
        "status": "success",
        "has_cookies": False,
        "message": "No saved cookies found"
    })


@app.route("/api/instagram/clear_cookies", methods=["POST"])
def clear_instagram_cookies():
    """Clear saved Instagram cookies."""
    session.pop('instagram_encrypted', None)
    session.pop('instagram_username', None)
    session.pop('instagram_saved', None)
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
        "message": "Instagram cookies cleared successfully"
    })





@app.route("/api/process-reels", methods=["POST"])
def process_reels():
    """
    Receives a list of Instagram Reel URLs, processes each to get a direct download URL,
    and returns the results.
    Expects JSON: {"reels": ["url1", "url2", ...]}
    """
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Invalid request body"}), 400

    reel_urls = data.get("reels")
    if not reel_urls or not isinstance(reel_urls, list):
        return jsonify({"error": "Missing or invalid 'reels' list"}), 400

    processed_results = []
    for reel_url in reel_urls:
        try:
            # Use your existing function to get the direct download URL
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


@app.route("/api/instagram/get_cookies", methods=["GET"])
def get_instagram_cookies():
    """Get the stored Instagram cookies."""
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
                return jsonify({
                    "status": "success",
                    "cookies": cookie_data
                })
        except Exception as e:
            app.logger.error(f"Failed to get cookies: {e}")
    
    return jsonify({
        "status": "error",
        "cookies": None,
        "error": "No cookies found"
    }), 404




@app.route("/api/debug/cookies", methods=["GET"])
def debug_cookies():
    """Debug endpoint to check cookie status."""
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




# ============== SCRAPED DATA STORAGE (for Render integration) ==============

# In-memory store for scraped data (ephemeral on serverless)
scraped_data_store = {}

@app.route("/api/scraped/store", methods=["POST"])
def store_scraped_data():
    """Store scraped data from Render."""
    data = request.get_json(silent=True) or {}
    results = data.get("results", [])
    job_id = data.get("job_id")
    
    if not results:
        return jsonify({"error": "No results provided"}), 400
    
    # Store in memory with timestamp
    scraped_data_store['latest'] = {
        'results': results,
        'job_id': job_id,
        'timestamp': datetime.utcnow().isoformat(),
        'count': len(results)
    }
    
    app.logger.info(f"Stored {len(results)} profiles from job {job_id}")
    
    return jsonify({
        "status": "success",
        "message": f"Stored {len(results)} profiles",
        "count": len(results)
    })


@app.route("/api/scraped/latest", methods=["GET"])
def get_scraped_data():
    """Get the latest scraped data."""
    latest = scraped_data_store.get('latest')
    if not latest:
        return jsonify({
            "status": "success",
            "results": [],
            "message": "No scraped data available"
        })
    
    return jsonify({
        "status": "success",
        "results": latest.get('results', []),
        "job_id": latest.get('job_id'),
        "timestamp": latest.get('timestamp'),
        "count": latest.get('count', 0)
    })


@app.route("/api/scraped/clear", methods=["POST"])
def clear_scraped_data():
    """Clear stored scraped data."""
    scraped_data_store.clear()
    return jsonify({
        "status": "success",
        "message": "Scraped data cleared"
    })






if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)