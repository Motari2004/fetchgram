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

// Pending Posts elements
const pendingPostsContainer = document.getElementById('pending-posts-container');
const pendingCount = document.getElementById('pending-count');
const processingCount = document.getElementById('processing-count');
const failedCount = document.getElementById('failed-count');

// Scheduled Jobs elements
const scheduledJobsContainer = document.getElementById('scheduled-jobs-container');
const toggleScheduledJobsBtn = document.getElementById('toggle-scheduled-jobs-btn');
const closeScheduledBtn = document.getElementById('close-scheduled-btn');
const refreshScheduledBtn = document.getElementById('refresh-scheduled-btn');
const scheduledPostsList = document.getElementById('scheduled-posts-list');
const scheduledCountBadge = document.getElementById('scheduled-count-badge');
const scheduledFilterStatus = document.getElementById('scheduled-filter-status');
const scheduledFilterPipeline = document.getElementById('scheduled-filter-pipeline');

let currentVideoUrl = null;
let currentVideoItem = null;
let scheduledPosts = [];
let scheduledPollingInterval = null;

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
syncExecuteBtn?.addEventListener('click', async function() {
  const username = syncUsernameSelect?.value;
  
  if (!username) {
    showSyncStatus('❌ Please select a profile', 'error');
    return;
  }
  
  if (!confirm(`🔄 Fetch captions for all reels of @${username}?\n\nThis may take a few moments depending on the number of reels.`)) {
    return;
  }
  
  this.disabled = true;
  this.innerHTML = '<span class="btn-spinner"></span> Syncing...';
  
  if (syncProgress) syncProgress.style.display = 'block';
  if (syncProgressBar) syncProgressBar.style.width = '10%';
  if (syncProgressText) syncProgressText.textContent = 'Starting...';
  
  showSyncStatus(`⏳ Fetching captions for @${username}...`, 'info');
  
  try {
    const response = await fetch('/api/sync-captions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ username })
    });
    
    const data = await response.json();
    
    if (syncProgressBar) syncProgressBar.style.width = '100%';
    if (syncProgressText) syncProgressText.textContent = 'Complete!';
    
    if (response.ok && (data.status === 'accepted' || data.status === 'success')) {
      showSyncStatus(
        `✅ Sync started for @${username}! Check the profile card for progress.`,
        'success'
      );
      
      // Start monitoring sync status immediately
      checkAndShowSyncStatus(username);
      
      // Refresh after a moment to show captions
      setTimeout(() => {
        autoLoadScrapedResults();
      }, 3000);
      
    } else {
      showSyncStatus(`❌ ${data.error || 'Failed to sync captions'}`, 'error');
      if (syncProgressBar) syncProgressBar.style.width = '0%';
      if (syncProgressText) syncProgressText.textContent = 'Failed';
    }
    
  } catch (error) {
    console.error('❌ Sync error:', error);
    showSyncStatus(`❌ Error: ${error.message}`, 'error');
    if (syncProgressBar) syncProgressBar.style.width = '0%';
    if (syncProgressText) syncProgressText.textContent = 'Failed';
  } finally {
    this.disabled = false;
    this.innerHTML = '<span class="btn-content">🔄 Sync Captions</span>';
    
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

let zernioAccountsLoadAttempts = 0;
const MAX_LOAD_ATTEMPTS = 3;

async function loadZernioAccounts() {
    zernioAccountsLoadAttempts = 0;
    return _loadZernioAccountsWithRetry();
}

async function _loadZernioAccountsWithRetry() {
    try {
        console.log(`📊 Loading Zernio accounts (attempt ${zernioAccountsLoadAttempts + 1})...`);
        
        // ✅ FIX: Fetch from /api/zernio/keys to get ALL accounts from ALL keys
        const response = await fetch('/api/zernio/keys', {
            credentials: 'same-origin',
            headers: { 'Cache-Control': 'no-cache' }
        });
        
        const data = await response.json();
        console.log('📊 Zernio keys response:', data);
        
        if (data.status === 'success' && data.keys && data.keys.length > 0) {
            // ✅ Combine accounts from ALL keys with key_id
            const allAccounts = [];
            
            data.keys.forEach(key => {
                if (key.accounts && key.accounts.length > 0) {
                    key.accounts.forEach(account => {
                        allAccounts.push({
                            id: account.id,
                            name: account.name,
                            page_id: account.page_id,
                            status: account.status,
                            key_id: key.id,        // ✅ Store the key ID
                            key_name: key.name     // ✅ Track which key it belongs to
                        });
                    });
                }
            });
            
            zernioAccounts = allAccounts;
            zernioAccountsLoaded = true;
            
            console.log(`✅ Loaded ${zernioAccounts.length} accounts from ${data.keys.length} keys`);
            console.log('📋 Accounts:', zernioAccounts.map(a => `${a.name} (${a.key_name})`));
            
            // ✅ Populate ALL dropdowns with combined accounts
            populateZernioAccountSelect(zernioAccounts);
            populatePipelineFacebookAccounts(zernioAccounts);
            populateEditFacebookAccounts();
            
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
            
            return true;
        } else {
            console.warn('⚠️ No keys or accounts found:', data.message || data);
            
            zernioAccounts = [];
            populateZernioAccountSelect([]);
            populatePipelineFacebookAccounts([]);
            populateEditFacebookAccounts();
            zernioAccountsLoaded = true;
            
            if (zernioStatusBadge) {
                zernioStatusBadge.textContent = '⚠️ No accounts';
                zernioStatusBadge.style.background = 'var(--warning-bg)';
                zernioStatusBadge.style.color = 'var(--warning)';
            }
            
            return false;
        }
    } catch (error) {
        console.error('❌ Failed to load Zernio accounts:', error);
        
        // Retry if under max attempts
        if (zernioAccountsLoadAttempts < MAX_LOAD_ATTEMPTS) {
            zernioAccountsLoadAttempts++;
            console.log(`⏳ Retrying in 1 second... (${zernioAccountsLoadAttempts}/${MAX_LOAD_ATTEMPTS})`);
            await new Promise(resolve => setTimeout(resolve, 1000));
            return _loadZernioAccountsWithRetry();
        }
        
        // Final fallback
        zernioAccounts = [];
        populateZernioAccountSelect([]);
        populatePipelineFacebookAccounts([]);
        populateEditFacebookAccounts();
        zernioAccountsLoaded = true;
        
        if (zernioStatusBadge) {
            zernioStatusBadge.textContent = '❌ Connection error';
            zernioStatusBadge.style.background = 'var(--error-bg)';
            zernioStatusBadge.style.color = 'var(--error)';
        }
        
        return false;
    }
}

function populateZernioAccountSelect(accounts) {
    if (!zernioAccountSelect) return;
    
    zernioAccountSelect.innerHTML = '';
    
    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = 'Select Facebook account...';
    defaultOption.disabled = true;
    defaultOption.selected = true;
    zernioAccountSelect.appendChild(defaultOption);
    
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
    
    // ✅ Group by key
    const grouped = {};
    accounts.forEach(account => {
        const keyName = account.key_name || 'Unknown Key';
        if (!grouped[keyName]) grouped[keyName] = [];
        grouped[keyName].push(account);
    });
    
    Object.keys(grouped).forEach(keyName => {
        const optgroup = document.createElement('optgroup');
        optgroup.label = `🔑 ${keyName}`;
        
        grouped[keyName].forEach(account => {
            const option = document.createElement('option');
            option.value = account.id;
            option.textContent = account.name;
            option.dataset.pageId = account.page_id;
            option.dataset.status = account.status;
            option.dataset.keyId = account.key_id || '';
            option.dataset.keyName = account.key_name || '';
            optgroup.appendChild(option);
        });
        
        zernioAccountSelect.appendChild(optgroup);
    });
    
    if (accounts.length === 1) {
        zernioAccountSelect.value = accounts[0].id;
    }
}

function populatePipelineFacebookAccounts(accounts) {
    let select = pipelineFacebookAccount;
    if (!select) {
        select = document.getElementById('pipeline-facebook-account');
    }
    
    if (!select) {
        console.warn('⚠️ pipeline-facebook-account element not found!');
        return;
    }
    
    select.innerHTML = '';
    
    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = 'Select Facebook account...';
    defaultOption.disabled = true;
    defaultOption.selected = true;
    select.appendChild(defaultOption);
    
    if (!accounts || accounts.length === 0) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = '❌ No accounts - Add a Zernio key';
        option.disabled = true;
        select.appendChild(option);
        return;
    }
    
    // ✅ Group accounts by key
    const grouped = {};
    accounts.forEach(account => {
        const keyName = account.key_name || 'Unknown Key';
        if (!grouped[keyName]) grouped[keyName] = [];
        grouped[keyName].push(account);
    });
    
    // ✅ Add optgroups with key names
    Object.keys(grouped).forEach(keyName => {
        const optgroup = document.createElement('optgroup');
        optgroup.label = `🔑 ${keyName}`;
        
        grouped[keyName].forEach(account => {
            const option = document.createElement('option');
            option.value = account.id;
            option.textContent = account.name;
            // ✅ Store the key ID as a data attribute
            option.dataset.keyId = account.key_id || '';
            option.dataset.keyName = account.key_name || '';
            optgroup.appendChild(option);
        });
        
        select.appendChild(optgroup);
    });
    
    console.log(`✅ Populated pipeline dropdown with ${accounts.length} accounts`);
}

function populateEditFacebookAccounts(selectedId) {
    const select = document.getElementById('edit-pipeline-facebook-account');
    if (!select) {
        console.warn('⚠️ edit-pipeline-facebook-account not found');
        return;
    }
    
    select.innerHTML = '';
    
    const defaultOption = document.createElement('option');
    defaultOption.value = '';
    defaultOption.textContent = 'Select Facebook account...';
    defaultOption.disabled = true;
    defaultOption.selected = true;
    select.appendChild(defaultOption);
    
    console.log('🔍 zernioAccounts in edit:', zernioAccounts);
    console.log('🔍 selectedId:', selectedId);
    
    // ✅ USE zernioAccounts DIRECTLY (has ALL 4 accounts)
    if (!zernioAccounts || zernioAccounts.length === 0) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = '❌ No accounts - Add a Zernio key';
        option.disabled = true;
        select.appendChild(option);
        return;
    }
    
    // ✅ Group by key
    const grouped = {};
    zernioAccounts.forEach(account => {
        const keyName = account.key_name || 'Unknown Key';
        if (!grouped[keyName]) grouped[keyName] = [];
        grouped[keyName].push(account);
    });
    
    let foundSelected = false;
    
    // ✅ Add optgroups with key names
    Object.keys(grouped).forEach(keyName => {
        const optgroup = document.createElement('optgroup');
        optgroup.label = `🔑 ${keyName}`;
        
        grouped[keyName].forEach(account => {
            const option = document.createElement('option');
            option.value = account.id;
            option.textContent = account.name || account.id;
            option.dataset.keyId = account.key_id || '';
            option.dataset.keyName = account.key_name || '';
            
            if (account.id === selectedId) {
                option.selected = true;
                foundSelected = true;
                console.log(`✅ Found selected account: ${account.name} (${account.id}) in key: ${keyName}`);
            }
            optgroup.appendChild(option);
        });
        
        select.appendChild(optgroup);
    });
    
    // If the selected account wasn't found, try to find it
    if (selectedId && !foundSelected) {
        const account = zernioAccounts.find(a => a.id === selectedId);
        if (account) {
            const option = document.createElement('option');
            option.value = account.id;
            option.textContent = `${account.name} (${account.key_name})`;
            option.dataset.keyId = account.key_id || '';
            option.dataset.keyName = account.key_name || '';
            option.selected = true;
            select.appendChild(option);
            console.log(`✅ Added selected account: ${account.name}`);
        } else {
            const option = document.createElement('option');
            option.value = selectedId;
            option.textContent = `⚠️ ${selectedId}`;
            option.disabled = true;
            option.selected = true;
            select.appendChild(option);
            console.warn(`⚠️ Account ${selectedId} not found in zernioAccounts`);
        }
    }
    
    console.log(`✅ Populated edit dropdown with ${zernioAccounts.length} accounts, found: ${foundSelected}`);
}

// ==================== FORCE REFRESH ACCOUNTS ====================

async function forceRefreshAccounts() {
    console.log('🔄 Force refreshing accounts...');
    
    if (zernioStatusBadge) {
        zernioStatusBadge.textContent = '⏳ Loading...';
        zernioStatusBadge.style.background = 'rgba(108, 99, 255, 0.15)';
        zernioStatusBadge.style.color = 'var(--accent)';
    }
    
    await loadZernioKeys();
    const success = await loadZernioAccounts();
    await loadPipelines();
    
    // Force populate one more time
    setTimeout(() => {
        populatePipelineFacebookAccounts(zernioAccounts);
        populateEditFacebookAccounts();
    }, 500);
    
    if (success) {
        showToast('✅ Accounts refreshed successfully', 'success');
    } else {
        showToast('⚠️ No accounts found. Check your Zernio key.', 'warning');
    }
    
    return success;
}













// ==================== DEBUG ACCOUNTS ====================

function debugAccounts() {
    console.log('🔍 Debugging accounts...');
    console.log('zernioAccounts:', zernioAccounts);
    console.log('zernioAccountsLoaded:', zernioAccountsLoaded);
    console.log('zernioKeys:', zernioKeys);
    
    const select = document.getElementById('pipeline-facebook-account');
    console.log('📋 Pipeline dropdown element:', select);
    if (select) {
        console.log('📋 Current options:', select.innerHTML);
    } else {
        console.log('❌ Pipeline dropdown NOT found in DOM');
    }
}

// Add to window for debugging
window.forceRefreshAccounts = forceRefreshAccounts;
window.debugAccounts = debugAccounts;








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
  
  // ✅ FIX: Remove the frontend cookie check - let backend handle auto-extraction
  
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
      
      // ✅ Handle cookie errors with extract button
      if (data.requires_cookies) {
        const statusEl = document.getElementById('scrape-job-status');
        if (statusEl) {
          statusEl.innerHTML = `
            <div style="padding: 12px; background: #f8d7da; border-radius: 8px; border-left: 3px solid #dc3545; margin-top: 10px;">
              <strong>⚠️ ${data.error || 'No Instagram cookies found.'}</strong>
              <div style="margin-top: 10px; display: flex; gap: 10px; flex-wrap: wrap;">
                <button id="scrape-extract-btn" class="btn btn-primary btn-sm">
                  🍪 Extract Cookies from Browserless
                </button>
                <button id="scrape-retry-btn" class="btn btn-success btn-sm">
                  🔄 Retry Scrape
                </button>
              </div>
            </div>
          `;
          statusEl.hidden = false;
          
          document.getElementById('scrape-extract-btn')?.addEventListener('click', async function() {
            this.disabled = true;
            this.textContent = '⏳ Extracting...';
            const success = await extractCookiesFromBrowserless();
            this.disabled = false;
            this.textContent = '🍪 Extract Cookies from Browserless';
            if (success) {
              document.getElementById('scrape-retry-btn')?.click();
            }
          });
          
          document.getElementById('scrape-retry-btn')?.addEventListener('click', function() {
            startScrapeBtn.click();
          });
        }
      } else {
        showScrapeStatus(`❌ ${data.error || 'Failed to start job'}`, 'error');
      }
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
  showTikTokSection();
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

// ==================== FORM SUBMISSION WITH AUTO-COOKIE EXTRACTION ====================

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

    // ========== CHECK IF IT'S A PRIVATE/LOGIN ERROR ==========
    if (!res.ok) {
      // Check if cookies were refreshed automatically
      if (data.cookies_refreshed) {
        showError(`⚠️ ${data.error || 'Still can\'t download after refreshing cookies. Please try again or upload fresh cookies.'}`);
        // Show extract button in error
        const errorContainer = document.getElementById('error-msg');
        if (errorContainer) {
          errorContainer.innerHTML = `
            <div style="padding: 12px; background: #f8d7da; border-radius: 8px; border-left: 3px solid #dc3545;">
              <strong>⚠️ ${data.error || 'Still can\'t download after refreshing cookies.'}</strong>
              <div style="margin-top: 10px; display: flex; gap: 10px; flex-wrap: wrap;">
                <button id="extract-manual-btn" class="btn btn-primary btn-sm">
                  🍪 Extract Cookies Manually
                </button>
                <button id="retry-btn" class="btn btn-success btn-sm">
                  🔄 Retry
                </button>
              </div>
            </div>
          `;
          errorContainer.hidden = false;
          
          document.getElementById('extract-manual-btn')?.addEventListener('click', async function() {
            this.disabled = true;
            this.textContent = '⏳ Extracting...';
            await extractCookiesFromBrowserless();
            this.disabled = false;
            this.textContent = '🍪 Extract Cookies Manually';
            // Retry after extraction
            document.getElementById('retry-btn')?.click();
          });
          
          document.getElementById('retry-btn')?.addEventListener('click', function() {
            form.dispatchEvent(new Event('submit'));
          });
        }
        setLoading(false);
        return;
      } else if (data.requires_cookies) {
        // Show private error with extract button
        showError(data.error || "This post is private or requires login.");
        handlePrivateError(data.error || "This post is private or requires login.");
        setLoading(false);
        return;
      } else {
        showError(data.error || "Something went wrong. Try again.");
        setLoading(false);
        return;
      }
    }

    // ========== SUCCESS ==========
    if (data.download_url) {
      const item = data.video_info || { title: "Instagram video" };
      renderResults([item], data.url);
      setTimeout(() => {
        showDirectUrl(data.download_url, item);
      }, 100);
      
      // Show message if cookies were refreshed
      if (data.cookies_refreshed && data.message) {
        showCookieStatus(`✅ ${data.message}`, 'success');
      }
    } else if (data.items) {
      renderResults(data.items, data.source_url);
    } else {
      showError("No video found at that link.");
    }
  } catch (err) {
    // Fallback to /api/fetch
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
    
    // Get counts with defaults
    const posted = p.success_count || 0;
    const failed = p.failed_count || 0;
    const pending = p.pending_posts || 0;
    const processing = p.processing_posts || 0;
    
    // Only show if > 0
    const showPending = pending > 0;
    const showProcessing = processing > 0;
    const showFailed = failed > 0;
    
    html += `
      <div class="pipeline-card">
        <div class="pipeline-card-header">
          <div class="pipeline-card-title">
            <span class="pipeline-name">${escapeHtml(p.name)}</span>
            <span class="pipeline-status ${statusClass}">${statusText}</span>
            ${showProcessing ? `<span class="badge-processing"><span class="dot"></span> ${processing} processing</span>` : ''}
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
          ${p.last_run ? `
          <div class="pipeline-detail">
            <span class="pipeline-label">Last Run:</span>
            <span class="pipeline-value">${new Date(p.last_run).toLocaleString()}</span>
          </div>` : ''}
          ${p.last_post_time ? `
          <div class="pipeline-detail">
            <span class="pipeline-label">Last Post:</span>
            <span class="pipeline-value">${new Date(p.last_post_time).toLocaleString()}</span>
          </div>` : ''}
          
          <!-- STATUS SUMMARY BADGES -->
          <div class="pipeline-status-summary">
            <span class="status-badge-summary posted">
              ✅ <span class="count">${posted}</span> Posted
            </span>
            ${showProcessing ? `
            <span class="status-badge-summary processing">
              🟡 <span class="count">${processing}</span> Processing
            </span>` : ''}
            ${showPending ? `
            <span class="status-badge-summary pending">
              ⏳ <span class="count">${pending}</span> Pending
            </span>` : ''}
            ${showFailed ? `
            <span class="status-badge-summary failed">
              ❌ <span class="count">${failed}</span> Failed
            </span>` : ''}
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
            
            // ✅ Show current account AND key info
            const keyInfoEl = document.getElementById('edit-pipeline-key-info');
            if (keyInfoEl) {
                let accountName = 'Unknown Account';
                let keyName = 'No key';
                
                // Find the account in zernioAccounts
                const account = zernioAccounts.find(a => a.id === pipeline.facebook_account_id);
                if (account) {
                    accountName = account.name || account.id;
                }
                
                if (pipeline.zernio_key_id) {
                    const key = zernioKeys.find(k => k.id === pipeline.zernio_key_id);
                    keyName = key ? key.name : 'Unknown Key';
                    keyInfoEl.textContent = `📱 ${accountName} (🔑 ${keyName})`;
                    keyInfoEl.style.color = 'var(--success)';
                    keyInfoEl.style.borderLeftColor = '#22c55e';
                } else {
                    keyInfoEl.textContent = `⚠️ ${accountName} - No key assigned!`;
                    keyInfoEl.style.color = 'var(--error)';
                    keyInfoEl.style.borderLeftColor = '#ef4444';
                }
                keyInfoEl.hidden = false;
            }
            
            // ✅ Populate accounts and select the current one
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
      // Reload pipelines to update pending count
      setTimeout(loadPipelines, 2000);
    } else {
      showPipelinesStatus(`❌ ${data.error || 'Failed to run pipeline'}`, 'error');
    }
  } catch (error) {
    showPipelinesStatus(`❌ Error: ${error.message}`, 'error');
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
    const accountSelect = pipelineFacebookAccount;
    const accountId = accountSelect?.value;
    const dailyLimit = parseInt(pipelineDailyLimit?.value) || 2;
    
    // ✅ Get the key ID from the selected option
    const selectedOption = accountSelect?.options[accountSelect.selectedIndex];
    const zernioKeyId = selectedOption?.dataset?.keyId || null;
    const keyName = selectedOption?.dataset?.keyName || 'Unknown';
    
    if (!name || !username || !accountId) {
        showPipelinesStatus('❌ Please fill in all fields', 'error');
        return;
    }
    
    if (!zernioKeyId) {
        showPipelinesStatus('⚠️ Please select an account with a valid Zernio key', 'error');
        return;
    }
    
    console.log(`🔑 Creating pipeline with key: ${keyName} (${zernioKeyId})`);
    
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
                daily_limit: dailyLimit,
                zernio_key_id: zernioKeyId  // ✅ Send the key ID!
            })
        });
        const data = await response.json();
        
        if (response.ok) {
            showPipelinesStatus(`✅ Pipeline "${name}" created with ${keyName}!`, 'success');
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
    loadBufferKeys();
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

// ==================== SYNC STATUS MONITORING ====================

// Store intervals for each username
const syncIntervals = {};

async function checkAndShowSyncStatus(username) {
    if (!username) return;
    
    try {
        const response = await fetch(`/api/sync-status/${username}`, {
            credentials: 'same-origin'
        });
        const data = await response.json();
        
        if (data.sync && data.sync.status === 'syncing') {
            // Show syncing indicator
            updateProfileSyncStatus(username, data.sync);
            
            // Poll every 2 seconds until complete
            if (!syncIntervals[username]) {
                syncIntervals[username] = setInterval(() => {
                    checkAndShowSyncStatus(username);
                }, 2000);
            }
        } else if (data.sync && data.sync.status === 'completed') {
            // Clear interval
            if (syncIntervals[username]) {
                clearInterval(syncIntervals[username]);
                delete syncIntervals[username];
            }
            
            // Update indicator to completed with nice styling
            updateProfileSyncStatus(username, data.sync);
            
            // Update captions in place WITHOUT full refresh
            await updateCaptionsInPlace(username);
            
            // Show completion notification
            const total = data.sync.total_reels || 0;
            const fetched = data.sync.captions_fetched || 0;
            if (fetched > 0 && fetched === total) {
                showScrapedStatus(`🎉 All ${fetched} captions synced for @${username}!`, 'success');
            } else if (fetched > 0) {
                showScrapedStatus(`✅ ${fetched}/${total} captions synced for @${username}`, 'success');
            } else {
                showScrapedStatus(`ℹ️ No captions found for @${username}`, 'info');
            }
            
        } else if (data.sync && data.sync.status === 'error') {
            // Show error
            updateProfileSyncStatus(username, data.sync);
            if (syncIntervals[username]) {
                clearInterval(syncIntervals[username]);
                delete syncIntervals[username];
            }
            showScrapedStatus(`❌ Failed to sync captions for @${username}`, 'error');
        }
    } catch (error) {
        console.error('Error checking sync status:', error);
    }
}

// ✅ Update only the captions, not the whole UI
async function updateCaptionsInPlace(username) {
    try {
        // Fetch fresh data for this username only
        const response = await fetch(`/api/scraped/latest`, {
            credentials: 'same-origin'
        });
        const data = await response.json();
        
        if (!data.results || data.results.length === 0) return;
        
        // Find the profile
        const profile = data.results.find(p => p.username === username);
        if (!profile) return;
        
        // Find the profile card in the UI
        const profileCards = document.querySelectorAll('.scraped-profile-card');
        let targetCard = null;
        
        for (const card of profileCards) {
            const nameEl = card.querySelector('.scraped-profile-name');
            if (nameEl && nameEl.textContent.includes(`@${username}`)) {
                targetCard = card;
                break;
            }
        }
        
        if (!targetCard) return;
        
        // Update the reels with captions
        const reelsBody = targetCard.querySelector('.scraped-profile-reels');
        if (!reelsBody) return;
        
        // Rebuild only the reels list with captions
        const reels = profile.reels || [];
        let html = '';
        
        reels.forEach((reel, idx) => {
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
                    ${reelCaption ? `<span class="scraped-reel-caption">📝 ${escapeHtml(reelCaption.substring(0, 60))}${reelCaption.length > 60 ? '...' : ''}</span>` : '<span class="scraped-reel-caption" style="color: var(--text-muted);">⏳ No caption yet. Click "Sync Captions" to fetch.</span>'}
                    <div class="scraped-reel-actions">
                        <button class="btn btn-sm btn-success btn-icon copy-reel-btn" data-url="${escapeHtml(reelUrl)}">📋</button>
                        <button class="btn btn-sm btn-primary btn-icon download-reel-btn" data-url="${escapeHtml(reelUrl)}">⬇</button>
                    </div>
                </div>
            `;
        });
        
        reelsBody.innerHTML = html;
        
        // Update the reel count
        const countSpan = targetCard.querySelector('.scraped-profile-count');
        if (countSpan) {
            countSpan.textContent = `📹 ${reels.length}`;
        }
        
        // Show a small notification without full refresh
        showScrapedStatus(`✅ Captions updated for @${username}`, 'success');
        
    } catch (error) {
        console.error('Error updating captions in place:', error);
    }
}

function updateProfileSyncStatus(username, syncData) {
    // Find the profile card
    const profileCards = document.querySelectorAll('.scraped-profile-card');
    let targetCard = null;
    
    for (const card of profileCards) {
        const nameEl = card.querySelector('.scraped-profile-name');
        if (nameEl && nameEl.textContent.includes(`@${username}`)) {
            targetCard = card;
            break;
        }
    }
    
    if (!targetCard) return;
    
    // Find or create the sync indicator
    let indicator = targetCard.querySelector('.sync-indicator');
    if (!indicator) {
        const header = targetCard.querySelector('.scraped-profile-header');
        if (header) {
            const countSpan = header.querySelector('.scraped-profile-count');
            if (countSpan) {
                indicator = document.createElement('span');
                indicator.className = 'sync-indicator';
                indicator.style.cssText = 'font-size: 11px; margin-left: 8px; padding: 3px 12px; border-radius: 20px; display: inline-block; font-weight: 600; transition: all 0.3s ease; letter-spacing: 0.3px;';
                countSpan.parentNode.insertBefore(indicator, countSpan.nextSibling);
            }
        }
    }
    
    if (!indicator) return;
    
    const status = syncData.status;
    const progress = syncData.progress || 0;
    const total = syncData.total_reels || 0;
    const fetched = syncData.captions_fetched || 0;
    
    // Clear previous classes
    indicator.className = 'sync-indicator';
    
    switch (status) {
        case 'syncing':
            indicator.textContent = `🔄 ${progress}% (${fetched}/${total})`;
            indicator.style.color = '#6c63ff';
            indicator.style.background = 'rgba(108, 99, 255, 0.12)';
            indicator.style.border = '1px solid rgba(108, 99, 255, 0.3)';
            indicator.style.animation = 'syncPulse 1.5s ease-in-out infinite';
            indicator.style.display = 'inline-block';
            indicator.style.boxShadow = '0 0 20px rgba(108, 99, 255, 0.08)';
            indicator.className = 'sync-indicator syncing';
            break;
            
        case 'completed':
            if (fetched > 0 && fetched === total) {
                indicator.textContent = `✅ ${fetched}/${total}`;
                indicator.style.color = '#22c55e';
                indicator.style.background = 'rgba(34, 197, 94, 0.12)';
                indicator.style.border = '1px solid rgba(34, 197, 94, 0.3)';
                indicator.style.animation = 'syncComplete 0.6s ease-in-out';
                indicator.style.display = 'inline-block';
                indicator.style.boxShadow = '0 0 20px rgba(34, 197, 94, 0.12)';
                indicator.className = 'sync-indicator completed';
                
                // Add green border to header
                const header = targetCard.querySelector('.scraped-profile-header');
                if (header) {
                    header.style.borderLeft = '3px solid #22c55e';
                    header.style.transition = 'border-left 0.3s ease';
                }
            } else if (fetched > 0 && fetched < total) {
                indicator.textContent = `⚠️ ${fetched}/${total}`;
                indicator.style.color = '#f59e0b';
                indicator.style.background = 'rgba(245, 158, 11, 0.12)';
                indicator.style.border = '1px solid rgba(245, 158, 11, 0.3)';
                indicator.style.animation = 'none';
                indicator.style.display = 'inline-block';
                indicator.style.boxShadow = '0 0 20px rgba(245, 158, 11, 0.08)';
                indicator.className = 'sync-indicator partial';
            } else {
                indicator.textContent = `ℹ️ No captions`;
                indicator.style.color = '#9ca3af';
                indicator.style.background = 'rgba(156, 163, 175, 0.08)';
                indicator.style.border = '1px solid rgba(156, 163, 175, 0.15)';
                indicator.style.animation = 'none';
                indicator.style.display = 'inline-block';
                indicator.className = 'sync-indicator idle';
            }
            break;
            
        case 'error':
            indicator.textContent = `❌ Failed`;
            indicator.style.color = '#ef4444';
            indicator.style.background = 'rgba(239, 68, 68, 0.12)';
            indicator.style.border = '1px solid rgba(239, 68, 68, 0.3)';
            indicator.style.animation = 'none';
            indicator.style.display = 'inline-block';
            indicator.style.boxShadow = '0 0 20px rgba(239, 68, 68, 0.08)';
            indicator.className = 'sync-indicator error';
            break;
            
        default:
            indicator.textContent = '';
            indicator.style.display = 'none';
            indicator.className = 'sync-indicator';
            break;
    }
}

// Auto-start sync monitoring when results are loaded
function startSyncMonitoringForAllProfiles(results) {
    if (!results || results.length === 0) return;
    
    const usernames = results.map(p => p.username);
    for (const username of usernames) {
        checkAndShowSyncStatus(username);
    }
}

// Override the renderScrapedResults to start monitoring
const originalRenderScrapedResults = renderScrapedResults;
renderScrapedResults = function(results, stats, isLoading = false) {
    // Call the original function
    originalRenderScrapedResults(results, stats, isLoading);
    
    // Start sync monitoring
    if (results && results.length > 0 && !isLoading) {
        startSyncMonitoringForAllProfiles(results);
    }
};

// ==================== SCHEDULED JOBS FUNCTIONS ====================

// Toggle scheduled jobs visibility
toggleScheduledJobsBtn?.addEventListener('click', function() {
    if (scheduledJobsContainer) {
        const isHidden = scheduledJobsContainer.style.display === 'none' || scheduledJobsContainer.style.display === '';
        scheduledJobsContainer.style.display = isHidden ? 'block' : 'none';
        this.textContent = isHidden ? '📅 Hide Scheduled Jobs' : '📅 View Scheduled Jobs';
        
        if (isHidden) {
            loadScheduledPosts();
            startScheduledPolling();
        } else {
            stopScheduledPolling();
        }
    }
});

// Close scheduled jobs
closeScheduledBtn?.addEventListener('click', function() {
    if (scheduledJobsContainer) {
        scheduledJobsContainer.style.display = 'none';
        toggleScheduledJobsBtn.textContent = '📅 View Scheduled Jobs';
        stopScheduledPolling();
    }
});

// Refresh scheduled posts
refreshScheduledBtn?.addEventListener('click', function() {
    loadScheduledPosts();
});

// Filter scheduled posts
scheduledFilterStatus?.addEventListener('change', loadScheduledPosts);
scheduledFilterPipeline?.addEventListener('change', loadScheduledPosts);

async function loadScheduledPosts() {
    const statusFilter = scheduledFilterStatus?.value || 'all';
    const pipelineFilter = scheduledFilterPipeline?.value || '';
    
    try {
        let url = `/api/scheduled-posts?status=${statusFilter}&limit=100`;
        if (pipelineFilter) {
            url += `&pipeline_id=${pipelineFilter}`;
        }
        
        const response = await fetch(url, { credentials: 'same-origin' });
        const data = await response.json();
        
        if (data.status === 'success') {
            scheduledPosts = data.scheduled_posts;
            renderScheduledPosts(data);
            updateScheduledSummary(data.counts);
        } else {
            console.error('Failed to load scheduled posts:', data.error);
            showScheduledError('Failed to load scheduled posts');
        }
    } catch (error) {
        console.error('Error loading scheduled posts:', error);
        showScheduledError('Network error loading scheduled posts');
    }
}

function renderScheduledPosts(data) {
    const container = scheduledPostsList;
    const posts = data.scheduled_posts || [];
    
    if (!container) return;
    
    // Update badge
    if (scheduledCountBadge) {
        const pending = data.counts?.pending || 0;
        scheduledCountBadge.textContent = `${pending} pending / ${posts.length} total`;
    }
    
    if (posts.length === 0) {
        container.innerHTML = `
            <div class="no-scheduled">
                <div class="empty-icon">📭</div>
                <strong>No scheduled posts</strong>
                <p style="margin-top: 8px; font-size: 13px; color: var(--text-secondary);">
                    Posts will appear here once they are scheduled.
                </p>
            </div>
        `;
        return;
    }
    
    let html = '';
    const now = new Date();
    
    posts.forEach(post => {
        const scheduledTime = new Date(post.scheduled_time);
        const isDue = scheduledTime <= now && post.status === 'pending';
        const timeRemaining = getTimeRemaining(scheduledTime);
        const statusClass = post.status === 'pending' ? 'pending' : 
                           post.status === 'posted' ? 'posted' : 'failed';
        
        html += `
            <div class="scheduled-post-item status-${statusClass}">
                <div class="scheduled-post-info">
                    <span class="post-url">${escapeHtml(post.reel_url || '')}</span>
                    <span class="post-time">
                        🕐 ${formatDateTime(scheduledTime)}
                        ${isDue ? ' 🔴 DUE NOW!' : ''}
                        ${post.status === 'pending' ? ` (${timeRemaining})` : ''}
                    </span>
                    ${post.caption ? `<span class="post-caption">📝 ${escapeHtml(post.caption.substring(0, 80))}${post.caption.length > 80 ? '...' : ''}</span>` : ''}
                    ${post.pipeline_name ? `<span class="post-caption" style="color: var(--accent);">🏗️ ${escapeHtml(post.pipeline_name)}</span>` : ''}
                </div>
                <div class="scheduled-post-status">
                    <span class="status-badge ${statusClass}">
                        ${post.status === 'pending' ? '⏳ Pending' : 
                          post.status === 'posted' ? '✅ Posted' : '❌ Failed'}
                    </span>
                    ${post.status === 'pending' ? `
                        <div class="scheduled-post-actions">
                            <button class="btn btn-sm btn-danger delete-scheduled-btn" data-id="${post.id}" title="Delete">🗑️</button>
                        </div>
                    ` : ''}
                    ${post.posted_at ? `<span style="font-size: 11px; color: var(--text-muted);">Posted: ${formatDateTime(new Date(post.posted_at))}</span>` : ''}
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
    
    // Add event listeners for delete buttons
    document.querySelectorAll('.delete-scheduled-btn').forEach(btn => {
        btn.addEventListener('click', async function(e) {
            e.stopPropagation();
            const postId = this.dataset.id;
            if (confirm('Delete this scheduled post?')) {
                await deleteScheduledPost(postId);
            }
        });
    });
}

function updateScheduledSummary(counts) {
    if (!counts) return;
    
    const totalEl = document.getElementById('summary-total');
    const pendingEl = document.getElementById('summary-pending');
    const postedEl = document.getElementById('summary-posted');
    const failedEl = document.getElementById('summary-failed');
    
    if (totalEl) totalEl.textContent = counts.total || 0;
    if (pendingEl) pendingEl.textContent = counts.pending || 0;
    if (postedEl) postedEl.textContent = counts.posted || 0;
    if (failedEl) failedEl.textContent = counts.failed || 0;
}

function getTimeRemaining(date) {
    const now = new Date();
    const diff = date - now;
    
    if (diff <= 0) return 'Due now';
    
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    
    if (hours > 24) {
        const days = Math.floor(hours / 24);
        return `${days}d ${hours % 24}h`;
    }
    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
}

function formatDateTime(date) {
    if (!date || isNaN(date.getTime())) return 'Unknown';
    return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    });
}

async function deleteScheduledPost(postId) {
    try {
        const response = await fetch(`/api/scheduled-posts/${postId}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });
        const data = await response.json();
        
        if (data.status === 'success') {
            showToast('✅ Post deleted', 'success');
            loadScheduledPosts();
        } else {
            showToast('❌ Failed to delete: ' + data.error, 'error');
        }
    } catch (error) {
        console.error('Error deleting post:', error);
        showToast('❌ Error deleting post', 'error');
    }
}

function showScheduledError(message) {
    const container = scheduledPostsList;
    if (container) {
        container.innerHTML = `
            <div class="no-scheduled">
                <div class="empty-icon">⚠️</div>
                <strong>Error</strong>
                <p style="margin-top: 8px; font-size: 13px; color: var(--error);">${escapeHtml(message)}</p>
            </div>
        `;
    }
}

function showToast(message, type) {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 8px;
        color: #fff;
        font-size: 14px;
        z-index: 9999;
        animation: slideIn 0.3s ease;
        max-width: 400px;
    `;
    
    if (type === 'success') {
        toast.style.background = 'rgba(34, 197, 94, 0.9)';
    } else if (type === 'error') {
        toast.style.background = 'rgba(239, 68, 68, 0.9)';
    } else {
        toast.style.background = 'rgba(59, 130, 246, 0.9)';
    }
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Populate pipeline filter
async function populatePipelineFilter() {
    try {
        const response = await fetch('/api/pipelines', { credentials: 'same-origin' });
        const data = await response.json();
        const select = scheduledFilterPipeline;
        
        if (select && data.pipelines) {
            select.innerHTML = '<option value="">All Pipelines</option>';
            data.pipelines.forEach(p => {
                const option = document.createElement('option');
                option.value = p.id;
                option.textContent = p.name || p.profile_username;
                select.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading pipelines:', error);
    }
}

// Start polling for scheduled posts
function startScheduledPolling() {
    if (scheduledPollingInterval) {
        clearInterval(scheduledPollingInterval);
    }
    
    // Load immediately
    loadScheduledPosts();
    
    // Poll every 30 seconds
    scheduledPollingInterval = setInterval(() => {
        // Only update if tab is visible
        if (!document.hidden && scheduledJobsContainer?.style.display !== 'none') {
            loadScheduledPosts();
        }
    }, 30000);
}

function stopScheduledPolling() {
    if (scheduledPollingInterval) {
        clearInterval(scheduledPollingInterval);
        scheduledPollingInterval = null;
    }
}

// Initialize scheduled jobs on page load
document.addEventListener('DOMContentLoaded', function() {
    populatePipelineFilter();
    // Don't auto-load scheduled jobs - wait for user to click toggle
});

console.log('✅ Fetchgram loaded successfully!');



























// ==================== ZERNIO KEYS MANAGEMENT ====================

let zernioKeys = [];

async function loadZernioKeys() {
    const container = document.getElementById('zernio-keys-list');
    const countBadge = document.getElementById('zernio-keys-count');
    
    try {
        const response = await fetch('/api/zernio/keys', {
            credentials: 'same-origin'
        });
        const data = await response.json();
        
        if (data.status === 'success') {
            zernioKeys = data.keys;
            
            if (countBadge) {
                countBadge.textContent = `${data.total} keys`;
            }
            
            renderZernioKeys(data.keys);
        } else {
            container.innerHTML = `<div class="empty-state">❌ Failed to load keys: ${data.error}</div>`;
        }
    } catch (error) {
        console.error('Failed to load Zernio keys:', error);
        container.innerHTML = `<div class="empty-state">❌ Error loading keys</div>`;
    }
}








function renderZernioKeys(keys) {
    const container = document.getElementById('zernio-keys-list');
    
    if (!keys || keys.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div style="font-size: 32px; margin-bottom: 12px;">🔑</div>
                <strong>No Zernio keys added</strong>
                <p style="margin-top: 8px; font-size: 13px; color: var(--text-secondary);">
                    Add your first Zernio API key to start posting to Facebook.
                </p>
                <button id="empty-add-key-btn" class="btn btn-sm btn-primary" style="margin-top: 12px;">➕ Add Key</button>
            </div>
        `;
        
        document.getElementById('empty-add-key-btn')?.addEventListener('click', () => {
            document.getElementById('add-zernio-key-modal').hidden = false;
        });
        return;
    }
    
    let html = `<div class="zernio-keys-grid">`;
    
    keys.forEach(key => {
        const isActive = key.is_active;
        // Use accounts from API response
        const accounts = key.accounts || [];
        const accountCount = accounts.length;
        
        html += `
            <div class="zernio-key-card ${isActive ? '' : 'inactive'}">
                <div class="zernio-key-header">
                    <div class="zernio-key-name">
                        <span class="key-icon">${isActive ? '🟢' : '🔴'}</span>
                        <span class="key-title">${escapeHtml(key.name)}</span>
                        <span class="key-status-badge ${isActive ? 'active' : 'inactive'}">
                            ${isActive ? 'Active' : 'Inactive'}
                        </span>
                        <span class="key-account-count-badge">${accountCount} account${accountCount !== 1 ? 's' : ''}</span>
                    </div>
                    <div class="zernio-key-actions">
                        <button class="btn btn-sm btn-ghost toggle-key-btn" data-id="${key.id}" data-active="${isActive}" title="Toggle Key">
                            ${isActive ? '⏸' : '▶'}
                        </button>
                        <button class="btn btn-sm btn-danger delete-zernio-key-btn" data-id="${key.id}" data-name="${escapeHtml(key.name)}" title="Delete Key">🗑️</button>
                    </div>
                </div>
                <div class="zernio-key-body">
                    <div class="key-detail">
                        <span class="key-label">API Key:</span>
                        <span class="key-value key-masked">${key.api_key_masked || '***'}</span>
                    </div>
                    
                    <!-- Show ALL Facebook accounts with ✅ -->
                    <div class="key-accounts-section">
                        <div class="key-detail" style="border-bottom: none; margin-bottom: 4px; font-weight: 600;">
                            <span class="key-label">Facebook Accounts:</span>
                            <span class="key-value" style="color: var(--accent);">${accountCount}</span>
                        </div>
                        ${accountCount > 0 ? `
                        <div class="key-accounts-list">
                            ${accounts.map((account, idx) => `
                                <div class="key-account-item">
                                    <span class="account-icon">📱</span>
                                    <span class="account-name">${escapeHtml(account.name)}</span>
                                    <span class="account-id">${escapeHtml(account.id)}</span>
                                    <span class="account-status">✅</span>
                                </div>
                            `).join('')}
                        </div>
                        ` : `
                        <div class="key-accounts-empty">
                            <span style="color: var(--text-muted); font-size: 13px;">No Facebook accounts found</span>
                        </div>
                        `}
                    </div>
                </div>
            </div>
        `;
    });
    
    html += `</div>`;
    container.innerHTML = html;
    
    // Delete button
    document.querySelectorAll('.delete-zernio-key-btn').forEach(btn => {
        btn.addEventListener('click', () => deleteZernioKey(btn.dataset.id, btn.dataset.name));
    });
    
    // Toggle button
    document.querySelectorAll('.toggle-key-btn').forEach(btn => {
        btn.addEventListener('click', () => toggleZernioKey(btn.dataset.id, btn.dataset.active === 'true'));
    });
}






// ==================== ADD ZERNIO KEY (SIMPLIFIED) ====================

document.getElementById('add-zernio-key-btn')?.addEventListener('click', () => {
    document.getElementById('add-zernio-key-modal').hidden = false;
    document.getElementById('add-zernio-key-status').style.display = 'none';
    document.getElementById('zernio-key-api').value = '';
});

document.getElementById('add-zernio-key-modal-close')?.addEventListener('click', () => {
    document.getElementById('add-zernio-key-modal').hidden = true;
});

document.getElementById('add-zernio-key-modal')?.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) {
        e.target.hidden = true;
    }
});

document.getElementById('save-zernio-key-btn')?.addEventListener('click', async function() {
    const apiKey = document.getElementById('zernio-key-api').value.trim();
    const status = document.getElementById('add-zernio-key-status');
    
    if (!apiKey) {
        status.textContent = '❌ Please enter your Zernio API key';
        status.className = 'status-message error';
        status.style.display = 'block';
        return;
    }
    
    this.disabled = true;
    this.textContent = '⏳ Checking key...';
    status.style.display = 'none';
    
    try {
        // First, validate the key by fetching accounts
        const validateResponse = await fetch('/api/zernio/validate-key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ api_key: apiKey })
        });
        
        const validateData = await validateResponse.json();
        
        if (!validateResponse.ok || !validateData.valid) {
            status.textContent = `❌ Invalid API key: ${validateData.message || 'Please check your key'}`;
            status.className = 'status-message error';
            status.style.display = 'block';
            this.disabled = false;
            this.textContent = 'Save Key';
            return;
        }
        
        // Key is valid, save it
        const response = await fetch('/api/zernio/keys', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({
                name: validateData.name || `Key ${new Date().toLocaleDateString()}`,
                api_key: apiKey,
                facebook_account_id: validateData.accounts?.[0]?.id || 'auto',
                facebook_page_name: validateData.accounts?.[0]?.name || '',
                daily_limit: 50
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            status.textContent = `✅ Key added! Found ${validateData.accounts?.length || 0} Facebook accounts.`;
            status.className = 'status-message success';
            status.style.display = 'block';
            
            document.getElementById('zernio-key-api').value = '';
            
            // ⭐ Reload EVERYTHING
            await loadZernioKeys();
            await loadZernioAccounts(); // Refresh account list
            await loadPipelines(); // Refresh pipelines
            
            setTimeout(() => {
                document.getElementById('add-zernio-key-modal').hidden = true;
            }, 2000);
        } else {
            status.textContent = `❌ ${data.error || 'Failed to add key'}`;
            status.className = 'status-message error';
            status.style.display = 'block';
        }
    } catch (error) {
        status.textContent = `❌ Error: ${error.message}`;
        status.className = 'status-message error';
        status.style.display = 'block';
    } finally {
        this.disabled = false;
        this.textContent = 'Save Key';
    }
});

// ==================== DELETE ZERNIO KEY ====================

async function deleteZernioKey(keyId, keyName) {
    if (!confirm(`⚠️ Are you sure you want to delete the Zernio key "${keyName}"?\n\nThis will NOT affect already posted content.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/zernio/keys/${keyId}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast(`✅ Zernio key "${keyName}" deleted`, 'success');
            await loadZernioKeys();
            await loadZernioAccounts(); // Refresh account list
            await loadPipelines();
        } else {
            showToast(`❌ ${data.error || 'Failed to delete key'}`, 'error');
        }
    } catch (error) {
        showToast(`❌ Error: ${error.message}`, 'error');
    }
}

// ==================== TOGGLE ZERNIO KEY ====================

async function toggleZernioKey(keyId, currentActive) {
    try {
        const response = await fetch(`/api/zernio/keys/${keyId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ is_active: !currentActive })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast(`✅ Key ${!currentActive ? 'activated' : 'deactivated'}`, 'success');
            await loadZernioKeys();
            await loadZernioAccounts(); // Refresh account list
            await loadPipelines();
        } else {
            showToast(`❌ ${data.error || 'Failed to toggle key'}`, 'error');
        }
    } catch (error) {
        showToast(`❌ Error: ${error.message}`, 'error');
    }
}

// ==================== REFRESH ZERNIO KEYS ====================

document.getElementById('refresh-zernio-keys-btn')?.addEventListener('click', function() {
    this.disabled = true;
    this.textContent = '⏳';
    loadZernioKeys();
    loadZernioAccounts();
    loadPipelines();
    setTimeout(() => {
        this.disabled = false;
        this.textContent = '🔄 Refresh';
        showToast('🔄 Keys and accounts refreshed', 'info');
    }, 2000);
});

// Load keys on page load
document.addEventListener('DOMContentLoaded', function() {
    loadZernioKeys();
});
























// ==================== EXTRACT COOKIES FROM RENDER SERVICE ====================

async function extractCookiesFromBrowserless() {
    console.log('🍪 Extracting cookies from Render cookie service...');
    
    // Show status in the cookie upload section
    const statusEl = document.getElementById('cookie-upload-status');
    if (statusEl) {
        statusEl.textContent = '⏳ Extracting cookies from Browserless...';
        statusEl.className = 'cookie-status-msg info';
        statusEl.hidden = false;
    }
    
    try {
        const response = await fetch('/api/cookies/extract-from-render', {
            method: 'POST',
            credentials: 'same-origin'
        });
        
        const data = await response.json();
        console.log('📊 Extract response:', data);
        
        if (data.success) {
            if (statusEl) {
                statusEl.textContent = `✅ ${data.message}`;
                statusEl.className = 'cookie-status-msg success';
                statusEl.hidden = false;
            }
            // Update cookie status in Instagram status card
            await checkInstagramStatus();
            // Update Zernio cookie status
            updateZernioCookieStatus();
            return true;
        } else {
            if (statusEl) {
                statusEl.textContent = `❌ ${data.error || 'Failed to extract cookies'}`;
                statusEl.className = 'cookie-status-msg error';
                statusEl.hidden = false;
            }
            showCookieStatus(`❌ ${data.error || 'Failed to extract cookies'}`, 'error');
            return false;
        }
    } catch (error) {
        console.error('❌ Extraction error:', error);
        if (statusEl) {
            statusEl.textContent = `❌ Failed to extract: ${error.message}`;
            statusEl.className = 'cookie-status-msg error';
            statusEl.hidden = false;
        }
        showCookieStatus(`❌ Failed to extract: ${error.message}`, 'error');
        return false;
    }
}

// Check if Render cookie service is available
async function checkCookieServiceStatus() {
    const statusEl = document.getElementById('cookie-service-status');
    if (!statusEl) return;
    
    try {
        const response = await fetch('/api/cookies/extract-from-render/status', {
            credentials: 'same-origin'
        });
        const data = await response.json();
        
        if (data.available) {
            console.log('✅ Render cookie service is available');
            statusEl.textContent = '✅ Cookie service: Online';
            statusEl.style.color = '#28a745';
        } else {
            console.warn('⚠️ Render cookie service is not available');
            statusEl.textContent = '⚠️ Cookie service: Offline';
            statusEl.style.color = '#ffc107';
        }
        return data.available;
    } catch (error) {
        console.error('❌ Failed to check cookie service:', error);
        statusEl.textContent = '❌ Cookie service: Unreachable';
        statusEl.style.color = '#dc3545';
        return false;
    }
}

// Add a button to the cookie upload area
function addExtractCookieButton() {
    const container = document.querySelector('.cookie-upload-area');
    if (!container) return;
    
    // Check if button already exists
    if (document.getElementById('extract-browserless-cookies-btn')) return;
    
    const extractBtn = document.createElement('button');
    extractBtn.id = 'extract-browserless-cookies-btn';
    extractBtn.className = 'btn btn-primary';
    extractBtn.style.marginTop = '8px';
    extractBtn.innerHTML = `
        <span class="btn-content">
            🍪 Extract from Browserless
        </span>
    `;
    extractBtn.addEventListener('click', async function() {
        this.disabled = true;
        this.innerHTML = '<span class="btn-spinner"></span> Extracting...';
        await extractCookiesFromBrowserless();
        this.disabled = false;
        this.innerHTML = '<span class="btn-content">🍪 Extract from Browserless</span>';
    });
    
    // Find the cookie-upload-actions div or create one
    let actionsDiv = container.querySelector('.cookie-upload-actions');
    if (!actionsDiv) {
        actionsDiv = document.createElement('div');
        actionsDiv.className = 'cookie-upload-actions';
        actionsDiv.style.cssText = 'display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px;';
        container.appendChild(actionsDiv);
    }
    
    // Add refresh status button
    const refreshBtn = document.createElement('button');
    refreshBtn.id = 'refresh-status-btn';
    refreshBtn.className = 'btn btn-sm btn-ghost';
    refreshBtn.innerHTML = '🔄 Refresh Status';
    refreshBtn.addEventListener('click', function() {
        checkCookieServiceStatus();
        checkInstagramStatus();
    });
    
    actionsDiv.appendChild(extractBtn);
    actionsDiv.appendChild(refreshBtn);
    
    // Add cookie service status indicator
    const statusDiv = document.createElement('div');
    statusDiv.className = 'cookie-service-status';
    statusDiv.style.cssText = 'margin-top: 8px; font-size: 12px; color: var(--text-muted);';
    statusDiv.innerHTML = `<span id="cookie-service-status">🔍 Checking cookie service...</span>`;
    container.appendChild(statusDiv);
    
    // Check status
    checkCookieServiceStatus();
}

// Handle private/login required errors
function handlePrivateError(errorMsg) {
    const errorContainer = document.getElementById('error-msg');
    if (!errorContainer) return;
    
    errorContainer.innerHTML = `
        <div style="padding: 12px; background: #f8d7da; border-radius: 8px; border-left: 3px solid #dc3545;">
            <strong>⚠️ ${errorMsg}</strong>
            <div style="margin-top: 10px; display: flex; gap: 10px; flex-wrap: wrap;">
                <button id="extract-on-error-btn" class="btn btn-primary btn-sm">
                    🍪 Extract Cookies from Browserless
                </button>
                <button id="retry-after-extract-btn" class="btn btn-success btn-sm">
                    🔄 Retry Download
                </button>
            </div>
        </div>
    `;
    errorContainer.hidden = false;
    
    document.getElementById('extract-on-error-btn')?.addEventListener('click', async function() {
        this.disabled = true;
        this.textContent = '⏳ Extracting...';
        const success = await extractCookiesFromBrowserless();
        this.disabled = false;
        this.textContent = '🍪 Extract Cookies from Browserless';
        if (success && window.currentVideoUrl) {
            retryDownload();
        }
    });
    
    document.getElementById('retry-after-extract-btn')?.addEventListener('click', function() {
        if (window.currentVideoUrl) {
            retryDownload();
        } else {
            showError('No video to retry. Please fetch a video first.');
        }
    });
}

// Retry download after cookie extraction
async function retryDownload() {
    if (!window.currentVideoUrl) return;
    
    const errorContainer = document.getElementById('error-msg');
    if (errorContainer) {
        errorContainer.innerHTML = '🔄 Retrying with fresh cookies...';
        errorContainer.className = 'error-msg info';
        errorContainer.hidden = false;
    }
    
    try {
        const res = await fetch("/api/commands/download", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: 'same-origin',
            body: JSON.stringify({ url: window.currentVideoUrl, action: "url_only" }),
        });
        const data = await res.json();
        
        if (res.ok && data.download_url) {
            const item = data.video_info || { title: "Instagram video" };
            if (typeof renderResults === 'function') {
                renderResults([item], data.url);
            }
            setTimeout(() => {
                if (typeof showDirectUrl === 'function') {
                    showDirectUrl(data.download_url, item);
                }
            }, 100);
            if (typeof clearError === 'function') {
                clearError();
            }
        } else {
            handlePrivateError(data.error || "Still can't download. Try again manually.");
        }
    } catch (err) {
        handlePrivateError("Failed to retry: " + err.message);
    }
}

// Update Zernio cookie status
async function updateZernioCookieStatus() {
    const statusEl = document.getElementById('zernio-cookie-status');
    if (!statusEl) return;
    
    try {
        const response = await fetch('/api/instagram/cookies_status', { 
            credentials: 'same-origin' 
        });
        const data = await response.json();
        
        if (data.has_cookies) {
            statusEl.textContent = '🍪 Connected';
            statusEl.style.background = '#d4edda';
            statusEl.style.color = '#155724';
        } else {
            statusEl.textContent = '🍪 No Cookies';
            statusEl.style.background = '#f8d7da';
            statusEl.style.color = '#721c24';
            // Add extract button if not exists
            if (!statusEl.querySelector('button')) {
                const extractBtn = document.createElement('button');
                extractBtn.className = 'btn btn-sm btn-primary';
                extractBtn.style.marginLeft = '8px';
                extractBtn.textContent = '🍪 Extract';
                extractBtn.addEventListener('click', async function() {
                    this.disabled = true;
                    this.textContent = '⏳';
                    await extractCookiesFromBrowserless();
                    this.disabled = false;
                    this.textContent = '🍪 Extract';
                    updateZernioCookieStatus();
                });
                statusEl.appendChild(extractBtn);
            }
        }
    } catch (error) {
        console.error('Failed to update cookie status:', error);
    }
}

// ==================== CHECK COOKIES BEFORE POSTING ====================

async function checkCookiesBeforePosting() {
    try {
        const response = await fetch('/api/instagram/cookies_status', { 
            credentials: 'same-origin' 
        });
        const data = await response.json();
        
        if (!data.has_cookies) {
            // Show cookie required message with extract option
            const statusEl = document.getElementById('zernio-status');
            if (statusEl) {
                statusEl.innerHTML = `
                    <div style="padding: 12px; background: #f8d7da; border-radius: 8px; border-left: 3px solid #dc3545;">
                        <strong>❌ Instagram cookies required for posting.</strong>
                        <div style="margin-top: 10px;">
                            <button id="extract-for-posting-btn" class="btn btn-primary btn-sm">
                                🍪 Extract Cookies from Browserless
                            </button>
                        </div>
                    </div>
                `;
                statusEl.hidden = false;
                
                document.getElementById('extract-for-posting-btn')?.addEventListener('click', async function() {
                    this.disabled = true;
                    this.textContent = '⏳ Extracting...';
                    const success = await extractCookiesFromBrowserless();
                    this.disabled = false;
                    this.textContent = '🍪 Extract Cookies from Browserless';
                    if (success) {
                        // Retry the post
                        const publishBtn = document.getElementById('zernio-publish-btn');
                        if (publishBtn) {
                            publishBtn.click();
                        }
                    }
                });
            }
            return false;
        }
        return true;
    } catch (error) {
        console.error('Failed to check cookies:', error);
        return false;
    }
}

// ==================== INITIALIZATION ====================

// Store current video URL globally
window.currentVideoUrl = null;

// Override the fetch function to store URL
const originalFetch = window.fetch;
window.fetch = function(...args) {
    // Check if this is a download request
    if (args[0] && typeof args[0] === 'string' && args[0].includes('/api/commands/download')) {
        const body = args[1]?.body;
        if (body) {
            try {
                const data = JSON.parse(body);
                if (data.url) {
                    window.currentVideoUrl = data.url;
                }
            } catch (e) {}
        }
    }
    return originalFetch.apply(this, args);
};

// Override showError to handle private errors
const originalShowError = window.showError || function(msg) {
    const errorContainer = document.getElementById('error-msg');
    if (errorContainer) {
        errorContainer.textContent = msg;
        errorContainer.hidden = false;
    }
};

window.showError = function(message) {
    if (message && (message.includes('private') || message.includes('login required') || message.includes('requires_cookies'))) {
        handlePrivateError(message);
    } else {
        originalShowError(message);
    }
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Add extract cookie button
    setTimeout(addExtractCookieButton, 500);
    // Check cookie service status
    checkCookieServiceStatus();
    // Update Zernio cookie status
    setTimeout(updateZernioCookieStatus, 1000);
});

console.log('✅ Browserless cookie extractor (Render service) loaded!');






// ==================== FIX: CLEAR COOKIES BUTTON ====================

// Show/hide Clear button based on cookie status
async function updateClearButton() {
    const clearBtn = document.getElementById('clear-cookie-btn');
    const clearMainBtn = document.getElementById('clear-cookie-main-btn');
    if (!clearBtn && !clearMainBtn) return;
    
    try {
        const response = await fetch('/api/instagram/cookies_status', {
            credentials: 'same-origin'
        });
        const data = await response.json();
        
        if (data.has_cookies) {
            // Show both clear buttons
            if (clearBtn) {
                clearBtn.hidden = false;
                clearBtn.disabled = false;
                clearBtn.textContent = '🗑️ Clear';
            }
            if (clearMainBtn) {
                clearMainBtn.hidden = false;
                clearMainBtn.disabled = false;
                clearMainBtn.textContent = '🗑️ Clear';
            }
        } else {
            if (clearBtn) clearBtn.hidden = true;
            if (clearMainBtn) clearMainBtn.hidden = true;
        }
    } catch (error) {
        console.error('Failed to check cookie status:', error);
        if (clearBtn) clearBtn.hidden = true;
        if (clearMainBtn) clearMainBtn.hidden = true;
    }
}

// Handle Clear button click from the status card
async function clearCookies() {
    const clearBtn = document.getElementById('clear-cookie-btn');
    const clearMainBtn = document.getElementById('clear-cookie-main-btn');
    
    // Disable both buttons
    if (clearBtn) {
        clearBtn.disabled = true;
        clearBtn.textContent = '⏳ Clearing...';
    }
    if (clearMainBtn) {
        clearMainBtn.disabled = true;
        clearMainBtn.textContent = '⏳ Clearing...';
    }
    
    try {
        const response = await fetch('/api/cookies/clear', {
            method: 'POST',
            credentials: 'same-origin'
        });
        
        const data = await response.json();
        console.log('Clear cookies response:', data);
        
        if (data.status === 'success') {
            showCookieStatus('✅ Cookies cleared successfully!', 'success');
            // Update UI
            await updateClearButton();
            await checkInstagramStatus();
            // Reset file input label
            const label = document.getElementById('cookie-file-label-text');
            if (label) label.textContent = 'Choose cookies.json';
            const uploadBtn = document.getElementById('upload-cookie-main-btn');
            if (uploadBtn) uploadBtn.disabled = true;
            // Clear file input
            const fileInput = document.getElementById('cookie-file-input-main');
            if (fileInput) fileInput.value = '';
        } else {
            showCookieStatus('❌ Failed to clear cookies: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('❌ Clear cookies error:', error);
        showCookieStatus('❌ Failed to clear cookies: ' + error.message, 'error');
    } finally {
        // Reset buttons
        if (clearBtn) {
            clearBtn.disabled = false;
            clearBtn.textContent = '🗑️ Clear';
        }
        if (clearMainBtn) {
            clearMainBtn.disabled = false;
            clearMainBtn.textContent = '🗑️ Clear';
        }
    }
}

// Initialize Clear buttons
document.addEventListener('DOMContentLoaded', function() {
    // ... existing code ...
    
    // Update clear button visibility
    setTimeout(updateClearButton, 500);
    
    // Add click handler for Clear button in status card
    const clearBtn = document.getElementById('clear-cookie-btn');
    if (clearBtn) {
        clearBtn.addEventListener('click', clearCookies);
        clearBtn.hidden = true; // Will be shown by updateClearButton
    }
    
    // Add click handler for Clear button in upload section
    const clearMainBtn = document.getElementById('clear-cookie-main-btn');
    if (clearMainBtn) {
        clearMainBtn.addEventListener('click', clearCookies);
        clearMainBtn.hidden = true; // Will be shown by updateClearButton
    }
});

// Also update when cookie status changes
const originalCheckInstagramStatus = window.checkInstagramStatus || function() {};
window.checkInstagramStatus = async function() {
    await originalCheckInstagramStatus();
    await updateClearButton();
};






































// ==================== MANUAL SCHEDULER (Allow Past Dates) ====================

let unpostedReels = [];
let selectedReels = new Set();
let schedulerPipelines = [];
let schedulerCurrentPage = 1;
let schedulerPageLimit = 25;
let schedulerFilteredReels = [];
let schedulerIsLoading = false;
let isSchedulerExpanded = false;

// ==================== TOGGLE SCHEDULER ====================

function toggleManualScheduler() {
    const body = document.getElementById('manual-scheduler-body');
    const status = document.getElementById('scheduler-status-indicator');
    const toggleBtn = document.getElementById('scheduler-toggle-btn');
    
    if (body) {
        isSchedulerExpanded = body.style.display !== 'none';
        body.style.display = isSchedulerExpanded ? 'none' : 'block';
        
        if (status) {
            status.textContent = isSchedulerExpanded ? '▼ Click to Expand' : '▲ Click to Collapse';
        }
        if (toggleBtn) {
            toggleBtn.textContent = isSchedulerExpanded ? '▼' : '▲';
        }
        
        if (!isSchedulerExpanded) {
            loadSchedulerPipelines();
            const select = document.getElementById('scheduler-pipeline-select');
            if (select && select.value) {
                loadUnpostedReels(select.value);
            }
        }
    }
}

// ==================== PAGINATION FUNCTIONS ====================

function getPaginatedReels() {
    const search = document.getElementById('scheduler-search')?.value?.toLowerCase() || '';
    const limit = parseInt(document.getElementById('scheduler-page-limit')?.value || 25);
    
    let filtered = unpostedReels;
    if (search) {
        filtered = unpostedReels.filter(reel => {
            const url = reel.url || '';
            const caption = reel.caption || '';
            return url.toLowerCase().includes(search) || caption.toLowerCase().includes(search);
        });
    }
    
    schedulerFilteredReels = filtered;
    schedulerPageLimit = limit;
    
    const total = filtered.length;
    const totalPages = Math.ceil(total / limit) || 1;
    
    if (schedulerCurrentPage > totalPages) {
        schedulerCurrentPage = totalPages;
    }
    if (schedulerCurrentPage < 1) {
        schedulerCurrentPage = 1;
    }
    
    const start = (schedulerCurrentPage - 1) * limit;
    const end = Math.min(start + limit, total);
    const pageReels = filtered.slice(start, end);
    
    const loadedCountEl = document.getElementById('scheduler-loaded-count');
    if (loadedCountEl) {
        loadedCountEl.textContent = total;
    }
    
    document.getElementById('scheduler-page-info').textContent = `Page ${schedulerCurrentPage} of ${totalPages}`;
    document.getElementById('scheduler-prev-page').disabled = schedulerCurrentPage <= 1;
    document.getElementById('scheduler-next-page').disabled = schedulerCurrentPage >= totalPages;
    
    return pageReels;
}

function goToPage(page) {
    schedulerCurrentPage = page;
    renderSchedulerReels(getPaginatedReels());
}

// ==================== INITIALIZE SCHEDULER ====================

async function initManualScheduler() {
    await loadSchedulerPipelines();
    setupSchedulerEventListeners();
    setDefaultDates();
    
    const body = document.getElementById('manual-scheduler-body');
    if (body) {
        body.style.display = 'none';
    }
}

// ==================== SET DEFAULT DATES ====================

function setDefaultDates() {
    const now = new Date();
    
    // ✅ Default to TODAY instead of tomorrow (allows past dates)
    const today = new Date(now);
    document.getElementById('batch-start-date').value = today.toISOString().split('T')[0];
    
    // Set default time to current time + 1 hour
    const currentHour = now.getHours();
    const currentMinute = now.getMinutes();
    
    // Set hour (12-hour format)
    let hour12 = currentHour % 12 || 12;
    const ampm = currentHour >= 12 ? 'PM' : 'AM';
    
    // Round minute to nearest 5
    let minute = Math.round(currentMinute / 5) * 5;
    if (minute >= 60) {
        minute = 0;
        hour12 = hour12 % 12 + 1;
    }
    const minuteStr = String(minute).padStart(2, '0');
    
    // Set default time
    document.getElementById('batch-start-hour').value = hour12;
    document.getElementById('batch-start-minute').value = minuteStr;
    document.getElementById('batch-start-ampm').value = ampm;
}

// ==================== LOAD PIPELINES ====================

async function loadSchedulerPipelines() {
    const select = document.getElementById('scheduler-pipeline-select');
    if (!select) return;
    
    try {
        const response = await fetch('/api/pipelines', { credentials: 'same-origin' });
        const data = await response.json();
        
        if (data.status === 'success' && data.pipelines) {
            schedulerPipelines = data.pipelines;
            const currentValue = select.value;
            
            select.innerHTML = '<option value="">Select a pipeline...</option>';
            
            data.pipelines.forEach(p => {
                const option = document.createElement('option');
                option.value = p.id;
                option.textContent = `${p.name} (@${p.profile_username})`;
                if (p.id === currentValue) {
                    option.selected = true;
                }
                select.appendChild(option);
            });
            
            updateSchedulerBadge();
        }
    } catch (error) {
        console.error('Failed to load pipelines:', error);
    }
}

function updateSchedulerBadge() {
    const badge = document.getElementById('scheduler-post-count');
    if (badge) {
        const total = unpostedReels.length || 0;
        badge.textContent = `${total} posts`;
    }
}

// ==================== LOAD UNPOSTED REELS ====================

async function loadUnpostedReels(pipelineId) {
    const container = document.getElementById('scheduler-reels-list');
    const stats = document.getElementById('scheduler-stats');
    const batchActions = document.getElementById('scheduler-batch-actions');
    const pagination = document.getElementById('scheduler-pagination');
    
    if (!pipelineId) {
        container.innerHTML = `
            <div class="empty-state">
                <div style="font-size: 32px; margin-bottom: 12px;">⚠️</div>
                <strong>Please select a pipeline</strong>
                <p style="margin-top: 8px; font-size: 13px; color: var(--text-secondary);">
                    Choose a pipeline from the dropdown above.
                </p>
            </div>
        `;
        stats.hidden = true;
        batchActions.hidden = true;
        pagination.hidden = true;
        return;
    }
    
    if (schedulerIsLoading) return;
    schedulerIsLoading = true;
    
    container.innerHTML = `
        <div class="loading-state">
            <div class="loading-spinner"></div>
            <p style="color: var(--text-muted); margin-top: 12px;">Loading reels...</p>
        </div>
    `;
    
    try {
        const response = await fetch(`/api/scheduler/unposted-reels/${pipelineId}`, {
            credentials: 'same-origin'
        });
        const data = await response.json();
        
        if (data.status === 'success') {
            unpostedReels = data.reels || [];
            selectedReels = new Set();
            schedulerCurrentPage = 1;
            
            document.getElementById('scheduler-total-reels').textContent = unpostedReels.length;
            document.getElementById('scheduler-scheduled-count').textContent = data.scheduled_count || 0;
            document.getElementById('scheduler-selected-count').textContent = '0';
            document.getElementById('scheduler-loaded-count').textContent = unpostedReels.length;
            stats.hidden = false;
            batchActions.hidden = false;
            pagination.hidden = false;
            
            updateSchedulerBadge();
            renderSchedulerReels(getPaginatedReels());
            
            // Set default date if not set
            if (!document.getElementById('batch-start-date').value) {
                const now = new Date();
                document.getElementById('batch-start-date').value = now.toISOString().split('T')[0];
            }
        } else {
            container.innerHTML = `
                <div class="empty-state">
                    <div style="font-size: 32px; margin-bottom: 12px;">❌</div>
                    <strong>${data.error || 'Failed to load reels'}</strong>
                </div>
            `;
            stats.hidden = true;
            batchActions.hidden = true;
            pagination.hidden = true;
        }
    } catch (error) {
        console.error('Failed to load reels:', error);
        container.innerHTML = `
            <div class="empty-state">
                <div style="font-size: 32px; margin-bottom: 12px;">❌</div>
                <strong>Error loading reels</strong>
                <p style="margin-top: 8px; font-size: 13px; color: var(--text-secondary);">${error.message}</p>
            </div>
        `;
        stats.hidden = true;
        batchActions.hidden = true;
        pagination.hidden = true;
    } finally {
        schedulerIsLoading = false;
    }
}

// ==================== RENDER SCHEDULER REELS ====================

function renderSchedulerReels(reels) {
    const container = document.getElementById('scheduler-reels-list');
    
    if (!reels || reels.length === 0) {
        const hasFiltered = schedulerFilteredReels && schedulerFilteredReels.length > 0;
        const hasUnposted = unpostedReels && unpostedReels.length > 0;
        
        if (hasFiltered && !hasUnposted) {
            container.innerHTML = `
                <div class="empty-state">
                    <div style="font-size: 32px; margin-bottom: 12px;">🔍</div>
                    <strong>No results match your search</strong>
                    <p style="margin-top: 8px; font-size: 13px; color: var(--text-secondary);">
                        Try adjusting your search terms.
                    </p>
                </div>
            `;
        } else {
            container.innerHTML = `
                <div class="empty-state">
                    <div style="font-size: 32px; margin-bottom: 12px;">🎉</div>
                    <strong>All reels are scheduled or posted!</strong>
                    <p style="margin-top: 8px; font-size: 13px; color: var(--text-secondary);">
                        No unposted reels found for this pipeline.
                    </p>
                </div>
            `;
        }
        return;
    }
    
    let html = `
        <div class="scheduler-reels-grid">
            <div class="scheduler-grid-header">
                <div class="scheduler-select-all">
                    <input type="checkbox" id="select-all-reels" />
                    <label for="select-all-reels">Select All</label>
                </div>
                <div class="scheduler-header-url">Reel URL</div>
                <div class="scheduler-header-caption">Caption</div>
                <div class="scheduler-header-status">Status</div>
                <div class="scheduler-header-actions">Actions</div>
            </div>
    `;
    
    reels.forEach((reel, index) => {
        const isScheduled = reel.is_scheduled;
        const scheduledTime = reel.scheduled_time;
        const caption = reel.caption || '';
        const url = reel.url || '';
        
        let scheduledDisplay = '';
        if (scheduledTime) {
            const date = new Date(scheduledTime);
            let hours = date.getHours();
            const ampm = hours >= 12 ? 'PM' : 'AM';
            hours = hours % 12 || 12;
            const minutes = String(date.getMinutes()).padStart(2, '0');
            scheduledDisplay = `${hours}:${minutes} ${ampm}`;
        }
        
        html += `
            <div class="scheduler-reel-item ${isScheduled ? 'scheduled' : ''}" data-index="${index}">
                <div class="scheduler-reel-select">
                    <input type="checkbox" class="reel-select-checkbox" data-url="${url}" ${isScheduled ? 'disabled' : ''} />
                </div>
                <div class="scheduler-reel-url">
                    <a href="${url}" target="_blank" title="${url}">${url.substring(0, 40)}...</a>
                </div>
                <div class="scheduler-reel-caption">
                    ${caption ? caption.substring(0, 40) + (caption.length > 40 ? '...' : '') : '<span style="color: var(--text-muted);">No caption</span>'}
                </div>
                <div class="scheduler-reel-status">
                    ${isScheduled ? `<span class="status-badge pending">⏳ ${scheduledDisplay}</span>` : '<span class="status-badge available">📥 Available</span>'}
                </div>
                <div class="scheduler-reel-actions">
                    ${!isScheduled ? `
                        <button class="btn btn-sm btn-primary schedule-single-btn" data-url="${url}">📅 Schedule</button>
                    ` : `
                        <button class="btn btn-sm btn-danger unschedule-btn" data-url="${url}">✕ Remove</button>
                    `}
                </div>
            </div>
        `;
    });
    
    html += `</div>`;
    container.innerHTML = html;
    
    document.getElementById('select-all-reels')?.addEventListener('change', function() {
        const checkboxes = container.querySelectorAll('.reel-select-checkbox:not(:disabled)');
        checkboxes.forEach(cb => cb.checked = this.checked);
        updateSelectedCount();
    });
    
    container.querySelectorAll('.reel-select-checkbox').forEach(cb => {
        cb.addEventListener('change', updateSelectedCount);
    });
    
    container.querySelectorAll('.schedule-single-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const url = this.dataset.url;
            openSingleScheduleModal(url);
        });
    });
    
    container.querySelectorAll('.unschedule-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const url = this.dataset.url;
            unscheduleSingleReel(url);
        });
    });
}

function updateSelectedCount() {
    const checkboxes = document.querySelectorAll('.reel-select-checkbox:checked:not(:disabled)');
    document.getElementById('scheduler-selected-count').textContent = checkboxes.length;
}

// ==================== 12-HOUR TIME HELPERS ====================

function parse12HourTime(hour, minute, ampm) {
    let hours = parseInt(hour);
    let minutes = parseInt(minute);
    
    if (ampm === 'PM' && hours !== 12) hours += 12;
    if (ampm === 'AM' && hours === 12) hours = 0;
    
    return { hours, minutes };
}

function format12HourTime(hours, minutes) {
    const ampm = hours >= 12 ? 'PM' : 'AM';
    const h12 = hours % 12 || 12;
    const m = String(minutes).padStart(2, '0');
    return `${h12}:${m} ${ampm}`;
}

// ==================== SINGLE SCHEDULE MODAL (ALLOWS PAST DATES) ====================

function openSingleScheduleModal(url) {
    const reel = unpostedReels.find(r => r.url === url);
    if (!reel) return;
    
    let modal = document.getElementById('single-schedule-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'single-schedule-modal';
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content premium-card">
                <div class="modal-header">
                    <h3>📅 Schedule Post</h3>
                    <button class="modal-close single-schedule-close">✕</button>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label>Reel URL</label>
                        <input type="text" id="single-schedule-url" class="input-field" readonly />
                    </div>
                    <div class="form-group">
                        <label>Caption</label>
                        <textarea id="single-schedule-caption" class="input-field" rows="2" placeholder="Enter caption..."></textarea>
                    </div>
                    <div class="form-group">
                        <label>Schedule Date</label>
                        <input type="date" id="single-schedule-date" class="input-field" />
                        <small style="color: var(--text-muted);">⚠️ Past dates are allowed for backfilling content</small>
                    </div>
                    <div class="form-group">
                        <label>Schedule Time (12-Hour)</label>
                        <div class="time-input-12">
                            <select id="single-schedule-hour" class="input-field time-select">
                                ${[12,1,2,3,4,5,6,7,8,9,10,11].map(h => 
                                    `<option value="${h}" ${h === 8 ? 'selected' : ''}>${h}</option>`
                                ).join('')}
                            </select>
                            <span class="time-separator">:</span>
                            <select id="single-schedule-minute" class="input-field time-select">
                                <option value="00">00</option>
                                <option value="15">15</option>
                                <option value="30" selected>30</option>
                                <option value="45">45</option>
                            </select>
                            <select id="single-schedule-ampm" class="input-field time-select">
                                <option value="AM">AM</option>
                                <option value="PM" selected>PM</option>
                            </select>
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Post Now?</label>
                        <div style="display: flex; gap: 10px; align-items: center;">
                            <button id="single-schedule-now-btn" class="btn btn-success">🚀 Post Now</button>
                            <span style="color: var(--text-muted); font-size: 13px;">or</span>
                            <button id="single-schedule-confirm" class="btn btn-primary">📅 Schedule</button>
                        </div>
                    </div>
                    <div id="single-schedule-status" class="status-message" hidden></div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        
        modal.querySelector('.single-schedule-close').addEventListener('click', () => modal.hidden = true);
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.hidden = true;
        });
    }
    
    document.getElementById('single-schedule-url').value = url;
    document.getElementById('single-schedule-caption').value = reel.caption || '';
    
    // ✅ Set default date to TODAY (allows past dates)
    const now = new Date();
    document.getElementById('single-schedule-date').value = now.toISOString().split('T')[0];
    
    // Set default time to current time + 1 hour
    const currentHour = now.getHours();
    const currentMinute = now.getMinutes();
    let hour12 = currentHour % 12 || 12;
    const ampm = currentHour >= 12 ? 'PM' : 'AM';
    let minute = Math.round(currentMinute / 5) * 5;
    if (minute >= 60) {
        minute = 0;
        hour12 = hour12 % 12 + 1;
    }
    document.getElementById('single-schedule-hour').value = hour12;
    document.getElementById('single-schedule-minute').value = String(minute).padStart(2, '0');
    document.getElementById('single-schedule-ampm').value = ampm;
    
    document.getElementById('single-schedule-status').style.display = 'none';
    modal.hidden = false;
    
    // ============================================================
    // SCHEDULE BUTTON (Allows past dates)
    // ============================================================
    document.getElementById('single-schedule-confirm').onclick = async function() {
        const date = document.getElementById('single-schedule-date').value;
        const hour = document.getElementById('single-schedule-hour').value;
        const minute = document.getElementById('single-schedule-minute').value;
        const ampm = document.getElementById('single-schedule-ampm').value;
        const caption = document.getElementById('single-schedule-caption').value.trim();
        const status = document.getElementById('single-schedule-status');
        
        if (!date) {
            status.textContent = '❌ Please select a date';
            status.className = 'status-message error';
            status.style.display = 'block';
            return;
        }
        
        const { hours, minutes } = parse12HourTime(hour, minute, ampm);
        const scheduledDate = new Date(date);
        scheduledDate.setHours(hours, minutes, 0, 0);
        
        // ✅ ALLOW PAST DATES - No validation!
        // Just show a warning if it's in the past
        const isPast = scheduledDate < new Date();
        if (isPast) {
            if (!confirm(`⚠️ This date/time (${scheduledDate.toLocaleString()}) is in the past.\n\nAre you sure you want to schedule a post for a past time?`)) {
                return;
            }
        }
        
        const pipelineId = document.getElementById('scheduler-pipeline-select').value;
        
        this.disabled = true;
        this.textContent = '⏳ Scheduling...';
        status.style.display = 'none';
        
        try {
            const response = await fetch('/api/scheduler/manual', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({
                    pipeline_id: pipelineId,
                    schedules: [{
                        reel_url: url,
                        scheduled_time: scheduledDate.toISOString(),
                        caption: caption
                    }]
                })
            });
            
            const data = await response.json();
            
            if (response.ok && data.status === 'success') {
                const displayTime = format12HourTime(hours, minutes);
                const pastLabel = isPast ? ' (Past Date)' : '';
                status.textContent = `✅ Post scheduled for ${date} at ${displayTime}${pastLabel}!`;
                status.className = 'status-message success';
                status.style.display = 'block';
                
                setTimeout(() => {
                    modal.hidden = true;
                    loadUnpostedReels(pipelineId);
                }, 1500);
            } else {
                status.textContent = `❌ ${data.error || 'Failed to schedule'}`;
                status.className = 'status-message error';
                status.style.display = 'block';
            }
        } catch (error) {
            status.textContent = `❌ Error: ${error.message}`;
            status.className = 'status-message error';
            status.style.display = 'block';
        } finally {
            this.disabled = false;
            this.textContent = '📅 Schedule';
        }
    };
    
    // ============================================================
    // POST NOW BUTTON
    // ============================================================
    document.getElementById('single-schedule-now-btn').onclick = async function() {
        const caption = document.getElementById('single-schedule-caption').value.trim();
        const status = document.getElementById('single-schedule-status');
        const pipelineId = document.getElementById('scheduler-pipeline-select').value;
        
        // Use current time
        const scheduledDate = new Date();
        
        this.disabled = true;
        this.textContent = '⏳ Posting...';
        status.style.display = 'none';
        
        try {
            const response = await fetch('/api/scheduler/manual', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({
                    pipeline_id: pipelineId,
                    schedules: [{
                        reel_url: url,
                        scheduled_time: scheduledDate.toISOString(),
                        caption: caption
                    }]
                })
            });
            
            const data = await response.json();
            
            if (response.ok && data.status === 'success') {
                status.textContent = `🚀 Post scheduled for NOW (${scheduledDate.toLocaleString()})!`;
                status.className = 'status-message success';
                status.style.display = 'block';
                
                setTimeout(() => {
                    modal.hidden = true;
                    loadUnpostedReels(pipelineId);
                }, 1500);
            } else {
                status.textContent = `❌ ${data.error || 'Failed to post'}`;
                status.className = 'status-message error';
                status.style.display = 'block';
            }
        } catch (error) {
            status.textContent = `❌ Error: ${error.message}`;
            status.className = 'status-message error';
            status.style.display = 'block';
        } finally {
            this.disabled = false;
            this.textContent = '🚀 Post Now';
        }
    };
}

// ==================== UNSCHEDULE SINGLE REEL ====================

async function unscheduleSingleReel(url) {
    if (!confirm(`Remove this reel from the schedule?`)) return;
    
    const pipelineId = document.getElementById('scheduler-pipeline-select').value;
    
    try {
        const response = await fetch(`/api/scheduled-posts?pipeline_id=${pipelineId}&status=pending`, {
            credentials: 'same-origin'
        });
        const data = await response.json();
        
        const post = data.scheduled_posts?.find(p => p.reel_url === url);
        if (!post) {
            showToast('❌ Post not found in schedule', 'error');
            return;
        }
        
        const deleteResponse = await fetch(`/api/scheduled-posts/${post.id}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });
        const deleteData = await deleteResponse.json();
        
        if (deleteData.status === 'success') {
            showToast('✅ Removed from schedule', 'success');
            loadUnpostedReels(pipelineId);
        } else {
            showToast('❌ Failed to remove: ' + deleteData.error, 'error');
        }
    } catch (error) {
        console.error('Failed to unschedule:', error);
        showToast('❌ Error: ' + error.message, 'error');
    }
}

// ==================== SETUP EVENT LISTENERS ====================

function setupSchedulerEventListeners() {
    document.getElementById('scheduler-pipeline-select')?.addEventListener('change', function() {
        if (this.value) {
            loadUnpostedReels(this.value);
        }
    });
    
    document.getElementById('load-unposted-btn')?.addEventListener('click', function() {
        const pipelineId = document.getElementById('scheduler-pipeline-select').value;
        if (pipelineId) {
            loadUnpostedReels(pipelineId);
        } else {
            showToast('⚠️ Please select a pipeline first', 'warning');
        }
    });
    
    document.getElementById('refresh-unposted-btn')?.addEventListener('click', function() {
        const pipelineId = document.getElementById('scheduler-pipeline-select').value;
        if (pipelineId) {
            loadUnpostedReels(pipelineId);
        } else {
            loadSchedulerPipelines();
        }
    });
    
    document.getElementById('scheduler-prev-page')?.addEventListener('click', function() {
        if (schedulerCurrentPage > 1) {
            goToPage(schedulerCurrentPage - 1);
        }
    });
    
    document.getElementById('scheduler-next-page')?.addEventListener('click', function() {
        const totalPages = Math.ceil(schedulerFilteredReels.length / schedulerPageLimit) || 1;
        if (schedulerCurrentPage < totalPages) {
            goToPage(schedulerCurrentPage + 1);
        }
    });
    
    document.getElementById('scheduler-page-limit')?.addEventListener('change', function() {
        schedulerCurrentPage = 1;
        renderSchedulerReels(getPaginatedReels());
    });
    
    document.getElementById('scheduler-search')?.addEventListener('input', function() {
        schedulerCurrentPage = 1;
        renderSchedulerReels(getPaginatedReels());
    });
    
    document.getElementById('clear-selection-btn')?.addEventListener('click', function() {
        document.querySelectorAll('.reel-select-checkbox:not(:disabled)').forEach(cb => {
            cb.checked = false;
        });
        updateSelectedCount();
        showToast('✅ Selection cleared', 'success');
    });
}

// ==================== BATCH SCHEDULING (ALLOWS PAST DATES) ====================

// Schedule selected reels sequentially
document.getElementById('schedule-sequential-btn')?.addEventListener('click', async function() {
    const pipelineId = document.getElementById('scheduler-pipeline-select').value;
    const date = document.getElementById('batch-start-date').value;
    const hour = document.getElementById('batch-start-hour').value;
    const minute = document.getElementById('batch-start-minute').value;
    const ampm = document.getElementById('batch-start-ampm').value;
    const intervalMinutes = parseInt(document.getElementById('batch-interval').value) || 60;
    
    if (!pipelineId) {
        showToast('❌ Please select a pipeline', 'error');
        return;
    }
    
    if (!date) {
        showToast('❌ Please select a date', 'error');
        return;
    }
    
    const { hours, minutes } = parse12HourTime(hour, minute, ampm);
    
    const checkboxes = document.querySelectorAll('.reel-select-checkbox:checked:not(:disabled)');
    if (checkboxes.length === 0) {
        showToast('❌ Please select at least one reel', 'error');
        return;
    }
    
    const startTime = new Date(date);
    startTime.setHours(hours, minutes, 0, 0);
    
    // ✅ Check if time is in the past - show warning but allow
    if (startTime < new Date()) {
        if (!confirm(`⚠️ The start time (${startTime.toLocaleString()}) is in the past.\n\nAre you sure you want to schedule posts for past times?`)) {
            return;
        }
    }
    
    const displayTime = format12HourTime(hours, minutes);
    if (!confirm(`Schedule ${checkboxes.length} reels sequentially starting at ${date} ${displayTime} (${intervalMinutes} min intervals)?`)) {
        return;
    }
    
    this.disabled = true;
    this.textContent = '⏳ Scheduling...';
    
    const schedules = [];
    let currentTime = new Date(startTime);
    
    checkboxes.forEach((cb, index) => {
        const url = cb.dataset.url;
        const reel = unpostedReels.find(r => r.url === url);
        const scheduledTime = new Date(currentTime);
        
        schedules.push({
            reel_url: url,
            scheduled_time: scheduledTime.toISOString(),
            caption: reel?.caption || ''
        });
        
        currentTime = new Date(currentTime.getTime() + intervalMinutes * 60 * 1000);
    });
    
    try {
        const response = await fetch('/api/scheduler/manual', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({
                pipeline_id: pipelineId,
                schedules: schedules
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.status === 'success') {
            showToast(`✅ Scheduled ${data.scheduled} posts sequentially`, 'success');
            loadUnpostedReels(pipelineId);
        } else {
            showToast(`❌ ${data.error || 'Failed to schedule'}`, 'error');
        }
    } catch (error) {
        showToast(`❌ Error: ${error.message}`, 'error');
    } finally {
        this.disabled = false;
        this.textContent = '⏱️ Schedule Sequential';
    }
});

// Schedule selected reels randomly
document.getElementById('schedule-random-btn')?.addEventListener('click', async function() {
    const pipelineId = document.getElementById('scheduler-pipeline-select').value;
    const date = document.getElementById('batch-start-date').value;
    const rangeStart = parseInt(document.getElementById('batch-range-start').value);
    const rangeEnd = parseInt(document.getElementById('batch-range-end').value);
    
    if (!pipelineId) {
        showToast('❌ Please select a pipeline', 'error');
        return;
    }
    
    if (!date) {
        showToast('❌ Please select a date', 'error');
        return;
    }
    
    const checkboxes = document.querySelectorAll('.reel-select-checkbox:checked:not(:disabled)');
    if (checkboxes.length === 0) {
        showToast('❌ Please select at least one reel', 'error');
        return;
    }
    
    if (rangeStart >= rangeEnd) {
        showToast('❌ Start time must be before end time', 'error');
        return;
    }
    
    const startDisplay = format12HourTime(rangeStart, 0);
    const endDisplay = format12HourTime(rangeEnd, 0);
    
    // ✅ Check if the date is in the past - show warning but allow
    const selectedDate = new Date(date);
    if (selectedDate < new Date()) {
        if (!confirm(`⚠️ The selected date (${date}) is in the past.\n\nAre you sure you want to schedule posts for past dates?`)) {
            return;
        }
    }
    
    if (!confirm(`Randomly schedule ${checkboxes.length} reels between ${startDisplay} and ${endDisplay} on ${date}?`)) {
        return;
    }
    
    this.disabled = true;
    this.textContent = '⏳ Generating...';
    
    try {
        const timeResponse = await fetch('/api/scheduler/generate-random-times', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({
                num_posts: checkboxes.length,
                start_hour: rangeStart,
                end_hour: rangeEnd
            })
        });
        const timeData = await timeResponse.json();
        
        if (timeData.status !== 'success') {
            showToast('❌ Failed to generate random times', 'error');
            return;
        }
        
        const baseDate = new Date(date);
        baseDate.setHours(0, 0, 0, 0);
        
        const schedules = [];
        const urls = [];
        checkboxes.forEach(cb => urls.push(cb.dataset.url));
        
        const shuffledUrls = [...urls].sort(() => Math.random() - 0.5);
        
        shuffledUrls.forEach((url, index) => {
            const reel = unpostedReels.find(r => r.url === url);
            const timeStr = timeData.times[index];
            const scheduledTime = new Date(timeStr);
            
            scheduledTime.setFullYear(baseDate.getFullYear());
            scheduledTime.setMonth(baseDate.getMonth());
            scheduledTime.setDate(baseDate.getDate());
            
            // ✅ Allow past dates - no adjustment
            // If time is in the past, still allow it (backfill)
            
            schedules.push({
                reel_url: url,
                scheduled_time: scheduledTime.toISOString(),
                caption: reel?.caption || ''
            });
        });
        
        const response = await fetch('/api/scheduler/manual', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({
                pipeline_id: pipelineId,
                schedules: schedules
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.status === 'success') {
            showToast(`✅ Scheduled ${data.scheduled} posts at random times`, 'success');
            loadUnpostedReels(pipelineId);
        } else {
            showToast(`❌ ${data.error || 'Failed to schedule'}`, 'error');
        }
    } catch (error) {
        showToast(`❌ Error: ${error.message}`, 'error');
    } finally {
        this.disabled = false;
        this.textContent = '🎲 Schedule Random';
    }
});

// Auto-schedule all
document.getElementById('auto-schedule-all-btn')?.addEventListener('click', async function() {
    const pipelineId = document.getElementById('scheduler-pipeline-select').value;
    const rangeStart = parseInt(document.getElementById('batch-range-start').value) || 8;
    const rangeEnd = parseInt(document.getElementById('batch-range-end').value) || 22;
    const date = document.getElementById('batch-start-date').value;
    
    if (!pipelineId) {
        showToast('❌ Please select a pipeline', 'error');
        return;
    }
    
    if (!date) {
        showToast('❌ Please select a date', 'error');
        return;
    }
    
    const availableReels = unpostedReels.filter(r => !r.is_scheduled);
    if (availableReels.length === 0) {
        showToast('🎉 All reels are already scheduled!', 'success');
        return;
    }
    
    const startDisplay = format12HourTime(rangeStart, 0);
    const endDisplay = format12HourTime(rangeEnd, 0);
    
    // ✅ Check if date is in the past - show warning but allow
    const selectedDate = new Date(date);
    if (selectedDate < new Date()) {
        if (!confirm(`⚠️ The selected date (${date}) is in the past.\n\nAre you sure you want to schedule ${availableReels.length} posts for past dates?`)) {
            return;
        }
    }
    
    if (!confirm(`Auto-schedule ${availableReels.length} reels between ${startDisplay} and ${endDisplay} on ${date}?`)) {
        return;
    }
    
    this.disabled = true;
    this.textContent = '⏳ Scheduling...';
    
    try {
        const timeResponse = await fetch('/api/scheduler/generate-random-times', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({
                num_posts: availableReels.length,
                start_hour: rangeStart,
                end_hour: rangeEnd
            })
        });
        const timeData = await timeResponse.json();
        
        const schedules = [];
        const baseDate = new Date(date);
        baseDate.setHours(0, 0, 0, 0);
        
        availableReels.forEach((reel, index) => {
            const timeStr = timeData.times[index];
            const scheduledTime = new Date(timeStr);
            scheduledTime.setFullYear(baseDate.getFullYear());
            scheduledTime.setMonth(baseDate.getMonth());
            scheduledTime.setDate(baseDate.getDate());
            
            // ✅ Allow past dates - no adjustment
            
            schedules.push({
                reel_url: reel.url,
                scheduled_time: scheduledTime.toISOString(),
                caption: reel.caption || ''
            });
        });
        
        const response = await fetch('/api/scheduler/manual', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({
                pipeline_id: pipelineId,
                schedules: schedules
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.status === 'success') {
            showToast(`✅ Auto-scheduled ${data.scheduled} posts`, 'success');
            loadUnpostedReels(pipelineId);
        } else {
            showToast(`❌ ${data.error || 'Failed to schedule'}`, 'error');
        }
    } catch (error) {
        showToast(`❌ Error: ${error.message}`, 'error');
    } finally {
        this.disabled = false;
        this.textContent = '🎯 Auto-Schedule All';
    }
});

// ==================== TOAST NOTIFICATION ====================

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 8px;
        color: #fff;
        font-size: 14px;
        z-index: 9999;
        animation: slideIn 0.3s ease;
        max-width: 400px;
        background: ${type === 'success' ? 'rgba(34, 197, 94, 0.9)' : 
                     type === 'error' ? 'rgba(239, 68, 68, 0.9)' : 
                     type === 'warning' ? 'rgba(245, 158, 11, 0.9)' : 
                     'rgba(59, 130, 246, 0.9)'};
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ==================== INITIALIZE ====================

document.addEventListener('DOMContentLoaded', function() {
    const body = document.getElementById('manual-scheduler-body');
    if (body) {
        body.style.display = 'none';
    }
    
    initManualScheduler();
});






// ==================== BUFFER KEYS (TIKTOK) ====================

let bufferKeys = [];

async function loadBufferKeys() {
    const container = document.getElementById('buffer-keys-list');
    const badge = document.getElementById('buffer-keys-count');
    if (!container) return;

    try {
        const res = await fetch('/api/buffer/keys', { credentials: 'same-origin' });
        const data = await res.json();

        if (data.status === 'success') {
            bufferKeys = data.keys || [];
            if (badge) badge.textContent = `${data.total} keys`;
            renderBufferKeys(bufferKeys);
        } else {
            container.innerHTML = `<div class="empty-state">❌ ${data.error || 'Failed to load keys'}</div>`;
        }
    } catch (err) {
        console.error('loadBufferKeys:', err);
        container.innerHTML = `<div class="empty-state">❌ ${err.message}</div>`;
    }
}

function renderBufferKeys(keys) {
    const container = document.getElementById('buffer-keys-list');
    if (!container) return;

    if (!keys || keys.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div style="font-size: 32px; margin-bottom: 12px;">🎵</div>
                <strong>No Buffer keys added</strong>
                <p style="margin-top: 8px; font-size: 13px; color: var(--text-secondary);">
                    Add your Buffer API key to start posting to TikTok.
                </p>
                <button id="empty-add-buffer-key-btn" class="btn btn-sm btn-primary" style="margin-top: 12px;">➕ Add Key</button>
            </div>`;
        document.getElementById('empty-add-buffer-key-btn')?.addEventListener('click', () => {
            document.getElementById('add-buffer-key-modal').hidden = false;
        });
        return;
    }

    let html = `<div class="zernio-keys-grid">`;
    keys.forEach(key => {
        const channels = key.channels || [];
        const isActive = key.is_active;
        html += `
            <div class="zernio-key-card ${isActive ? '' : 'inactive'}">
                <div class="zernio-key-header">
                    <div class="zernio-key-name">
                        <span class="key-icon">${isActive ? '🟢' : '🔴'}</span>
                        <span class="key-title">${escapeHtml(key.name)}</span>
                        <span class="key-status-badge ${isActive ? 'active' : 'inactive'}">
                            ${isActive ? 'Active' : 'Inactive'}
                        </span>
                        <span class="key-account-count-badge">
                            ${channels.length} channel${channels.length !== 1 ? 's' : ''}
                        </span>
                    </div>
                    <div class="zernio-key-actions">
                        <button class="btn btn-sm btn-ghost toggle-buffer-key-btn"
                                data-id="${key.id}" data-active="${isActive}" title="Toggle">${isActive ? '⏸' : '▶'}</button>
                        <button class="btn btn-sm btn-danger delete-buffer-key-btn"
                                data-id="${key.id}" data-name="${escapeHtml(key.name)}">🗑️</button>
                    </div>
                </div>
                <div class="zernio-key-body">
                    <div class="key-detail">
                        <span class="key-label">API Key:</span>
                        <span class="key-value key-masked">${key.api_key_masked || '***'}</span>
                    </div>
                    <div class="key-accounts-section">
                        <div class="key-detail" style="border-bottom: none; font-weight: 600;">
                            <span class="key-label">TikTok Channels:</span>
                            <span class="key-value" style="color: var(--accent);">${channels.length}</span>
                        </div>
                        ${channels.length ? `
                            <div class="key-accounts-list">
                                ${channels.map(c => `
                                    <div class="key-account-item">
                                        <span class="account-icon">🎵</span>
                                        <span class="account-name">${escapeHtml(c.name || c.id)}</span>
                                        <span class="account-id">${escapeHtml(c.id)}</span>
                                        <span class="account-status">✅</span>
                                    </div>`).join('')}
                            </div>` : `
                            <div class="key-accounts-empty">
                                <span style="color: var(--text-muted); font-size: 13px;">No TikTok channels</span>
                            </div>`}
                    </div>
                </div>
            </div>`;
    });
    html += `</div>`;
    container.innerHTML = html;

    document.querySelectorAll('.delete-buffer-key-btn').forEach(btn =>
        btn.addEventListener('click', () => deleteBufferKey(btn.dataset.id, btn.dataset.name)));
    document.querySelectorAll('.toggle-buffer-key-btn').forEach(btn =>
        btn.addEventListener('click', () => toggleBufferKey(btn.dataset.id, btn.dataset.active === 'true')));
}

// --- Add key modal ---
document.getElementById('add-buffer-key-btn')?.addEventListener('click', () => {
    document.getElementById('add-buffer-key-modal').hidden = false;
    document.getElementById('add-buffer-key-status').style.display = 'none';
    document.getElementById('buffer-key-api').value = '';
    document.getElementById('buffer-key-name').value = '';
});

document.getElementById('add-buffer-key-modal-close')?.addEventListener('click', () => {
    document.getElementById('add-buffer-key-modal').hidden = true;
});

document.getElementById('add-buffer-key-modal')?.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) e.target.hidden = true;
});

document.getElementById('save-buffer-key-btn')?.addEventListener('click', async function () {
    const apiKey = document.getElementById('buffer-key-api').value.trim();
    const name = document.getElementById('buffer-key-name').value.trim();
    const status = document.getElementById('add-buffer-key-status');

    if (!apiKey) {
        status.textContent = '❌ Please enter your Buffer API key';
        status.className = 'status-message error';
        status.style.display = 'block';
        return;
    }

    this.disabled = true;
    this.textContent = '⏳ Checking key...';
    status.style.display = 'none';

    try {
        const res = await fetch('/api/buffer/keys', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ api_key: apiKey, name })
        });
        const data = await res.json();

        if (res.ok) {
            status.textContent = `✅ ${data.message}`;
            status.className = 'status-message success';
            status.style.display = 'block';

            await loadBufferKeys();
            await loadTikTokChannels();

            setTimeout(() => {
                document.getElementById('add-buffer-key-modal').hidden = true;
            }, 1500);
        } else {
            status.textContent = `❌ ${data.error || 'Failed to add key'}`;
            status.className = 'status-message error';
            status.style.display = 'block';
        }
    } catch (err) {
        status.textContent = `❌ ${err.message}`;
        status.className = 'status-message error';
        status.style.display = 'block';
    } finally {
        this.disabled = false;
        this.textContent = 'Save Key';
    }
});

async function deleteBufferKey(keyId, keyName) {
    if (!confirm(`Delete Buffer key "${keyName}"?`)) return;
    try {
        const res = await fetch(`/api/buffer/keys/${keyId}`, {
            method: 'DELETE',
            credentials: 'same-origin'
        });
        const data = await res.json();
        if (res.ok) {
            showToast(`✅ Buffer key "${keyName}" deleted`, 'success');
            await loadBufferKeys();
            await loadTikTokChannels();
        } else {
            showToast(`❌ ${data.error || 'Failed to delete'}`, 'error');
        }
    } catch (err) {
        showToast(`❌ ${err.message}`, 'error');
    }
}

async function toggleBufferKey(keyId, currentActive) {
    try {
        const res = await fetch(`/api/buffer/keys/${keyId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ is_active: !currentActive })
        });
        const data = await res.json();
        if (res.ok) {
            showToast(`✅ Key ${!currentActive ? 'activated' : 'deactivated'}`, 'success');
            await loadBufferKeys();
            await loadTikTokChannels();
        } else {
            showToast(`❌ ${data.error}`, 'error');
        }
    } catch (err) {
        showToast(`❌ ${err.message}`, 'error');
    }
}

document.getElementById('refresh-buffer-keys-btn')?.addEventListener('click', async function () {
    this.disabled = true;
    this.textContent = '⏳';
    await loadBufferKeys();
    await loadTikTokChannels();
    this.disabled = false;
    this.textContent = '🔄 Refresh';
});


// ==================== TIKTOK POSTING ====================

function showTikTokSection() {
    const section = document.getElementById('tiktok-section');
    if (!section) return;
    section.hidden = false;
    loadTikTokChannels();
}

function showTikTokStatus(message, type) {
    const el = document.getElementById('tiktok-status');
    if (!el) return;
    el.textContent = message;
    el.className = 'status-message ' + (type || '');
    el.hidden = false;
    if (type === 'success' || type === 'info') {
        setTimeout(() => { el.hidden = true; }, 8000);
    }
}

async function loadTikTokChannels() {
    const select = document.getElementById('tiktok-channel-select');
    const badge = document.getElementById('tiktok-status-badge');
    if (!select) return;

    try {
        const res = await fetch('/api/buffer/channels', { credentials: 'same-origin' });
        const data = await res.json();

        if (data.status !== 'success') throw new Error(data.error || 'Failed to load channels');

        select.innerHTML = '';
        const channels = data.channels || [];

        if (channels.length === 0) {
            const opt = document.createElement('option');
            opt.value = '';
            opt.textContent = 'No TikTok channels — add a Buffer key';
            opt.disabled = true;
            opt.selected = true;
            select.appendChild(opt);
            if (badge) badge.textContent = '⚠️ No channels';
            return;
        }

        channels.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.id;
            opt.textContent = `${c.name} (${c.key_name})`;
            opt.dataset.keyId = c.key_id;
            select.appendChild(opt);
        });

        if (badge) badge.textContent = `✅ ${channels.length} channel(s)`;
    } catch (err) {
        console.error('loadTikTokChannels:', err);
        if (badge) badge.textContent = '❌ Error';
    }
}

document.getElementById('tiktok-text')?.addEventListener('input', function () {
    const counter = document.getElementById('tiktok-char-count');
    if (counter) {
        counter.textContent = `${this.value.length}/150`;
        counter.style.color = this.value.length > 150 ? 'var(--error)' : 'var(--text-muted)';
    }
});

document.getElementById('refresh-tiktok-btn')?.addEventListener('click', function () {
    this.disabled = true;
    this.textContent = '⏳';
    loadTikTokChannels().finally(() => {
        this.disabled = false;
        this.textContent = '🔄';
    });
});

document.getElementById('tiktok-post-btn')?.addEventListener('click', async function () {
    const select = document.getElementById('tiktok-channel-select');
    const channelId = select?.value;
    const keyId = select?.selectedOptions?.[0]?.dataset?.keyId || null;
    const text = document.getElementById('tiktok-text')?.value.trim();
    const mode = document.getElementById('tiktok-mode')?.value || 'addToQueue';
    const thumbOffset = Number(document.getElementById('tiktok-thumb-offset')?.value || 1000);

    if (!currentVideoUrl) {
        showTikTokStatus('❌ No video loaded. Fetch a video first.', 'error');
        return;
    }
    if (!channelId) {
        showTikTokStatus('❌ Select a TikTok channel.', 'error');
        return;
    }
    if (!text || text.length > 150) {
        showTikTokStatus('❌ Caption must be 1–150 characters.', 'error');
        return;
    }

    this.disabled = true;
    this.innerHTML = '<span class="btn-spinner"></span> Posting...';
    showTikTokStatus('⏳ Sending video to Buffer/TikTok...', 'info');

    try {
        const res = await fetch('/api/tiktok/post', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({
                channelId,
                videoUrl: currentVideoUrl,
                text,
                mode,
                thumbnailOffset: thumbOffset,
                key_id: keyId,
            }),
        });
        const data = await res.json();

        if (res.ok && data.status === 'success' && data.post) {
            showTikTokStatus(
                `✅ Posted! ID: ${data.post.id || 'N/A'} · Status: ${data.post.status || 'unknown'}`,
                'success'
            );
        } else {
            showTikTokStatus(`❌ ${data.error || 'Failed to post to TikTok'}`, 'error');
        }
    } catch (err) {
        showTikTokStatus(`❌ ${err.message}`, 'error');
    } finally {
        this.disabled = false;
        this.innerHTML = `
            <span class="btn-content">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                    <path d="M3 10L7 14L17 6" stroke="currentColor" stroke-width="2"
                          stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                Post to TikTok
            </span>`;
    }
});

console.log('✅ Buffer/TikTok integration loaded');