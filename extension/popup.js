// Job Finder — Extension Popup Script (v2.1)
// Connects to local Job Finder backend (127.0.0.1:8000) and orchestrates harvesting on active LinkedIn tab.

document.addEventListener('DOMContentLoaded', async () => {
  const backendStatusEl = document.getElementById('backend-status');
  const backendStatusText = document.getElementById('backend-status-text');
  const statScreenJobs = document.getElementById('stat-screen-jobs');
  const statTotalJobs = document.getElementById('stat-total-jobs');
  const statLastSync = document.getElementById('stat-last-sync');
  const btnHarvestVisible = document.getElementById('btn-harvest-visible');
  const btnAutoScroll = document.getElementById('btn-auto-scroll');
  const statusMsg = document.getElementById('status-msg');

  function setStatus(msg, type = 'info') {
    statusMsg.innerHTML = msg;
    if (type === 'error') {
      statusMsg.style.color = '#ef4444';
    } else if (type === 'success') {
      statusMsg.style.color = '#10b981';
    } else {
      statusMsg.style.color = '#64748b';
    }
  }

  // 1. Check Backend Connectivity
  async function refreshBackendStatus() {
    try {
      chrome.runtime.sendMessage({ action: 'CHECK_STATUS' }, (response) => {
        if (chrome.runtime.lastError || !response || !response.online) {
          backendStatusEl.className = 'status-badge offline';
          backendStatusText.textContent = 'Job Finder Offline (port 8000)';
          statTotalJobs.textContent = 'Disconnected';
        } else {
          backendStatusEl.className = 'status-badge online';
          backendStatusText.textContent = 'Connected (127.0.0.1:8000)';
          if (response.stats && response.stats.total_jobs !== undefined) {
            statTotalJobs.textContent = `${response.stats.total_jobs} active listings`;
          }
        }
      });
    } catch (e) {
      backendStatusEl.className = 'status-badge offline';
      backendStatusText.textContent = 'Backend Offline';
    }
  }

  // 2. Load Local Sync History
  chrome.storage.local.get(['total_ingested', 'last_sync', 'last_saved_count'], (res) => {
    if (res.last_sync) {
      const d = new Date(res.last_sync);
      const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      statLastSync.textContent = `${res.last_saved_count || 0} jobs (${timeStr})`;
    } else {
      statLastSync.textContent = 'None yet';
    }
  });

  // 3. Inspect Active Tab & Auto-Inject Content Script if missing
  const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const isLinkedIn = activeTab && activeTab.url && activeTab.url.includes('linkedin.com');

  if (!isLinkedIn) {
    statScreenJobs.textContent = 'Not on LinkedIn';
    statScreenJobs.style.color = '#94a3b8';
    btnHarvestVisible.disabled = true;
    btnHarvestVisible.style.opacity = '0.5';
    btnHarvestVisible.style.cursor = 'not-allowed';
    btnAutoScroll.disabled = true;
    btnAutoScroll.style.opacity = '0.5';
    btnAutoScroll.style.cursor = 'not-allowed';
    setStatus('👉 Navigate to your LinkedIn feed or search to harvest jobs.');
    refreshBackendStatus();
    return;
  }

  // Helper to ensure content script is injected
  async function ensureContentScript() {
    return new Promise((resolve) => {
      chrome.tabs.sendMessage(activeTab.id, { action: 'GET_SCREEN_STATS' }, async (resp) => {
        if (chrome.runtime.lastError || !resp) {
          // Dynamically inject content.js and content.css into tab
          try {
            await chrome.scripting.executeScript({
              target: { tabId: activeTab.id },
              files: ['content.js']
            });
            await chrome.scripting.insertCSS({
              target: { tabId: activeTab.id },
              files: ['content.css']
            });
            // Brief pause for script initialization
            setTimeout(() => {
              chrome.tabs.sendMessage(activeTab.id, { action: 'GET_SCREEN_STATS' }, (r) => {
                resolve(r || { count: 0 });
              });
            }, 300);
          } catch (err) {
            resolve({ count: 0, error: err });
          }
        } else {
          resolve(resp);
        }
      });
    });
  }

  // Query jobs on screen
  const screenStats = await ensureContentScript();
  if (screenStats && screenStats.count !== undefined) {
    statScreenJobs.textContent = `${screenStats.count} eligible job(s)`;
    statScreenJobs.style.color = screenStats.count > 0 ? '#0a66c2' : '#64748b';
  } else {
    statScreenJobs.textContent = 'Ready to harvest';
  }

  // 4. Action: Harvest Visible Jobs
  btnHarvestVisible.addEventListener('click', async () => {
    btnHarvestVisible.disabled = true;
    btnAutoScroll.disabled = true;
    setStatus('⏳ Scraping visible jobs & syncing...', 'info');

    await ensureContentScript();

    chrome.tabs.sendMessage(activeTab.id, { action: 'TRIGGER_HARVEST' }, (response) => {
      btnHarvestVisible.disabled = false;
      btnAutoScroll.disabled = false;

      if (response && response.count !== undefined) {
        setStatus(`🎉 Harvested <strong>${response.count}</strong> jobs into Job Finder!`, 'success');
        refreshBackendStatus();
      } else {
        setStatus('Scan completed.', 'info');
      }
    });
  });

  // 5. Action: Auto-Scroll & Harvest All
  btnAutoScroll.addEventListener('click', async () => {
    btnHarvestVisible.disabled = true;
    btnAutoScroll.disabled = true;
    setStatus('📜 Auto-scrolling LinkedIn feed to discover more jobs...', 'info');

    await ensureContentScript();

    chrome.tabs.sendMessage(activeTab.id, { action: 'TRIGGER_AUTO_SCROLL' }, (response) => {
      btnHarvestVisible.disabled = false;
      btnAutoScroll.disabled = false;

      if (response && response.count !== undefined) {
        setStatus(`🎉 Discovered & synced <strong>${response.count}</strong> jobs!`, 'success');
        refreshBackendStatus();
      } else {
        setStatus('Auto-scroll harvest completed.', 'info');
      }
    });
  });

  refreshBackendStatus();
});
