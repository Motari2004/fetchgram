import os
import re
import uuid
import shutil
import tempfile
import json
import time
from datetime import datetime
from flask import Flask, request, jsonify, send_file, render_template, after_this_request, redirect, session
from flask_cors import CORS
import yt_dlp
import requests

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
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


def is_valid_instagram_url(url: str) -> bool:
    return bool(url) and bool(IG_URL_RE.match(url.strip()))


def get_cookie_file():
    """
    Get cookies from login session, environment variable, or file.
    """
    # PRIORITY 1: Check if we have login cookies from session
    cookie_file = session.get('cookie_file')
    if cookie_file and os.path.exists(cookie_file):
        app.logger.info(f"Using login cookies from: {cookie_file}")
        return cookie_file
    
    # PRIORITY 2: Check environment variable (Vercel)
    cookies_json_env = os.environ.get('COOKIES_JSON')
    if cookies_json_env:
        try:
            app.logger.info("Found COOKIES_JSON environment variable")
            cookies_data = json.loads(cookies_json_env)
            
            # Convert to Netscape format
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
    
    # PRIORITY 3: Check for cookies.json in the current directory (local development)
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


def get_instagram_session_from_browser():
    """
    Detect Instagram session from browser cookies using yt-dlp's cookie extraction.
    """
    try:
        # Try to extract cookies from browser
        import subprocess
        
        # Use yt-dlp to extract cookies
        cmd = ['yt-dlp', '--cookies-from-browser', 'chrome', '--cookies', '/tmp/browser_cookies.txt', '--skip-download', 'https://instagram.com']
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if os.path.exists('/tmp/browser_cookies.txt'):
            # Read the cookies
            with open('/tmp/browser_cookies.txt', 'r') as f:
                cookies = f.read()
            
            # Parse to get username
            session_cookie = None
            for line in cookies.split('\n'):
                if 'sessionid' in line:
                    session_cookie = line
                    break
            
            if session_cookie:
                # Extract username from session cookie
                parts = session_cookie.split('\t')
                if len(parts) >= 7:
                    username = parts[6] if parts[6] else 'Instagram User'
                    return {
                        'success': True,
                        'username': username,
                        'cookie_file': '/tmp/browser_cookies.txt',
                        'message': f'Found Instagram session for @{username}'
                    }
        
        return {
            'success': False,
            'error': 'Could not detect Instagram session in browser'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def detect_instagram_user_from_cookies(cookie_file):
    """
    Detect Instagram username from cookies.
    """
    try:
        if not os.path.exists(cookie_file):
            return None
        
        with open(cookie_file, 'r') as f:
            content = f.read()
        
        # Look for ds_user_id or sessionid
        for line in content.split('\n'):
            if 'ds_user_id' in line or 'sessionid' in line:
                parts = line.split('\t')
                if len(parts) >= 7:
                    # Try to find username
                    if parts[5] == 'ds_user':
                        return parts[6]
                    elif parts[5] == 'sessionid':
                        # sessionid format: username%3A...
                        if '%3A' in parts[6]:
                            return parts[6].split('%3A')[0]
                        elif ':' in parts[6]:
                            return parts[6].split(':')[0]
        
        return None
    except Exception:
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
        return "Authentication required. Please login or check your cookies."
    if len(msg) > 160:
        return "Couldn't process that link. Double-check it's a public post and try again."
    return msg


@app.route("/")
def index():
    return render_template("index.html")


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
    return jsonify({
        "status": "running",
        "version": "1.0.0",
        "cookies": cookie_status,
        "download_history_count": len(download_history),
        "recent_downloads": download_history[-10:]
    })


@app.route("/api/session/detect", methods=["GET"])
def detect_session():
    """Detect Instagram session from browser cookies."""
    result = get_instagram_session_from_browser()
    return jsonify(result)


@app.route("/api/session/status", methods=["GET"])
def session_status():
    """Check if we have a valid Instagram session."""
    cookie_file = get_cookie_file()
    if cookie_file and os.path.exists(cookie_file):
        # Try to detect username
        username = detect_instagram_user_from_cookies(cookie_file)
        return jsonify({
            "status": "success",
            "has_session": True,
            "username": username or "Unknown",
            "cookie_file": cookie_file
        })
    else:
        return jsonify({
            "status": "success",
            "has_session": False,
            "message": "No Instagram session found"
        })


@app.route("/api/session/use_browser", methods=["POST"])
def use_browser_session():
    """Use the browser's Instagram session."""
    result = get_instagram_session_from_browser()
    
    if result['success']:
        session['cookie_file'] = result['cookie_file']
        session['username'] = result.get('username', 'Instagram User')
        
        return jsonify({
            "status": "success",
            "username": result.get('username'),
            "message": result.get('message'),
            "cookie_file": result.get('cookie_file')
        })
    else:
        return jsonify({
            "status": "error",
            "error": result.get('error', 'Failed to detect Instagram session')
        }), 404


@app.route("/api/session/logout", methods=["POST"])
def logout_session():
    """Clear the session."""
    # Remove cookie files
    for file in ['cookies_netscape.txt', 'browser_cookies.txt', 'instagram_cookies.json']:
        path = os.path.join('/tmp', file)
        if os.path.exists(path):
            try:
                os.remove(path)
            except:
                pass
    
    session.clear()
    return jsonify({
        "status": "success",
        "message": "Session cleared successfully"
    })


@app.route("/api/debug/cookies", methods=["GET"])
def debug_cookies():
    """Debug endpoint to check cookie status."""
    cookie_file = get_cookie_file()
    if cookie_file and os.path.exists(cookie_file):
        with open(cookie_file, 'r') as f:
            first_lines = f.readlines()[:10]
        
        username = detect_instagram_user_from_cookies(cookie_file)
        
        return jsonify({
            "cookie_file_exists": True,
            "cookie_file_path": cookie_file,
            "sample_cookies": first_lines,
            "has_session_cookie": any("sessionid" in line for line in first_lines),
            "username": username or "Unknown",
            "env_cookies_configured": bool(os.environ.get('COOKIES_JSON'))
        })
    return jsonify({
        "cookie_file_exists": False,
        "message": "No cookie file found",
        "env_cookies_configured": bool(os.environ.get('COOKIES_JSON'))
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)