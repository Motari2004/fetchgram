const form = document.getElementById("fetch-form");
const input = document.getElementById("url-input");
const fetchBtn = document.getElementById("fetch-btn");
const errorMsg = document.getElementById("error-msg");
const results = document.getElementById("results");
const template = document.getElementById("result-template");

// Cookie elements
const cookieIndicator = document.getElementById("cookie-indicator");
const cookieStatusText = document.getElementById("cookie-status-text");
const fileInput = document.getElementById("cookie-file-input");
const fileLabelText = document.getElementById("file-label-text");
const uploadBtn = document.getElementById("upload-cookie-btn");
const clearBtn = document.getElementById("clear-cookie-btn");
const cookieInfo = document.getElementById("cookie-upload-info");
const cookieError = document.getElementById("cookie-upload-error");

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

// Bluesky elements
const blueskySection = document.getElementById('bluesky-section');
const blueskyText = document.getElementById('bluesky-text');
const charCount = document.getElementById('char-count');
const blueskyIdentifier = document.getElementById('bluesky-identifier');
const blueskyPassword = document.getElementById('bluesky-password');
const blueskyRemember = document.getElementById('bluesky-remember');
const blueskyPostBtn = document.getElementById('bluesky-post-btn');
const blueskyStatus = document.getElementById('bluesky-status');
const blueskyPostUrl = document.getElementById('bluesky-post-url');
const savedCredentialsInfo = document.getElementById('saved-credentials-info');
const savedCredentialsText = document.getElementById('saved-credentials-text');
const clearBlueskyCredsBtn = document.getElementById('clear-bluesky-creds-btn');

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

function updateCookieStatus(hasCookies, username) {
  if (hasCookies) {
    cookieIndicator.textContent = '🟢';
    cookieIndicator.className = 'status-indicator online';
    cookieStatusText.textContent = `Logged in as @${username || 'Instagram User'}`;
    clearBtn.hidden = false;
    uploadBtn.textContent = '✅ Uploaded';
    uploadBtn.disabled = true;
    fileInput.disabled = true;
    if (fileLabelText) {
      fileLabelText.textContent = '📄 cookies.json uploaded';
    }
  } else {
    cookieIndicator.textContent = '⚪';
    cookieIndicator.className = 'status-indicator offline';
    cookieStatusText.textContent = 'No cookies uploaded';
    clearBtn.hidden = true;
    uploadBtn.textContent = '⬆ Upload';
    uploadBtn.disabled = true;
    fileInput.disabled = false;
    if (fileLabelText) {
      fileLabelText.textContent = '📁 Choose cookies.json';
    }
    fileInput.value = '';
  }
}

async function checkCookieStatus() {
  try {
    const response = await fetch('/api/cookies/status');
    const data = await response.json();
    updateCookieStatus(data.has_cookies, data.username);
  } catch (error) {
    console.error('Failed to check cookie status:', error);
    updateCookieStatus(false);
  }
}

// File input change handler
fileInput.addEventListener('change', function() {
  if (this.files.length > 0) {
    const fileName = this.files[0].name;
    if (fileLabelText) {
      fileLabelText.textContent = `📄 ${fileName}`;
    }
    uploadBtn.disabled = false;
  } else {
    if (fileLabelText) {
      fileLabelText.textContent = '📁 Choose cookies.json';
    }
    uploadBtn.disabled = true;
  }
});

// Upload cookies
uploadBtn.addEventListener('click', async function() {
  const file = fileInput.files[0];
  if (!file) {
    showCookieError('Please select a cookies.json file first');
    return;
  }
  
  if (!file.name.endsWith('.json')) {
    showCookieError('File must be a JSON file');
    return;
  }
  
  const formData = new FormData();
  formData.append('cookies_file', file);
  
  this.textContent = '⏳ Uploading...';
  this.disabled = true;
  
  try {
    const response = await fetch('/api/cookies/upload', {
      method: 'POST',
      body: formData
    });
    
    const data = await response.json();
    
    if (response.ok) {
      updateCookieStatus(true, data.username);
      showCookieInfo(`✅ ${data.message}`);
      fileInput.value = '';
      if (fileLabelText) {
        fileLabelText.textContent = '📁 Choose cookies.json';
      }
    } else {
      showCookieError(data.error || 'Upload failed');
      updateCookieStatus(false);
    }
  } catch (error) {
    showCookieError('Failed to upload: ' + error.message);
  } finally {
    this.textContent = '⬆ Upload';
    this.disabled = true;
  }
});

// Clear cookies
clearBtn.addEventListener('click', async function() {
  this.textContent = '⏳ Clearing...';
  this.disabled = true;
  
  try {
    const response = await fetch('/api/cookies/clear', {
      method: 'POST'
    });
    const data = await response.json();
    
    if (response.ok) {
      updateCookieStatus(false);
      showCookieInfo('✅ Cookies cleared');
    } else {
      showCookieError(data.error || 'Failed to clear cookies');
    }
  } catch (error) {
    showCookieError('Failed to clear: ' + error.message);
  } finally {
    this.textContent = '🗑️ Clear';
    this.disabled = false;
  }
});

function showCookieInfo(message) {
  if (cookieInfo) {
    cookieInfo.hidden = false;
    cookieInfo.textContent = message;
  }
  if (cookieError) {
    cookieError.hidden = true;
  }
  setTimeout(() => {
    if (cookieInfo) {
      cookieInfo.hidden = true;
    }
  }, 5000);
}

function showCookieError(message) {
  if (cookieError) {
    cookieError.hidden = false;
    cookieError.textContent = '❌ ' + message;
  }
  if (cookieInfo) {
    cookieInfo.hidden = true;
  }
  setTimeout(() => {
    if (cookieError) {
      cookieError.hidden = true;
    }
  }, 5000);
}

// Character counter for Bluesky
if (blueskyText) {
  blueskyText.addEventListener('input', function() {
    const count = this.value.length;
    charCount.textContent = `${count}/300`;
    charCount.style.color = count > 300 ? 'var(--error)' : 'var(--text-muted)';
  });
}

function showBlueskySection() {
  blueskySection.hidden = false;
}

function showBlueskyStatus(message, type, postUrl) {
  blueskyStatus.hidden = false;
  blueskyStatus.textContent = message;
  blueskyStatus.className = 'bluesky-status' + (type ? ' ' + type : '');
  
  if (postUrl) {
    blueskyPostUrl.hidden = false;
    blueskyPostUrl.innerHTML = `🔗 <a href="${postUrl}" target="_blank">${postUrl}</a>`;
  } else {
    blueskyPostUrl.hidden = true;
  }
}

// Check for saved Bluesky credentials on load
async function checkBlueskyCredentials() {
  try {
    const response = await fetch('/api/bluesky/credentials_status');
    const data = await response.json();
    
    if (data.has_credentials) {
      // Fill in the identifier field
      if (blueskyIdentifier) {
        blueskyIdentifier.value = data.identifier;
        blueskyIdentifier.disabled = true;
      }
      if (blueskyPassword) {
        blueskyPassword.disabled = true;
        blueskyPassword.placeholder = '•••••••• (saved)';
      }
      if (blueskyRemember) {
        blueskyRemember.checked = true;
      }
      
      // Show saved credentials info
      if (savedCredentialsInfo) {
        savedCredentialsInfo.hidden = false;
        if (savedCredentialsText) {
          savedCredentialsText.textContent = `✅ Credentials saved for @${data.handle || data.identifier}`;
        }
      }
    }
  } catch (error) {
    console.error('Failed to check Bluesky credentials:', error);
  }
}

// Clear saved Bluesky credentials
async function clearBlueskyCredentials() {
  try {
    const response = await fetch('/api/bluesky/clear_credentials', {
      method: 'POST'
    });
    const data = await response.json();
    
    if (response.ok) {
      if (savedCredentialsInfo) {
        savedCredentialsInfo.hidden = true;
      }
      if (blueskyIdentifier) {
        blueskyIdentifier.disabled = false;
        blueskyIdentifier.value = '';
      }
      if (blueskyPassword) {
        blueskyPassword.disabled = false;
        blueskyPassword.value = '';
        blueskyPassword.placeholder = 'Your Bluesky app password';
      }
      if (blueskyRemember) {
        blueskyRemember.checked = true;
      }
      showBlueskyStatus('✅ Credentials cleared', 'success');
    }
  } catch (error) {
    console.error('Failed to clear credentials:', error);
    showBlueskyStatus('❌ Failed to clear credentials', 'error');
  }
}

// Bluesky Post
blueskyPostBtn.addEventListener('click', async function() {
  const text = blueskyText.value.trim() || 'Check out this video! 🎬';
  
  if (text.length > 300) {
    showBlueskyStatus('Caption is too long (max 300 characters)', 'error');
    return;
  }
  
  if (!currentVideoUrl) {
    showBlueskyStatus('No video to post. Please fetch a video first.', 'error');
    return;
  }
  
  let identifier = blueskyIdentifier.value.trim();
  let password = blueskyPassword.value.trim();
  
  // If credentials are disabled but we have saved ones, use those
  if (blueskyIdentifier.disabled && !identifier) {
    // Get from saved
    try {
      const statusResponse = await fetch('/api/bluesky/credentials_status');
      const statusData = await statusResponse.json();
      if (statusData.has_credentials) {
        identifier = statusData.identifier;
        // Password will be retrieved server-side
      }
    } catch (e) {
      showBlueskyStatus('Error retrieving saved credentials', 'error');
      return;
    }
  }
  
  if (!identifier) {
    showBlueskyStatus('Please enter your Bluesky handle.', 'error');
    return;
  }
  
  if (!password && !blueskyPassword.disabled) {
    showBlueskyStatus('Please enter your Bluesky password.', 'error');
    return;
  }
  
  const remember = blueskyRemember ? blueskyRemember.checked : true;
  
  this.textContent = '⏳ Posting...';
  this.disabled = true;
  showBlueskyStatus('⏳ Uploading video to Bluesky... This may take a moment.', 'info');
  
  try {
    const response = await fetch('/api/bluesky/post', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: currentVideoUrl,
        text: text,
        identifier: identifier,
        password: password || undefined,
        remember: remember
      })
    });
    
    const data = await response.json();
    
    if (response.ok) {
      const postUrl = `https://bsky.app/profile/${identifier}/post/${data.post_id}`;
      showBlueskyStatus(
        `✅ ${data.message}`,
        'success',
        postUrl
      );
      
      // If credentials were saved, update the UI
      if (data.saved) {
        if (savedCredentialsInfo) {
          savedCredentialsInfo.hidden = false;
          if (savedCredentialsText) {
            savedCredentialsText.textContent = `✅ Credentials saved for @${identifier}`;
          }
        }
        if (blueskyIdentifier) {
          blueskyIdentifier.disabled = true;
          blueskyIdentifier.value = identifier;
        }
        if (blueskyPassword) {
          blueskyPassword.disabled = true;
          blueskyPassword.value = '';
          blueskyPassword.placeholder = '•••••••• (saved)';
        }
        if (blueskyRemember) {
          blueskyRemember.checked = true;
        }
      }
    } else {
      showBlueskyStatus(`❌ Error: ${data.error || 'Unknown error'}`, 'error');
    }
  } catch (error) {
    showBlueskyStatus(`❌ Error: ${error.message}`, 'error');
  } finally {
    this.textContent = '📤 Post to Bluesky';
    this.disabled = false;
  }
});

// Clear credentials button handler
if (clearBlueskyCredsBtn) {
  clearBlueskyCredsBtn.addEventListener('click', clearBlueskyCredentials);
}

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
  
  // Show Bluesky section
  showBlueskySection();
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
  blueskySection.hidden = true;
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

// Check cookie status on page load
checkCookieStatus();

// Check Bluesky credentials on page load
checkBlueskyCredentials();