// Job Finder — Background Service Worker (Manifest V3)
// Communicates with local Job Finder backend (127.0.0.1:8000) with full extension privileges.

const HOSTS = ['http://127.0.0.1:8000', 'http://localhost:8000'];

// Check if Job Finder web backend is running
async function checkBackendHealth() {
  for (const host of HOSTS) {
    try {
      const res = await fetch(`${host}/api/stats`, { method: 'GET' });
      if (res.ok) {
        const stats = await res.json();
        return { online: true, host, stats };
      }
    } catch (e) {
      // try next host
    }
  }
  return { online: false, host: null, stats: null };
}

// Ingest a batch of scraped LinkedIn posts & job cards
async function ingestBatch(posts) {
  if (!posts || posts.length === 0) {
    return { success: false, error: 'No posts provided for ingestion' };
  }

  for (const host of HOSTS) {
    try {
      const res = await fetch(`${host}/api/scraper/linkedin/ingest/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ posts })
      });

      if (res.ok) {
        const data = await res.json();
        // Update local statistics
        chrome.storage.local.get(['total_ingested'], (result) => {
          const prev = result.total_ingested || 0;
          chrome.storage.local.set({
            total_ingested: prev + (data.saved_count || 0),
            last_sync: new Date().toISOString(),
            last_saved_count: data.saved_count || 0,
            last_skipped_count: data.skipped_count || 0
          });
        });
        return { success: true, host, data };
      }
    } catch (err) {
      console.warn(`Failed batch ingest on ${host}:`, err);
    }
  }

  // Fallback: Ingest items one-by-one if batch failed
  let saved = 0;
  let skipped = 0;
  for (const post of posts) {
    for (const host of HOSTS) {
      try {
        const res = await fetch(`${host}/api/scraper/linkedin/ingest`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(post)
        });
        if (res.ok) {
          const item = await res.json();
          if (item.success || item.id) {
            saved++;
            break;
          }
        } else if (res.status === 422) {
          skipped++;
          break;
        }
      } catch (e) {}
    }
  }

  return {
    success: saved > 0 || skipped > 0,
    data: { saved_count: saved, skipped_count: skipped, total: posts.length }
  };
}

// Message Dispatcher
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'CHECK_STATUS') {
    checkBackendHealth().then(sendResponse);
    return true; // Keep message channel open for async response
  }

  if (message.action === 'INGEST_BATCH') {
    ingestBatch(message.posts).then(sendResponse);
    return true;
  }
});
