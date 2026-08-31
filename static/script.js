const form = document.getElementById("fetch-form");
const input = document.getElementById("url-input");
const fetchBtn = document.getElementById("fetch-btn");
const errorMsg = document.getElementById("error-msg");
const results = document.getElementById("results");
const template = document.getElementById("result-template");

// New elements for direct URL display
const directUrlSection = document.getElementById("direct-url-section");
const directUrlDisplay = document.getElementById("direct-url-display");
const copyBtn = document.getElementById("copy-url-btn");
const videoPreview = document.getElementById("video-preview");
const previewVideo = document.getElementById("preview-video");
const videoInfo = document.getElementById("video-info");

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

function renderResults(items, sourceUrl) {
  results.innerHTML = "";
  results.hidden = false;
  directUrlSection.hidden = true;
  videoPreview.hidden = true;

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
    
    // Add direct URL fetch on click
    dlBtn.addEventListener('click', async function(e) {
      e.preventDefault();
      const label = this.querySelector('.btn-label');
      const originalText = label.textContent;
      label.textContent = 'Getting URL…';
      
      try {
        const params = new URLSearchParams({ url: sourceUrl, id: item.id || "" });
        const response = await fetch(`/api/download?${params.toString()}`, {
          method: 'GET',
          redirect: 'manual'
        });
        
        if (response.status === 200 || response.status === 302) {
          const data = await response.text();
          // Try to parse as JSON (for direct URL) or use location
          try {
            const jsonData = JSON.parse(data);
            if (jsonData.download_url) {
              showDirectUrl(jsonData.download_url, item);
              return;
            }
          } catch {
            // Not JSON, might be a redirect or file
          }
          
          // Check if it's a redirect URL
          if (response.url && response.url.startsWith('http')) {
            showDirectUrl(response.url, item);
            return;
          }
        }
        
        // Fallback: open in new tab
        const params2 = new URLSearchParams({ url: sourceUrl, id: item.id || "" });
        window.open(`/api/download?${params2.toString()}`, '_blank');
      } catch (err) {
        // Fallback: open in new tab
        const params3 = new URLSearchParams({ url: sourceUrl, id: item.id || "" });
        window.open(`/api/download?${params3.toString()}`, '_blank');
      } finally {
        label.textContent = originalText;
      }
    });

    results.appendChild(node);
  });
}

function showDirectUrl(url, item) {
  directUrlSection.hidden = false;
  directUrlDisplay.value = url;
  
  // Show video preview
  if (url && (url.endsWith('.mp4') || url.includes('video'))) {
    videoPreview.hidden = false;
    previewVideo.src = url;
    previewVideo.load();
    
    let infoHtml = '';
    if (item.uploader) infoHtml += `<p><strong>Uploader:</strong> @${item.uploader}</p>`;
    if (item.title) infoHtml += `<p><strong>Title:</strong> ${item.title}</p>`;
    if (item.duration) infoHtml += `<p><strong>Duration:</strong> ${formatDuration(item.duration)}</p>`;
    videoInfo.innerHTML = infoHtml || '<p>Video ready for download</p>';
  }
}

// Copy URL handler
copyBtn.addEventListener('click', async function() {
  const url = directUrlDisplay.value;
  if (!url) return;
  
  try {
    await navigator.clipboard.writeText(url);
    this.textContent = 'Copied!';
    this.classList.add('copied');
    setTimeout(() => {
      this.textContent = 'Copy';
      this.classList.remove('copied');
    }, 2000);
  } catch {
    // Fallback
    directUrlDisplay.select();
    document.execCommand('copy');
    this.textContent = 'Copied!';
    setTimeout(() => {
      this.textContent = 'Copy';
    }, 2000);
  }
});

// Also allow direct download via right-click on the URL display
directUrlDisplay.addEventListener('click', function() {
  this.select();
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearError();
  results.hidden = true;
  directUrlSection.hidden = true;
  videoPreview.hidden = true;

  const url = input.value.trim();
  if (!url) return;

  setLoading(true);
  try {
    // Try the new API endpoint first for direct URL
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

    // Check if we got a direct URL
    if (data.download_url) {
      // Display single video with direct URL
      const item = data.video_info || { title: "Instagram video" };
      renderResults([item], data.url);
      // Show the direct URL
      setTimeout(() => {
        showDirectUrl(data.download_url, item);
      }, 100);
    } else if (data.items) {
      renderResults(data.items, data.source_url);
    } else {
      showError("No video found at that link.");
    }
  } catch (err) {
    // Fallback to old API
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