# Fetchgram — Instagram video downloader

A small Flask app with a web UI for saving public Instagram videos (reels,
posts, IGTV). It uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) server-side
to fetch the file, then streams it to your browser as a normal download.
No files are kept on the server — each download is deleted right after it's
sent.

## How it works

- `POST /api/fetch` — takes an Instagram URL, returns title/thumbnail/duration
  without downloading anything (uses `yt_dlp.extract_info(download=False)`).
- `GET /api/download?url=...&id=...` — downloads the video to a temp folder,
  streams it back as an attachment, then deletes the temp folder.
- Only public content is supported — private or login-walled posts will
  return a clear error instead of failing silently.

## Run it locally

Requires Python 3.9+.

```bash
cd igdl
python3 -m venv .venv
source .venv/bin/activate        # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000**, paste an Instagram link, click **Fetch**,
then **Download**.

To run it the same way production will (via gunicorn):

```bash
gunicorn app:app --workers 2 --timeout 120
```

## Deploy to Render

**Option A — one-click via Blueprint**
1. Push this folder to a GitHub/GitLab repo.
2. In Render: **New → Blueprint**, point it at the repo. Render will read
   `render.yaml` and set everything up automatically (build command, start
   command, Python version).
3. Click **Apply** and wait for the first deploy to finish.

**Option B — manual web service**
1. In Render: **New → Web Service**, connect your repo.
2. Runtime: **Python 3**
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app --workers 2 --timeout 120`
5. Deploy.

No environment variables or database are required. The free Render plan
works fine — video files are only ever held in a temp directory during a
single download and removed right after.

## Notes & limits

- Only works on **public** Instagram content — private posts require login,
  which this app deliberately does not implement.
- Instagram can change its site/API at any time, which may break extraction
  until `yt-dlp` is updated. If downloads suddenly start failing, try:
  ```bash
  pip install -U yt-dlp
  ```
- This tool downloads a single already-muxed video stream (`format: best`)
  so it doesn't need `ffmpeg` installed — keeps the Render deploy simple.
- Please only download content you own or have permission to save, and
  respect creators' rights and Instagram's Terms of Service.

## Project structure

```
igdl/
├── app.py              # Flask backend + yt-dlp logic
├── templates/
│   └── index.html
├── static/
│   ├── style.css
│   └── script.js
├── requirements.txt
├── render.yaml          # Render Blueprint config
├── Procfile              # fallback start command
└── README.md
```
"# fetchgram" 
