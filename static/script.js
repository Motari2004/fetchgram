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

// All Usernames elements
const allUsernamesSection = document.getElementById('all-usernames-section');
const allUsernamesList = document.getElementById('all-usernames-list');

// Sync elements
const syncControls = document.getElementById('sync-controls');
const syncUsernameSelect = document.getElementById('sync-username-select');
const syncExecuteBtn = document.getElementById('sync-execute-btn');
const syncStatus = document.getElementById('sync-status');
const syncProgress = document.getElementById('sync-progress');
const syncProgressBar = document.getElementById('sync-progress-bar');
const syncProgressText = document.getElementById('sync-progress-text');
const syncCaptionsBtn = document.getElementById('sync-captions-btn');

// Zernio (Facebook) elements
const zernioAccountSelect = document.getElementById('zernio-account-select');
const zernioText = document.getElementById('zernio-text');
const zernioSchedule = document.getElementById('zernio-schedule');
const zernioPublishBtn = document.getElementById('zernio-publish-btn');
const zernioScheduleBtn = document.getElementById('zernio-schedule-btn');
const zernioStatus = document.getElementById('zernio-status');
const zernioStatusBadge = document.getElementById('zernio-status-badge');

// Pipeline elements
const pipelinesList = document.getElementById('pipelines-list');
const pipelinesStatus = document.getElementById('pipelines-status');
const runAllPipelinesBtn = document.getElementById('run-all-pipelines-btn');
const refreshPipelinesBtn = document.getElementById('refresh-pipelines-btn');
const createPipelineBtn = document.getElementById('create-pipeline-btn');
const pipelineName = document.getElementById('pipeline-name');
const pipelineUsername = document.getElementById('pipeline-username');
const pipelineFacebookAccount = document.getElementById('pipeline-facebook-account');
const pipelineDailyLimit = document.getElementById('pipeline-daily-limit');

let currentVideoUrl = null;
let currentVideoItem = null;

// Zernio state
let zernioAccounts = [];
let zernioAccountsLoaded = false;

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
    const savedResponse = await fetch('/api/instagram/cookies_status', { 
      credentials: 'same-origin' 
    });
    const savedData = await savedResponse.json();
    console.log('📊 Database status response:', savedData);
    
    if (savedData.has_cookies) {
      updateInstagramStatus(true, savedData.username);
      return;
    }
    
    const response = await fetch('/api/cookies/status', { 
      credentials: 'same-origin' 
    });
    const data = await response.json();
    console.log('📊 Session status response:', data);
    updateInstagramStatus(data.has_cookies, data.username);
    
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

// ==================== SYNC CAPTIONS FUNCTIONS ====================

function showSyncControls(usernames) {
  if (!syncControls || !syncUsernameSelect) return;
  
  if (usernames && usernames.length > 0) {
    syncControls.style.display = 'block';
    syncUsernameSelect.innerHTML = '';
    
    usernames.forEach(username => {
      const option = document.createElement('option');
      option.value = username;
      option.textContent = `@${username}`;
      syncUsernameSelect.appendChild(option);
    });
    
    if (usernames.length === 1) {
      syncUsernameSelect.value = usernames[0];
    }
  } else {
    syncControls.style.display = 'none';
  }
}

function showSyncStatus(message, type) {
  if (!syncStatus) return;
  
  syncStatus.textContent = message;
  syncStatus.className = type || '';
  syncStatus.style.display = 'block';
  
  if (type === 'success' || type === 'error') {
    setTimeout(() => {
      syncStatus.style.display = 'none';
    }, 8000);
  }
}

// Sync Captions Button - opens sync controls
syncCaptionsBtn?.addEventListener('click', function() {
  // If sync controls are hidden, show them
  if (syncControls.style.display === 'none' || syncControls.style.display === '') {
    // Load available profiles first
    const usernames = window.allUsernames || [];
    if (usernames.length > 0) {
      showSyncControls(usernames);
      showSyncStatus('Select a profile and click "Sync Captions"', 'info');
      // Scroll to sync controls
      syncControls.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else {
      showSyncStatus('No profiles found. Load results first.', 'error');
    }
  } else {
    // Toggle visibility
    syncControls.style.display = syncControls.style.display === 'none' ? 'block' : 'none';
  }
});





























// Execute Sync
// In script.js - update sync button handler
syncExecuteBtn?.addEventListener('click', async function() {
  const username = syncUsernameSelect?.value;
  
  if (!username) {
    showSyncStatus('❌ Please select a profile', 'error');
    return;
  }
  
  this.disabled = true;
  this.innerHTML = '<span class="btn-spinner"></span> Starting...';
  
  showSyncStatus(`⏳ Starting caption sync for @${username}...`, 'info');
  
  try {
    const response = await fetch('/api/sync-captions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ username })
    });
    
    const data = await response.json();
    
    if (response.status === 202) {
      showSyncStatus(
        `✅ Sync started for @${username}! Captions will appear in 1-2 minutes.`,
        'success'
      );
      
      // Start polling for updated data
      let attempts = 0;
      const maxAttempts = 30; // 30 * 5s = 2.5 minutes
      
      const checkUpdates = setInterval(async () => {
        attempts++;
        const reloadRes = await fetch('/api/scraped/latest', { credentials: 'same-origin' });
        const reloadData = await reloadRes.json();
        
        if (reloadData.results && reloadData.results.length > 0) {
          // Check if our profile has captions now
          const profile = reloadData.results.find(p => p.username === username);
          if (profile) {
            const withCaptions = profile.reels.filter(r => r.caption && r.caption.trim().length > 0);
            if (withCaptions.length > 0 || attempts >= maxAttempts) {
              clearInterval(checkUpdates);
              window.scrapedData = reloadData.results;
              renderScrapedResults(reloadData.results);
              showSyncStatus(
                `✅ Captions updated! ${withCaptions.length} captions fetched.`,
                'success'
              );
            }
          }
        }
        
        if (attempts >= maxAttempts) {
          clearInterval(checkUpdates);
          showSyncStatus('⏳ Sync is still processing. Click "Load Results" to check.', 'info');
        }
      }, 5000); // Check every 5 seconds
      
    } else {
      showSyncStatus(`❌ ${data.error || 'Failed to start sync'}`, 'error');
    }
    
  } catch (error) {
    console.error('Sync error:', error);
    showSyncStatus(`❌ Error: ${error.message}`, 'error');
  } finally {
    this.disabled = false;
    this.innerHTML = '<span class="btn-content">🔄 Sync Captions</span>';
  }
});








    
    setTimeout(() => {
      if (syncProgress) syncProgress.style.display = 'none';
      if (syncProgressBar) syncProgressBar.style.width = '0%';
    }, 3000);
  }
});

// ==================== ZERNIO (FACEBOOK) FUNCTIONS ====================

function showZernioStatus(message, type) {
  if (!zernioStatus) return;
  
  zernioStatus.hidden = false;
  zernioStatus.style.display = 'block';
  zernioStatus.innerHTML = '';
  zernioStatus.className = 'status-message ' + type;
  
  const textSpan = document.createElement('span');
  textSpan.textContent = message;
  zernioStatus.appendChild(textSpan);
  
  if (type === 'success' || type === 'error') {
    const closeBtn = document.createElement('span');
    closeBtn.textContent = ' ✕';
    closeBtn.style.cssText = `
      float: right;
      cursor: pointer;
      font-weight: bold;
      margin-left: 12px;
      opacity: 0.7;
      padding: 0 4px;
    `;
    closeBtn.onclick = function(e) {
      e.stopPropagation();
      zernioStatus.style.display = 'none';
      zernioStatus.hidden = true;
    };
    zernioStatus.appendChild(closeBtn);
  }
  
  if (type === 'info') {
    setTimeout(() => {
      if (zernioStatus) {
        zernioStatus.style.display = 'none';
        zernioStatus.hidden = true;
      }
    }, 8000);
  }
}

function showZernioSuccess(message, details) {
  if (!zernioStatus) return;
  
  zernioStatus.hidden = false;
  zernioStatus.style.display = 'block';
  
  let html = `<div style="display: flex; align-items: flex-start; gap: 10px; padding: 4px 0;">`;
  html += `<span style="font-size: 18px; flex-shrink: 0;">✅</span>`;
  html += `<div style="flex: 1;">`;
  html += `<div style="font-weight: 600; font-size: 14px;">${message}</div>`;
  
  if (details) {
    html += `<div style="margin-top: 6px; font-size: 13px; opacity: 0.85; line-height: 1.6;">`;
    if (details.accounts) {
      html += `<div>📱 <strong>Account:</strong> ${details.accounts}</div>`;
    }
    if (details.post_id) {
      html += `<div>📋 <strong>Post ID:</strong> ${details.post_id}</div>`;
    }
    if (details.status) {
      html += `<div>📊 <strong>Status:</strong> ${details.status}</div>`;
    }
    if (details.scheduled_for) {
      html += `<div>📅 <strong>Scheduled:</strong> ${new Date(details.scheduled_for).toLocaleString()}</div>`;
    }
    if (details.url) {
      html += `<div>🔗 <a href="${details.url}" target="_blank" style="color: var(--accent); text-decoration: underline;">View on Facebook</a></div>`;
    }
    html += `</div>`;
  }
  
  html += `</div>`;
  html += `<button onclick="this.parentElement.parentElement.style.display='none'; this.parentElement.parentElement.hidden=true;" style="background:none;border:none;cursor:pointer;font-size:16px;color:var(--text-muted);flex-shrink:0;padding:0 4px;">✕</button>`;
  html += `</div>`;
  
  zernioStatus.innerHTML = html;
  zernioStatus.className = 'status-message success';
  zernioStatus.style.display = 'block';
  zernioStatus.hidden = false;
  
  setTimeout(() => {
    zernioStatus.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, 300);
}

// ==================== LOAD ZERNIO ACCOUNTS ====================

async function loadZernioAccounts() {
  try {
    const response = await fetch('/api/zernio/accounts', {
      credentials: 'same-origin'
    });
    const data = await response.json();
    
    if (data.status === 'success' && data.accounts) {
      zernioAccounts = data.accounts;
      populateZernioAccountSelect(zernioAccounts);
      populatePipelineFacebookAccounts(zernioAccounts);
      zernioAccountsLoaded = true;
      console.log('✅ Loaded Zernio accounts:', zernioAccounts);
      
      if (zernioStatusBadge) {
        if (zernioAccounts.length > 0) {
          zernioStatusBadge.textContent = `✅ ${zernioAccounts.length} accounts`;
          zernioStatusBadge.style.background = 'var(--success-bg)';
          zernioStatusBadge.style.color = 'var(--success)';
        } else {
          zernioStatusBadge.textContent = '⚠️ No accounts';
          zernioStatusBadge.style.background = 'var(--warning-bg)';
          zernioStatusBadge.style.color = 'var(--warning)';
        }
      }
    } else {
      console.warn('⚠️ Failed to load Zernio accounts:', data.message);
    }
  } catch (error) {
    console.error('❌ Failed to load Zernio accounts:', error);
  }
}

function populateZernioAccountSelect(accounts) {
  if (!zernioAccountSelect) return;
  
  zernioAccountSelect.innerHTML = '';
  
  if (accounts.length > 1) {
    const allOption = document.createElement('option');
    allOption.value = 'all';
    allOption.textContent = `All Accounts (${accounts.length})`;
    zernioAccountSelect.appendChild(allOption);
  }
  
  if (accounts.length === 0) {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = 'No Facebook accounts found';
    option.disabled = true;
    zernioAccountSelect.appendChild(option);
    return;
  }
  
  accounts.sort((a, b) => a.name.localeCompare(b.name));
  
  accounts.forEach(account => {
    const option = document.createElement('option');
    option.value = account.id;
    option.textContent = account.name;
    option.dataset.pageId = account.page_id;
    option.dataset.status = account.status;
    zernioAccountSelect.appendChild(option);
  });
  
  if (accounts.length === 1) {
    zernioAccountSelect.value = accounts[0].id;
  }
}

function populatePipelineFacebookAccounts(accounts) {
  if (!pipelineFacebookAccount) return;
  
  pipelineFacebookAccount.innerHTML = '';
  
  if (accounts.length === 0) {
    const option = document.createElement('option');
    option.value = '';
    option.textContent = 'No Facebook accounts found';
    option.disabled = true;
    pipelineFacebookAccount.appendChild(option);
    return;
  }
  
  accounts.forEach(account => {
    const option = document.createElement('option');
    option.value = account.id;
    option.textContent = account.name;
    pipelineFacebookAccount.appendChild(option);
  });
}

// ==================== PUBLISH FUNCTIONS ====================

async function publishToFacebook(videoUrl, text, accountId, publishNow = true, scheduledTime = null) {
  const payload = {
    video_url: videoUrl,
    text: text,
    publish_now: publishNow
  };

  if (accountId && accountId !== 'all') {
    payload.account_id = accountId;
  }

  if (scheduledTime) {
    payload.scheduled_time = scheduledTime;
  }

  try {
    const response = await fetch('/api/zernio/publish', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      credentials: 'same-origin',
      body: JSON.stringify(payload)
    });

    const data = await response.json();
    console.log('📤 Zernio response:', data);
    return data;
  } catch (error) {
    console.error('❌ Zernio error:', error);
    throw error;
  }
}

async function checkZernioStatus() {
  try {
    const response = await fetch('/api/zernio/status', {
      credentials: 'same-origin'
    });
    const data = await response.json();
    
    if (data.status === 'connected') {
      if (zernioStatusBadge) {
        zernioStatusBadge.textContent = '✅ Connected';
        zernioStatusBadge.style.background = 'var(--success-bg)';
        zernioStatusBadge.style.color = 'var(--success)';
      }
      console.log('✅ Zernio connected');
    } else {
      if (zernioStatusBadge) {
        zernioStatusBadge.textContent = '⚠️ Disconnected';
        zernioStatusBadge.style.background = 'var(--error-bg)';
        zernioStatusBadge.style.color = 'var(--error)';
      }
      console.warn('⚠️ Zernio not connected');
    }
  } catch (error) {
    console.error('Failed to check Zernio status:', error);
  }
}

function showZernioSection() {
  const section = document.getElementById('zernio-section');
  if (section) {
    section.hidden = false;
    if (!zernioAccountsLoaded) {
      loadZernioAccounts();
    }
    setTimeout(() => {
      section.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 300);
  }
}

// ==================== ZERNIO EVENT LISTENERS ====================

zernioPublishBtn?.addEventListener('click', async function() {
  const text = zernioText.value.trim() || 'Check out this video! 🎬';
  const accountId = zernioAccountSelect.value;
  const videoUrl = currentVideoUrl;
  
  if (!videoUrl) {
    showZernioStatus('❌ No video loaded. Please fetch a video first.', 'error');
    return;
  }
  
  let accountName = accountId === 'all' ? 'All Accounts' : 'Selected Account';
  if (accountId !== 'all') {
    const selectedOption = zernioAccountSelect.options[zernioAccountSelect.selectedIndex];
    accountName = selectedOption ? selectedOption.textContent : 'Selected Account';
  }
  
  this.disabled = true;
  this.innerHTML = '<span class="btn-spinner"></span> Publishing...';
  showZernioStatus(`⏳ Publishing to ${accountName}...`, 'info');
  
  try {
    const result = await publishToFacebook(videoUrl, text, accountId, true, null);
    console.log('📤 Publish result:', result);
    
    if (result.error) {
      showZernioStatus(`❌ ${result.error}`, 'error');
      return;
    }
    
    let successMessage = '';
    let details = {};
    
    if (result.status === 'success') {
      const results = result.results || {};
      const accountNames = Object.values(results).map(r => r.account_name).join(', ');
      successMessage = `✅ Published successfully to ${Object.keys(results).length} account(s)!`;
      details = {
        accounts: accountNames || accountName,
        post_id: result.post_id || 'N/A',
        status: 'published'
      };
      
      const failed = Object.values(results).filter(r => r.result && r.result.error);
      if (failed.length > 0) {
        successMessage += ` (${failed.length} account(s) had issues)`;
      }
      
      showZernioSuccess(successMessage, details);
      
    } else {
      const post = result.post || result;
      const postStatus = post.status || 'unknown';
      
      if (postStatus === 'published') {
        successMessage = '✅ Video published successfully to Facebook!';
        details = {
          post_id: post._id || 'N/A',
          status: 'published',
          url: post.platforms?.find(p => p.platform === 'facebook')?.publishedUrl || null,
          accounts: accountName
        };
        showZernioSuccess(successMessage, details);
        
      } else if (postStatus === 'scheduled') {
        const scheduledTime = post.scheduledFor || 'later';
        successMessage = `📅 Video scheduled for ${new Date(scheduledTime).toLocaleString()}`;
        details = {
          post_id: post._id || 'N/A',
          status: 'scheduled',
          scheduled_for: scheduledTime,
          accounts: accountName
        };
        showZernioSuccess(successMessage, details);
        
      } else if (postStatus === 'draft') {
        successMessage = '📝 Video saved as draft.';
        details = {
          post_id: post._id || 'N/A',
          status: 'draft',
          accounts: accountName
        };
        showZernioSuccess(successMessage, details);
        
      } else {
        successMessage = `📊 Post created with status: ${postStatus}`;
        details = {
          post_id: post._id || 'N/A',
          status: postStatus,
          accounts: accountName
        };
        showZernioSuccess(successMessage, details);
      }
    }
    
    if (zernioSchedule) {
      zernioSchedule.value = '';
    }
    
  } catch (error) {
    console.error('Publish error:', error);
    showZernioStatus(`❌ Failed to publish: ${error.message || 'Unknown error'}`, 'error');
  } finally {
    this.disabled = false;
    this.innerHTML = `
      <span class="btn-content">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <path d="M3 10L7 14L17 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        Publish Now
      </span>
    `;
  }
});

zernioScheduleBtn?.addEventListener('click', async function() {
  const text = zernioText.value.trim() || 'Check out this video! 🎬';
  const accountId = zernioAccountSelect.value;
  const videoUrl = currentVideoUrl;
  const scheduleTime = zernioSchedule.value;
  
  if (!videoUrl) {
    showZernioStatus('❌ No video loaded. Please fetch a video first.', 'error');
    return;
  }
  
  if (!scheduleTime) {
    showZernioStatus('❌ Please select a date and time to schedule.', 'error');
    return;
  }
  
  let accountName = accountId === 'all' ? 'All Accounts' : 'Selected Account';
  if (accountId !== 'all') {
    const selectedOption = zernioAccountSelect.options[zernioAccountSelect.selectedIndex];
    accountName = selectedOption ? selectedOption.textContent : 'Selected Account';
  }
  
  const scheduledDateTime = new Date(scheduleTime).toISOString();
  const displayTime = new Date(scheduleTime).toLocaleString();
  
  this.disabled = true;
  this.innerHTML = '<span class="btn-spinner"></span> Scheduling...';
  showZernioStatus(`⏳ Scheduling post for ${displayTime}...`, 'info');
  
  try {
    const result = await publishToFacebook(videoUrl, text, accountId, false, scheduledDateTime);
    console.log('📤 Schedule result:', result);
    
    if (result.error) {
      showZernioStatus(`❌ ${result.error}`, 'error');
      return;
    }
    
    const post = result.post || result;
    const postStatus = post.status || 'unknown';
    
    if (postStatus === 'scheduled') {
      const successMessage = `📅 Post scheduled for ${displayTime}`;
      const details = {
        post_id: post._id || 'N/A',
        status: 'scheduled',
        scheduled_for: scheduledDateTime,
        accounts: accountName
      };
      showZernioSuccess(successMessage, details);
    } else if (postStatus === 'published') {
      showZernioSuccess('✅ Video published immediately!', {
        post_id: post._id || 'N/A',
        status: 'published',
        accounts: accountName
      });
    } else {
      showZernioSuccess(`📊 Post status: ${postStatus}`, {
        post_id: post._id || 'N/A',
        status: postStatus,
        accounts: accountName
      });
    }
    
    zernioSchedule.value = '';
    
  } catch (error) {
    console.error('Schedule error:', error);
    showZernioStatus(`❌ Failed to schedule: ${error.message || 'Unknown error'}`, 'error');
  } finally {
    this.disabled = false;
    this.innerHTML = '<span class="btn-content">📅 Schedule</span>';
  }
});

// ==================== REFRESH ZERNIO ACCOUNTS ====================

document.getElementById('refresh-zernio-btn')?.addEventListener('click', async function() {
  this.disabled = true;
  this.textContent = '⏳';
  
  try {
    const response = await fetch('/api/zernio/accounts?t=' + Date.now(), {
      credentials: 'same-origin'
    });
    const data = await response.json();
    
    if (data.status === 'success' && data.accounts) {
      zernioAccounts = data.accounts;
      populateZernioAccountSelect(zernioAccounts);
      populatePipelineFacebookAccounts(zernioAccounts);
      zernioAccountsLoaded = true;
      showZernioStatus(`✅ Refreshed ${data.accounts.length} accounts`, 'success');
      
      if (zernioStatusBadge) {
        if (zernioAccounts.length > 0) {
          zernioStatusBadge.textContent = `✅ ${zernioAccounts.length} accounts`;
          zernioStatusBadge.style.background = 'var(--success-bg)';
          zernioStatusBadge.style.color = 'var(--success)';
        } else {
          zernioStatusBadge.textContent = '⚠️ No accounts';
          zernioStatusBadge.style.background = 'var(--warning-bg)';
          zernioStatusBadge.style.color = 'var(--warning)';
        }
      }
    }
  } catch (error) {
    showZernioStatus('❌ Failed to refresh accounts', 'error');
  } finally {
    this.disabled = false;
    this.textContent = '🔄 Refresh';
  }
});

// ==================== DELETE FUNCTIONS ====================

async function deleteProfile(username) {
  if (!confirm(`⚠️ Permanently delete ALL data for @${username} from the database?`)) {
    return;
  }
  
  showScrapedStatus(`🗑️ Permanently deleting @${username} from database...`, 'info');
  
  try {
    const response = await fetch('/api/scraped/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ username: username })
    });
    
    const data = await response.json();
    console.log('Delete response:', data);
    
    if (response.ok && data.status === 'success') {
      if (window.scrapedData) {
        window.scrapedData = window.scrapedData.filter(p => p.username !== username);
        renderScrapedResults(window.scrapedData);
      }
      
      window.allUsernames = window.allUsernames?.filter(u => u !== username) || [];
      
      showScrapedStatus(
        `✅ Permanently deleted @${username} (${data.deleted_count || 0} jobs removed from database)`, 
        'success'
      );
      
      setTimeout(() => {
        autoLoadScrapedResults();
      }, 1500);
      
    } else {
      showScrapedStatus(`❌ Failed to delete: ${data.error || 'Unknown error'}`, 'error');
    }
  } catch (error) {
    console.error('Delete error:', error);
    showScrapedStatus(`❌ Failed to delete: ${error.message}`, 'error');
  }
}

// ==================== SCRAPED REELS FUNCTIONS ====================

function renderScrapedResults(results, stats, isLoading = false) {
  const content = document.getElementById('scraped-reels-content');
  const statsContainer = document.getElementById('scraped-stats');
  const exportBtn = document.getElementById('export-scraped-btn');
  const countBadge = document.getElementById('scraped-count-badge');
  
  if (allUsernamesSection && allUsernamesList) {
    if (results && results.length > 0) {
      const usernames = results.map(p => `@${p.username}`).join(', ');
      allUsernamesList.textContent = usernames;
      allUsernamesSection.hidden = false;
      window.allUsernames = usernames;
    } else {
      allUsernamesSection.hidden = true;
      window.allUsernames = [];
    }
  }
  
  // Show sync controls if we have results
  if (results && results.length > 0) {
    const usernames = results.map(p => p.username);
    showSyncControls(usernames);
  } else {
    showSyncControls([]);
  }
  
  if (isLoading) {
    content.innerHTML = `
      <div class="loading-state">
        <div class="loading-spinner"></div>
        <p style="color: var(--text-muted); margin-top: 12px;">Loading scraped data...</p>
      </div>
    `;
    if (statsContainer) statsContainer.hidden = true;
    if (exportBtn) exportBtn.hidden = true;
    if (countBadge) countBadge.textContent = 'Loading...';
    return;
  }
  
  if (!results || results.length === 0) {
    content.innerHTML = `
      <div class="empty-state">
        <div style="font-size: 32px; margin-bottom: 12px;">📭</div>
        <strong>No scraped data found</strong>
        <p style="margin-top: 8px; font-size: 13px; color: var(--text-secondary);">
          Enter usernames below and click "Start Scraping" to begin.
        </p>
      </div>
    `;
    if (statsContainer) statsContainer.hidden = true;
    if (exportBtn) exportBtn.hidden = true;
    if (countBadge) countBadge.textContent = '0 profiles';
    return;
  }
  
  let totalReels = 0;
  let successCount = 0;
  let errorCount = 0;
  
  results.forEach(profile => {
    const reels = profile.reels || [];
    totalReels += reels.length;
    if (profile.status === 'ok') successCount++;
    else errorCount++;
  });
  
  document.getElementById('stat-profiles').textContent = results.length;
  document.getElementById('stat-reels').textContent = totalReels;
  document.getElementById('stat-success').textContent = successCount;
  document.getElementById('stat-errors').textContent = errorCount;
  
  if (statsContainer) statsContainer.hidden = false;
  if (exportBtn) exportBtn.hidden = false;
  if (countBadge) countBadge.textContent = `${results.length} profiles (${totalReels} reels)`;
  
  let html = `<div class="scraped-profiles-grid">`;
  
  results.forEach((profile, index) => {
    const username = profile.username || 'unknown';
    const reelCount = (profile.reels || []).length;
    const status = profile.status || 'ok';
    const statusClass = status === 'ok' ? 'ok' : 
                        (status === 'no_reels_found' || status === 'private') ? 'warn' : 'err';
    const isOpen = false;
    
    html += `
      <div class="scraped-profile-card">
        <div class="scraped-profile-header" onclick="toggleProfile(this)">
          <div class="scraped-profile-name">
            👤 @${escapeHtml(username)}
            <span class="status-badge ${statusClass}">${escapeHtml(status)}</span>
          </div>
          <div style="display:flex;align-items:center;gap:8px;">
            <span class="scraped-profile-count">📹 ${reelCount}</span>
            <button class="btn btn-sm btn-danger delete-profile-btn" data-username="${escapeHtml(username)}" onclick="event.stopPropagation(); deleteProfile('${escapeHtml(username)}')">
              🗑️
            </button>
            <span class="scraped-profile-toggle ${isOpen ? 'open' : ''}">▼</span>
          </div>
        </div>
        <div class="scraped-profile-body ${isOpen ? 'open' : ''}">
          <div class="scraped-profile-reels">
    `;
    
    if (reelCount > 0) {
      const reelsToShow = profile.reels.slice(0, 50);
      reelsToShow.forEach((reel, idx) => {
        let reelUrl = reel;
        let reelCaption = '';
        if (typeof reel === 'object') {
          reelUrl = reel.url || reel;
          reelCaption = reel.caption || '';
        }
        
        html += `
          <div class="scraped-reel-item">
            <span class="scraped-reel-index">#${idx + 1}</span>
            <span class="scraped-reel-url"><a href="${escapeHtml(reelUrl)}" target="_blank">${escapeHtml(reelUrl)}</a></span>
            ${reelCaption ? `<span class="scraped-reel-caption">📝 ${escapeHtml(reelCaption.substring(0, 60))}${reelCaption.length > 60 ? '...' : ''}</span>` : ''}
            <div class="scraped-reel-actions">
              <button class="btn btn-sm btn-success btn-icon copy-reel-btn" data-url="${escapeHtml(reelUrl)}">📋</button>
              <button class="btn btn-sm btn-primary btn-icon download-reel-btn" data-url="${escapeHtml(reelUrl)}">⬇</button>
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
  
  document.querySelectorAll('.copy-reel-btn').forEach(btn => {
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      const url = this.dataset.url;
      copyToClipboard(url, this);
    });
  });
  
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
  
  renderScrapedResults(null, null, true);
  
  try {
    const response = await fetch('/api/scraped/latest', { credentials: 'same-origin' });
    const data = await response.json();
    console.log('📊 Scraped data:', data);
    
    if (response.ok && data.results && data.results.length > 0) {
      window.scrapedData = data.results;
      window.allUsernames = data.usernames || [];
      renderScrapedResults(data.results);
      
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
    renderScrapedResults([]);
  } finally {
    btn.textContent = '📊 Load Results';
    btn.disabled = false;
  }
}

fetchScrapedBtn.addEventListener('click', fetchScrapedResults);

// ==================== EXPORT SCRAPED RESULTS ====================

document.getElementById('export-scraped-btn')?.addEventListener('click', function() {
  const results = window.scrapedData || [];
  if (results.length === 0) {
    showScrapedStatus('No data to export', 'error');
    return;
  }
  
  const dataStr = JSON.stringify(results, null, 2);
  const blob = new Blob([dataStr], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `scraped_reels_${new Date().toISOString().slice(0,10)}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showScrapedStatus('✅ Exported successfully!', 'success');
});

clearScrapedBtn.addEventListener('click', function() {
  document.getElementById('scraped-reels-content').innerHTML = `<div class="empty-state">No scraped data. Start a scrape job below or load existing results.</div>`;
  document.getElementById('scraped-stats').hidden = true;
  document.getElementById('export-scraped-btn').hidden = true;
  document.getElementById('scraped-count-badge').textContent = '0 profiles';
  window.scrapedData = [];
  this.hidden = true;
  showScrapedStatus('✅ Cleared scraped results', 'success');
  localStorage.removeItem('last_scrape_job_id');
});

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
  showZernioSection();
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

// ==================== PIPELINE FUNCTIONS ====================

function showPipelinesStatus(message, type) {
  if (!pipelinesStatus) return;
  pipelinesStatus.textContent = message;
  pipelinesStatus.className = 'status-message ' + type;
  pipelinesStatus.style.display = 'block';
  setTimeout(() => {
    pipelinesStatus.style.display = 'none';
  }, 8000);
}

async function loadPipelines() {
  try {
    const response = await fetch('/api/pipelines', { 
      credentials: 'same-origin' 
    });
    const data = await response.json();
    
    if (data.status === 'success') {
      renderPipelines(data.pipelines);
    } else {
      console.error('Failed to load pipelines:', data.error);
    }
  } catch (error) {
    console.error('Failed to load pipelines:', error);
  }
}

function renderPipelines(pipelines) {
  if (!pipelinesList) return;
  
  if (!pipelines || pipelines.length === 0) {
    pipelinesList.innerHTML = `<div class="empty-state">No pipelines created yet.</div>`;
    return;
  }
  
  let html = `<div class="pipelines-grid">`;
  
  pipelines.forEach(p => {
    const statusClass = p.is_active ? 'active' : 'inactive';
    const statusText = p.is_active ? '🟢 Active' : '🔴 Inactive';
    
    html += `
      <div class="pipeline-card">
        <div class="pipeline-card-header">
          <div class="pipeline-card-title">
            <span class="pipeline-name">${escapeHtml(p.name)}</span>
            <span class="pipeline-status ${statusClass}">${statusText}</span>
          </div>
          <div class="pipeline-card-actions">
            <button class="btn btn-sm btn-ghost edit-pipeline-btn" data-id="${p.id}" title="Edit Pipeline">
              ✏️
            </button>
            <button class="btn btn-sm btn-danger delete-pipeline-btn" data-id="${p.id}" data-name="${escapeHtml(p.name)}" title="Delete Pipeline">
              🗑️
            </button>
            <button class="btn btn-sm btn-success run-pipeline-btn" data-id="${p.id}">▶ Run</button>
            <button class="btn btn-sm btn-danger reset-pipeline-btn" data-id="${p.id}">↺ Reset</button>
            <button class="btn btn-sm btn-ghost toggle-pipeline-btn" data-id="${p.id}" data-active="${p.is_active}">
              ${p.is_active ? '⏸' : '▶'}
            </button>
          </div>
        </div>
        <div class="pipeline-card-body">
          <div class="pipeline-detail">
            <span class="pipeline-label">Profile:</span>
            <span class="pipeline-value">@${escapeHtml(p.profile_username)}</span>
          </div>
          <div class="pipeline-detail">
            <span class="pipeline-label">Facebook:</span>
            <span class="pipeline-value">${escapeHtml(p.facebook_page_name || p.facebook_account_id)}</span>
          </div>
          <div class="pipeline-detail">
            <span class="pipeline-label">Daily Limit:</span>
            <span class="pipeline-value">${p.daily_limit}</span>
          </div>
          <div class="pipeline-detail">
            <span class="pipeline-label">Total Posted:</span>
            <span class="pipeline-value">${p.total_posted || 0}</span>
          </div>
          <div class="pipeline-detail">
            <span class="pipeline-label">Last Run:</span>
            <span class="pipeline-value">${p.last_run ? new Date(p.last_run).toLocaleString() : 'Never'}</span>
          </div>
          ${p.last_post_time ? `
          <div class="pipeline-detail">
            <span class="pipeline-label">Last Post:</span>
            <span class="pipeline-value">${new Date(p.last_post_time).toLocaleString()}</span>
          </div>` : ''}
          <div class="pipeline-stats">
            <span class="stat-success">✅ ${p.success_count || 0}</span>
            <span class="stat-failed">❌ ${p.failed_count || 0}</span>
          </div>
        </div>
      </div>
    `;
  });
  
  html += `</div>`;
  pipelinesList.innerHTML = html;
  
  // Add event listeners
  document.querySelectorAll('.run-pipeline-btn').forEach(btn => {
    btn.addEventListener('click', () => runPipeline(btn.dataset.id));
  });
  
  document.querySelectorAll('.reset-pipeline-btn').forEach(btn => {
    btn.addEventListener('click', () => resetPipeline(btn.dataset.id));
  });
  
  document.querySelectorAll('.toggle-pipeline-btn').forEach(btn => {
    btn.addEventListener('click', () => togglePipeline(btn.dataset.id, btn.dataset.active === 'true'));
  });
  
  document.querySelectorAll('.edit-pipeline-btn').forEach(btn => {
    btn.addEventListener('click', () => editPipeline(btn.dataset.id));
  });
  
  document.querySelectorAll('.delete-pipeline-btn').forEach(btn => {
    btn.addEventListener('click', () => deletePipeline(btn.dataset.id, btn.dataset.name));
  });
}

// ==================== DELETE PIPELINE ====================

async function deletePipeline(pipelineId, pipelineName) {
  if (!confirm(`⚠️ Are you sure you want to delete the pipeline "${pipelineName}"?\n\nThis will also delete:\n• All posted reels history for this pipeline\n• All pipeline run logs\n\nThis action cannot be undone!`)) {
    return;
  }
  
  showPipelinesStatus(`🗑️ Deleting pipeline "${pipelineName}"...`, 'info');
  
  try {
    const response = await fetch(`/api/pipelines/${pipelineId}`, {
      method: 'DELETE',
      credentials: 'same-origin'
    });
    
    const data = await response.json();
    
    if (response.ok && data.status === 'success') {
      showPipelinesStatus(
        `✅ ${data.message} (${data.deleted.posted_reels_deleted} posted reels, ${data.deleted.runs_deleted} run logs removed)`,
        'success'
      );
      setTimeout(loadPipelines, 1000);
    } else {
      showPipelinesStatus(`❌ Failed to delete pipeline: ${data.error || 'Unknown error'}`, 'error');
    }
  } catch (error) {
    console.error('Delete pipeline error:', error);
    showPipelinesStatus(`❌ Error: ${error.message}`, 'error');
  }
}

// ==================== EDIT PIPELINE FUNCTIONS ====================

async function editPipeline(pipelineId) {
  const modal = document.getElementById('edit-pipeline-modal');
  const status = document.getElementById('edit-pipeline-status');
  
  modal.hidden = false;
  status.style.display = 'none';
  status.className = 'status-message';
  
  try {
    const response = await fetch(`/api/pipelines/${pipelineId}`, {
      credentials: 'same-origin'
    });
    const data = await response.json();
    
    if (data.status === 'success' && data.pipeline) {
      const pipeline = data.pipeline;
      
      document.getElementById('edit-pipeline-id').value = pipeline.id;
      document.getElementById('edit-pipeline-name').value = pipeline.name || '';
      document.getElementById('edit-pipeline-username').value = pipeline.profile_username || '';
      document.getElementById('edit-pipeline-daily-limit').value = pipeline.daily_limit || 2;
      document.getElementById('edit-pipeline-active').checked = pipeline.is_active;
      
      await populateEditFacebookAccounts(pipeline.facebook_account_id);
    } else {
      showEditPipelineStatus('❌ Failed to load pipeline data', 'error');
    }
  } catch (error) {
    console.error('Error loading pipeline:', error);
    showEditPipelineStatus(`❌ Error: ${error.message}`, 'error');
  }
}

async function populateEditFacebookAccounts(selectedId) {
  const select = document.getElementById('edit-pipeline-facebook-account');
  
  try {
    const response = await fetch('/api/zernio/accounts', {
      credentials: 'same-origin'
    });
    const data = await response.json();
    
    select.innerHTML = '';
    
    if (data.status === 'success' && data.accounts && data.accounts.length > 0) {
      data.accounts.forEach(account => {
        const option = document.createElement('option');
        option.value = account.id;
        option.textContent = account.name;
        if (account.id === selectedId) {
          option.selected = true;
        }
        select.appendChild(option);
      });
    } else {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = 'No Facebook accounts found';
      option.disabled = true;
      select.appendChild(option);
    }
  } catch (error) {
    console.error('Error loading Facebook accounts:', error);
    const option = document.createElement('option');
    option.value = '';
    option.textContent = 'Error loading accounts';
    option.disabled = true;
    select.appendChild(option);
  }
}

function showEditPipelineStatus(message, type) {
  const status = document.getElementById('edit-pipeline-status');
  status.textContent = message;
  status.className = 'status-message ' + type;
  status.style.display = 'block';
}

document.getElementById('save-pipeline-edit-btn')?.addEventListener('click', async function() {
  const pipelineId = document.getElementById('edit-pipeline-id').value;
  const name = document.getElementById('edit-pipeline-name').value.trim();
  const username = document.getElementById('edit-pipeline-username').value.trim();
  const accountId = document.getElementById('edit-pipeline-facebook-account').value;
  const dailyLimit = parseInt(document.getElementById('edit-pipeline-daily-limit').value) || 2;
  const isActive = document.getElementById('edit-pipeline-active').checked;
  
  if (!name || !username || !accountId) {
    showEditPipelineStatus('❌ Please fill in all fields', 'error');
    return;
  }
  
  this.disabled = true;
  this.textContent = 'Saving...';
  
  try {
    const response = await fetch(`/api/pipelines/${pipelineId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({
        name,
        profile_username: username,
        facebook_account_id: accountId,
        daily_limit: dailyLimit,
        is_active: isActive
      })
    });
    
    const data = await response.json();
    
    if (response.ok) {
      showEditPipelineStatus(`✅ Pipeline "${name}" updated successfully!`, 'success');
      setTimeout(() => {
        document.getElementById('edit-pipeline-modal').hidden = true;
        loadPipelines();
      }, 1500);
    } else {
      showEditPipelineStatus(`❌ ${data.error || 'Failed to update pipeline'}`, 'error');
    }
  } catch (error) {
    showEditPipelineStatus(`❌ Error: ${error.message}`, 'error');
  } finally {
    this.disabled = false;
    this.textContent = 'Save Changes';
  }
});

document.getElementById('edit-pipeline-modal-close')?.addEventListener('click', function() {
  document.getElementById('edit-pipeline-modal').hidden = true;
});

document.getElementById('edit-pipeline-modal')?.addEventListener('click', function(e) {
  if (e.target === this) {
    this.hidden = true;
  }
});

async function runPipeline(pipelineId) {
  showPipelinesStatus('⏳ Running pipeline...', 'info');
  
  try {
    const response = await fetch(`/api/pipelines/${pipelineId}/run`, {
      method: 'POST',
      credentials: 'same-origin'
    });
    const data = await response.json();
    
    if (response.ok) {
      showPipelinesStatus(`✅ ${data.message}`, 'success');
    } else {
      showPipelinesStatus(`❌ ${data.error || 'Failed to run pipeline'}`, 'error');
    }
  } catch (error) {
    showPipelinesStatus(`❌ Error: ${error.message}`, 'error');
  } finally {
    setTimeout(loadPipelines, 2000);
  }
}

async function runAllPipelines() {
  showPipelinesStatus('⏳ Running all pipelines...', 'info');
  
  try {
    const response = await fetch('/api/pipelines/run-all', {
      method: 'POST',
      credentials: 'same-origin'
    });
    const data = await response.json();
    
    if (response.ok) {
      showPipelinesStatus(`✅ ${data.message}`, 'success');
    } else {
      showPipelinesStatus(`❌ ${data.error || 'Failed to run pipelines'}`, 'error');
    }
  } catch (error) {
    showPipelinesStatus(`❌ Error: ${error.message}`, 'error');
  } finally {
    setTimeout(loadPipelines, 2000);
  }
}

async function resetPipeline(pipelineId) {
  if (!confirm('⚠️ Reset will mark ALL reels as unposted. Are you sure?')) return;
  
  try {
    const response = await fetch(`/api/pipelines/${pipelineId}/reset`, {
      method: 'POST',
      credentials: 'same-origin'
    });
    const data = await response.json();
    
    if (response.ok) {
      showPipelinesStatus(`✅ ${data.message}`, 'success');
    } else {
      showPipelinesStatus(`❌ ${data.error || 'Failed to reset'}`, 'error');
    }
  } catch (error) {
    showPipelinesStatus(`❌ Error: ${error.message}`, 'error');
  } finally {
    setTimeout(loadPipelines, 1500);
  }
}

async function togglePipeline(pipelineId, currentActive) {
  try {
    const response = await fetch(`/api/pipelines/${pipelineId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ is_active: !currentActive })
    });
    const data = await response.json();
    
    if (response.ok) {
      showPipelinesStatus(`✅ Pipeline ${!currentActive ? 'activated' : 'deactivated'}`, 'success');
    } else {
      showPipelinesStatus(`❌ ${data.error || 'Failed to toggle'}`, 'error');
    }
  } catch (error) {
    showPipelinesStatus(`❌ Error: ${error.message}`, 'error');
  } finally {
    setTimeout(loadPipelines, 1000);
  }
}

// ==================== CREATE PIPELINE ====================

createPipelineBtn?.addEventListener('click', async function() {
  const name = pipelineName?.value.trim();
  const username = pipelineUsername?.value.trim();
  const accountId = pipelineFacebookAccount?.value;
  const dailyLimit = parseInt(pipelineDailyLimit?.value) || 2;
  
  if (!name || !username || !accountId) {
    showPipelinesStatus('❌ Please fill in all fields', 'error');
    return;
  }
  
  this.disabled = true;
  this.textContent = 'Creating...';
  
  try {
    const response = await fetch('/api/pipelines', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({
        name,
        profile_username: username,
        facebook_account_id: accountId,
        daily_limit: dailyLimit
      })
    });
    const data = await response.json();
    
    if (response.ok) {
      showPipelinesStatus(`✅ Pipeline "${name}" created!`, 'success');
      if (pipelineName) pipelineName.value = '';
      if (pipelineUsername) pipelineUsername.value = '';
      if (pipelineDailyLimit) pipelineDailyLimit.value = '2';
      loadPipelines();
    } else {
      showPipelinesStatus(`❌ ${data.error || 'Failed to create pipeline'}`, 'error');
    }
  } catch (error) {
    showPipelinesStatus(`❌ Error: ${error.message}`, 'error');
  } finally {
    this.disabled = false;
    this.textContent = 'Create Pipeline';
  }
});

// ==================== AUTO-LOAD ON PAGE LOAD ====================

async function autoLoadScrapedResults() {
  renderScrapedResults(null, null, true);
  
  try {
    const response = await fetch('/api/scraped/latest', { credentials: 'same-origin' });
    const data = await response.json();
    console.log('📊 Auto-loading scraped data:', data);
    
    if (response.ok && data.results && data.results.length > 0) {
      window.scrapedData = data.results;
      window.allUsernames = data.usernames || [];
      renderScrapedResults(data.results);
      
      const usernameList = data.usernames ? data.usernames.join(', ') : '';
      showScrapedStatus(
        `✅ Auto-loaded ${data.results.length} profiles: ${usernameList}`,
        'success'
      );
    } else {
      renderScrapedResults([]);
    }
  } catch (error) {
    console.error('❌ Auto-load failed:', error);
    renderScrapedResults([]);
  }
}

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

// ==================== INIT WITH AUTO-LOAD ====================

initSession().then(() => {
    checkInstagramStatus();
    checkBlueskyStatus();
    checkZernioStatus();
    loadZernioAccounts();
    loadPipelines();
    setTimeout(autoLoadScrapedResults, 1000);
});

document.addEventListener('visibilitychange', function() {
  if (!document.hidden) {
    autoLoadScrapedResults();
  }
});

// ==================== PIPELINE EVENT LISTENERS ====================

runAllPipelinesBtn?.addEventListener('click', runAllPipelines);
refreshPipelinesBtn?.addEventListener('click', loadPipelines);

// ==================== REFRESH STATUS BUTTON ====================

document.getElementById('refresh-status-btn')?.addEventListener('click', function() {
  checkInstagramStatus();
  checkBlueskyStatus();
  checkZernioStatus();
  loadZernioAccounts();
  loadPipelines();
  autoLoadScrapedResults();
  showCookieStatus('🔄 Status refreshed', 'info');
});

console.log('✅ Fetchgram loaded successfully!');