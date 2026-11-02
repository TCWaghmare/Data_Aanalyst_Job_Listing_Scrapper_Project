// Job Finder — LinkedIn Feed & Jobs Harvester Content Script (v2.1)
// Comprehensive harvester for Official Job Cards & Recruiter Posts across LinkedIn Feed & Search.

const ROLE_REGEX = /(?:data\s*(?:analyst|analytics|engineer|scientist|intern|trainee|associate|specialist|consultant)|business\s*(?:analyst|intelligence)|bi\s*(?:analyst|developer)|power\s*bi|tableau|sql\s*(?:developer|analyst)?|reporting\s*analyst|mis\s*(?:analyst|executive)|analytics\s*engineer|data\s*visualization|decision\s*scientist|junior\s*analyst|associate\s*analyst|financial\s*analyst|operations\s*analyst|product\s*analyst|marketing\s*analyst|research\s*analyst|fresher\s*analyst|entry\s*level\s*analyst|\banalyst\b)/i;
const HIRING_REGEX = /(?:hiring|actively\s*hiring|hiring\s*now|open\s*position|job\s*opening|openings|vacancy|vacancies|recruitment|recruiting|looking\s*for|immediate\s*hiring|we\s*are\s*hiring|we['’]re\s*hiring|join\s*our\s*team|apply\s*now|apply\s*here|register\s*here|apply\s*link|apply\s*through|how\s*to\s*apply|send\s*(?:your\s*)?(?:resume|cv)|share\s*(?:your\s*)?(?:resume|cv)|fresher\s*hiring|walk-?in|hiring\s*alert|job\s*alert|opportunity|opportunities|easy\s*apply|job\s*listing|role\s*:|position\s*:|experience\s*:|qualification\s*:|requirements?\s*:|eligibility\s*:)/i;
const DISQUALIFIER_REGEX = /(?:certificate\s*of\s*completion|completed\s*the\s*course|thrilled\s*to\s*share\s*that\s*i\s*(?:have\s*)?completed|course\s*completed|internship\s*certificate|completed\s*an\s*online|webinar\s*recording|happy\s*to\s*share\s*my\s*certificate|thought\s*for\s*the\s*day|monday\s*motivation)/i;

// Expand all visible "...see more" buttons
function expandAllSeeMore() {
  document.querySelectorAll(
    'button[aria-label*="more" i], ' +
    'button.feed-shared-inline-show-more-text__see-more-less-toggle, ' +
    'button.update-components-text__see-more-button, ' +
    'button.see-more, ' +
    '[data-view-name*="see-more"], ' +
    '.feed-shared-see-more-less-toggle, ' +
    'span.feed-shared-inline-show-more-text__see-more-less-toggle'
  ).forEach(b => {
    try { b.click(); } catch (e) {}
  });
}

// Generate simple hash for deduplication
function simpleHash(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash) + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash).toString(36);
}

// Comprehensive extractor: finds official cards AND recruiter posts
function extractAllJobsOnScreen() {
  expandAllSeeMore();

  const postsToIngest = [];
  const seenUrls = new Set();
  const seenSignatures = new Set();

  // 1. Gather all candidate card elements across feed, search, and job pages
  const candidateSet = new Set();
  const containerSelectors = [
    'div.feed-shared-update-v2',
    'div[data-view-name="search-entity-result"]',
    'li.reusable-search__result-container',
    'div[data-view-name*="feed-full-update"]',
    'div.job-card-container',
    'li.jobs-search-results__list-item',
    'div[data-job-id]',
    'div.base-card[data-entity-urn*="jobPosting"]',
    'div[data-urn*="activity"]',
    'div[data-urn*="ugcPost"]',
    'div[data-urn*="jobPosting"]',
    'div[data-urn*="share"]',
    'div[data-chameleon-result-urn]',
    'div[data-entity-urn*="activity"]',
    'div[data-id*="activity"]',
    '.search-results__cluster-content li',
    'article'
  ];

  document.querySelectorAll(containerSelectors.join(',')).forEach(el => {
    const parent = el.closest('.feed-shared-update-v2, li.reusable-search__result-container, li.jobs-search-results__list-item, div.artdeco-card') || el;
    candidateSet.add(parent);
  });

  // Also query content markers to locate parent cards
  document.querySelectorAll(
    '.update-components-actor, .feed-shared-actor, a[data-field="actor_name"], ' +
    'a[href*="/jobs/view/"], .update-components-text, .feed-shared-update-v2__description'
  ).forEach(el => {
    const parent = el.closest('li, article, div.feed-shared-update-v2, div[data-urn], div[data-view-name], div.job-card-container, .artdeco-card') || el.parentElement?.parentElement;
    if (parent && parent !== document.body) {
      candidateSet.add(parent);
    }
  });

  const rawCards = Array.from(candidateSet);
  // Keep only distinct top-level cards (filter out sub-elements already contained)
  const cards = rawCards.filter(c => {
    for (const other of rawCards) {
      if (other !== c && other.contains(c)) return false;
    }
    return true;
  });

  // 2. Evaluate each card
  cards.forEach(card => {
    const fullCardText = (card.innerText || '').trim();
    if (fullCardText.length < 25) return;
    if (DISQUALIFIER_REGEX.test(fullCardText)) return;

    // Check if this card contains an Official LinkedIn Job Link (/jobs/view/)
    const jobLinkEl = card.querySelector('a[href*="/jobs/view/"], a[href*="linkedin.com/jobs/view/"]');

    if (jobLinkEl && jobLinkEl.href) {
      const jm = jobLinkEl.href.match(/https?:\/\/(?:[a-z]{2,3}\.)?linkedin\.com\/jobs\/view\/(\d+)/i);
      if (jm) {
        const postUrl = `https://www.linkedin.com/jobs/view/${jm[1]}/`;
        if (seenUrls.has(postUrl)) return;

        // Title
        let title = '';
        const titleEl = card.querySelector(
          '.job-card-list__title, ' +
          '.artdeco-entity-lockup__title, ' +
          '.entity-result__title-text, ' +
          'a[href*="/jobs/view/"]'
        );
        if (titleEl) {
          title = titleEl.innerText.trim().split('\n')[0].trim();
        }

        // Validate role matches data/analytics
        if (!title || !ROLE_REGEX.test(title)) {
          if (!ROLE_REGEX.test(fullCardText)) return;
          if (!title) title = 'Data Analyst';
        }

        // Company
        let company = '';
        const compEl = card.querySelector(
          '.job-card-container__company-name, ' +
          '.artdeco-entity-lockup__subtitle, ' +
          '.entity-result__primary-subtitle, ' +
          'span.job-card-container__primary-description'
        );
        if (compEl) {
          company = compEl.innerText.trim().split('\n')[0].trim();
        }

        // Location
        let location = '';
        const locEl = card.querySelector(
          '.job-card-container__metadata-item, ' +
          '.artdeco-entity-lockup__caption, ' +
          '.entity-result__secondary-subtitle'
        );
        if (locEl) {
          location = locEl.innerText.trim().split('\n')[0].trim();
        }

        seenUrls.add(postUrl);
        postsToIngest.push({
          post_text: `Official LinkedIn Job Listing:\nTitle: ${title}\nCompany: ${company || 'Enterprise'}\nLocation: ${location || 'India (Hybrid/Remote)'}\nApplication Link: ${postUrl}\n\nJob Details: ${fullCardText.replace(/\s+/g, ' ').slice(0, 350)}`,
          post_url: postUrl,
          company: company || 'Enterprise',
          location: location || 'India',
          recruiter_name: company ? `${company} Talent Acquisition` : 'LinkedIn Recruiter',
          designation: 'Recruitment Partner',
          linkedin_profile: '',
          apply_url: postUrl
        });
        return;
      }
    }

    // -------------------------------------------------------------
    // Recruiter / Feed Post Evaluation
    // -------------------------------------------------------------
    // Must match our analytical role filter
    if (!ROLE_REGEX.test(fullCardText)) return;

    // Check hiring signals or application links
    const hasHiringWords = HIRING_REGEX.test(fullCardText);
    const hasApplyLink = /https?:\/\/(?:lnkd\.in|forms\.gle|bit\.ly|[a-zA-Z0-9\-_.]+\.[a-zA-Z]{2,}(?:\/[^\s)"]*)?)/i.test(fullCardText);
    const hasEmail = /[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/.test(fullCardText);

    if (!hasHiringWords && !hasApplyLink && !hasEmail) return;

    const sig = fullCardText.replace(/\s+/g, ' ').slice(0, 100);
    if (seenSignatures.has(sig)) return;
    seenSignatures.add(sig);

    // Extract exact Activity / Post URL
    let postUrl = '';
    const urnAttrEl = card.matches('[data-urn*="activity"], [data-urn*="ugcPost"], [data-chameleon-result-urn*="activity"], [data-entity-urn*="activity"], [data-id*="activity"]')
      ? card
      : card.querySelector('[data-urn*="activity"], [data-urn*="ugcPost"], [data-chameleon-result-urn*="activity"], [data-entity-urn*="activity"], [data-id*="activity"]');

    const urnVal = urnAttrEl
      ? (urnAttrEl.getAttribute('data-urn') || urnAttrEl.getAttribute('data-chameleon-result-urn') || urnAttrEl.getAttribute('data-entity-urn') || urnAttrEl.getAttribute('data-id') || '')
      : '';
    const matchUrn = urnVal.match(/urn:li:(?:activity|ugcPost|share):(\d+)/);
    if (matchUrn) {
      postUrl = `https://www.linkedin.com/feed/update/urn:li:activity:${matchUrn[1]}/`;
    }

    if (!postUrl) {
      const permalink = card.querySelector(
        'a.update-components-actor__sub-description-link, ' +
        'a[href*="/feed/update/urn:li:activity:"], ' +
        'a[href*="/feed/update/urn:li:ugcPost:"], ' +
        'a[href*="/posts/"], ' +
        'a[href*="activity-"], ' +
        'a.app-aware-link[href*="activity"], ' +
        'a.app-aware-link[href*="/posts/"]'
      );
      if (permalink && permalink.href) {
        const href = permalink.href;
        const actMatch = href.match(/urn:li:activity:(\d+)/);
        const postSlugMatch = href.match(/https?:\/\/(?:[a-z]{2,3}\.)?linkedin\.com\/posts\/[a-zA-Z0-9_\-]+/i);
        if (actMatch) {
          postUrl = `https://www.linkedin.com/feed/update/urn:li:activity:${actMatch[1]}/`;
        } else if (postSlugMatch) {
          postUrl = postSlugMatch[0];
        } else if (href.includes('/feed/update/') || href.includes('/posts/')) {
          postUrl = href.split('?')[0];
        }
      }
    }

    if (!postUrl) {
      const htmlMatch = card.innerHTML.match(/urn:li:(?:activity|ugcPost|share):(\d{15,22})/);
      if (htmlMatch) {
        postUrl = `https://www.linkedin.com/feed/update/urn:li:activity:${htmlMatch[1]}/`;
      }
    }

    // Direct apply link extraction
    let applyUrl = '';
    const applyMatch = fullCardText.match(/https?:\/\/(?:lnkd\.in\/[a-zA-Z0-9_\-]+|forms\.gle\/[a-zA-Z0-9_\-]+|bit\.ly\/[a-zA-Z0-9_\-]+|[a-zA-Z0-9\-_.]+\.[a-zA-Z]{2,}(?:\/[^\s)"]*)?)/i);
    if (applyMatch) {
      applyUrl = applyMatch[0].replace(/[.,;:)]+$/, '');
    }

    // If no post URL was found, use the direct lnkd.in or apply link
    if (!postUrl && applyUrl && applyUrl.includes('lnkd.in')) {
      postUrl = applyUrl;
    }

    // Fallback: If still no URL, synthesize deterministic activity URL using text hash
    if (!postUrl) {
      const hash = simpleHash(fullCardText.slice(0, 150));
      postUrl = `https://www.linkedin.com/feed/update/urn:li:activity:${hash}/`;
    }

    // Clean post URL
    if (postUrl && (postUrl.includes('/feed/?') || postUrl.endsWith('/feed') || postUrl.endsWith('/feed/') || postUrl.includes('/search/') || postUrl.includes('127.0.0.1'))) {
      if (applyUrl) {
        postUrl = applyUrl;
      } else {
        const hash = simpleHash(fullCardText.slice(0, 150));
        postUrl = `https://www.linkedin.com/feed/update/urn:li:activity:${hash}/`;
      }
    }

    if (seenUrls.has(postUrl)) return;
    seenUrls.add(postUrl);

    // Recruiter Name
    let recruiterName = '';
    const authorEl = card.querySelector(
      '.update-components-actor__name, ' +
      '.feed-shared-actor__name, ' +
      'a[data-field="actor_name"], ' +
      '.entity-result__title-text, ' +
      'span.update-components-actor__single-line-truncate, ' +
      'h3, h4'
    );
    if (authorEl && authorEl.innerText.trim()) {
      recruiterName = authorEl.innerText.trim().split('\n')[0].trim();
    }

    // Recruiter Designation
    let recruiterDesignation = '';
    const desigEl = card.querySelector(
      '.update-components-actor__description, ' +
      '.feed-shared-actor__description, ' +
      '.update-components-actor__sub-description, ' +
      '.entity-result__primary-subtitle'
    );
    if (desigEl && desigEl.innerText.trim()) {
      recruiterDesignation = desigEl.innerText.trim().split('\n')[0].trim();
    }

    // LinkedIn Profile
    let linkedinProfile = '';
    const profEl = card.querySelector(
      '.update-components-actor a[href*="/in/"], ' +
      '.feed-shared-actor a[href*="/in/"], ' +
      'a.app-aware-link[href*="/in/"], ' +
      'a[href*="linkedin.com/in/"]'
    );
    if (profEl && profEl.href) {
      const pm = profEl.href.match(/https?:\/\/(?:[a-z]{2,3}\.)?linkedin\.com\/in\/[a-zA-Z0-9\-_%]+/i);
      if (pm) linkedinProfile = pm[0].replace(/\/+$/, '') + '/';
    }

    postsToIngest.push({
      post_text: fullCardText,
      post_url: postUrl,
      recruiter_name: recruiterName,
      designation: recruiterDesignation,
      linkedin_profile: linkedinProfile,
      apply_url: applyUrl || postUrl
    });
  });

  return postsToIngest;
}

// -------------------------------------------------------------
// UI Toast Notifications
// -------------------------------------------------------------
function showToast(message, type = 'info', duration = 4000) {
  let toast = document.getElementById('jf-floating-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'jf-floating-toast';
    document.body.appendChild(toast);
  }
  toast.className = `jf-toast jf-toast-${type} jf-toast-visible`;
  toast.innerHTML = message;

  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => {
    toast.classList.remove('jf-toast-visible');
  }, duration);
}

// -------------------------------------------------------------
// In-Page Floating Pill Action Widget (Bottom-Left)
// -------------------------------------------------------------
function injectFloatingPill() {
  if (document.getElementById('jf-harvester-pill')) return;

  const pill = document.createElement('div');
  pill.id = 'jf-harvester-pill';
  pill.innerHTML = `
    <div class="jf-pill-content" id="jf-pill-trigger">
      <span class="jf-pill-logo">🎯</span>
      <span class="jf-pill-label">Job Finder</span>
      <span class="jf-pill-badge" id="jf-detected-count">0</span>
    </div>
    <div class="jf-pill-menu" id="jf-pill-menu">
      <div class="jf-menu-header">
        <strong>LinkedIn Harvester</strong>
        <span class="jf-status-dot online" title="Job Finder Connected"></span>
      </div>
      <div class="jf-menu-stats" id="jf-menu-stats">Detecting jobs on screen...</div>
      <button type="button" class="jf-menu-btn jf-btn-primary" id="jf-btn-harvest-visible">
        ⚡ Harvest Visible Jobs
      </button>
      <button type="button" class="jf-menu-btn jf-btn-secondary" id="jf-btn-harvest-scroll">
        📜 Auto-Scroll & Harvest All
      </button>
      <div class="jf-menu-footer">
        <a href="http://127.0.0.1:8000" target="_blank">Open Job Finder &rarr;</a>
      </div>
    </div>
  `;

  document.body.appendChild(pill);

  const trigger = document.getElementById('jf-pill-trigger');
  const menu = document.getElementById('jf-pill-menu');
  const harvestVisibleBtn = document.getElementById('jf-btn-harvest-visible');
  const harvestScrollBtn = document.getElementById('jf-btn-harvest-scroll');

  trigger.addEventListener('click', (e) => {
    e.stopPropagation();
    menu.classList.toggle('is-open');
    updatePillCounter();
  });

  harvestVisibleBtn.addEventListener('click', async (e) => {
    e.stopPropagation();
    menu.classList.remove('is-open');
    await harvestVisibleJobs();
  });

  harvestScrollBtn.addEventListener('click', async (e) => {
    e.stopPropagation();
    menu.classList.remove('is-open');
    await autoScrollAndHarvest();
  });

  document.addEventListener('click', (e) => {
    if (!pill.contains(e.target)) {
      menu.classList.remove('is-open');
    }
  });

  updatePillCounter();
}

function updatePillCounter() {
  const badge = document.getElementById('jf-detected-count');
  const stats = document.getElementById('jf-menu-stats');
  if (!badge) return;

  const jobs = extractAllJobsOnScreen();
  badge.textContent = jobs.length;
  if (stats) {
    stats.textContent = `${jobs.length} qualified Data / Business Analyst job(s) detected on screen`;
  }
}

// -------------------------------------------------------------
// Harvest Execution
// -------------------------------------------------------------
async function harvestVisibleJobs() {
  showToast('⏳ <strong>Scanning & Harvesting...</strong> Extracting qualified job listings...', 'info', 2000);

  const jobs = extractAllJobsOnScreen();
  if (jobs.length === 0) {
    showToast('ℹ️ <strong>No matching jobs detected:</strong> Scroll down to reveal posts or search "Data Analyst".', 'warning', 4500);
    return { count: 0 };
  }

  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ action: 'INGEST_BATCH', posts: jobs }, (response) => {
      if (response && response.success) {
        const saved = response.data.saved_count || 0;
        const skipped = response.data.skipped_count || 0;
        showToast(
          `🎉 <strong>Synced Successfully!</strong><br>✅ Added <strong>${saved}</strong> fresh jobs into Job Finder!` +
          (skipped > 0 ? `<br><small style="opacity:0.85;">⏭️ ${skipped} duplicates or disqualified</small>` : ''),
          'success',
          5000
        );
        resolve({ count: saved });
      } else {
        showToast(`❌ <strong>Sync Failed:</strong> Please make sure Job Finder is running at http://127.0.0.1:8000`, 'error', 5000);
        resolve({ count: 0 });
      }
    });
  });
}

// Auto-Scroll down page to load 30+ jobs, then harvest
async function autoScrollAndHarvest() {
  showToast('📜 <strong>Auto-Scrolling LinkedIn...</strong> Discovering fresh posts...', 'info', 6000);

  for (let i = 0; i < 5; i++) {
    window.scrollBy({ top: window.innerHeight * 0.9, behavior: 'smooth' });
    await new Promise(r => setTimeout(r, 1200));
    expandAllSeeMore();
  }

  await new Promise(r => setTimeout(r, 600));
  await harvestVisibleJobs();
}

// -------------------------------------------------------------
// Message Listener for Extension Popup
// -------------------------------------------------------------
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'GET_SCREEN_STATS') {
    const jobs = extractAllJobsOnScreen();
    sendResponse({ count: jobs.length });
    return false;
  }

  if (message.action === 'TRIGGER_HARVEST') {
    harvestVisibleJobs().then(sendResponse);
    return true;
  }

  if (message.action === 'TRIGGER_AUTO_SCROLL') {
    autoScrollAndHarvest().then(sendResponse);
    return true;
  }
});

// Periodic observer to ensure pill is always present across SPA navigations
function startPillKeepAlive() {
  injectFloatingPill();
  setInterval(() => {
    if (!document.getElementById('jf-harvester-pill')) {
      injectFloatingPill();
    } else {
      updatePillCounter();
    }
  }, 2500);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', startPillKeepAlive);
} else {
  startPillKeepAlive();
}
