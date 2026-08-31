import os
import re
import uuid
import shutil
import tempfile
import json
import time
import hashlib
import base64
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file, render_template, after_this_request, redirect, session, url_for
from flask_cors import CORS
import yt_dlp
import requests
from urllib.parse import urlencode, quote

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
CORS(app)

IG_URL_RE = re.compile(r"^https?://(www\.)?instagram\.com/", re.IGNORECASE)

# For Vercel - only /tmp is writable
DOWNLOAD_ROOT = os.path.join('/tmp', "igdl_downloads")
os.makedirs(DOWNLOAD_ROOT, exist_ok=True)

# For local development, also support local temp
if not os.path.exists(DOWNLOAD_ROOT):
    DOWNLOAD_ROOT = os.path.join(tempfile.gettempdir(), "igdl_downloads")
    os.makedirs(DOWNLOAD_ROOT, exist_ok=True)

# Store download history
download_history = []

# Instagram OAuth-like configuration
# These are the same credentials used by the Instagram web app
INSTAGRAM_CLIENT_ID = "936619743392459"  # Instagram's web app client ID
INSTAGRAM_REDIRECT_URI = os.environ.get('REDIRECT_URI', 'http://localhost:5000/oauth/callback')
INSTAGRAM_OAUTH_URL = "https://www.instagram.com/oauth/authorize"
INSTAGRAM_TOKEN_URL = "https://www.instagram.com/oauth/access_token"
INSTAGRAM_API_URL = "https://graph.instagram.com"

# Session storage (in production, use Redis or database)
active_sessions = {}


def is_valid_instagram_url(url: str) -> bool:
    return bool(url) and bool(IG_URL_RE.match(url.strip()))


def get_cookie_file():
    """
    Get cookies from session, environment variable, or file.
    """
    # PRIORITY 1: Check if we have session cookies
    session_cookie_file = session.get('cookie_file')
    if session_cookie_file and os.path.exists(session_cookie_file):
        # Check if session is still valid
        try:
            with open(session_cookie_file, 'r') as f:
                content = f.read()
                if 'sessionid' in content and 'ds_user_id' in content:
                    app.logger.info(f"Using session cookies from: {session_cookie_file}")
                    return session_cookie_file
        except:
            pass
    
    # PRIORITY 2: Check active sessions
    for session_id, session_data in active_sessions.items():
        cookie_file = session_data.get('cookie_file')
        expiry = session_data.get('expiry', 0)
        if cookie_file and os.path.exists(cookie_file) and time.time() < expiry:
            app.logger.info(f"Using active session: {session_id}")
            return cookie_file
    
    # PRIORITY 3: Check environment variable (Vercel)
    cookies_json_env = os.environ.get('COOKIES_JSON')
    if cookies_json_env:
        try:
            app.logger.info("Found COOKIES_JSON environment variable")
            cookies_data = json.loads(cookies_json_env)
            
            cookie_file = os.path.join('/tmp', 'cookies_netscape.txt')
            with open(cookie_file, 'w') as f:
                f.write("# Netscape HTTP Cookie File\n")
                for cookie in cookies_data:
                    if isinstance(cookie, dict):
                        domain = cookie.get('domain', '')
                        flag = 'TRUE' if cookie.get('hostOnly') != True else 'FALSE'
                        path = cookie.get('path', '/')
                        secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'
                        expiry = cookie.get('expirationDate')
                        if expiry is None:
                            expiry = cookie.get('expiry', 0)
                        expiry = str(int(expiry) if expiry else '0')
                        name = cookie.get('name', '')
                        value = cookie.get('value', '')
                        if not name or not domain:
                            continue
                        f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")
            
            app.logger.info(f"Converted COOKIES_JSON to Netscape format at: {cookie_file}")
            return cookie_file
            
        except Exception as e:
            app.logger.error(f"Failed to parse COOKIES_JSON: {e}")
    
    # PRIORITY 4: Check for cookies.json file
    cookie_json_path = os.path.join(os.getcwd(), 'cookies.json')
    if os.path.exists(cookie_json_path):
        try:
            app.logger.info(f"Found cookies.json at: {cookie_json_path}")
            
            with open(cookie_json_path, 'r') as f:
                cookies_data = json.load(f)
            
            cookie_file = os.path.join('/tmp', 'cookies_netscape.txt')
            with open(cookie_file, 'w') as f:
                f.write("# Netscape HTTP Cookie File\n")
                for cookie in cookies_data:
                    if isinstance(cookie, dict):
                        domain = cookie.get('domain', '')
                        flag = 'TRUE' if cookie.get('hostOnly') != True else 'FALSE'
                        path = cookie.get('path', '/')
                        secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'
                        expiry = cookie.get('expirationDate')
                        if expiry is None:
                            expiry = cookie.get('expiry', 0)
                        expiry = str(int(expiry) if expiry else '0')
                        name = cookie.get('name', '')
                        value = cookie.get('value', '')
                        if not name or not domain:
                            continue
                        f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")
            
            app.logger.info(f"Converted cookies.json to Netscape format at: {cookie_file}")
            return cookie_file
            
        except Exception as e:
            app.logger.error(f"Failed to parse cookies.json: {e}")
            return None
    
    app.logger.warning("No cookies found")
    return None


def get_instagram_oauth_url():
    """Generate Instagram OAuth URL for login."""
    state = hashlib.sha256(os.urandom(32)).hexdigest()
    session['oauth_state'] = state
    
    params = {
        'client_id': INSTAGRAM_CLIENT_ID,
        'redirect_uri': INSTAGRAM_REDIRECT_URI,
        'scope': 'user_profile,user_media',
        'response_type': 'code',
        'state': state
    }
    
    return f"{INSTAGRAM_OAUTH_URL}?{urlencode(params)}"


def exchange_code_for_token(code):
    """Exchange authorization code for access token."""
    try:
        response = requests.post(
            INSTAGRAM_TOKEN_URL,
            data={
                'client_id': INSTAGRAM_CLIENT_ID,
                'client_secret': os.environ.get('INSTAGRAM_CLIENT_SECRET', ''),
                'grant_type': 'authorization_code',
                'redirect_uri': INSTAGRAM_REDIRECT_URI,
                'code': code
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        app.logger.error(f"Token exchange failed: {e}")
        return None


def get_user_profile(access_token):
    """Get user profile from Instagram API."""
    try:
        response = requests.get(
            f"{INSTAGRAM_API_URL}/me",
            params={
                'fields': 'id,username,account_type,media_count',
                'access_token': access_token
            }
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        app.logger.error(f"Failed to get user profile: {e}")
        return None


def create_session_from_oauth(username, access_token, user_id):
    """Create a session using OAuth token and get cookies."""
    try:
        # Since Instagram doesn't provide cookies directly via OAuth,
        # we'll use the access token to authenticate and get cookies
        session_cookie_file = os.path.join('/tmp', f'oauth_cookies_{user_id}.txt')
        
        # Try to get cookies using yt-dlp with the access token
        # This is a workaround - we'll simulate a browser session
        
        # For now, we'll store the token and use it for API calls
        # The actual video download will use the token-based approach
        session_data = {
            'access_token': access_token,
            'username': username,
            'user_id': user_id,
            'cookie_file': session_cookie_file,
            'expiry': time.time() + (7 * 24 * 60 * 60),  # 7 days
            'created_at': time.time()
        }
        
        # Store in active sessions
        active_sessions[user_id] = session_data
        
        # Also store in Flask session
        session['user_id'] = user_id
        session['username'] = username
        session['cookie_file'] = session_cookie_file
        session['access_token'] = access_token
        
        return session_data
        
    except Exception as e:
        app.logger.error(f"Failed to create session: {e}")
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
    
    # Try to get cookies
    cookie_file = get_cookie_file()
    if cookie_file and os.path.exists(cookie_file):
        opts["cookiefile"] = cookie_file
        app.logger.info(f"Using cookies from: {cookie_file}")
    else:
        # Fallback: try browser cookies (works locally)
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
        
        # Fallback to first format
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
        return "Authentication required. Please login via Instagram."
    if len(msg) > 160:
        return "Couldn't process that link. Double-check it's a public post and try again."
    return msg


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/oauth/login")
def oauth_login():
    """Initiate Instagram OAuth login."""
    oauth_url = get_instagram_oauth_url()
    return redirect(oauth_url)


@app.route("/oauth/callback")
def oauth_callback():
    """Handle OAuth callback from Instagram."""
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    error_reason = request.args.get('error_reason')
    
    # Check for errors
    if error:
        app.logger.error(f"OAuth error: {error} - {error_reason}")
        return render_template('oauth_error.html', error=error, error_reason=error_reason)
    
    # Verify state
    if state != session.get('oauth_state'):
        app.logger.error("State mismatch in OAuth callback")
        return render_template('oauth_error.html', error="state_mismatch", error_reason="Security check failed")
    
    if not code:
        app.logger.error("No code in OAuth callback")
        return render_template('oauth_error.html', error="no_code", error_reason="Authorization code not received")
    
    # Exchange code for token
    token_data = exchange_code_for_token(code)
    if not token_data:
        app.logger.error("Failed to exchange code for token")
        return render_template('oauth_error.html', error="token_exchange", error_reason="Failed to get access token")
    
    access_token = token_data.get('access_token')
    user_id = token_data.get('user_id')
    
    if not access_token or not user_id:
        app.logger.error("Invalid token data received")
        return render_template('oauth_error.html', error="invalid_token", error_reason="Invalid token data")
    
    # Get user profile
    profile = get_user_profile(access_token)
    if not profile:
        app.logger.error("Failed to get user profile")
        return render_template('oauth_error.html', error="profile_fetch", error_reason="Failed to fetch user profile")
    
    username = profile.get('username', 'Instagram User')
    
    # Create session
    session_data = create_session_from_oauth(username, access_token, user_id)
    if not session_data:
        app.logger.error("Failed to create session")
        return render_template('oauth_error.html', error="session_create", error_reason="Failed to create session")
    
    # Redirect back to the app with success
    return redirect(url_for('oauth_success', username=username))


@app.route("/oauth/success")
def oauth_success():
    """Show OAuth success page."""
    username = request.args.get('username', 'Instagram User')
    return render_template('oauth_success.html', username=username)


@app.route("/api/oauth/status")
def oauth_status():
    """Check OAuth login status."""
    user_id = session.get('user_id')
    username = session.get('username')
    cookie_file = session.get('cookie_file')
    
    if user_id and username and cookie_file and os.path.exists(cookie_file):
        return jsonify({
            "status": "success",
            "logged_in": True,
            "username": username,
            "user_id": user_id,
            "cookie_file": cookie_file
        })
    else:
        return jsonify({
            "status": "success",
            "logged_in": False,
            "message": "Not logged in"
        })


@app.route("/api/oauth/logout", methods=["POST"])
def oauth_logout():
    """Logout from the app."""
    user_id = session.get('user_id')
    
    # Remove from active sessions
    if user_id and user_id in active_sessions:
        del active_sessions[user_id]
    
    # Remove cookie files
    cookie_file = session.get('cookie_file')
    if cookie_file and os.path.exists(cookie_file):
        try:
            os.remove(cookie_file)
        except:
            pass
    
    # Clear session
    session.clear()
    
    return jsonify({
        "status": "success",
        "message": "Logged out successfully"
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
        items.append(
            {
                "id": e.get("id"),
                "title": (e.get("title") or e.get("description") or "Instagram video").strip()[:140],
                "thumbnail": e.get("thumbnail"),
                "duration": e.get("duration"),
                "uploader": e.get("uploader") or e.get("uploader_id"),
                "ext": e.get("ext", "mp4"),
            }
        )

    if not items:
        return jsonify({"error": "No downloadable video found at that link."}), 422

    return jsonify({"items": items, "source_url": url})


@app.route("/api/download", methods=["GET"])
def download_video():
    url = (request.args.get("url") or "").strip()
    media_id = (request.args.get("id") or "").strip()

    if not is_valid_instagram_url(url):
        return jsonify({"error": "Invalid or missing url."}), 400

    # Try direct URL first
    try:
        direct_url = get_direct_video_url(url, media_id)
        if direct_url:
            return jsonify({"download_url": direct_url})
    except Exception as e:
        app.logger.warning(f"Direct URL failed: {e}")
        # Fall through to file download

    # Fallback: download and stream
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
        
        # Step 1: Get video info
        with yt_dlp.YoutubeDL(base_ydl_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
        
        entries = info.get("entries") if "entries" in info else [info]
        entries = [e for e in entries if e]
        
        if not entries:
            return jsonify({"error": "No videos found"}), 422
        
        # Find target entry
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
        
        # Step 2: Handle different actions
        if action == "url_only":
            # Just return the direct URL
            direct_url = get_direct_video_url(url, media_id)
            if direct_url:
                response["download_url"] = direct_url
            else:
                # Fallback to streaming URL
                response["download_url"] = f"/api/download?url={url}&id={media_id}"
                response["warning"] = "Direct URL not available, using streaming fallback"
        
        elif action == "download":
            # Download file and return it
            filepath, job_dir, target = download_video_file(url, media_id)
            download_name = f"{target.get('id', 'instagram_video')}.{target.get('ext', 'mp4')}"
            
            # Clean up after response
            @after_this_request
            def cleanup(response_obj):
                shutil.rmtree(job_dir, ignore_errors=True)
                return response_obj
            
            return send_file(filepath, as_attachment=True, download_name=download_name)
        
        else:
            return jsonify({"error": f"Unknown action: {action}"}), 400
        
        # Store in history
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


@app.route("/api/commands/status", methods=["GET"])
def api_status():
    """Get service status and download history."""
    cookie_status = "configured" if get_cookie_file() else "not configured"
    logged_in = session.get('user_id') is not None
    return jsonify({
        "status": "running",
        "version": "1.0.0",
        "cookies": cookie_status,
        "logged_in": logged_in,
        "username": session.get('username'),
        "download_history_count": len(download_history),
        "recent_downloads": download_history[-10:]
    })


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
            "logged_in": session.get('user_id') is not None,
            "username": session.get('username'),
            "env_cookies_configured": bool(os.environ.get('COOKIES_JSON'))
        })
    return jsonify({
        "cookie_file_exists": False,
        "message": "No cookie file found",
        "logged_in": False,
        "env_cookies_configured": bool(os.environ.get('COOKIES_JSON'))
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)