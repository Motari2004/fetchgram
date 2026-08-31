import os
import re
import uuid
import shutil
import tempfile
import json
import base64
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify, send_file, render_template, after_this_request, redirect
from flask_cors import CORS
import yt_dlp
import requests

app = Flask(__name__)
CORS(app)

IG_URL_RE = re.compile(r"^https?://(www\.)?instagram\.com/", re.IGNORECASE)

# For Vercel compatibility
DOWNLOAD_ROOT = os.path.join('/tmp', "igdl_downloads")
os.makedirs(DOWNLOAD_ROOT, exist_ok=True)

# For local development
if not os.path.exists(DOWNLOAD_ROOT):
    DOWNLOAD_ROOT = os.path.join(tempfile.gettempdir(), "igdl_downloads")
    os.makedirs(DOWNLOAD_ROOT, exist_ok=True)

# Store download history
download_history = []


def is_valid_instagram_url(url: str) -> bool:
    return bool(url) and bool(IG_URL_RE.match(url.strip()))


def get_cookie_file():
    """Get cookies from cookies.json in the root directory."""
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
            return cookie_file
        except Exception as e:
            app.logger.error(f"Failed to parse cookies.json: {e}")
            return None
    
    app.logger.warning("No cookies.json found")
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
        return "Authentication required. Please check your cookies.json file."
    if len(msg) > 160:
        return "Couldn't process that link. Double-check it's a public post and try again."
    return msg


# ============== BLUESKY AT PROTOCOL INTEGRATION ==============

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

def upload_bluesky_blob(session, file_data, mime_type):
    """Upload a blob (image or video) to Bluesky"""
    try:
        response = requests.post(
            "https://bsky.social/xrpc/com.atproto.repo.uploadBlob",
            headers={
                "Authorization": f"Bearer {session['accessJwt']}",
                "Content-Type": mime_type
            },
            data=file_data,
            timeout=60
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to upload blob to Bluesky: {str(e)}")

def upload_video_to_bluesky(session, video_url, text, thumbnail_url=None):
    """Upload a video to Bluesky using the direct URL"""
    try:
        # Download the video
        print(f"Downloading video from: {video_url}")
        video_response = requests.get(video_url, stream=True, timeout=60)
        video_response.raise_for_status()
        
        content_type = video_response.headers.get("content-type", "video/mp4")
        if not content_type.startswith("video/"):
            content_type = "video/mp4"
        
        # Upload video blob
        print("Uploading video to Bluesky...")
        blob_response = upload_bluesky_blob(session, video_response.content, content_type)
        
        # Get user's DID
        did = session["did"]
        
        # Create post with video embed
        record = {
            "$type": "app.bsky.feed.post",
            "text": text or "Instagram video",
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "embed": {
                "$type": "app.bsky.embed.video",
                "video": blob_response["blob"]
            }
        }
        
        # Add thumbnail if available
        if thumbnail_url:
            try:
                thumb_response = requests.get(thumbnail_url, timeout=10)
                thumb_response.raise_for_status()
                thumb_mime = thumb_response.headers.get("content-type", "image/jpeg")
                thumb_blob = upload_bluesky_blob(session, thumb_response.content, thumb_mime)
                record["embed"]["thumbnail"] = thumb_blob["blob"]
            except Exception as e:
                print(f"Failed to upload thumbnail: {e}")
        
        print("Creating Bluesky post...")
        response = requests.post(
            "https://bsky.social/xrpc/com.atproto.repo.createRecord",
            json={
                "repo": did,
                "collection": "app.bsky.feed.post",
                "record": record
            },
            headers={"Authorization": f"Bearer {session['accessJwt']}"},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        raise Exception(f"Failed to upload video to Bluesky: {str(e)}")

def post_to_bluesky(video_url, text, thumbnail_url=None, identifier=None, password=None):
    """Main function to post a video to Bluesky"""
    try:
        identifier = identifier or os.environ.get("BLUESKY_IDENTIFIER")
        password = password or os.environ.get("BLUESKY_PASSWORD")
        
        if not identifier or not password:
            raise Exception("Bluesky credentials not configured. Please set BLUESKY_IDENTIFIER and BLUESKY_PASSWORD environment variables.")
        
        session = create_bluesky_session(identifier, password)
        result = upload_video_to_bluesky(session, video_url, text, thumbnail_url)
        
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


@app.route("/api/bluesky/post", methods=["POST"])
def bluesky_post():
    """Post a video to Bluesky."""
    data = request.get_json(silent=True) or {}
    
    url = data.get("url", "").strip()
    text = data.get("text", "Check out this video! 🎬").strip()
    identifier = data.get("identifier", "").strip()
    password = data.get("password", "").strip()
    
    if not url:
        return jsonify({"error": "Missing 'url' parameter"}), 400
    
    try:
        if is_valid_instagram_url(url):
            direct_url = get_direct_video_url(url, None)
            if not direct_url:
                return jsonify({"error": "Could not get direct video URL"}), 422
            
            with yt_dlp.YoutubeDL(base_ydl_opts()) as ydl:
                info = ydl.extract_info(url, download=False)
            
            entries = info.get("entries") if "entries" in info else [info]
            entries = [e for e in entries if e]
            target = entries[0] if entries else None
            
            thumbnail_url = target.get("thumbnail") if target else None
            title = target.get("title", "Instagram video") if target else "Instagram video"
            video_url = direct_url
            post_text = text or f"📹 {title}"
            
        elif url.startswith("http") and (url.endswith(".mp4") or "video" in url.lower()):
            video_url = url
            post_text = text
            thumbnail_url = None
        else:
            return jsonify({"error": "Invalid URL provided"}), 400
        
        result = post_to_bluesky(
            video_url=video_url,
            text=post_text,
            thumbnail_url=thumbnail_url,
            identifier=identifier,
            password=password
        )
        
        if result["success"]:
            return jsonify({
                "status": "success",
                "post_uri": result.get("post_uri"),
                "post_cid": result.get("post_cid"),
                "post_id": result.get("post_id"),
                "message": result.get("message"),
                "video_url": video_url
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
        session = create_bluesky_session(identifier, password)
        return jsonify({
            "status": "success",
            "did": session.get("did"),
            "handle": session.get("handle"),
            "email": session.get("email"),
            "message": "Authentication successful!"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 401


@app.route("/api/bluesky/status", methods=["GET"])
def bluesky_status():
    """Check if Bluesky is configured."""
    has_credentials = bool(
        os.environ.get("BLUESKY_IDENTIFIER") and 
        os.environ.get("BLUESKY_PASSWORD")
    )
    return jsonify({
        "configured": has_credentials,
        "message": "Bluesky credentials are configured" if has_credentials else "Bluesky credentials are not configured. Set BLUESKY_IDENTIFIER and BLUESKY_PASSWORD."
    })


@app.route("/api/commands/status", methods=["GET"])
def api_status():
    """Get service status and download history."""
    cookie_status = "configured" if get_cookie_file() else "not configured"
    bluesky_status_val = "configured" if (os.environ.get("BLUESKY_IDENTIFIER") and os.environ.get("BLUESKY_PASSWORD")) else "not configured"
    return jsonify({
        "status": "running",
        "version": "1.0.0",
        "cookies": cookie_status,
        "bluesky": bluesky_status_val,
        "download_history_count": len(download_history),
        "recent_downloads": download_history[-10:]
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)