const form = document.getElementById("fetch-form");
const input = document.getElementById("url-input");
const fetchBtn = document.getElementById("fetch-btn");
const errorMsg = document.getElementById("error-msg");
const results = document.getElementById("results");
const template = document.getElementById("result-template");

// Session elements
const sessionIndicator = document.getElementById("session-indicator");
const sessionText = document.getElementById("session-text");
const detectSessionBtn = document.getElementById("detect-session-btn");
const logoutSessionBtn = document.getElementById("logout-session-btn");

// Direct URL elements
const directUrlSection = document.getElementById("direct-url-section");
const directUrlDisplay = document.getElementById("direct-url-display");
const copyBtn = document.getElementById("copy-url-btn");
const directDownloadBtn = document.getElementById("direct-download-btn");
const videoPreview = document.getElementById("video-preview");
const previewVideo = document.getElementById("preview-video");
const videoInfo = document.getElementById("video-info");
const downloadProgress = document.getElementById("download-progress");
const progressFill = document.getElementById("progress-fill");
const progressText = document.getElementById("progress-text");

let currentVideoUrl = null;
let currentVideoItem = null;

function setLoading(isLoading) {
  fetchBtn.disabled = isLoading;
  fetchBtn.querySelector(".btn-label").textContent = isLoading ? "Fetching…" : "Fetch";
  fetchBtn.querySelector(".btn-spinner").hidden = !isLoading;
}

function showError(message) {
  errorMsg.textContent = message;
  errorMsg.hidden = false;
}

function clearError() {
  errorMsg.hidden = true;
  errorMsg.textContent = "";
}

function formatDuration(seconds) {
  if (!seconds && seconds !== 0) return "";
  const s = Math.round(seconds);
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}:${String(rem).padStart(2, "0")}`;
}

function updateSessionStatus(hasSession, username) {
  if (hasSession) {
    sessionIndicator.textContent = '🟢';
    sessionIndicator.className = 'session-indicator online';
    sessionText.textContent = `Logged in as @${username || 'Instagram User'}`;
    detectSessionBtn.hidden = true;
    logoutSessionBtn.hidden = false;
  } else {
    sessionIndicator.textContent = '⚪';
    sessionIndicator.className = 'session-indicator offline';
    sessionText.textContent = 'Not logged in to Instagram';
    detectSessionBtn.hidden = false;
    logoutSessionBtn.hidden = true;
  }
}

async function checkSessionStatus() {
  try {
    const response = await fetch('/api/session/status');
    const data = await response.json();
    updateSessionStatus(data.has_session, data.username);
  } catch (error) {
    console.error('Failed to check session:', error);
    updateSessionStatus(false);
  }
}

// Detect session from browser
detectSessionBtn.addEventListener('click', async function() {
  this.textContent = '⏳ Detecting...';
  this.disabled = true;
  
  try {
    const response = await fetch('/api/session/use_browser', {
      method: 'POST'
    });
    const data = await response.json();
    
    if (data.status === 'success') {
      updateSessionStatus(true, data.username);
      showError(`✅ ${data.message}`);
      setTimeout(() => clearError(), 3000);
    } else {
      showError(`❌ ${data.error}`);
    }
  } catch (error) {
    showError(`❌ Failed to detect session: ${error.message}`);
  } finally {
    this.textContent = '🔍 Detect Account';
    this.disabled = false;
  }
});

// Logout session
logoutSessionBtn.addEventListener('click', async function() {
  this.textContent = '⏳ Logging out...';
  this.disabled = true;
  
  try {
    const response = await fetch('/api/session/logout', {
      method: 'POST'
    });
    const data = await response.json();
    
    if (data.status === 'success') {
      updateSessionStatus(false);
      showError('✅ Logged out successfully');
      setTimeout(() => clearError(), 3000);
    }
  } catch (error) {
    showError(`❌ Failed to logout: ${error.message}`);
  } finally {
    this.textContent = '🚪 Logout';
    this.disabled = false;
  }
});

function downloadVideo(url, filename) {
  if (!url) {
    showError("No video URL available to download");
    return;
  }
  
  downloadProgress.hidden = false;
  progressFill.style.width = '0%';
  progressText.textContent = 'Starting download...';
  
  const safeFilename = (filename || 'instagram_video')
    .replace(/[^a-zA-Z0-9]/g, '_')
    .substring(0, 50) + '.mp4';
  
  fetch(url)
    .then(response => {
      if (!response.ok) throw new Error('Network response was not ok');
      
      const contentLength = response.headers.get('content-length');
      const total = parseInt(contentLength, 10);
      let loaded = 0;
      
      progressText.textContent = 'Downloading...';
      
      const reader = response.body.getReader();
      const stream = new ReadableStream({
        start(controller) {
          function push() {
            reader.read().then(({done, value}) => {
              if (done) {
                controller.close();
                return;
              }
              loaded += value.byteLength;
              if (total) {
                const percent = Math.round((loaded / total) * 100);
                progressFill.style.width = percent + '%';
                progressText.textContent = `Downloading... ${percent}%`;
              }
              controller.enqueue(value);
              push();
            });
          }
          push();
        }
      });
      
      return new Response(stream, {
        headers: response.headers
      }).blob();
    })
    .then(blob => {
      progressText.textContent = 'Download complete!';
      progressFill.style.width = '100%';
      
      const blobUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = safeFilename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      setTimeout(() => {
        URL.revokeObjectURL(blobUrl);
        downloadProgress.hidden = true;
      }, 2000);
    })
    .catch(error => {
      console.error('Download failed:', error);
      progressText.textContent = 'Download failed, opening in new tab...';
      setTimeout(() => {
        window.open(url, '_blank');
        downloadProgress.hidden = true;
      }, 1000);
    });
}

function renderResults(items, sourceUrl) {
  results.innerHTML = "";
  results.hidden = false;
  directUrlSection.hidden = true;
  videoPreview.hidden = true;
  downloadProgress.hidden = true;

  items.forEach((item) => {
    const node = template.content.cloneNode(true);

    const img = node.querySelector(".thumb img");
    if (item.thumbnail) {
      img.src = item.thumbnail;
      img.alt = item.title || "Video thumbnail";
    } else {
      img.closest(".thumb").style.display = "none";
    }

    node.querySelector(".meta-title").textContent = item.title || "Instagram video";

    const uploaderEl = node.querySelector(".uploader");
    const durationEl = node.querySelector(".duration");
    const dotEl = node.querySelector(".dot");

    uploaderEl.textContent = item.uploader ? `@${item.uploader}` : "";
    const dur = formatDuration(item.duration);
    durationEl.textContent = dur;

    if (!item.uploader || !dur) dotEl.style.display = "none";

    const dlBtn = node.querySelector(".dl-btn");
    
    dlBtn.addEventListener('click', function(e) {
      e.preventDefault();
      if (currentVideoUrl) {
        downloadVideo(currentVideoUrl, item.title || 'instagram_video');
      } else {
        const params = new URLSearchParams({ url: sourceUrl, id: item.id || "" });
        window.open(`/api/download?${params.toString()}`, '_blank');
      }
    });

    results.appendChild(node);
  });
}

function showDirectUrl(url, item) {
  currentVideoUrl = url;
  currentVideoItem = item;
  
  directUrlSection.hidden = false;
  directUrlDisplay.value = url;
  
  if (url && (url.endsWith('.mp4') || url.includes('video'))) {
    videoPreview.hidden = false;
    previewVideo.src = url;
    previewVideo.load();
    
    let infoHtml = '';
    if (item.uploader) infoHtml += `<p><strong>Uploader:</strong> @${item.uploader}</p>`;
    if (item.title) infoHtml += `<p><strong>Title:</strong> ${item.title}</p>`;
    if (item.duration) infoHtml += `<p><strong>Duration:</strong> ${formatDuration(item.duration)}</p>`;
    
    videoInfo.innerHTML = infoHtml + `<button id="video-download-btn" class="copy-btn video-download-btn">⬇ Download Video</button>`;
    
    document.getElementById('video-download-btn').addEventListener('click', function() {
      if (currentVideoUrl) {
        downloadVideo(currentVideoUrl, item?.title || 'instagram_video');
      }
    });
  }
}

// Copy URL handler
copyBtn.addEventListener('click', async function() {
  const url = directUrlDisplay.value;
  if (!url) return;
  
  try {
    await navigator.clipboard.writeText(url);
    this.textContent = '✅ Copied!';
    this.classList.add('copied');
    setTimeout(() => {
      this.textContent = '📋 Copy';
      this.classList.remove('copied');
    }, 2000);
  } catch {
    directUrlDisplay.select();
    document.execCommand('copy');
    this.textContent = '✅ Copied!';
    setTimeout(() => {
      this.textContent = '📋 Copy';
    }, 2000);
  }
});

// Direct Download button
directDownloadBtn.addEventListener('click', function() {
  if (currentVideoUrl) {
    downloadVideo(currentVideoUrl, currentVideoItem?.title || 'instagram_video');
  }
});

directUrlDisplay.addEventListener('click', function() {
  this.select();
});

// Main form submission
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearError();
  results.hidden = true;
  directUrlSection.hidden = true;
  videoPreview.hidden = true;
  downloadProgress.hidden = true;
  currentVideoUrl = null;
  currentVideoItem = null;

  const url = input.value.trim();
  if (!url) return;

  setLoading(true);
  try {
    const res = await fetch("/api/commands/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, action: "url_only" }),
    });
    const data = await res.json();

    if (!res.ok) {
      showError(data.error || "Something went wrong. Try again.");
      return;
    }

    if (data.download_url) {
      const item = data.video_info || { title: "Instagram video" };
      renderResults([item], data.url);
      setTimeout(() => {
        showDirectUrl(data.download_url, item);
      }, 100);
    } else if (data.items) {
      renderResults(data.items, data.source_url);
    } else {
      showError("No video found at that link.");
    }
  } catch (err) {
    try {
      const res = await fetch("/api/fetch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();

      if (!res.ok) {
        showError(data.error || "Something went wrong. Try again.");
        return;
      }

      renderResults(data.items, data.source_url);
    } catch (err2) {
      showError("Couldn't reach the server. Check your connection and try again.");
    }
  } finally {
    setLoading(false);
  }
});

// Check session status on page load
checkSessionStatus();