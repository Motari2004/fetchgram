const form = document.getElementById("fetch-form");
const input = document.getElementById("url-input");
const fetchBtn = document.getElementById("fetch-btn");
const errorMsg = document.getElementById("error-msg");
const results = document.getElementById("results");
const template = document.getElementById("result-template");

// Instagram cookie elements
const instagramIndicator = document.getElementById("instagram-indicator");
const instagramStatusText = document.getElementById("instagram-status-text");
const instagramUsernameDisplay = document.getElementById("instagram-username-display");
const clearCookieBtn = document.getElementById("clear-cookie-btn");

// Bluesky elements
const blueskyIndicator = document.getElementById("bluesky-indicator");
const blueskyStatusText = document.getElementById("bluesky-status-text");
const blueskyUsernameDisplay = document.getElementById("bluesky-username-display");
const blueskyToggleBtn = document.getElementById("bluesky-toggle-btn");
const blueskyModal = document.getElementById("bluesky-modal");
const blueskyModalClose = document.getElementById("bluesky-modal-close");
const blueskyIdentifierModal = document.getElementById("bluesky-identifier-modal");
const blueskyPasswordModal = document.getElementById("bluesky-password-modal");
const blueskyRememberModal = document.getElementById("bluesky-remember-modal");
const blueskySaveBtn = document.getElementById("bluesky-save-btn");
const blueskyModalStatus = document.getElementById("bluesky-modal-status");
const clearBlueskyCredsBtn = document.getElementById("clear-bluesky-creds-btn");
const savedCredentialsInfo = document.getElementById("saved-credentials-info");
const blueskySection = document.getElementById("bluesky-section");
const blueskyText = document.getElementById("bluesky-text");
const charCount = document.getElementById("char-count");
const blueskyPostBtn = document.getElementById("bluesky-post-btn");
const blueskyStatus = document.getElementById("bluesky-status");
const blueskyPostUrl = document.getElementById("bluesky-post-url");
const blueskyConnectedBadge = document.getElementById("bluesky-connected-badge");

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

// Scrape elements
const scrapeUsernames = document.getElementById("scrape-usernames");
const scrapeMaxReels = document.getElementById("scrape-max-reels");
const scrapeMaxScrolls = document.getElementById("scrape-max-scrolls");
const scrapeHeadless = document.getElementById("scrape-headless");
const startScrapeBtn = document.getElementById("start-scrape-btn");
const scrapeJobStatus = document.getElementById("scrape-job-status");
const fetchScrapedBtn = document.getElementById("fetch-scraped-btn");
const clearScrapedBtn = document.getElementById("clear-scraped-btn");
const scrapedReelsContent = document.getElementById("scraped-reels-content");
const scrapedReelsStatus = document.getElementById("scraped-reels-status");

// Cookie upload elements
const cookieFileInput = document.getElementById('cookie-file-input-main');
const cookieFileLabelText = document.getElementById('cookie-file-label-text');
const uploadCookieMainBtn = document.getElementById('upload-cookie-main-btn');
const clearCookieMainBtn = document.getElementById('clear-cookie-main-btn');
const cookieUploadStatus = document.getElementById('cookie-upload-status');

let currentVideoUrl = null;
let currentVideoItem = null;

// Render scraper URL
const RENDER_SCRAPER_URL = 'https://ig-reels-scraper.onrender.com';

// ==================== INSTAGRAM COOKIE FUNCTIONS ====================

function updateInstagramStatus(hasCookies, username) {
  console.log('🔄 Updating status:', { hasCookies, username });
  
  if (hasCookies) {
    instagramIndicator.textContent = '🟢';
    instagramIndicator.className = 'status-icon online';
    instagramStatusText.textContent = 'Connected';
    if (instagramUsernameDisplay) {
      instagramUsernameDisplay.textContent = `@${username || 'Instagram User'}`;
    }
    clearCookieBtn.hidden = false;
    clearCookieMainBtn.hidden = false;
    
    // Update the upload label
    if (cookieFileLabelText) {
      cookieFileLabelText.textContent = `✅ Connected as @${username || 'Instagram User'}`;
    }
    const label = document.querySelector('.cookie-upload-label');
    if (label) {
      label.style.borderColor = 'var(--success)';
      label.classList.add('has-file');
    }
  } else {
    instagramIndicator.textContent = '⚪';
    instagramIndicator.className = 'status-icon offline';
    instagramStatusText.textContent = 'Not connected';
    if (instagramUsernameDisplay) {
      instagramUsernameDisplay.textContent = '';
    }
    clearCookieBtn.hidden = true;
    clearCookieMainBtn.hidden = true;
    
    // Reset the upload label
    if (cookieFileLabelText) {
      cookieFileLabelText.textContent = 'Choose cookies.json';
    }
    const label = document.querySelector('.cookie-upload-label');
    if (label) {
      label.style.borderColor = '';
      label.classList.remove('has-file');
    }
  }
}

async function checkInstagramStatus() {
  console.log('🔍 Checking Instagram status...');
  
  try {
    // First check the database (persistent storage)
    const savedResponse = await fetch('/api/instagram/cookies_status', { 
      credentials: 'same-origin' 
    });
    const savedData = await savedResponse.json();
    console.log('📊 Database status response:', savedData);
    
    if (savedData.has_cookies) {
      updateInstagramStatus(true, savedData.username);
      return;
    }
    
    // Fallback: check session cookies
    const response = await fetch('/api/cookies/status', { 
      credentials: 'same-origin' 
    });
    const data = await response.json();
    console.log('📊 Session status response:', data);
    updateInstagramStatus(data.has_cookies, data.username);
    
    // If we have cookies in session but not DB, something is wrong
    if (data.has_cookies && !savedData.has_cookies) {
      console.warn('Cookies found in session but not in DB - re-saving...');
      const cookiesResponse = await fetch('/api/instagram/get_cookies', { credentials: 'same-origin' });
      const cookiesData = await cookiesResponse.json();
      if (cookiesData.cookies) {
        await fetch('/api/instagram/save_cookies', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({ cookies: cookiesData.cookies, remember: true })
        });
      }
    }
    
  } catch (error) {
    console.error('❌ Failed to check Instagram status:', error);
    updateInstagramStatus(false);
  }
}

// ==================== BLUESKY FUNCTIONS ====================

async function checkBlueskyStatus() {
  try {
    const response = await fetch('/api/bluesky/credentials_status', { credentials: 'same-origin' });
    const data = await response.json();
    
    if (data.has_credentials) {
      blueskyIndicator.textContent = '🟢';
      blueskyIndicator.className = 'status-icon online';
      blueskyStatusText.textContent = 'Connected';
      if (blueskyUsernameDisplay) {
        blueskyUsernameDisplay.textContent = `@${data.handle || data.identifier}`;
      }
      blueskyConnectedBadge.hidden = false;
      clearBlueskyCredsBtn.hidden = false;
      if (savedCredentialsInfo) {
        savedCredentialsInfo.textContent = `✅ Connected as @${data.handle || data.identifier}`;
        savedCredentialsInfo.style.display = 'block';
      }
    } else {
      blueskyIndicator.textContent = '⚪';
      blueskyIndicator.className = 'status-icon offline';
      blueskyStatusText.textContent = 'Not connected';
      if (blueskyUsernameDisplay) {
        blueskyUsernameDisplay.textContent = '';
      }
      blueskyConnectedBadge.hidden = true;
      clearBlueskyCredsBtn.hidden = true;
      if (savedCredentialsInfo) {
        savedCredentialsInfo.style.display = 'none';
      }
    }
  } catch (error) {
    console.error('Failed to check Bluesky status:', error);
  }
}

blueskyToggleBtn.addEventListener('click', function() {
  blueskyModal.hidden = false;
  blueskyModalStatus.style.display = 'none';
  blueskyIdentifierModal.value = '';
  blueskyPasswordModal.value = '';
  blueskyRememberModal.checked = true;
});

blueskyModalClose.addEventListener('click', function() {
  blueskyModal.hidden = true;
});

blueskyModal.addEventListener('click', function(e) {
  if (e.target === this) {
    blueskyModal.hidden = true;
  }
});

blueskySaveBtn.addEventListener('click', async function() {
  const identifier = blueskyIdentifierModal.value.trim();
  const password = blueskyPasswordModal.value.trim();
  const remember = blueskyRememberModal.checked;
  
  if (!identifier || !password) {
    blueskyModalStatus.textContent = '❌ Please enter both handle and password';
    blueskyModalStatus.className = 'status-message error';
    blueskyModalStatus.style.display = 'block';
    return;
  }
  
  this.textContent = '⏳ Saving...';
  this.disabled = true;
  
  try {
    const response = await fetch('/api/bluesky/save_credentials', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ identifier, password, remember })
    });
    
    const data = await response.json();
    
    if (response.ok) {
      blueskyModalStatus.textContent = `✅ ${data.message}`;
      blueskyModalStatus.className = 'status-message success';
      blueskyModalStatus.style.display = 'block';
      setTimeout(() => {
        blueskyModal.hidden = true;
        checkBlueskyStatus();
      }, 1500);
    } else {
      blueskyModalStatus.textContent = `❌ ${data.error}`;
      blueskyModalStatus.className = 'status-message error';
      blueskyModalStatus.style.display = 'block';
    }
  } catch (error) {
    blueskyModalStatus.textContent = `❌ ${error.message}`;
    blueskyModalStatus.className = 'status-message error';
    blueskyModalStatus.style.display = 'block';
  } finally {
    this.textContent = 'Save Connection';
    this.disabled = false;
  }
});

clearBlueskyCredsBtn.addEventListener('click', async function() {
  this.textContent = '⏳';
  this.disabled = true;
  
  try {
    const response = await fetch('/api/bluesky/clear_credentials', {
      method: 'POST',
      credentials: 'same-origin'
    });
    const data = await response.json();
    
    if (response.ok) {
      checkBlueskyStatus();
      showBlueskyStatus('✅ Credentials cleared', 'success');
    }
  } catch (error) {
    console.error('Failed to clear credentials:', error);
  } finally {
    this.textContent = 'Clear';
    this.disabled = false;
  }
});

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
  blueskyStatus.textContent = message;
  blueskyStatus.className = 'status-message ' + type;
  blueskyStatus.style.display = 'block';
  
  if (postUrl) {
    blueskyPostUrl.hidden = false;
    blueskyPostUrl.innerHTML = `🔗 <a href="${postUrl}" target="_blank">${postUrl}</a>`;
  } else {
    blueskyPostUrl.hidden = true;
  }
  
  setTimeout(() => {
    blueskyStatus.style.display = 'none';
  }, 8000);
}

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
  
  this.disabled = true;
  this.innerHTML = '<span class="btn-spinner"></span> Posting...';
  showBlueskyStatus('⏳ Uploading video to Bluesky... This may take a moment.', 'info');
  
  try {
    const response = await fetch('/api/bluesky/post', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({
        url: currentVideoUrl,
        text: text,
        remember: true
      })
    });
    
    const data = await response.json();
    
    if (response.ok) {
      let postUrl = null;
      if (data.post_uri && data.post_id) {
        const handleResponse = await fetch('/api/bluesky/credentials_status', { credentials: 'same-origin' });
        const handleData = await handleResponse.json();
        const handle = handleData.handle || handleData.identifier;
        if (handle) {
          postUrl = `https://bsky.app/profile/${handle}/post/${data.post_id}`;
        }
      }
      showBlueskyStatus(
        `✅ ${data.message}`,
        'success',
        postUrl
      );
    } else {
      showBlueskyStatus(`❌ ${data.error || 'Unknown error'}`, 'error');
    }
  } catch (error) {
    showBlueskyStatus(`❌ ${error.message}`, 'error');
  } finally {
    this.innerHTML = '📤 Post to Bluesky';
    this.disabled = false;
  }
});

// ==================== COOKIE UPLOAD FUNCTIONS ====================

function showCookieStatus(message, type) {
  cookieUploadStatus.textContent = message;
  cookieUploadStatus.className = 'cookie-status-msg ' + (type || '');
  cookieUploadStatus.style.display = 'block';
  if (type !== 'error') {
    setTimeout(() => {
      cookieUploadStatus.style.display = 'none';
    }, 8000);
  }
}

cookieFileInput.addEventListener('change', function() {
  if (this.files.length > 0) {
    const fileName = this.files[0].name;
    cookieFileLabelText.textContent = `📄 ${fileName}`;
    this.parentElement.classList.add('has-file');
    uploadCookieMainBtn.disabled = false;
    cookieUploadStatus.style.display = 'none';
  } else {
    cookieFileLabelText.textContent = 'Choose cookies.json';
    this.parentElement.classList.remove('has-file');
    uploadCookieMainBtn.disabled = true;
  }
});

uploadCookieMainBtn.addEventListener('click', async function() {
  const file = cookieFileInput.files[0];
  if (!file) {
    showCookieStatus('❌ Please select a cookies.json file first', 'error');
    return;
  }
  
  if (!file.name.endsWith('.json')) {
    showCookieStatus('❌ File must be a .json file', 'error');
    return;
  }
  
  this.disabled = true;
  this.innerHTML = '<span class="btn-spinner"></span> Uploading...';
  showCookieStatus('⏳ Uploading cookies...', 'info');
  
  try {
    const formData = new FormData();
    formData.append('cookies_file', file);
    
    const response = await fetch('/api/cookies/upload', {
      method: 'POST',
      body: formData
    });
    
    const data = await response.json();
    console.log('Upload response:', data);
    
    if (response.ok && data.status === 'success') {
      showCookieStatus(`✅ ${data.message || 'Cookies uploaded successfully!'}`, 'success');
      updateInstagramStatus(true, data.username || 'Instagram User');
      cookieFileInput.value = '';
      cookieFileLabelText.textContent = '✅ Uploaded!';
      cookieFileInput.parentElement.classList.remove('has-file');
      cookieFileInput.parentElement.classList.add('has-file');
      this.disabled = true;
      clearCookieMainBtn.hidden = false;
      
      setTimeout(() => {
        checkInstagramStatus();
      }, 1000);
      
    } else {
      showCookieStatus(`❌ ${data.error || 'Upload failed. Please try again.'}`, 'error');
      this.disabled = false;
    }
  } catch (error) {
    console.error('Upload error:', error);
    showCookieStatus(`❌ Network error: ${error.message}`, 'error');
    this.disabled = false;
  } finally {
    if (!this.disabled) {
      this.innerHTML = '<span class="btn-content">⬆ Upload</span>';
    } else {
      setTimeout(() => {
        this.innerHTML = '<span class="btn-content">⬆ Upload</span>';
        if (!cookieFileInput.files || cookieFileInput.files.length === 0) {
          this.disabled = true;
        }
      }, 2000);
    }
  }
});

clearCookieMainBtn.addEventListener('click', async function() {
  this.disabled = true;
  this.textContent = '⏳';
  
  try {
    const response = await fetch('/api/cookies/clear', { 
      method: 'POST',
      credentials: 'same-origin'
    });
    const data = await response.json();
    
    if (response.ok) {
      showCookieStatus('✅ Cookies cleared successfully', 'success');
      updateInstagramStatus(false);
      this.hidden = true;
      cookieFileLabelText.textContent = 'Choose cookies.json';
      cookieFileInput.parentElement.classList.remove('has-file');
      uploadCookieMainBtn.disabled = true;
    } else {
      showCookieStatus(`❌ ${data.error || 'Failed to clear cookies'}`, 'error');
    }
  } catch (error) {
    showCookieStatus(`❌ Failed to clear: ${error.message}`, 'error');
  } finally {
    this.disabled = false;
    this.textContent = '🗑️ Clear';
  }
});

// ==================== SCRAPE FUNCTIONS ====================

function showScrapeStatus(message, type) {
  scrapeJobStatus.textContent = message;
  scrapeJobStatus.className = 'scrape-status ' + (type || '');
  scrapeJobStatus.hidden = false;
}

function showScrapeProgress(percent, text) {
  const progressBar = document.getElementById('scrape-job-progress');
  const fill = document.getElementById('scrape-progress-fill');
  const label = document.getElementById('scrape-progress-text');
  
  if (progressBar) {
    progressBar.hidden = false;
    if (fill) fill.style.width = percent + '%';
    if (label) label.textContent = text || percent + '%';
  }
}

function hideScrapeProgress() {
  const progressBar = document.getElementById('scrape-job-progress');
  if (progressBar) progressBar.hidden = true;
}

function showScrapedStatus(message, type) {
  const statusEl = document.getElementById('scraped-reels-status');
  statusEl.textContent = message;
  statusEl.className = 'status-message ' + type;
  statusEl.style.display = 'block';
  setTimeout(() => {
    statusEl.style.display = 'none';
  }, 8000);
}

// ==================== SCRAPED REELS FUNCTIONS ====================

function renderScrapedResults(results, stats) {
  const content = document.getElementById('scraped-reels-content');
  const statsContainer = document.getElementById('scraped-stats');
  const exportBtn = document.getElementById('export-scraped-btn');
  const countBadge = document.getElementById('scraped-count-badge');
  
  if (!results || results.length === 0) {
    content.innerHTML = `<div class="empty-state">No profiles found in the scraped data.</div>`;
    if (statsContainer) statsContainer.hidden = true;
    if (exportBtn) exportBtn.hidden = true;
    if (countBadge) countBadge.textContent = '0 profiles';
    return;
  }
  
  // Calculate stats
  let totalReels = 0;
  let successCount = 0;
  let errorCount = 0;
  
  results.forEach(profile => {
    const reels = profile.reels || [];
    totalReels += reels.length;
    if (profile.status === 'ok') successCount++;
    else errorCount++;
  });
  
  // Update stats
  document.getElementById('stat-profiles').textContent = results.length;
  document.getElementById('stat-reels').textContent = totalReels;
  document.getElementById('stat-success').textContent = successCount;
  document.getElementById('stat-errors').textContent = errorCount;
  
  if (statsContainer) statsContainer.hidden = false;
  if (exportBtn) exportBtn.hidden = false;
  if (countBadge) countBadge.textContent = `${results.length} profiles (${totalReels} reels)`;
  
  // Build HTML - Show ALL profiles with their usernames
  let html = `<div class="scraped-profiles-grid">`;
  
  results.forEach((profile, index) => {
    const username = profile.username || 'unknown';
    const reelCount = (profile.reels || []).length;
    const status = profile.status || 'ok';
    const statusClass = status === 'ok' ? 'ok' : 
                        (status === 'no_reels_found' || status === 'private') ? 'warn' : 'err';
    const isOpen = index < 3; // First 3 open by default
    
    html += `
      <div class="scraped-profile-card">
        <div class="scraped-profile-header" onclick="toggleProfile(this)">
          <div class="scraped-profile-name">
            👤 @${escapeHtml(username)}
            <span class="status-badge ${statusClass}">${escapeHtml(status)}</span>
          </div>
          <div style="display:flex;align-items:center;gap:8px;">
            <span class="scraped-profile-count">📹 ${reelCount}</span>
            <span class="scraped-profile-toggle ${isOpen ? 'open' : ''}">▼</span>
          </div>
        </div>
        <div class="scraped-profile-body ${isOpen ? 'open' : ''}">
          <div class="scraped-profile-reels">
    `;
    
    if (reelCount > 0) {
      // Show all reels (up to 50)
      const reelsToShow = profile.reels.slice(0, 50);
      reelsToShow.forEach((url, idx) => {
        html += `
          <div class="scraped-reel-item">
            <span class="scraped-reel-index">#${idx + 1}</span>
            <span class="scraped-reel-url"><a href="${escapeHtml(url)}" target="_blank">${escapeHtml(url)}</a></span>
            <div class="scraped-reel-actions">
              <button class="btn btn-sm btn-success btn-icon copy-reel-btn" data-url="${escapeHtml(url)}">📋</button>
              <button class="btn btn-sm btn-primary btn-icon download-reel-btn" data-url="${escapeHtml(url)}">⬇</button>
            </div>
          </div>
        `;
      });
      
      if (reelCount > 50) {
        html += `<div style="color:var(--text-muted);font-size:12px;padding:6px 0;text-align:center;">+${reelCount - 50} more reels</div>`;
      }
    } else {
      html += `<div style="color:var(--text-muted);font-size:12px;padding:8px 0;">No reels found</div>`;
    }
    
    html += `
          </div>
        </div>
      </div>
    `;
  });
  
  html += `</div>`;
  content.innerHTML = html;
  clearScrapedBtn.hidden = false;
  
  // Add copy functionality
  document.querySelectorAll('.copy-reel-btn').forEach(btn => {
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      const url = this.dataset.url;
      copyToClipboard(url, this);
    });
  });
  
  // Add download functionality
  document.querySelectorAll('.download-reel-btn').forEach(btn => {
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      const url = this.dataset.url;
      downloadVideo(url, 'instagram_reel');
    });
  });
}

// ==================== SCRAPED REELS HELPER FUNCTIONS ====================

function toggleProfile(header) {
  const body = header.nextElementSibling;
  const toggle = header.querySelector('.scraped-profile-toggle');
  
  if (body.classList.contains('open')) {
    body.classList.remove('open');
    toggle.classList.remove('open');
    toggle.textContent = '▼';
  } else {
    body.classList.add('open');
    toggle.classList.add('open');
    toggle.textContent = '▲';
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

async function copyToClipboard(text, btn) {
  try {
    await navigator.clipboard.writeText(text);
    btn.textContent = '✅';
    setTimeout(() => { btn.textContent = '📋'; }, 2000);
  } catch {
    const input = document.createElement('input');
    input.value = text;
    document.body.appendChild(input);
    input.select();
    document.execCommand('copy');
    document.body.removeChild(input);
    btn.textContent = '✅';
    setTimeout(() => { btn.textContent = '📋'; }, 2000);
  }
}

// ==================== START SCRAPING ====================

startScrapeBtn.addEventListener('click', async function() {
  const usernames = scrapeUsernames.value
    .split('\n')
    .map(s => s.trim())
    .filter(Boolean);
  
  if (usernames.length === 0) {
    showScrapeStatus('Please enter at least one username', 'error');
    return;
  }
  
  const maxReels = parseInt(scrapeMaxReels.value) || 50;
  const maxScrolls = parseInt(scrapeMaxScrolls.value) || 8;
  const headless = scrapeHeadless.checked;
  
  try {
    const cookieStatus = await fetch('/api/instagram/cookies_status', { credentials: 'same-origin' });
    const cookieData = await cookieStatus.json();
    
    if (!cookieData.has_cookies) {
      showScrapeStatus('❌ Please upload your Instagram cookies.json file first!', 'error');
      return;
    }
  } catch (error) {
    showScrapeStatus('❌ Failed to check cookie status', 'error');
    return;
  }
  
  this.disabled = true;
  this.innerHTML = '<span class="btn-spinner"></span> Starting job...';
  showScrapeStatus('⏳ Sending request to Render...', 'running');
  showScrapeProgress(10, 'Connecting to Vercel proxy...');
  
  try {
    const response = await fetch('/api/scrape/proxy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        usernames: usernames,
        maxReels: maxReels,
        maxScrolls: maxScrolls,
        headless: headless,
        sendToVercel: true
      })
    });
    
    const data = await response.json();
    
    if (response.ok) {
      showScrapeProgress(100, '✅ Job started!');
      showScrapeStatus(`✅ Job started! Job ID: ${data.jobId}`, 'success');
      
      localStorage.setItem('last_scrape_job_id', data.jobId);
      
      scrapedReelsContent.innerHTML = `
        <div class="empty-state" style="border-color: var(--success);">
          <div style="font-size: 24px; margin-bottom: 8px;">🚀</div>
          <strong>Job sent to Render!</strong>
          <p style="margin-top: 8px; font-size: 13px; color: var(--text-secondary);">
            Job ID: <code style="background: var(--bg-secondary); padding: 2px 8px; border-radius: 4px;">${data.jobId}</code>
          </p>
          <p style="margin-top: 4px; font-size: 13px; color: var(--text-secondary);">
            Render is scraping the profiles. Results will be sent back automatically.
          </p>
          <p style="margin-top: 8px; font-size: 13px; color: var(--text-muted);">
            ⏱️ This may take a minute or two. Click <strong>"Load Results"</strong> after the job completes.
          </p>
        </div>
      `;
      
      setTimeout(() => {
        hideScrapeProgress();
      }, 3000);
      
    } else {
      showScrapeProgress(0, '❌ Failed');
      showScrapeStatus(`❌ ${data.error || 'Failed to start job'}`, 'error');
    }
  } catch (error) {
    console.error('Scrape error:', error);
    showScrapeProgress(0, '❌ Error');
    showScrapeStatus(`❌ ${error.message}`, 'error');
  } finally {
    this.innerHTML = `
      <span class="btn-content">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <path d="M3 10L7 14L17 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        Start Scraping
      </span>
    `;
    this.disabled = false;
  }
});

// ==================== FETCH SCRAPED RESULTS ====================
async function fetchScrapedResults() {
  const btn = document.getElementById('fetch-scraped-btn');
  btn.textContent = '⏳ Loading...';
  btn.disabled = true;
  
  try {
    const response = await fetch('/api/scraped/latest', { credentials: 'same-origin' });
    const data = await response.json();
    console.log('📊 Scraped data:', data);
    
    if (response.ok && data.results && data.results.length > 0) {
      window.scrapedData = data.results;
      window.allUsernames = data.usernames || [];
      
      // Render all profiles
      renderScrapedResults(data.results);
      
      // Show status with all usernames
      const usernameList = data.usernames ? data.usernames.join(', ') : '';
      showScrapedStatus(
        `✅ Loaded ${data.results.length} profiles: ${usernameList}`,
        'success'
      );
    } else {
      showScrapedStatus('No results found. Start a new scrape job.', 'error');
      renderScrapedResults([]);
    }
  } catch (error) {
    console.error('❌ Fetch error:', error);
    showScrapedStatus(`❌ Failed to load results: ${error.message}`, 'error');
  } finally {
    btn.textContent = '📊 Load Results';
    btn.disabled = false;
  }
}

// ==================== DOWNLOAD FUNCTIONS ====================

function downloadVideo(url, filename) {
  if (!url) {
    showError("No video URL available to download");
    return;
  }
  
  downloadProgress.hidden = false;
  progressFill.style.width = '0%';
  progressText.textContent = '0%';
  
  const safeFilename = (filename || 'instagram_video')
    .replace(/[^a-zA-Z0-9]/g, '_')
    .substring(0, 50) + '.mp4';
  
  fetch(url)
    .then(response => {
      if (!response.ok) throw new Error('Network response was not ok');
      
      const contentLength = response.headers.get('content-length');
      const total = parseInt(contentLength, 10);
      let loaded = 0;
      
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
                progressText.textContent = percent + '%';
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
      progressFill.style.width = '100%';
      progressText.textContent = '100%';
      
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
      progressText.textContent = 'Failed';
      setTimeout(() => {
        window.open(url, '_blank');
        downloadProgress.hidden = true;
      }, 1000);
    });
}

// ==================== RESULTS FUNCTIONS ====================

function renderResults(items, sourceUrl) {
  results.innerHTML = "";
  results.hidden = false;
  directUrlSection.hidden = true;
  videoPreview.hidden = true;
  downloadProgress.hidden = true;
  blueskySection.hidden = true;

  items.forEach((item) => {
    const node = template.content.cloneNode(true);

    const img = node.querySelector(".result-thumb img");
    if (item.thumbnail) {
      img.src = item.thumbnail;
      img.alt = item.title || "Video thumbnail";
    } else {
      img.closest(".result-thumb").style.display = "none";
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
  
  if (url && (url.endsWith('.mp4') || url.includes('video') || url.includes('cdninstagram') || url.includes('fbcdn'))) {
    videoPreview.hidden = false;
    previewVideo.src = url;
    previewVideo.load();
    
    let infoHtml = '';
    if (item.uploader) infoHtml += `<p><strong>Uploader:</strong> @${item.uploader}</p>`;
    if (item.title) infoHtml += `<p><strong>Title:</strong> ${item.title}</p>`;
    if (item.duration) infoHtml += `<p><strong>Duration:</strong> ${formatDuration(item.duration)}</p>`;
    
    videoInfo.innerHTML = infoHtml + `<button id="video-download-btn" class="btn btn-success btn-block">⬇ Download Video</button>`;
    
    document.getElementById('video-download-btn').addEventListener('click', function() {
      if (currentVideoUrl) {
        downloadVideo(currentVideoUrl, item?.title || 'instagram_video');
      }
    });
  }
  
  showBlueskySection();
}

function formatDuration(seconds) {
  if (!seconds && seconds !== 0) return "";
  const s = Math.round(seconds);
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}:${String(rem).padStart(2, "0")}`;
}

function showError(message) {
  errorMsg.textContent = message;
  errorMsg.hidden = false;
}

function clearError() {
  errorMsg.hidden = true;
  errorMsg.textContent = "";
}

function setLoading(isLoading) {
  fetchBtn.disabled = isLoading;
  const label = fetchBtn.querySelector(".btn-label");
  const spinner = fetchBtn.querySelector(".btn-spinner");
  if (isLoading) {
    label.textContent = "Fetching...";
    spinner.hidden = false;
  } else {
    label.textContent = "Fetch";
    spinner.hidden = true;
  }
}

// ==================== EVENT LISTENERS ====================

copyBtn.addEventListener('click', async function() {
  const url = directUrlDisplay.value;
  if (!url) return;
  
  try {
    await navigator.clipboard.writeText(url);
    this.innerHTML = '✅ Copied!';
    setTimeout(() => {
      this.innerHTML = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M5 5V3C5 2.46957 5.21071 1.96086 5.58579 1.58579C5.96086 1.21071 6.46957 1 7 1H13C13.5304 1 14.0391 1.21071 14.4142 1.58579C14.7893 1.96086 15 2.46957 15 3V9C15 9.53043 14.7893 10.0391 14.4142 10.4142C14.0391 10.7893 13.5304 11 13 11H11M3 15H9C9.53043 15 10.0391 14.7893 10.4142 14.4142C10.7893 14.0391 11 13.5304 11 13V7C11 6.46957 10.7893 5.96086 10.4142 5.58579C10.0391 5.21071 9.53043 5 9 5H3C2.46957 5 1.96086 5.21071 1.58579 5.58579C1.21071 5.96086 1 6.46957 1 7V13C1 13.5304 1.21071 14.0391 1.58579 14.4142C1.21071 14.7893 2.46957 15 3 15Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg> Copy';
    }, 2000);
  } catch {
    directUrlDisplay.select();
    document.execCommand('copy');
    this.innerHTML = '✅ Copied!';
    setTimeout(() => {
      this.innerHTML = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M5 5V3C5 2.46957 5.21071 1.96086 5.58579 1.58579C5.96086 1.21071 6.46957 1 7 1H13C13.5304 1 14.0391 1.21071 14.4142 1.58579C14.7893 1.96086 15 2.46957 15 3V9C15 9.53043 14.7893 10.0391 14.4142 10.4142C14.0391 10.7893 13.5304 11 13 11H11M3 15H9C9.53043 15 10.0391 14.7893 10.4142 14.4142C10.7893 14.0391 11 13.5304 11 13V7C11 6.46957 10.7893 5.96086 10.4142 5.58579C10.0391 5.21071 9.53043 5 9 5H3C2.46957 5 1.96086 5.21071 1.58579 5.58579C1.21071 5.96086 1 6.46957 1 7V13C1 13.5304 1.21071 14.0391 1.58579 14.4142C1.21071 14.7893 2.46957 15 3 15Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg> Copy';
    }, 2000);
  }
});

directDownloadBtn.addEventListener('click', function() {
  if (currentVideoUrl) {
    downloadVideo(currentVideoUrl, currentVideoItem?.title || 'instagram_video');
  }
});

directUrlDisplay.addEventListener('click', function() {
  this.select();
});

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
      credentials: 'same-origin',
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
        credentials: 'same-origin',
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

// ==================== INIT ====================

async function initSession() {
    try {
        const response = await fetch('/api/init', { credentials: 'same-origin' });
        const data = await response.json();
        console.log('Session initialized:', data);
        
        if (data.has_cookies) {
            await checkInstagramStatus();
        }
    } catch (error) {
        console.error('Failed to initialize session:', error);
    }
}

// Call init before checking status
initSession().then(() => {
    checkInstagramStatus();
    checkBlueskyStatus();
});

const savedJobId = localStorage.getItem('last_scrape_job_id');
if (savedJobId) {
  showScrapeStatus(`ℹ️ Last job ID: ${savedJobId.slice(0, 8)}... - Click "Load Results" to check for completed jobs.`, 'running');
  scrapedReelsContent.innerHTML = `
    <div class="empty-state">
      <div style="font-size: 24px; margin-bottom: 8px;">📋</div>
      <strong>Previous job found</strong>
      <p style="margin-top: 8px; font-size: 13px; color: var(--text-secondary);">
        Job ID: <code style="background: var(--bg-secondary); padding: 2px 8px; border-radius: 4px;">${savedJobId}</code>
      </p>
      <p style="margin-top: 4px; font-size: 13px; color: var(--text-muted);">
        Click "Load Results" to check if the job has completed.
      </p>
    </div>
  `;
}