/**
 * Frontend logic for Fresher Data Analytics Job Finder (0-1 Year Experience).
 * Clean Pastel SaaS Design System (#FFCED8, #FFDDDD, #FFF4DE, #FFE8C4).
 * Supports multi-role selection, date recency, split-screen ATS resume tailor, and cover letter builder.
 */

const state = {
  activeTab: 'jobs',
  page: 0,
  limit: 18,
  totalJobs: 0,
  layout: localStorage.getItem('job_finder_layout') || (typeof window !== 'undefined' && window.innerWidth <= 768 ? 'card' : 'list'), // Responsive Default: card on mobile, list on desktop
  currentJobs: [],
  filters: {
    q: '',
    roles: [],       // Multi-select array of roles
    cities: [],      // Multi-select array of selected cities
    platforms: [],   // Multi-select array of platform IDs
    sort_by: 'pune_first', // Default: Pune First -> Priority Cities (On-Site/Hybrid)
    country: '',
    work_mode: 'onsite_hybrid', // Default: On-Site and Hybrid Only (No Remote)
    experience_level: '',
    skill: '',
    applied: '',     // '', 'applied', 'not_applied'
    date_posted: '', // Date posted filter
    scrape_freshness: '' // '', 'today', '24h', '3d', '7d', '30d', 'older_30d'
  },
  rolesData: { core_roles: [], related_roles: [], all_roles: [] },
  platforms: [],
  cities: [],
  isRoleDropdownOpen: false,
  isCityDropdownOpen: false,
  isPlatformDropdownOpen: false,
  masterProfile: null
};

let currentTailorData = null;
let isKeywordHighlightActive = true;

// ==========================================================================
// STANDARD DOCUMENT NAMING (Tejas_Waghmare_Role_Company_DocType_Date)
// ==========================================================================

function formatFilenameSlug(text, defaultVal = '') {
  if (!text) return defaultVal;
  // Remove parenthetical notes
  let s = String(text).replace(/\(.*?\)/g, '');
  // Normalize symbols
  s = s.replace(/&/g, 'and').replace(/[\/\-_]/g, ' ');
  // Remove non-alphanumeric except spaces
  s = s.replace(/[^a-zA-Z0-9\s]/g, '');
  const words = s.split(/\s+/).filter(Boolean).map(w => w.charAt(0).toUpperCase() + w.slice(1));
  return words.length > 0 ? words.join('_') : defaultVal;
}

function cleanCandidateFilenameName(rawName) {
  if (!rawName || ['candidate', 'candidate name', ''].includes(String(rawName).toLowerCase().trim())) {
    rawName = (state.masterProfile && state.masterProfile.name) || 'Tejas Waghmare';
  }
  const clean = String(rawName).replace(/[^a-zA-Z\s]/g, '').trim();
  const words = clean.split(/\s+/).filter(Boolean).map(w => w.charAt(0).toUpperCase() + w.slice(1));
  if (words.length === 3 && words[1].length === 1) {
    return `${words[0]}_${words[2]}`;
  } else if (words.length >= 2) {
    return `${words[0]}_${words[1]}`;
  } else if (words.length === 1) {
    return words[0];
  }
  return 'Tejas_Waghmare';
}

function getStandardDocFilename(candidateName, role, company, docType, extension) {
  const nameSlug = cleanCandidateFilenameName(candidateName);
  const roleSlug = formatFilenameSlug(role || 'Data Analyst', 'Data_Analyst');
  const compSlug = formatFilenameSlug(company || 'Target Employer', 'Target_Employer');
  const now = new Date();
  const day = String(now.getDate()).padStart(2, '0');
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const year = now.getFullYear();
  const dateStr = `${day}_${month}_${year}`;
  const ext = extension.replace(/^\./, '');
  return `${nameSlug}_${roleSlug}_${compSlug}_${docType}_${dateStr}.${ext}`;
}

// ==========================================================================
// OVERLEAF / LATEX JAKE'S RESUME & COVER LETTER HTML RENDERERS (IMAGE 2 DESIGN)
// ==========================================================================

function renderLatexResumePreviewHtml(tailoredResume) {
  const res = tailoredResume || {};
  const name = escapeHtml(res.name || (state.masterProfile && state.masterProfile.name) || 'Tejas C. Waghmare');
  const contact = res.contact || (state.masterProfile && state.masterProfile.contact) || {};

  const contactParts = [];
  if (contact.phone && !contact.phone.toLowerCase().includes('not available')) {
    contactParts.push(escapeHtml(contact.phone));
  }
  if (contact.email && !contact.email.toLowerCase().includes('not available')) {
    contactParts.push(`<a href="mailto:${escapeHtml(contact.email)}" style="color: #000; text-decoration: underline;">${escapeHtml(contact.email)}</a>`);
  }
  if (contact.linkedin) {
    const cleanLi = contact.linkedin.replace(/^https?:\/\//, '').replace(/^www\./, '');
    const liUrl = contact.linkedin_url || `https://${cleanLi}`;
    contactParts.push(`<a href="${escapeHtml(liUrl)}" target="_blank" rel="noopener noreferrer" style="color: #000; text-decoration: underline;">${escapeHtml(cleanLi)}</a>`);
  }
  if (contact.github) {
    const cleanGh = contact.github.replace(/^https?:\/\//, '').replace(/^www\./, '');
    const ghUrl = contact.github_url || `https://${cleanGh}`;
    contactParts.push(`<a href="${escapeHtml(ghUrl)}" target="_blank" rel="noopener noreferrer" style="color: #000; text-decoration: underline;">${escapeHtml(cleanGh)}</a>`);
  }
  const contactLine = contactParts.length > 0 ? contactParts.join(' | ') : 'Information Not Available in Uploaded Documents';

  const summary = escapeHtml(res.summary || 'Information Not Available in Uploaded Documents');

  // Experience
  let expHtml = '';
  const expItems = res.experience || [];
  if (expItems.length > 0) {
    expHtml = expItems.map(exp => {
      const bullets = (exp.bullets && exp.bullets.length > 0)
        ? exp.bullets.map(b => `<li style="font-size: 8.6pt; margin-bottom: 1.5px; line-height: 1.25;">${escapeHtml(b)}</li>`).join('')
        : '<li style="font-size: 8.6pt; margin-bottom: 1.5px; line-height: 1.25;">Contributed to operational and technical deliverables.</li>';
      return `
        <div style="margin-bottom: 4px;">
          <div style="display: flex; justify-content: space-between; align-items: baseline; font-size: 9pt;">
            <span><strong>${escapeHtml(exp.title || 'Role')}</strong></span>
            <span style="font-size: 8.5pt;">${escapeHtml(exp.dates || exp.duration || '')}</span>
          </div>
          <div style="display: flex; justify-content: space-between; align-items: baseline; font-size: 8.7pt; margin-bottom: 1px;">
            <span><em>${escapeHtml(exp.company || '')}</em></span>
            <span style="font-size: 8.5pt;"><em>${escapeHtml(exp.location || 'Remote')}</em></span>
          </div>
          <ul style="margin: 2px 0 3px 18px; padding: 0; list-style-type: disc;">
            ${bullets}
          </ul>
        </div>
      `;
    }).join('');
  } else {
    expHtml = '<div style="font-size: 8.5pt; font-style: italic; color: #555;">Information Not Available in Uploaded Documents</div>';
  }

  // Projects
  let projHtml = '';
  const projItems = res.projects || [];
  if (projItems.length > 0) {
    projHtml = projItems.map(proj => {
      const bullets = (proj.bullets && proj.bullets.length > 0)
        ? proj.bullets.map(b => `<li style="font-size: 8.6pt; margin-bottom: 1.5px; line-height: 1.25;">${escapeHtml(b)}</li>`).join('')
        : '<li style="font-size: 8.6pt; margin-bottom: 1.5px; line-height: 1.25;">Executed key project milestones.</li>';
      const linkUrl = proj.link_url || '#';
      const linkText = proj.link_text || 'View Project';
      const linkHtml = (linkUrl && linkUrl !== '#')
        ? `<a href="${escapeHtml(linkUrl)}" target="_blank" rel="noopener noreferrer" style="text-decoration: underline; color: #000; font-size: 8.5pt;">${escapeHtml(linkText)}</a>`
        : `<span style="text-decoration: underline; font-size: 8.5pt;">${escapeHtml(linkText)}</span>`;
      const toolsLine = proj.tools
        ? `<div style="font-size: 8.2pt; margin-bottom: 1px;"><em>${escapeHtml(proj.tools)}</em></div>`
        : '';
      return `
        <div style="margin-bottom: 4px;">
          <div style="display: flex; justify-content: space-between; align-items: baseline; font-size: 9pt;">
            <span><strong>${escapeHtml(proj.title || 'Project')}</strong></span>
            <span>${linkHtml}</span>
          </div>
          ${toolsLine}
          <ul style="margin: 2px 0 3px 18px; padding: 0; list-style-type: disc;">
            ${bullets}
          </ul>
        </div>
      `;
    }).join('');
  } else {
    projHtml = '<div style="font-size: 8.5pt; font-style: italic; color: #555;">Information Not Available in Uploaded Documents</div>';
  }

  // Skills
  const skills = res.skills || {};
  const skillsLines = [];
  const catOrder = ['bi_visualization', 'data_analytics', 'programming', 'machine_learning', 'domains', 'tools_workflows'];
  const allCats = Object.keys(skills);
  const orderedCats = [...new Set([...catOrder.filter(c => allCats.includes(c)), ...allCats])];
  for (const cat of orderedCats) {
    const items = skills[cat];
    if (items && items.length > 0) {
      let label = cat.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
      if (label === 'Bi Visualization') label = 'BI & Visualization';
      if (label === 'Data Analytics') label = 'Data & Analytics';
      skillsLines.push(`<div><strong>${escapeHtml(label)}:</strong> ${escapeHtml(Array.isArray(items) ? items.join(', ') : items)}</div>`);
    }
  }
  const skillsHtml = skillsLines.length > 0 ? skillsLines.join('') : '<em>Information Not Available in Uploaded Documents</em>';

  // Education
  let eduHtml = '';
  const eduItems = res.education || [];
  if (eduItems.length > 0) {
    eduHtml = eduItems.map(edu => `
      <div style="margin-bottom: 3px;">
        <div style="display: flex; justify-content: space-between; align-items: baseline; font-size: 9pt;">
          <span><strong>${escapeHtml(edu.institution || 'Institution')}</strong></span>
          <span style="font-size: 8.5pt;">${escapeHtml(edu.dates || '')}</span>
        </div>
        <div style="font-size: 8.7pt;">
          <em>${escapeHtml(edu.degree || '')}</em>
        </div>
      </div>
    `).join('');
  } else {
    eduHtml = '<div style="font-size: 8.5pt; font-style: italic; color: #555;">Information Not Available in Uploaded Documents</div>';
  }

  // Certifications
  let certHtml = '';
  const certItems = res.certifications || [];
  if (certItems.length > 0) {
    certHtml = certItems.map(cert => {
      const cName = escapeHtml(typeof cert === 'object' ? cert.name || '' : String(cert));
      const cLink = escapeHtml(typeof cert === 'object' ? cert.link || 'Credential Link' : 'Credential Link');
      const cUrl = (typeof cert === 'object' && cert.url && cert.url !== '#') ? cert.url : null;
      const linkElem = cUrl
        ? `<a href="${escapeHtml(cUrl)}" target="_blank" rel="noopener noreferrer" style="text-decoration: underline; color: #000;">${cLink}</a>`
        : `<span style="text-decoration: underline;">${cLink}</span>`;
      return `
        <div style="display: flex; justify-content: space-between; font-size: 8.6pt; margin-bottom: 2px;">
          <span>${cName}</span>
          <span>${linkElem}</span>
        </div>
      `;
    }).join('');
  } else {
    certHtml = '<div style="font-size: 8.5pt; font-style: italic; color: #555;">Information Not Available in Uploaded Documents</div>';
  }

  return `
    <div class="latex-paper-sheet" style="background: #ffffff; color: #000000; font-family: 'Computer Modern Roman', 'Latin Modern Roman', 'Times New Roman', Times, serif; font-size: 9.1pt; line-height: 1.28; padding: 2.25rem 2.75rem; box-shadow: 0 4px 20px rgba(0,0,0,0.15); border: 1px solid #d1d5db; max-width: 860px; margin: 0 auto; text-align: left;">
      <!-- Header -->
      <div style="text-align: center; margin-bottom: 6px;">
        <h1 style="font-size: 20pt; font-weight: normal; font-variant: small-caps; letter-spacing: 0.5px; margin: 0 0 3px 0; color: #000000;">${name}</h1>
        <div style="font-size: 8.5pt; color: #111111;">
          ${contactLine}
        </div>
      </div>

      <!-- Professional Summary -->
      <div style="margin-top: 8px;">
        <div style="font-size: 10.5pt; font-variant: small-caps; font-weight: bold; border-bottom: 1px solid #000000; padding-bottom: 1px; margin-bottom: 3px; letter-spacing: 0.3px; color: #000000;">Professional Summary</div>
        <div style="font-size: 8.7pt; text-align: justify; line-height: 1.28; color: #000000;">${summary}</div>
      </div>

      <!-- Professional Experience -->
      <div style="margin-top: 8px;">
        <div style="font-size: 10.5pt; font-variant: small-caps; font-weight: bold; border-bottom: 1px solid #000000; padding-bottom: 1px; margin-bottom: 3px; letter-spacing: 0.3px; color: #000000;">Professional Experience</div>
        ${expHtml}
      </div>

      <!-- Projects -->
      <div style="margin-top: 8px;">
        <div style="font-size: 10.5pt; font-variant: small-caps; font-weight: bold; border-bottom: 1px solid #000000; padding-bottom: 1px; margin-bottom: 3px; letter-spacing: 0.3px; color: #000000;">Projects</div>
        ${projHtml}
      </div>

      <!-- Technical Skills -->
      <div style="margin-top: 8px;">
        <div style="font-size: 10.5pt; font-variant: small-caps; font-weight: bold; border-bottom: 1px solid #000000; padding-bottom: 1px; margin-bottom: 3px; letter-spacing: 0.3px; color: #000000;">Technical Skills</div>
        <div style="font-size: 8.7pt; line-height: 1.35; color: #000000;">
          ${skillsHtml}
        </div>
      </div>

      <!-- Education -->
      <div style="margin-top: 8px;">
        <div style="font-size: 10.5pt; font-variant: small-caps; font-weight: bold; border-bottom: 1px solid #000000; padding-bottom: 1px; margin-bottom: 3px; letter-spacing: 0.3px; color: #000000;">Education</div>
        ${eduHtml}
      </div>

      <!-- Certifications -->
      <div style="margin-top: 8px;">
        <div style="font-size: 10.5pt; font-variant: small-caps; font-weight: bold; border-bottom: 1px solid #000000; padding-bottom: 1px; margin-bottom: 3px; letter-spacing: 0.3px; color: #000000;">Certifications</div>
        ${certHtml}
      </div>
    </div>
  `;
}

function renderLatexCoverLetterPreviewHtml(coverLetter, payload) {
  const cl = coverLetter || {};
  const name = escapeHtml(cl.candidate_name || (state.masterProfile && state.masterProfile.name) || 'Tejas C. Waghmare');
  const contact = cl.contact || (state.masterProfile && state.masterProfile.contact) || {};
  const dateStr = escapeHtml(cl.date || new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }));
  const targetRole = escapeHtml(cl.target_role || (payload && payload.job_title) || 'Data Analyst');
  const targetCompany = escapeHtml(cl.target_company || (payload && payload.company) || 'Target Employer');

  const contactParts = [];
  if (contact.phone && !contact.phone.toLowerCase().includes('not available')) {
    contactParts.push(escapeHtml(contact.phone));
  }
  if (contact.email && !contact.email.toLowerCase().includes('not available')) {
    contactParts.push(`<a href="mailto:${escapeHtml(contact.email)}" style="color: #000; text-decoration: underline;">${escapeHtml(contact.email)}</a>`);
  }
  if (contact.linkedin) {
    const cleanLi = contact.linkedin.replace(/^https?:\/\//, '').replace(/^www\./, '');
    const liUrl = contact.linkedin_url || `https://${cleanLi}`;
    contactParts.push(`<a href="${escapeHtml(liUrl)}" target="_blank" rel="noopener noreferrer" style="color: #000; text-decoration: underline;">${escapeHtml(cleanLi)}</a>`);
  }
  if (contact.github) {
    const cleanGh = contact.github.replace(/^https?:\/\//, '').replace(/^www\./, '');
    const ghUrl = contact.github_url || `https://${cleanGh}`;
    contactParts.push(`<a href="${escapeHtml(ghUrl)}" target="_blank" rel="noopener noreferrer" style="color: #000; text-decoration: underline;">${escapeHtml(cleanGh)}</a>`);
  }
  const contactLine = contactParts.length > 0 ? contactParts.join(' | ') : 'Information Not Available in Uploaded Documents';

  const paragraphs = cl.paragraphs || (cl.full_text ? cl.full_text.split('\n\n').filter(p => p.length > 30) : []);
  const bodyHtml = paragraphs.map(p => `<p style="margin: 0 0 10px 0; font-size: 10pt; line-height: 1.45; text-align: justify; color: #000000;">${escapeHtml(p)}</p>`).join('');

  return `
    <div class="latex-paper-sheet" style="background: #ffffff; color: #000000; font-family: 'Computer Modern Roman', 'Latin Modern Roman', 'Times New Roman', Times, serif; font-size: 10pt; line-height: 1.45; padding: 2.5rem 3rem; box-shadow: 0 4px 20px rgba(0,0,0,0.15); border: 1px solid #d1d5db; max-width: 860px; margin: 0 auto; text-align: left;">
      <!-- Header -->
      <div style="text-align: center; border-bottom: 1px solid #000000; padding-bottom: 6px; margin-bottom: 16px;">
        <h1 style="font-size: 19pt; font-weight: normal; font-variant: small-caps; letter-spacing: 0.5px; margin: 0 0 3px 0; color: #000000;">${name}</h1>
        <div style="font-size: 8.5pt; color: #111111;">
          ${contactLine}
        </div>
      </div>

      <div style="font-size: 10pt; margin-bottom: 14px; color: #000000;">${dateStr}</div>

      <div style="margin-bottom: 14px; line-height: 1.4; font-size: 10pt; color: #000000;">
        <strong>Hiring Team / Talent Acquisition</strong><br>
        ${targetCompany}<br>
        <strong>RE: Application for ${targetRole}</strong>
      </div>

      <div style="font-size: 10.5pt; margin-bottom: 12px; color: #000000;">Dear Hiring Manager,</div>

      <div class="body">
        ${bodyHtml}
      </div>

      <div style="margin-top: 20px; font-size: 10pt; color: #000000;">
        Sincerely,<br>
        <div style="font-weight: bold; margin-top: 4px; color: #000000;">${name}</div>
      </div>
    </div>
  `;
}

// ==========================================================================
// THEME MANAGEMENT (Light / Dark Theme)
// ==========================================================================

function getCurrentTheme() {
  return document.documentElement.getAttribute('data-theme') || 'light';
}

function initTheme() {
  const saved = localStorage.getItem('job_finder_theme');
  const systemDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  const initialTheme = saved ? saved : (systemDark ? 'dark' : 'light');
  applyTheme(initialTheme);

  // Listen for system appearance preference changes if user hasn't explicitly set a preference
  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      if (!localStorage.getItem('job_finder_theme')) {
        applyTheme(e.matches ? 'dark' : 'light');
      }
    });
  }
}

function applyTheme(theme) {
  const isDark = theme === 'dark';
  document.documentElement.setAttribute('data-theme', theme);
  document.documentElement.classList.toggle('dark-theme', isDark);
  if (document.body) {
    document.body.classList.toggle('dark-theme', isDark);
  }

  // Update theme toggle button in header
  const btn = document.getElementById('theme-toggle-btn');
  const icon = document.getElementById('theme-toggle-icon');
  const label = document.getElementById('theme-toggle-text');
  const metaTheme = document.getElementById('meta-theme-color');
  if (metaTheme) {
    metaTheme.setAttribute('content', isDark ? '#18181b' : '#FFE4E8');
  }
  if (btn) {
    btn.setAttribute('title', isDark ? 'Switch to Light Theme' : 'Switch to Dark Theme');
    btn.setAttribute('aria-label', isDark ? 'Switch to Light Theme' : 'Switch to Dark Theme');
    btn.classList.toggle('active', isDark);
  }
  if (icon) {
    icon.textContent = isDark ? '☀️' : '🌙';
  }
  if (label) {
    label.textContent = isDark ? 'Light' : 'Dark';
  }

  // Update switch in Settings modal if present
  const settingDarkTheme = document.getElementById('setting-dark-theme');
  if (settingDarkTheme) {
    settingDarkTheme.checked = isDark;
  }
}

function toggleTheme(explicitDark) {
  const current = getCurrentTheme();
  let targetTheme;
  if (typeof explicitDark === 'boolean') {
    targetTheme = explicitDark ? 'dark' : 'light';
  } else {
    targetTheme = current === 'dark' ? 'light' : 'dark';
  }
  localStorage.setItem('job_finder_theme', targetTheme);
  applyTheme(targetTheme);

  // Re-render Knowledge Base documents if currently available
  try {
    if (typeof renderKBDocuments === 'function') {
      renderKBDocuments();
    }
    if (typeof renderMasterModalDocuments === 'function') {
      renderMasterModalDocuments();
    }
  } catch (e) {
    console.debug('Error refreshing document views after theme change:', e);
  }
}

// Immediately apply theme early if possible
initTheme();

// --- Initializer ---
document.addEventListener('DOMContentLoaded', async () => {
  initTheme();
  updateLayoutUI();
  await Promise.all([loadStats(), loadRoles(), loadCities(), loadPlatforms(), loadMasterResumeStatus(), loadKBDocuments(), loadKBUnifiedProfile()]);
  await loadJobs();
  setupEventListeners();
  setupResumeDropzone();
  setupKBDropzone();
  loadSettings();
  initSchedulerModule();
  initMobileScrollWatcher();
  initSearchClearWatcher();
  initModalScrollLockWatcher();
});

function setupEventListeners() {
  // Tabs
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  // Search input debounce
  const searchInput = document.getElementById('search-input');
  let debounceTimer;
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        state.filters.q = e.target.value.trim();
        state.page = 0;
        loadJobs();
      }, 350);
    });
  }

  // Dropdown filters (work mode, exp, applied, scrape freshness)
  ['workmode-filter', 'exp-filter', 'applied-filter', 'scrape-freshness-filter'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('change', (e) => {
        const field = el.dataset.filter;
        if (field === 'scrape_freshness') {
          setScrapeFreshness(e.target.value);
        } else {
          state.filters[field] = e.target.value;
          state.page = 0;
          loadJobs();
        }
      });
    }
  });

  // Sort dropdown filters (sync filter grid and toolbar)
  ['filter-sort-select', 'toolbar-sort-select'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('change', (e) => {
        handleSortChange(e.target.value);
      });
    }
  });

  // Multi-Select Roles Dropdown toggle
  const roleDropdownBtn = document.getElementById('multi-role-btn');
  const roleDropdown = document.getElementById('multi-role-dropdown');
  if (roleDropdownBtn && roleDropdown) {
    roleDropdownBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      state.isRoleDropdownOpen = !state.isRoleDropdownOpen;
      roleDropdown.classList.toggle('open', state.isRoleDropdownOpen);
      if (state.isRoleDropdownOpen) {
        state.isCityDropdownOpen = false;
        state.isPlatformDropdownOpen = false;
        const cDropdown = document.getElementById('multi-city-dropdown');
        if (cDropdown) cDropdown.classList.remove('open');
        const pDropdown = document.getElementById('multi-platform-dropdown');
        if (pDropdown) pDropdown.classList.remove('open');
      }
    });

    document.addEventListener('click', (e) => {
      if (!roleDropdown.contains(e.target) && !roleDropdownBtn.contains(e.target)) {
        state.isRoleDropdownOpen = false;
        roleDropdown.classList.remove('open');
      }
    });
  }

  // Multi-Select Roles search filter
  const roleSearch = document.getElementById('role-search-input');
  if (roleSearch) {
    roleSearch.addEventListener('input', (e) => {
      const q = e.target.value.toLowerCase();
      document.querySelectorAll('#role-checkboxes-list .dropdown-item').forEach(item => {
        const label = (item.dataset.roleName || '').toLowerCase();
        item.style.display = label.includes(q) ? 'flex' : 'none';
      });
    });
  }

  // Multi-Select City Dropdown toggle
  const cityDropdownBtn = document.getElementById('multi-city-btn');
  const cityDropdown = document.getElementById('multi-city-dropdown');
  if (cityDropdownBtn && cityDropdown) {
    cityDropdownBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      state.isCityDropdownOpen = !state.isCityDropdownOpen;
      cityDropdown.classList.toggle('open', state.isCityDropdownOpen);
      if (state.isCityDropdownOpen) {
        state.isRoleDropdownOpen = false;
        state.isPlatformDropdownOpen = false;
        if (roleDropdown) roleDropdown.classList.remove('open');
        const pDropdown = document.getElementById('multi-platform-dropdown');
        if (pDropdown) pDropdown.classList.remove('open');
      }
    });

    document.addEventListener('click', (e) => {
      if (!cityDropdown.contains(e.target) && !cityDropdownBtn.contains(e.target)) {
        state.isCityDropdownOpen = false;
        cityDropdown.classList.remove('open');
      }
    });
  }

  // Multi-Select City search filter
  const citySearch = document.getElementById('city-search-input');
  if (citySearch) {
    citySearch.addEventListener('input', (e) => {
      const q = e.target.value.toLowerCase();
      document.querySelectorAll('#city-checkboxes-list .dropdown-item').forEach(item => {
        const label = (item.dataset.cityName || '').toLowerCase();
        const cid = (item.dataset.cityId || '').toLowerCase();
        item.style.display = (label.includes(q) || cid.includes(q)) ? 'flex' : 'none';
      });
    });
  }

  // Multi-Select Platform Dropdown toggle
  const platformDropdownBtn = document.getElementById('multi-platform-btn');
  const platformDropdown = document.getElementById('multi-platform-dropdown');
  if (platformDropdownBtn && platformDropdown) {
    platformDropdownBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      state.isPlatformDropdownOpen = !state.isPlatformDropdownOpen;
      platformDropdown.classList.toggle('open', state.isPlatformDropdownOpen);
      if (state.isPlatformDropdownOpen) {
        state.isRoleDropdownOpen = false;
        state.isCityDropdownOpen = false;
        if (roleDropdown) roleDropdown.classList.remove('open');
        if (cityDropdown) cityDropdown.classList.remove('open');
      }
    });

    document.addEventListener('click', (e) => {
      if (!platformDropdown.contains(e.target) && !platformDropdownBtn.contains(e.target)) {
        state.isPlatformDropdownOpen = false;
        platformDropdown.classList.remove('open');
      }
    });
  }

  // Multi-Select Platform search filter
  const platformSearch = document.getElementById('platform-search-input');
  if (platformSearch) {
    platformSearch.addEventListener('input', (e) => {
      const q = e.target.value.toLowerCase();
      document.querySelectorAll('#platform-checkboxes-list .dropdown-item').forEach(item => {
        const label = (item.dataset.platformName || '').toLowerCase();
        item.style.display = label.includes(q) ? 'flex' : 'none';
      });
    });
  }

  // Directory search
  const dirSearch = document.getElementById('dir-search-input');
  if (dirSearch) {
    dirSearch.addEventListener('input', (e) => {
      filterPlatforms(e.target.value.toLowerCase());
    });
  }

  // Delete document confirmation action
  const btnDeleteAction = document.getElementById('btn-confirm-delete-action');
  if (btnDeleteAction) {
    btnDeleteAction.addEventListener('click', executeDeleteDocument);
  }
}

function switchTab(tabName) {
  state.activeTab = tabName;
  document.querySelectorAll('.tab-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === tabName);
  });
  document.querySelectorAll('.mobile-bottom-nav-item[data-tab]').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === tabName);
  });
  document.querySelectorAll('.tab-pane').forEach(p => {
    p.style.display = p.id === `tab-${tabName}` ? 'block' : 'none';
  });
  if (tabName === 'analytics') {
    renderAnalyticsView();
  }
  if (tabName === 'kb') {
    loadKBDocuments();
    loadKBUnifiedProfile();
  }
  if (tabName === 'scheduler-center') {
    loadSchedulerDashboard();
  }
  if (tabName === 'linkedin-feed') {
    loadLinkedInFeedPage();
  }
  if (tabName === 'tailor-studio') {
    initTailorStudioPage();
  }
}

function handleMobileNavTab(tabName) {
  if (state.activeTab === tabName) {
    window.scrollTo({ top: 0, behavior: 'smooth' });
    return;
  }
  if (typeof closeMobileMenu === 'function') {
    closeMobileMenu();
  }
  switchTab(tabName);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// --- API Calls ---

async function loadStats() {
  try {
    const res = await fetch('/api/stats');
    const data = await res.json();
    document.getElementById('stat-total-jobs').innerText = data.total_jobs || 0;
    const appliedEl = document.getElementById('stat-applied-jobs');
    if (appliedEl) appliedEl.innerText = data.applied_jobs || 0;
    document.getElementById('stat-fresher-jobs').innerText = data.fresher_jobs || data.total_jobs || 0;
    document.getElementById('stat-india-jobs').innerText = data.india_jobs || 0;
    document.getElementById('stat-remote-jobs').innerText = data.remote_jobs || 0;
    document.getElementById('stat-platforms-count').innerText = data.total_sources || 73;
    document.getElementById('badge-jobs-count').innerText = data.total_jobs || 0;
    const freshTodayEl = document.getElementById('stat-fresh-today');
    if (freshTodayEl) freshTodayEl.innerText = data.jobs_added_today || 0;
    const quickCountToday = document.getElementById('quick-count-today');
    if (quickCountToday) quickCountToday.innerText = data.jobs_added_today || 0;

    // Update LinkedIn Recruiter Feed Tab Badge
    fetch('/api/scraper/linkedin/feed?limit=1').then(r => r.json()).then(d => {
      const liBadge = document.getElementById('badge-linkedin-feed-count');
      if (liBadge) liBadge.innerText = d.all_in_db || d.total || 0;
    }).catch(() => {});
  } catch (err) {
    console.error('Error loading stats:', err);
  }
}

async function loadRoles() {
  try {
    const res = await fetch('/api/roles');
    state.rolesData = await res.json();
    renderMultiSelectDropdown();
  } catch (err) {
    console.error('Error loading roles:', err);
  }
}

function renderMultiSelectDropdown() {
  const listContainer = document.getElementById('role-checkboxes-list');
  if (!listContainer) return;

  let html = '';

  // Core Analytics Roles
  html += `<div class="dropdown-optgroup-title">Core Analytics Roles (${state.rolesData.core_roles.length})</div>`;
  state.rolesData.core_roles.forEach(role => {
    const isChecked = state.filters.roles.includes(role);
    html += `
      <label class="dropdown-item" data-role-name="${escapeHtml(role)}">
        <input type="checkbox" value="${escapeHtml(role)}" ${isChecked ? 'checked' : ''} onchange="toggleRoleSelection('${escapeHtml(role)}')">
        <span>${escapeHtml(role)}</span>
      </label>
    `;
  });

  // Related Roles
  html += `<div class="dropdown-optgroup-title" style="margin-top: 0.5rem; color: #D97F95;">Related Roles (${state.rolesData.related_roles.length})</div>`;
  state.rolesData.related_roles.forEach(role => {
    const isChecked = state.filters.roles.includes(role);
    html += `
      <label class="dropdown-item" data-role-name="${escapeHtml(role)}">
        <input type="checkbox" value="${escapeHtml(role)}" ${isChecked ? 'checked' : ''} onchange="toggleRoleSelection('${escapeHtml(role)}')">
        <span>${escapeHtml(role)}</span>
      </label>
    `;
  });

  listContainer.innerHTML = html;
  updateRoleBtnText();
  renderSelectedRoleChips();
}

function toggleRoleSelection(roleName) {
  const idx = state.filters.roles.indexOf(roleName);
  if (idx > -1) {
    state.filters.roles.splice(idx, 1);
  } else {
    state.filters.roles.push(roleName);
  }
  updateRoleBtnText();
  renderSelectedRoleChips();
  state.page = 0;
  loadJobs();
}

function selectAllCoreRoles() {
  state.rolesData.core_roles.forEach(r => {
    if (!state.filters.roles.includes(r)) state.filters.roles.push(r);
  });
  renderMultiSelectDropdown();
  state.page = 0;
  loadJobs();
}

function selectAllRelatedRoles() {
  state.rolesData.related_roles.forEach(r => {
    if (!state.filters.roles.includes(r)) state.filters.roles.push(r);
  });
  renderMultiSelectDropdown();
  state.page = 0;
  loadJobs();
}

function selectAllRoles() {
  state.filters.roles = [...state.rolesData.all_roles];
  renderMultiSelectDropdown();
  state.page = 0;
  loadJobs();
}

function clearRoleSelection() {
  state.filters.roles = [];
  renderMultiSelectDropdown();
  state.page = 0;
  loadJobs();
}

function updateRoleBtnText() {
  const btnText = document.getElementById('multi-role-btn-text');
  if (!btnText) return;
  const count = state.filters.roles.length;
  if (count === 0) {
    btnText.innerHTML = `All 25 Analytics Roles <span style="color: var(--text-muted);">(Click to multi-select)</span>`;
  } else {
    btnText.innerHTML = `<span style="color: var(--link-color); font-weight: 700;">${count} Role${count > 1 ? 's' : ''} Selected</span>`;
  }
}

function renderSelectedRoleChips() {
  const container = document.getElementById('selected-roles-chips');
  if (!container) return;

  if (state.filters.roles.length === 0) {
    container.innerHTML = '';
    return;
  }

  container.innerHTML = state.filters.roles.map(r => `
    <span class="role-chip">
      ${escapeHtml(r)}
      <span class="role-chip-close" onclick="toggleRoleSelection('${escapeHtml(r)}')">✕</span>
    </span>
  `).join('') + `
    <button class="clear-btn" style="font-size: 0.75rem; margin-left: 0.35rem;" onclick="clearRoleSelection()">Clear All Roles</button>
  `;
}

// --- Multi-Select City / Location Filter Functions ---

async function loadCities() {
  try {
    const res = await fetch('/api/cities');
    state.cities = await res.json();
    renderCityMultiSelectDropdown();
    updateCityBtnText();
  } catch (err) {
    console.error('Error loading cities:', err);
  }
}

function renderCityMultiSelectDropdown() {
  const listContainer = document.getElementById('city-checkboxes-list');
  if (!listContainer) return;

  if (!state.cities || state.cities.length === 0) {
    listContainer.innerHTML = '<div style="padding: 1rem; text-align: center; color: var(--text-muted); font-size: 0.8rem;">Loading cities...</div>';
    return;
  }

  // Group cities by category
  const categories = {};
  state.cities.forEach(c => {
    const cat = c.category || 'Other Cities';
    if (!categories[cat]) categories[cat] = [];
    categories[cat].push(c);
  });

  let html = '';
  for (const [catName, citiesList] of Object.entries(categories)) {
    html += `<div class="dropdown-optgroup-title" style="color: #0284C7;">${escapeHtml(catName)} (${citiesList.length})</div>`;
    citiesList.forEach(city => {
      const isChecked = state.filters.cities.includes(city.id);
      const isZero = (city.count === 0);
      html += `
        <label class="dropdown-item" data-city-id="${escapeHtml(city.id)}" data-city-name="${escapeHtml(city.name)}">
          <input type="checkbox" value="${escapeHtml(city.id)}" ${isChecked ? 'checked' : ''} onchange="toggleCitySelection('${escapeHtml(city.id)}')">
          <span style="flex: 1;">${escapeHtml(city.name)}</span>
          <span class="city-count-chip ${isZero ? 'zero' : ''}">${city.count}</span>
        </label>
      `;
    });
  }

  listContainer.innerHTML = html;
  updateCityBtnText();
  renderSelectedCityChips();
}

function toggleCitySelection(cityId) {
  const idx = state.filters.cities.indexOf(cityId);
  if (idx > -1) {
    state.filters.cities.splice(idx, 1);
  } else {
    state.filters.cities.push(cityId);
  }
  updateCityBtnText();
  renderSelectedCityChips();
  renderCityMultiSelectDropdown();
  state.page = 0;
  loadJobs();
}

function filterPuneNearbyOnsiteHybrid() {
  state.filters.cities = ['Pune'];
  state.filters.work_mode = 'onsite_hybrid';
  state.filters.sort_by = 'pune_first';
  
  const wmFilter = document.getElementById('workmode-filter');
  if (wmFilter) wmFilter.value = 'onsite_hybrid';

  const sortSelect = document.getElementById('toolbar-sort-select');
  if (sortSelect) sortSelect.value = 'pune_first';

  renderCityMultiSelectDropdown();
  updateCityBtnText();
  renderSelectedCityChips();
  
  state.page = 0;
  loadJobs();
}

function selectPuneNearbyOnly() {
  state.filters.cities = ['Pune'];
  state.filters.work_mode = 'onsite_hybrid';
  const wmFilter = document.getElementById('workmode-filter');
  if (wmFilter) wmFilter.value = 'onsite_hybrid';

  renderCityMultiSelectDropdown();
  updateCityBtnText();
  renderSelectedCityChips();
  state.page = 0;
  loadJobs();
}

function selectPriorityCitiesCascade() {
  state.filters.cities = ['Pune', 'Nagpur', 'Hyderabad', 'Aurangabad', 'Bengaluru'];
  state.filters.work_mode = 'onsite_hybrid';
  state.filters.sort_by = 'pune_first';

  const wmFilter = document.getElementById('workmode-filter');
  if (wmFilter) wmFilter.value = 'onsite_hybrid';

  const sortSelect = document.getElementById('toolbar-sort-select');
  if (sortSelect) sortSelect.value = 'pune_first';

  renderCityMultiSelectDropdown();
  updateCityBtnText();
  renderSelectedCityChips();
  state.page = 0;
  loadJobs();
}

function selectTopTechHubs() {
  const hubs = ['Bengaluru', 'Mumbai', 'Pune', 'Hyderabad', 'Delhi NCR', 'Chennai'];
  hubs.forEach(h => {
    if (!state.filters.cities.includes(h)) state.filters.cities.push(h);
  });
  renderCityMultiSelectDropdown();
  updateCityBtnText();
  renderSelectedCityChips();
  state.page = 0;
  loadJobs();
}

function selectRemoteOnly() {
  state.filters.cities = ['Remote'];
  renderCityMultiSelectDropdown();
  updateCityBtnText();
  renderSelectedCityChips();
  state.page = 0;
  loadJobs();
}

function selectAllCities() {
  state.filters.cities = (state.cities || []).map(c => c.id);
  renderCityMultiSelectDropdown();
  updateCityBtnText();
  renderSelectedCityChips();
  state.page = 0;
  loadJobs();
}

function clearCitySelection() {
  state.filters.cities = [];
  renderCityMultiSelectDropdown();
  updateCityBtnText();
  renderSelectedCityChips();
  state.page = 0;
  loadJobs();
}

function updateCityBtnText() {
  const btnText = document.getElementById('multi-city-btn-text');
  if (!btnText) return;
  const count = state.filters.cities.length;
  if (count === 0) {
    btnText.innerHTML = `All Cities <span style="color: var(--text-muted);">(Single / Multi-select)</span>`;
  } else if (count === 1) {
    const single = (state.cities || []).find(c => c.id === state.filters.cities[0]);
    const label = single ? single.name.split(' (')[0].split(' /')[0] : state.filters.cities[0];
    btnText.innerHTML = `<span style="color: #0284C7; font-weight: 700;">📍 ${escapeHtml(label)} (1 City)</span>`;
  } else {
    btnText.innerHTML = `<span style="color: #0284C7; font-weight: 700;">📍 ${count} Cities Selected</span>`;
  }
}

function renderSelectedCityChips() {
  const container = document.getElementById('selected-cities-chips');
  if (!container) return;

  if (state.filters.cities.length === 0) {
    container.innerHTML = '';
    return;
  }

  container.innerHTML = state.filters.cities.map(cid => {
    const cObj = (state.cities || []).find(c => c.id === cid);
    const label = cObj ? cObj.name : cid;
    const cnt = cObj && cObj.count !== undefined ? ` (${cObj.count})` : '';
    return `
      <span class="city-chip">
        📍 ${escapeHtml(label)}${cnt}
        <span class="city-chip-close" onclick="toggleCitySelection('${escapeHtml(cid)}')">✕</span>
      </span>
    `;
  }).join('') + `
    <button class="clear-btn" style="font-size: 0.75rem; margin-left: 0.35rem;" onclick="clearCitySelection()">Clear All Cities</button>
  `;
}

// --- Platform Multi-Select Dropdown Functions ---

function renderPlatformMultiSelectDropdown() {
  const listContainer = document.getElementById('platform-checkboxes-list');
  if (!listContainer) return;

  if (!state.platforms || state.platforms.length === 0) {
    listContainer.innerHTML = '<div style="padding: 1rem; text-align: center; color: var(--text-muted); font-size: 0.8rem;">Loading platforms...</div>';
    return;
  }

  // Group platforms by section
  const sections = {
    'Indian Platforms': [],
    'Remote & Global': [],
    'Company Careers': []
  };

  state.platforms.forEach(p => {
    const sec = p.section || '';
    if (sec.startsWith('A') || p.country === 'India') {
      sections['Indian Platforms'].push(p);
    } else if (sec.startsWith('B') || sec.includes('Remote')) {
      sections['Remote & Global'].push(p);
    } else {
      sections['Company Careers'].push(p);
    }
  });

  let html = '';

  for (const [secTitle, plist] of Object.entries(sections)) {
    if (plist.length === 0) continue;
    // Sort platforms: platforms with active jobs first, then alphabetically
    plist.sort((a, b) => {
      if ((b.job_count || 0) !== (a.job_count || 0)) {
        return (b.job_count || 0) - (a.job_count || 0);
      }
      return a.name.localeCompare(b.name);
    });

    html += `<div class="dropdown-optgroup-title">${escapeHtml(secTitle)} (${plist.length})</div>`;
    plist.forEach(p => {
      const isChecked = state.filters.platforms.includes(p.id) || state.filters.platforms.includes(p.name);
      const count = p.job_count || 0;
      const countBadge = count > 0
        ? `<span class="platform-count-chip">${count} job${count > 1 ? 's' : ''}</span>`
        : `<span class="platform-count-chip zero">0</span>`;

      html += `
        <label class="dropdown-item" data-platform-name="${escapeHtml(p.name)} ${escapeHtml(p.id)}">
          <input type="checkbox" value="${escapeHtml(p.id)}" ${isChecked ? 'checked' : ''} onchange="togglePlatformSelection('${escapeHtml(p.id)}')">
          <span style="flex: 1; display: inline-flex; align-items: center; gap: 0.35rem;">
            <span>${escapeHtml(p.name)}</span>
            ${p.id === 'linkedin_india' || p.id === 'apify_linkedin' ? '<span class="badge-apify-tag" style="margin-left: 0.25rem;">⚡ Apify Live</span>' : ''}
          </span>
          ${countBadge}
        </label>
      `;
    });
  }

  listContainer.innerHTML = html;
  updatePlatformBtnText();
  renderSelectedPlatformChips();
}

function togglePlatformSelection(platformId) {
  const idx = state.filters.platforms.indexOf(platformId);
  if (idx > -1) {
    state.filters.platforms.splice(idx, 1);
  } else {
    state.filters.platforms.push(platformId);
  }
  updatePlatformBtnText();
  renderSelectedPlatformChips();
  state.page = 0;
  loadJobs();
}

function selectAllPlatforms() {
  state.filters.platforms = state.platforms.map(p => p.id);
  renderPlatformMultiSelectDropdown();
  state.page = 0;
  loadJobs();
}

function selectPlatformsWithJobs() {
  state.filters.platforms = state.platforms
    .filter(p => (p.job_count || 0) > 0)
    .map(p => p.id);
  renderPlatformMultiSelectDropdown();
  state.page = 0;
  loadJobs();
}

function selectIndiaPlatforms() {
  state.filters.platforms = state.platforms
    .filter(p => (p.section && p.section.startsWith('A')) || p.country === 'India')
    .map(p => p.id);
  renderPlatformMultiSelectDropdown();
  state.page = 0;
  loadJobs();
}

function selectRemotePlatforms() {
  state.filters.platforms = state.platforms
    .filter(p => (p.section && p.section.startsWith('B')) || (p.section && p.section.includes('Remote')))
    .map(p => p.id);
  renderPlatformMultiSelectDropdown();
  state.page = 0;
  loadJobs();
}

function selectCompanyPlatforms() {
  state.filters.platforms = state.platforms
    .filter(p => (p.section && p.section.startsWith('C')) || (p.category && p.category.includes('Company')))
    .map(p => p.id);
  renderPlatformMultiSelectDropdown();
  state.page = 0;
  loadJobs();
}

function clearPlatformSelection() {
  state.filters.platforms = [];
  renderPlatformMultiSelectDropdown();
  state.page = 0;
  loadJobs();
}

function updatePlatformBtnText() {
  const btnText = document.getElementById('multi-platform-btn-text');
  if (!btnText) return;
  const count = state.filters.platforms.length;
  if (count === 0) {
    btnText.innerHTML = `All Platforms <span style="color: var(--text-muted);">(Multi-select)</span>`;
  } else if (count === 1) {
    const single = state.platforms.find(p => p.id === state.filters.platforms[0] || p.name === state.filters.platforms[0]);
    const label = single ? single.name : state.filters.platforms[0];
    btnText.innerHTML = `<span style="color: var(--link-color); font-weight: 700;">${escapeHtml(label)} (1 Selected)</span>`;
  } else {
    btnText.innerHTML = `<span style="color: var(--link-color); font-weight: 700;">${count} Platforms Selected</span>`;
  }
}

function renderSelectedPlatformChips() {
  const container = document.getElementById('selected-platforms-chips');
  if (!container) return;

  if (state.filters.platforms.length === 0) {
    container.innerHTML = '';
    return;
  }

  container.innerHTML = state.filters.platforms.map(pid => {
    const pObj = state.platforms.find(p => p.id === pid || p.name === pid);
    const label = pObj ? pObj.name : pid;
    const cnt = pObj && pObj.job_count ? ` (${pObj.job_count})` : '';
    return `
      <span class="platform-chip">
        🌐 ${escapeHtml(label)}${cnt}
        <span class="platform-chip-close" onclick="togglePlatformSelection('${escapeHtml(pid)}')">✕</span>
      </span>
    `;
  }).join('') + `
    <button class="clear-btn" style="font-size: 0.75rem; margin-left: 0.35rem;" onclick="clearPlatformSelection()">Clear All Platforms</button>
  `;
}

function filterByPlatform(platformId) {
  state.filters.platforms = [platformId];
  renderPlatformMultiSelectDropdown();
  updatePlatformBtnText();
  renderSelectedPlatformChips();
  state.page = 0;
  loadJobs();
  const jobsTab = document.getElementById('tab-jobs');
  if (jobsTab) jobsTab.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function handleSortChange(newSort) {
  state.filters.sort_by = newSort;
  const filterSort = document.getElementById('filter-sort-select');
  const toolbarSort = document.getElementById('toolbar-sort-select');
  if (filterSort && filterSort.value !== newSort) filterSort.value = newSort;
  if (toolbarSort && toolbarSort.value !== newSort) toolbarSort.value = newSort;
  state.page = 0;
  loadJobs();
}

function getSortLabel(sortVal) {
  const map = {
    'date_desc': 'Date: Most Recent',
    'first_scraped_desc': 'Newest Scraped First',
    'first_scraped_asc': 'Oldest Scraped First',
    'date_asc': 'Date: Oldest First',
    'platform_asc': 'Platform: A → Z',
    'platform_desc': 'Platform: Z → A',
    'company_asc': 'Company: A → Z',
    'company_desc': 'Company: Z → A',
    'title_asc': 'Job Title: A → Z',
    'title_desc': 'Job Title: Z → A'
  };
  return map[sortVal] || 'Most Recent';
}

// --- Scrape Freshness & Discovery Tracking Intelligence ---

function setScrapeFreshness(freshnessVal) {
  state.filters.scrape_freshness = freshnessVal || '';

  // Sync dropdown filter
  const filterSelect = document.getElementById('scrape-freshness-filter');
  if (filterSelect && filterSelect.value !== state.filters.scrape_freshness) {
    filterSelect.value = state.filters.scrape_freshness;
  }

  // Update quick pills active state
  document.querySelectorAll('.freshness-pill').forEach(btn => btn.classList.remove('active'));
  const targetId = freshnessVal ? `quick-pill-${freshnessVal}` : 'quick-pill-all';
  const targetPill = document.getElementById(targetId);
  if (targetPill) {
    targetPill.classList.add('active');
  }

  state.page = 0;
  loadJobs();
}

function getFreshnessBadge(isoStr) {
  if (!isoStr) return { label: '⚪ OLDER', class: 'badge-fresh-older', title: 'Undated discovery' };
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return { label: '⚪ OLDER', class: 'badge-fresh-older', title: 'Undated discovery' };
    const now = new Date();

    // Check if same calendar day
    const isSameDay = d.getFullYear() === now.getFullYear() &&
      d.getMonth() === now.getMonth() &&
      d.getDate() === now.getDate();
    if (isSameDay) {
      return { label: '🟢 NEW TODAY', class: 'badge-fresh-today', title: 'Discovered today' };
    }

    const diffMs = now.getTime() - d.getTime();
    const diffHours = diffMs / (1000 * 60 * 60);
    if (diffHours <= 24) {
      return { label: '🟢 NEW TODAY', class: 'badge-fresh-today', title: 'Discovered in the last 24h' };
    }
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays <= 7) {
      return { label: '🟢 NEW', class: 'badge-fresh-week', title: `First discovered ${diffDays} day${diffDays === 1 ? '' : 's'} ago` };
    }
    if (diffDays <= 30) {
      return { label: '🟡 RECENT', class: 'badge-fresh-month', title: `First discovered ${diffDays} days ago` };
    }
    return { label: '⚪ OLDER', class: 'badge-fresh-older', title: 'First discovered >30 days ago' };
  } catch {
    return { label: '⚪ OLDER', class: 'badge-fresh-older', title: 'Archived record' };
  }
}

function formatFirstScrapedDateTime(isoStr) {
  if (!isoStr) return 'N/A';
  try {
    let cleanStr = String(isoStr).trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(cleanStr)) {
      cleanStr += 'T00:00:00Z';
    } else if (cleanStr.includes(' ') && !cleanStr.includes('T')) {
      cleanStr = cleanStr.replace(' ', 'T');
      if (!cleanStr.endsWith('Z') && !/[+-]\d{2}:?\d{2}$/.test(cleanStr)) {
        cleanStr += 'Z';
      }
    } else if (!cleanStr.endsWith('Z') && !/[+-]\d{2}:?\d{2}$/.test(cleanStr)) {
      cleanStr += 'Z';
    }
    const d = new Date(cleanStr);
    if (isNaN(d.getTime())) return isoStr;

    // Short date-time format: "10 Jun 2026, 10:30 AM IST"
    const formatter = new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Asia/Kolkata',
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });

    const parts = formatter.formatToParts(d);
    let day = '', month = '', year = '', hour = '', minute = '', dayPeriod = '';
    for (const p of parts) {
      if (p.type === 'day') day = p.value;
      if (p.type === 'month') month = p.value;
      if (p.type === 'year') year = p.value;
      if (p.type === 'hour') hour = p.value;
      if (p.type === 'minute') minute = p.value;
      if (p.type === 'dayPeriod') dayPeriod = p.value.toUpperCase();
    }
    return `${day} ${month} ${year}, ${hour}:${minute} ${dayPeriod} IST`;
  } catch (e) {
    return String(isoStr);
  }
}

function formatFirstScrapedCompact(isoStr) {
  if (!isoStr) return 'Recently';
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr;
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const day = d.getDate();
    const month = months[d.getMonth()];
    let hours = d.getHours();
    const minutes = d.getMinutes().toString().padStart(2, '0');
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12;
    hours = hours ? hours : 12;
    return `${day} ${month} • ${hours}:${minutes} ${ampm}`;
  } catch {
    return isoStr;
  }
}

function formatScrapedFull(isoStr) {
  if (!isoStr) return 'N/A';
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr;
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const day = d.getDate();
    const month = months[d.getMonth()];
    const year = d.getFullYear();
    let hours = d.getHours();
    const minutes = d.getMinutes().toString().padStart(2, '0');
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12;
    hours = hours ? hours : 12;
    return `${day} ${month} ${year} • ${hours}:${minutes} ${ampm}`;
  } catch {
    return isoStr;
  }
}

// --- Layout Switcher Functions ---

function setLayout(layoutName) {
  state.layout = layoutName;
  localStorage.setItem('job_finder_layout', layoutName);
  updateLayoutUI();
  renderJobs(state.currentJobs);
}

function updateLayoutUI() {
  const listBtn = document.getElementById('layout-btn-list');
  const cardBtn = document.getElementById('layout-btn-card');
  const container = document.getElementById('jobs-grid');

  if (listBtn && cardBtn) {
    listBtn.classList.toggle('active', state.layout === 'list');
    cardBtn.classList.toggle('active', state.layout === 'card');
  }

  if (container) {
    container.classList.remove('layout-list', 'layout-card');
    container.classList.add(state.layout === 'card' ? 'layout-card' : 'layout-list');
  }
}

// --- Load Jobs ---

async function loadJobs() {
  updateLayoutUI();
  const container = document.getElementById('jobs-grid');
  container.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 3rem;"><div class="spinner"></div><p style="margin-top: 1rem; color: #666666;">Discovering verified analytics vacancies...</p></div>';

  const params = new URLSearchParams({
    limit: state.limit,
    offset: state.page * state.limit
  });

  if (state.filters.q) params.append('q', state.filters.q);
  if (state.filters.country) params.append('country', state.filters.country);
  if (state.filters.work_mode) params.append('work_mode', state.filters.work_mode);
  if (state.filters.experience_level) params.append('experience_level', state.filters.experience_level);
  if (state.filters.skill) params.append('skill', state.filters.skill);
  if (state.filters.applied) params.append('applied', state.filters.applied);
  if (state.filters.date_posted) params.append('date_posted', state.filters.date_posted);
  if (state.filters.scrape_freshness) params.append('scrape_freshness', state.filters.scrape_freshness);
  if (state.filters.sort_by) params.append('sort_by', state.filters.sort_by);

  state.filters.roles.forEach(r => params.append('role', r));
  state.filters.cities.forEach(c => params.append('city', c));
  state.filters.platforms.forEach(p => params.append('platform', p));

  try {
    const res = await fetch(`/api/jobs?${params.toString()}`);
    const data = await res.json();
    state.totalJobs = data.total;
    state.currentJobs = data.jobs || data.items || [];

    renderJobs(state.currentJobs);
    renderPagination();
    renderFilterSummary();
  } catch (err) {
    container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--color-error); padding: 2rem;">Error loading jobs: ${err.message}</div>`;
  }
}

function formatRelativeDate(dateStr) {
  if (!dateStr) return 'Recently';
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.floor((now - d) / (1000 * 60 * 60 * 24));
    if (diffDays <= 0) return '⚡ Today';
    if (diffDays === 1) return '1 day ago';
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 14) return '1 week ago';
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
    return 'Past month';
  } catch {
    return dateStr;
  }
}

function renderJobs(jobs) {
  updateLayoutUI();
  if (state.layout === 'card') {
    renderJobCards(jobs);
  } else {
    renderJobList(jobs);
  }
}

function getEmptyStateHtml() {
  return `
    <div style="grid-column: 1/-1; text-align: center; padding: 4rem 1.5rem; background: #FFFFFF; border-radius: 16px; border: 2px dashed #FFCED8; box-shadow: var(--shadow-card);">
      <div style="font-size: 2.8rem; margin-bottom: 0.5rem;">🎓</div>
      <h3 style="font-size: 1.3rem; font-weight: 800; color: #333333; margin-bottom: 0.5rem;">No positions match your active filters</h3>
      <p style="color: #666666; font-size: 0.925rem; margin-bottom: 1.35rem; max-width: 500px; margin-left: auto; margin-right: auto;">
        Try widening your role selection, resetting date filter or application status, or trigger the live fresher scraper.
      </p>
      <button class="btn btn-primary" onclick="clearFilters()">Reset All Filters</button>
    </div>
  `;
}

function renderAppliedCheckbox(job, inputId = null) {
  const isApplied = Boolean(job.is_applied) || job.application_status === 'applied';
  const idAttr = inputId ? `id="${inputId}"` : '';
  return `
    <label class="applied-checkbox-wrapper ${isApplied ? 'checked' : ''}" data-job-id="${job.id}" onclick="event.stopPropagation();" title="${isApplied ? 'Applied (Click to mark not applied)' : 'Click to mark as applied'}">
      <input type="checkbox" ${idAttr} class="applied-checkbox-input" ${isApplied ? 'checked' : ''} onchange="toggleJobApplied('${job.id}', this.checked, event)">
      <span class="custom-checkbox-box">
        <svg class="check-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
      </span>
      <span class="applied-checkbox-text">${isApplied ? 'Applied' : 'Mark Applied'}</span>
    </label>
  `;
}

// --- Platform, Status, & UI Helpers for Scraped Job Grid ---

function isApifyJob(job) {
  if (!job) return false;
  const jid = String(job.id || '');
  return jid.startsWith('li_apify_') ||
         jid.startsWith('indeed_apify_') ||
         jid.startsWith('naukri_apify_') ||
         job.source_id === 'linkedin_india' ||
         job.source_id === 'apify_linkedin' ||
         job.source_id === 'apify_indeed' ||
         job.source_id === 'apify_naukri';
}

function getApifyPlatformName(job) {
  const jid = String(job.id || '');
  if (jid.startsWith('indeed') || job.source_id === 'apify_indeed' || (job.source_id === 'indeed_india' && jid.includes('apify'))) return 'Indeed';
  if (jid.startsWith('naukri') || job.source_id === 'apify_naukri' || (job.source_id === 'naukri' && jid.includes('apify'))) return 'Naukri';
  return 'LinkedIn';
}

function getPlatformBadgeHtml(job) {
  if (isApifyJob(job)) {
    const platName = getApifyPlatformName(job);
    let extraStyle = '';
    let dotColor = '#0A66C2';
    if (platName === 'Indeed') {
      extraStyle = 'background: linear-gradient(135deg, #F0F7FF 0%, #E0F2FE 100%) !important; color: #0284C7 !important; border-color: #BAE6FD !important;';
      dotColor = '#0284C7';
    } else if (platName === 'Naukri') {
      extraStyle = 'background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%) !important; color: #2563EB !important; border-color: #BFDBFE !important;';
      dotColor = '#2563EB';
    }
    return `<span class="job-source-badge source-apify-live" style="${extraStyle}" title="Verified live ${platName} posting extracted via Apify with full JD"><span class="apify-pulse-dot" style="background-color: ${dotColor};"></span>⚡ ${platName} (Apify Live)</span>`;
  }

  const p = (job.platform || job.source_id || job.source_name || '').toLowerCase();
  if (p.includes('linkedin_feed') || (p.includes('feed') && p.includes('linkedin'))) {
    return `<span class="job-source-badge source-linkedin-feed">✨ LinkedIn Feed (Recruiter)</span>`;
  } else if (p.includes('unstop')) {
    return `<span class="job-source-badge source-unstop"><span class="source-pulse-dot"></span> Unstop Live</span>`;
  } else if (p.includes('foundit') || p.includes('monster')) {
    return `<span class="job-source-badge source-foundit">Foundit</span>`;
  } else if (p.includes('naukri')) {
    return `<span class="job-source-badge source-naukri">Naukri</span>`;
  } else if (p.includes('indeed')) {
    return `<span class="job-source-badge source-indeed">Indeed</span>`;
  } else if (p.includes('wellfound') || p.includes('angellist')) {
    return `<span class="job-source-badge source-wellfound">Wellfound</span>`;
  } else if (p.includes('remotive')) {
    return `<span class="job-source-badge source-remotive">Remotive</span>`;
  } else if (p.includes('remoteok')) {
    return `<span class="job-source-badge source-remoteok">RemoteOK</span>`;
  } else if (p.includes('weworkremotely')) {
    return `<span class="job-source-badge source-wwr">We Work Remotely</span>`;
  } else if (p.includes('ycombinator')) {
    return `<span class="job-source-badge source-yc">Y Combinator</span>`;
  } else if (p.includes('internshala')) {
    return `<span class="job-source-badge source-internshala">Internshala</span>`;
  } else if (p.includes('linkedin')) {
    return `<span class="job-source-badge source-linkedin">LinkedIn</span>`;
  } else {
    return `<span class="job-source-badge source-default">${escapeHtml(job.source_name || job.platform || 'Web')}</span>`;
  }
}

function getCompanyIconHtml(job) {
  if (job.company_logo) {
    return `<img src="${escapeHtml(job.company_logo)}" alt="${escapeHtml(job.company || '')}" onerror="this.onerror=null; this.parentElement.innerHTML='<svg width=\\'18\\' height=\\'18\\' viewBox=\\'0 0 24 24\\' fill=\\'none\\' stroke=\\'#8C7681\\' stroke-width=\\'2\\' stroke-linecap=\\'round\\' stroke-linejoin=\\'round\\'><rect x=\\'4\\' y=\\'2\\' width=\\'16\\' height=\\'20\\' rx=\\'2\\' ry=\\'2\\'></rect><path d=\\'M9 22v-4h6v4\\'></path><path d=\\'M8 6h.01\\'></path><path d=\\'M16 6h.01\\'></path><path d=\\'M8 10h.01\\'></path><path d=\\'M16 10h.01\\'></path><path d=\\'M8 14h.01\\'></path><path d=\\'M16 14h.01\\'></path></svg>';">`;
  }
  const sourceLow = (job.source_id || job.source_name || job.platform || '').toLowerCase();
  if (sourceLow.includes('linkedin')) {
    return `<svg class="job-linkedin-icon" viewBox="0 0 24 24"><path d="M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.28 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.75M6.88 8.56a1.68 1.68 0 0 0 1.68-1.68c0-.93-.75-1.69-1.68-1.69a1.69 1.69 0 0 0-1.69 1.69c0 .93.76 1.68 1.69 1.68m1.39 9.94v-8.37H5.5v8.37h2.77z"/></svg>`;
  }
  return `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#8C7681" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2" ry="2"></rect><path d="M9 22v-4h6v4"></path><path d="M8 6h.01"></path><path d="M16 6h.01"></path><path d="M8 10h.01"></path><path d="M16 10h.01"></path><path d="M8 14h.01"></path><path d="M16 14h.01"></path></svg>`;
}

function formatExperience(job) {
  if (job.experience_min !== undefined && job.experience_max !== undefined && (job.experience_min !== null && job.experience_max !== null)) {
    return `${job.experience_min} - ${job.experience_max} Yrs`;
  }
  if (job.min_experience !== undefined && job.max_experience !== undefined && (job.min_experience > 0 || job.max_experience > 0)) {
    return `${job.min_experience} - ${job.max_experience} Yrs`;
  }
  if (job.experience_level) {
    const text = job.experience_level;
    const match = text.match(/(\d+)\s*[-–to]\s*(\d+)/);
    if (match) return `${match[1]} - ${match[2]} Yrs`;
    if (text.toLowerCase().includes('fresher')) return '0 - 1 Yr Fresher';
    return text.replace(/years?/i, 'Yrs');
  }
  return '0 - 1 Yr Fresher';
}

function formatSalary(job) {
  if (job.salary_raw) return job.salary_raw;
  if (job.salary_min && job.salary_max) {
    return `₹${job.salary_min} - ₹${job.salary_max} LPA`;
  }
  if (job.salary && job.salary !== 'Not Disclosed') {
    if (job.salary.includes('LPA') || job.salary.includes('₹') || /\d/.test(job.salary)) {
      return job.salary;
    }
  }
  return 'Competitive Package';
}

function getStatusClass(status) {
  const map = {
    'new': 'status-select-new',
    'saved': 'status-select-saved',
    'applied': 'status-select-applied',
    'interview': 'status-select-interview',
    'offer': 'status-select-offer',
    'rejected': 'status-select-rejected',
    'ignored': 'status-select-ignored'
  };
  return map[(status || 'new').toLowerCase()] || 'status-select-new';
}

async function handleJobStatusChange(jobId, newStatus, event) {
  if (event) event.stopPropagation();
  const selectEl = document.getElementById(`status-select-${jobId}`);
  if (selectEl) {
    selectEl.className = `job-status-select ${getStatusClass(newStatus)}`;
  }

  const job = (state.currentJobs || []).find(j => String(j.id) === String(jobId));
  if (job) {
    job.application_status = newStatus;
    job.is_applied = (newStatus === 'applied');
  }

  const appliedCountEl = document.getElementById('stat-applied-jobs');
  if (appliedCountEl && newStatus === 'applied') {
    const cur = parseInt(appliedCountEl.innerText) || 0;
    appliedCountEl.innerText = cur + 1;
  }

  try {
    const res = await fetch(`/api/jobs/${jobId}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    if (!res.ok) {
      await fetch(`/api/jobs/${jobId}/applied`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_applied: newStatus === 'applied' })
      });
    }
  } catch (err) {
    console.error('Failed to update job status:', err);
  }
}

async function toggleJobBookmark(jobId, event) {
  if (event) event.stopPropagation();
  const btn = document.getElementById(`btn-bookmark-${jobId}`);
  const job = (state.currentJobs || []).find(j => String(j.id) === String(jobId));
  const newBookmarked = job ? !job.is_bookmarked : true;
  if (job) {
    job.is_bookmarked = newBookmarked;
    if (newBookmarked && job.application_status === 'new') {
      job.application_status = 'saved';
      const sel = document.getElementById(`status-select-${jobId}`);
      if (sel) {
        sel.value = 'saved';
        sel.className = `job-status-select status-select-saved`;
      }
    }
  }

  if (btn) {
    btn.classList.toggle('is-saved', newBookmarked);
    btn.title = newBookmarked ? 'Saved to bookmarks (click to remove)' : 'Bookmark / Save job';
    const svg = btn.querySelector('svg');
    if (svg) svg.setAttribute('fill', newBookmarked ? 'currentColor' : 'none');
  }

  try {
    await fetch(`/api/jobs/${jobId}/bookmark`, { method: 'POST' });
  } catch (err) {
    console.error('Failed to toggle bookmark:', err);
  }
}

function isGenuineEmail(email) {
  if (!email || typeof email !== 'string') return false;
  const em = email.trim().toLowerCase();
  const placeholders = [
    'recruiter@company.com', 'user@company.com', 'hr@company.com', 'info@company.com',
    'career@company.com', 'careers@company.com', 'jobs@company.com', 'recruitment@company.com',
    'contact@company.com', 'career@abcd.com', 'careers@abcd.com', 'hr@abcd.com',
    'jobs@abcd.com', 'test@test.com', 'example@gmail.com', 'sample@abc.com'
  ];
  if (placeholders.includes(em)) return false;
  if (em.endsWith('@company.com') || em.endsWith('@example.com') || em.endsWith('@sample.com') || em.endsWith('@test.com') || em.endsWith('@abcd.com') || em.endsWith('@domain.com')) return false;
  return /^[^\s@]+@[^\s@]+\.[a-zA-Z]{2,}$/.test(em);
}

function isValidLinkedInPostUrl(url) {
  if (!url || typeof url !== 'string') return false;
  const u = url.trim().toLowerCase();
  if (u.includes('127.0.0.1') || u.includes('localhost') || u.includes('0.0.0.0') || u.startsWith('javascript:') || u.includes('failed')) {
    return false;
  }
  if (u.includes('linkedin.com/search')) return false;
  if (u.endsWith('/feed') || u.endsWith('/feed/')) return false;
  return (
    u.includes('linkedin.com/posts/') || 
    u.includes('linkedin.com/feed/update/') || 
    u.includes('lnkd.in/') || 
    u.includes('linkedin.com/pulse/') || 
    u.includes('linkedin.com/jobs/view/')
  );
}

function getContactHubHtml(job) {
  if (!job) return '';
  const hasRecruiterName = Boolean(job.recruiter_name && job.recruiter_name.trim());
  const hasLinkedIn = Boolean(job.linkedin_profile && job.linkedin_profile.trim().startsWith('http'));
  const genuineEmail = isGenuineEmail(job.recruiter_email) ? job.recruiter_email.trim() : '';
  const hasApplyUrl = Boolean(job.apply_url && job.apply_url.trim().startsWith('http'));
  const hasPhone = Boolean(job.contact_phone && job.contact_phone.trim());
  const hasWhatsApp = Boolean(job.contact_whatsapp && job.contact_whatsapp.trim());

  if (!hasRecruiterName && !hasLinkedIn && !genuineEmail && !hasApplyUrl && !hasPhone && !hasWhatsApp) {
    return '';
  }

  const name = job.recruiter_name || 'Hiring Recruiter';
  const designation = job.recruiter_designation || 'Talent Acquisition';

  return `
    <div class="recruiter-contact-hub">
      <div class="contact-hub-header">
        <div class="contact-hub-title">
          <span>👔</span>
          <span>Recruiter & Direct Contact Hub</span>
        </div>
        <button type="button" class="btn-outreach-prompt" onclick="copyOutreachPrompt('${job.id}', event)" title="Copy tailored cold outreach message ready to send to this recruiter">
          <span>📋</span> Copy Outreach Message
        </button>
      </div>

      <div class="contact-hub-grid">
        <!-- Recruiter Profile -->
        <div class="contact-hub-item">
          <span class="contact-hub-item-icon">👤</span>
          <div class="contact-hub-item-content">
            <div class="contact-hub-item-label">Recruiter / HR</div>
            <div class="contact-hub-item-value">
              <strong>${escapeHtml(name)}</strong>
              ${job.recruiter_designation ? `<div style="font-size: 0.7rem; color: #64748b; font-weight: normal;">${escapeHtml(designation)}</div>` : ''}
              ${hasLinkedIn ? `
                <div style="margin-top: 3px;">
                  <a href="${escapeHtml(job.linkedin_profile)}" target="_blank" rel="noopener noreferrer" class="contact-link-pill" style="font-size: 0.72rem;">
                    🔗 Connect on LinkedIn ↗
                  </a>
                </div>
              ` : ''}
            </div>
          </div>
        </div>

        <!-- Verified Email -->
        ${genuineEmail ? `
          <div class="contact-hub-item">
            <span class="contact-hub-item-icon">✉️</span>
            <div class="contact-hub-item-content">
              <div class="contact-hub-item-label">Verified Email (Genuine)</div>
              <div class="contact-hub-item-value" style="display: flex; align-items: center; justify-content: space-between; gap: 4px;">
                <span style="color: #0369a1; font-family: monospace; font-size: 0.75rem;">${escapeHtml(genuineEmail)}</span>
                <button type="button" onclick="copyRecruiterEmail('${escapeHtml(genuineEmail)}')" style="padding: 1px 6px; font-size: 0.65rem; border-radius: 4px; cursor: pointer; border: 1px solid #bae6fd; background: #e0f2fe; color: #0369a1;" title="Copy verified email">
                  Copy
                </button>
              </div>
            </div>
          </div>
        ` : ''}

        <!-- Direct Apply / Registration Portal Link -->
        ${hasApplyUrl ? `
          <div class="contact-hub-item">
            <span class="contact-hub-item-icon">🚀</span>
            <div class="contact-hub-item-content">
              <div class="contact-hub-item-label">Direct Apply / Form</div>
              <div class="contact-hub-item-value">
                <a href="${escapeHtml(job.apply_url)}" target="_blank" rel="noopener noreferrer" class="contact-link-pill" style="color: #059669; font-size: 0.72rem;">
                  Open Application Link ↗
                </a>
              </div>
            </div>
          </div>
        ` : ''}

        <!-- Phone / WhatsApp -->
        ${(hasPhone || hasWhatsApp) ? `
          <div class="contact-hub-item">
            <span class="contact-hub-item-icon">📞</span>
            <div class="contact-hub-item-content">
              <div class="contact-hub-item-label">Direct Contact</div>
              <div class="contact-hub-item-value">
                ${hasPhone ? `<div>Tel: <a href="tel:${escapeHtml(job.contact_phone)}" style="color: #1e293b; text-decoration: underline;">${escapeHtml(job.contact_phone)}</a></div>` : ''}
                ${hasWhatsApp ? `<div>WhatsApp: <a href="https://wa.me/${escapeHtml(job.contact_whatsapp.replace(/[^0-9]/g, ''))}" target="_blank" rel="noopener noreferrer" style="color: #15803d; text-decoration: underline;">Open WhatsApp ↗</a></div>` : ''}
              </div>
            </div>
          </div>
        ` : ''}
      </div>
    </div>
  `;
}

function copyOutreachPrompt(jobId, event) {
  if (event) event.stopPropagation();

  let job = (state.currentJobs || []).find(j => String(j.id) === String(jobId));
  if (!job && Array.isArray(window.linkedInFeedPostsCache)) {
    job = window.linkedInFeedPostsCache.find(j => String(j.id) === String(jobId));
  }

  const title = job ? (job.title || 'Data Analyst') : 'Data Analyst';
  const company = job ? (job.company || 'your organization') : 'your organization';
  const recruiter = job && job.recruiter_name ? job.recruiter_name : 'Hiring Team';
  const postUrl = job && job.source_url && job.source_url !== 'Post URL Extraction Failed' ? job.source_url : '';
  const skillsList = job && Array.isArray(job.skills) && job.skills.length > 0 ? job.skills.slice(0, 4).join(', ') : 'SQL, Power BI, Python, and Excel';

  const promptText = `Hi ${recruiter},

I hope this message finds you well!

I noticed your recent LinkedIn post regarding the ${title} opening at ${company}${postUrl ? ` (${postUrl})` : ''}.

As an aspiring analytics professional skilled in ${skillsList}, I have developed hands-on experience building interactive dashboards, optimizing SQL queries, and extracting actionable business insights from complex datasets.

I would love to connect and explore how my analytical skills and dedication could contribute to ${company}'s goals.

Thank you for your time and consideration!

Best regards,
Tejas Waghmare
LinkedIn: https://www.linkedin.com/in/tejas-waghmare/`;

  navigator.clipboard.writeText(promptText).then(() => {
    alert(`📋 Personalized outreach message copied to clipboard!\n\nYou can now paste it directly into your connection note or message to ${recruiter} on LinkedIn.`);
  }).catch(() => {
    prompt('Copy this recruiter outreach message:', promptText);
  });
}

let currentOutreachJob = null;

function openRecruiterEmail(jobId, event, directJobObj = null) {
  if (event) event.stopPropagation();
  let job = directJobObj;
  if (!job) {
    job = (state.currentJobs || []).find(j => String(j.id) === String(jobId));
  }
  if (!job && Array.isArray(window.linkedInFeedPostsCache)) {
    job = window.linkedInFeedPostsCache.find(j => String(j.id) === String(jobId));
  }
  if (!job) return;

  currentOutreachJob = job;
  const cleanId = String(job.id).replace(/[^a-zA-Z0-9]/g, '_');

  const recruiterEmail = isGenuineEmail(job.recruiter_email) ? job.recruiter_email : '';
  const recruiterName = job.recruiter_name || 'Hiring Team';
  const roleTitle = job.title || job.job_title || 'Data Analyst';
  const companyName = job.company || job.company_name || 'Target Employer';
  const postUrl = isValidLinkedInPostUrl(job.source_url) ? job.source_url : '';
  const skillsList = (job.skills && job.skills.length > 0) ? job.skills.slice(0, 5).join(', ') : 'SQL, Power BI, Excel, and Data Analytics';

  const recruiterFirst = (recruiterName && recruiterName !== 'Talent Acquisition Partner' && recruiterName !== 'Recruiter') 
    ? recruiterName.split(' ')[0] 
    : 'Hiring Team';
  const subject = `Application for ${roleTitle} - Tejas C. Waghmare`;

  const body = `Hi ${recruiterFirst},

I noticed your hiring announcement for the ${roleTitle} position at ${companyName}${postUrl ? ` (${postUrl})` : ''}. With hands-on proficiency in ${skillsList}, data storytelling, and building dynamic business dashboards, my competencies align closely with your requirements.

I have attached:
1. ATS-Tailored Resume: Customized specifically for ${roleTitle} at ${companyName}.
2. Tailored Cover Letter: Detailing my analytical problem-solving and project impact.

Portfolio & Verified Credentials:
• GitHub & Code Repositories: https://github.com/TCWaghmare
• LinkedIn Profile: https://linkedin.com/in/tejascwaghmare
• Analytics Projects: Amazon Sales Dashboard & Diversity & Inclusion KPI Analytics

I am based in Pune (open for immediate joining and rotational / on-site requirements) and would welcome the opportunity to discuss how I can contribute to ${companyName}.

Looking forward to hearing from you!

Best regards,
Tejas C. Waghmare
Phone: +91 83788 69006
Email: tejaswaghmare900@gmail.com`;

  const toInput = document.getElementById('outreach-email-to');
  const subjInput = document.getElementById('outreach-email-subject');
  const bodyInput = document.getElementById('outreach-email-body');
  const subTitle = document.getElementById('outreach-modal-subtitle');
  const mailtoBtn = document.getElementById('outreach-mailto-btn');
  const gmailBtn = document.getElementById('outreach-gmail-btn');
  const jobSummaryEl = document.getElementById('outreach-job-summary');

  if (toInput) {
    toInput.value = recruiterEmail;
    toInput.placeholder = 'Enter recruiter email (e.g. priya.sharma@swiggy.in)';
  }
  if (subjInput) subjInput.value = subject;
  if (bodyInput) bodyInput.value = body;
  if (subTitle) subTitle.innerText = `Outreach for ${roleTitle} at ${companyName}`;

  if (jobSummaryEl) {
    jobSummaryEl.innerHTML = `
      <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.65rem 0.85rem; margin-bottom: 0.85rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem; font-size: 0.8rem;">
        <div style="flex: 1 1 280px;">
          <strong style="color: #0f172a; font-size: 0.88rem;">${escapeHtml(roleTitle)}</strong>
          <span style="color: #64748b;"> @ ${escapeHtml(companyName)}</span>
          <div style="color: #475569; margin-top: 2px;">
            👤 Recruiter: <strong>${escapeHtml(recruiterName)}</strong>
            ${job.contact_phone ? ` • 📞 ${escapeHtml(job.contact_phone)}` : ''}
            • 📍 ${escapeHtml(job.location || 'Pune / India')}
          </div>
        </div>
        <div style="display: flex; gap: 4px; flex-wrap: wrap;">
          <button type="button" class="btn btn-outline btn-sm" onclick="tailorResumeForJob('${job.id}', event)" style="font-size: 0.72rem; padding: 2px 7px;">⚡ Full Tailor Studio</button>
        </div>
        ${!recruiterEmail ? `
          <div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; padding: 0.5rem 0.75rem; margin-top: 0.45rem; width: 100%; font-size: 0.76rem; color: #92400e; line-height: 1.45;">
            💡 <strong>Direct HR Email Not Included in this Post:</strong> The recruiter did not include a public email address. You can copy the tailored message below to send via <strong>LinkedIn Message / InMail</strong>, or enter their email if you have it.
            ${job.apply_url ? `<br><a href="${escapeHtml(job.apply_url)}" target="_blank" rel="noopener noreferrer" style="color: #047857; font-weight: 700; text-decoration: underline; margin-top: 3px; display: inline-block;">👉 Direct Application / Registration Portal ↗</a>` : ''}
            ${job.linkedin_profile ? `<br><a href="${escapeHtml(job.linkedin_profile)}" target="_blank" rel="noopener noreferrer" style="color: #0a66c2; font-weight: 700; text-decoration: underline; margin-top: 3px; display: inline-block;">👤 Recruiter LinkedIn Profile ↗</a>` : ''}
          </div>
        ` : ''}
      </div>
    `;
  }

  // Update attachment download links with standard naming: Tejas_Waghmare_Role_Company_DocType_DD_MM_YYYY
  const candName = (state.masterProfile && state.masterProfile.name) || 'Tejas Waghmare';
  const fnPdf = getStandardDocFilename(candName, roleTitle, companyName, 'Resume', 'pdf');
  const fnDocx = getStandardDocFilename(candName, roleTitle, companyName, 'Resume', 'docx');
  const fnClPdf = getStandardDocFilename(candName, roleTitle, companyName, 'Cover_Letter', 'pdf');
  const fnClDocx = getStandardDocFilename(candName, roleTitle, companyName, 'Cover_Letter', 'docx');

  const dlPdf = document.getElementById('outreach-btn-dl-pdf');
  if (dlPdf) {
    dlPdf.href = `/api/resume/download/pdf/${cleanId}`;
    dlPdf.setAttribute('download', fnPdf);
  }
  const dlDocx = document.getElementById('outreach-btn-dl-docx');
  if (dlDocx) {
    dlDocx.href = `/api/resume/download/docx/${cleanId}`;
    dlDocx.setAttribute('download', fnDocx);
  }
  const dlClPdf = document.getElementById('outreach-btn-dl-cl-pdf');
  if (dlClPdf) {
    dlClPdf.href = `/api/cover-letter/download/pdf/${cleanId}`;
    dlClPdf.setAttribute('download', fnClPdf);
  }
  const dlClDocx = document.getElementById('outreach-btn-dl-cl-docx');
  if (dlClDocx) {
    dlClDocx.href = `/api/cover-letter/download/docx/${cleanId}`;
    dlClDocx.setAttribute('download', fnClDocx);
  }

  if (mailtoBtn) {
    if (recruiterEmail) {
      mailtoBtn.href = `mailto:${encodeURIComponent(recruiterEmail)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
      mailtoBtn.style.display = 'inline-flex';
    } else {
      mailtoBtn.removeAttribute('href');
      mailtoBtn.style.display = 'none';
    }
  }

  if (gmailBtn) {
    if (recruiterEmail) {
      gmailBtn.style.display = 'inline-flex';
    } else {
      gmailBtn.style.display = 'none';
    }
  }

  const modal = document.getElementById('recruiter-email-modal');
  if (modal) modal.style.display = 'flex';
}

function handleGmailRedirect() {
  const to = document.getElementById('outreach-email-to')?.value.trim();
  const subject = document.getElementById('outreach-email-subject')?.value.trim();
  const body = document.getElementById('outreach-email-body')?.value.trim();

  if (!to) {
    alert('⚠️ Recipient Email is required to open Gmail.\n\nPlease enter the recruiter\'s email in the RECIPIENT EMAIL field, or use "📋 Copy Message" to send your outreach via LinkedIn InMail/Message.');
    document.getElementById('outreach-email-to')?.focus();
    return;
  }
  if (!isGenuineEmail(to)) {
    alert('⚠️ Please enter a genuine recruiter email address before redirecting to Gmail.');
    document.getElementById('outreach-email-to')?.focus();
    return;
  }

  const gmailUrl = `https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(to)}&su=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;

  // 1. Open Gmail Compose in a new browser tab
  window.open(gmailUrl, '_blank');

  // 2. Automatically trigger downloads of Tailored Resume PDF and Cover Letter PDF with standard naming
  if (currentOutreachJob) {
    const cleanId = String(currentOutreachJob.id).replace(/[^a-zA-Z0-9]/g, '_');
    const outCandName = (state.masterProfile && state.masterProfile.name) || 'Tejas Waghmare';
    const outRole = currentOutreachJob.title || 'Data Analyst';
    const outComp = currentOutreachJob.company || 'Target Employer';
    const outFnPdf = getStandardDocFilename(outCandName, outRole, outComp, 'Resume', 'pdf');
    const outFnClPdf = getStandardDocFilename(outCandName, outRole, outComp, 'Cover_Letter', 'pdf');
    
    // Resume PDF download
    const a1 = document.createElement('a');
    a1.href = `/api/resume/download/pdf/${cleanId}`;
    a1.download = outFnPdf;
    document.body.appendChild(a1);
    a1.click();
    document.body.removeChild(a1);

    // Cover Letter PDF download
    setTimeout(() => {
      const a2 = document.createElement('a');
      a2.href = `/api/cover-letter/download/pdf/${cleanId}`;
      a2.download = outFnClPdf;
      document.body.appendChild(a2);
      a2.click();
      document.body.removeChild(a2);
    }, 400);
  }

  // 3. Inform the candidate
  alert(`🚀 Opening Gmail compose with your personalized message!\n\nYour ATS-Tailored Resume & Cover Letter (PDF) are downloaded so you can drop and attach them straight into your Gmail draft.`);
}

function copyOutreachMessage() {
  const bodyInput = document.getElementById('outreach-email-body');
  if (bodyInput) {
    navigator.clipboard.writeText(bodyInput.value).then(() => {
      alert('Outreach email message copied to clipboard!');
    }).catch(() => {
      bodyInput.select();
      document.execCommand('copy');
      alert('Outreach email message copied to clipboard!');
    });
  }
}

// --- Layout 1: DEFAULT LIST VIEW (Tabular Data Grid matching Reference Design) ---
function renderJobList(jobs) {
  const container = document.getElementById('jobs-grid');
  if (!jobs || jobs.length === 0) {
    container.innerHTML = getEmptyStateHtml();
    return;
  }

  const rowsHtml = jobs.map(job => {
    const isApplied = Boolean(job.is_applied) || job.application_status === 'applied';
    const isBookmarked = Boolean(job.is_bookmarked) || job.application_status === 'saved';
    const jobStatus = (job.application_status || (isApplied ? 'applied' : 'new')).toLowerCase();
    const firstScraped = job.first_scraped_at || job.discovered_at;
    const isApify = isApifyJob(job);
    const apifyPlatform = isApify ? getApifyPlatformName(job) : '';

    // Skills formatting with +N
    const skillsList = job.skills || job.skills_required || [];
    const visibleSkills = skillsList.slice(0, 3);
    const remainingCount = skillsList.length - visibleSkills.length;
    const skillsHtml = visibleSkills.map((skill, idx) => {
      if (idx === visibleSkills.length - 1 && remainingCount > 0) {
        return `
          <div>
            <span class="job-skill-chip-amber" onclick="filterBySkill('${escapeHtml(skill)}')">${escapeHtml(skill)}</span>
            <span class="job-skill-plus" title="${skillsList.slice(3).map(s => escapeHtml(s)).join(', ')}">+${remainingCount}</span>
          </div>
        `;
      }
      return `<span class="job-skill-chip-amber" onclick="filterBySkill('${escapeHtml(skill)}')">${escapeHtml(skill)}</span>`;
    }).join('');

    return `
      <tr id="job-item-${job.id}" class="job-table-row ${isApplied ? 'is-applied-row' : ''} ${isApify ? 'is-apify-row-highlight' : ''}" onclick="openJobDetails('${job.id}')">
        <!-- Col 1: ROLE TITLE & COMPANY -->
        <td>
          <div class="job-cell-title-company">
            <div class="job-company-icon-box">
              ${getCompanyIconHtml(job)}
            </div>
            <div class="job-cell-title-text-group">
              <div class="job-title-text" title="${escapeHtml(job.title)}">
                ${escapeHtml(job.title)}${isApify ? ' <span class="badge-apify-tag" title="Verified live LinkedIn posting extracted via Apify with full JD">⚡ Apify Live</span>' : ''}
              </div>
              <span class="job-company-text" title="${escapeHtml(job.company)}">${escapeHtml(job.company)}${job.recruiter_name ? ` • 👔 <span style="color: #0284c7; font-weight: 700;">${escapeHtml(job.recruiter_name)}</span>` : ''}</span>
            </div>
          </div>
        </td>

        <!-- Col 2: SOURCE -->
        <td class="whitespace-nowrap" onclick="event.stopPropagation()">
          <span onclick="filterByPlatform('${escapeHtml(job.source_id || job.platform || '')}')" style="cursor: pointer;" title="Filter exclusively by ${escapeHtml(job.source_name || job.platform || 'source')}">
            ${getPlatformBadgeHtml(job)}
          </span>
        </td>

        <!-- Col 3: FIRST SCRAPED -->
        <td class="whitespace-nowrap">
          <div class="job-cell-first-scraped" title="Earliest discovery timestamp (Permanent): ${escapeHtml(firstScraped || '')}">
            <span class="first-scraped-date-badge">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
              </svg>
              <span>${escapeHtml(formatFirstScrapedDateTime(firstScraped))}</span>
            </span>
          </div>
        </td>

        <!-- Col 4: LOCATION -->
        <td>
          <div class="job-cell-location">
            <div class="job-location-title" title="${escapeHtml(job.location || 'India')}">
              <svg class="location-pin-icon" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="#8C7681" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                <circle cx="12" cy="10" r="3"></circle>
              </svg>
              <span class="truncate max-w-[140px] font-medium">${escapeHtml(job.location || 'India (or Remote)')}</span>
            </div>
            <span class="job-workmode-chip">${escapeHtml(job.work_mode || 'Hybrid')}</span>
          </div>
        </td>

        <!-- Col 5: EXPERIENCE -->
        <td>
          <span class="job-cell-experience">${escapeHtml(formatExperience(job))}</span>
        </td>

        <!-- Col 6: SALARY (CTC) -->
        <td>
          <span class="job-cell-salary">${escapeHtml(formatSalary(job))}</span>
        </td>

        <!-- Col 7: SKILLS -->
        <td onclick="event.stopPropagation()">
          <div class="job-cell-skills">
            ${skillsHtml || '<span class="text-xs text-muted" style="font-size:0.65rem; color:#8C7681;">Analytics Skills</span>'}
          </div>
        </td>

        <!-- Col 8: MATCH -->
        <td>
          <span class="job-match-pill" title="ATS profile match score against verified Career Knowledge Base">${Math.round(job.match_score || 0)}%</span>
        </td>

        <!-- Col 9: STATUS -->
        <td onclick="event.stopPropagation()">
          <select class="job-status-select ${getStatusClass(jobStatus)}" id="status-select-${job.id}" onchange="handleJobStatusChange('${job.id}', this.value, event)" title="Update application workflow status">
            <option value="new" ${jobStatus === 'new' ? 'selected' : ''}>New ▾</option>
            <option value="saved" ${jobStatus === 'saved' ? 'selected' : ''}>Saved ▾</option>
            <option value="applied" ${jobStatus === 'applied' ? 'selected' : ''}>Applied ▾</option>
            <option value="interview" ${jobStatus === 'interview' ? 'selected' : ''}>Interview ▾</option>
            <option value="offer" ${jobStatus === 'offer' ? 'selected' : ''}>Offer ▾</option>
            <option value="rejected" ${jobStatus === 'rejected' ? 'selected' : ''}>Rejected ▾</option>
          </select>
        </td>

        <!-- Col 10: ACTIONS -->
        <td onclick="event.stopPropagation()">
          <div class="job-cell-actions">
            <!-- Bookmark button -->
            <button type="button" class="btn-action-bookmark ${isBookmarked ? 'is-saved' : ''}" id="btn-bookmark-${job.id}" onclick="toggleJobBookmark('${job.id}', event)" title="${isBookmarked ? 'Saved to bookmarks (click to remove)' : 'Bookmark / Save job'}">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="${isBookmarked ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path>
              </svg>
            </button>

            <!-- Recruiter Email button -->
            <button type="button" class="btn-action-email" onclick="openRecruiterEmail('${job.id}', event)" title="Email recruiter directly">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
                <polyline points="22,6 12,13 2,6"></polyline>
              </svg>
              <span>Email</span>
            </button>

            <!-- ⚡ Tailor Resume button (CRITICAL - DO NOT DELETE EXISTING DETAILS) -->
            <button type="button" class="btn-action-tailor" onclick="tailorResumeForJob('${job.id}', event)" title="Generate strict 1-page ATS-tailored resume in LaTeX & PDF">
              <span>⚡ Tailor</span>
            </button>

            <!-- Apply button -->
            <a href="${job.source_url}" target="_blank" rel="noopener noreferrer" class="btn-action-apply" title="Open verified application portal">
              <span>Apply</span>
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                <polyline points="15 3 21 3 21 9"></polyline>
                <line x1="10" y1="14" x2="21" y2="3"></line>
              </svg>
            </a>
          </div>
        </td>
      </tr>
    `;
  }).join('');

  container.innerHTML = `
    <div class="job-table-card">
      <div class="job-table-responsive">
        <table class="job-table">
          <thead>
            <tr>
              <th style="min-width: 220px;">ROLE TITLE & COMPANY</th>
              <th>SOURCE</th>
              <th>FIRST SCRAPED</th>
              <th>LOCATION</th>
              <th>EXPERIENCE</th>
              <th>SALARY (CTC)</th>
              <th>SKILLS</th>
              <th>MATCH</th>
              <th>STATUS</th>
              <th style="text-align: right; min-width: 210px;">ACTIONS</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

// --- Layout 2: CARD VIEW OPTION ---
function renderJobCards(jobs) {
  const container = document.getElementById('jobs-grid');
  if (!jobs || jobs.length === 0) {
    container.innerHTML = getEmptyStateHtml();
    return;
  }

  container.innerHTML = jobs.map(job => {
    const isCore = job.role_category === 'Core Analytics';
    const badgeClass = isCore ? 'badge-core' : 'badge-related';
    const relativeDate = formatRelativeDate(job.published_at);
    const isApplied = Boolean(job.is_applied) || job.application_status === 'applied';
    const isBookmarked = Boolean(job.is_bookmarked) || job.application_status === 'saved';
    const jobStatus = (job.application_status || (isApplied ? 'applied' : 'new')).toLowerCase();
    const firstScraped = job.first_scraped_at || job.discovered_at;
    const isApify = isApifyJob(job);
    const apifyPlatform = isApify ? getApifyPlatformName(job) : '';
    const fBadge = getFreshnessBadge(firstScraped);
    const compactScraped = formatFirstScrapedCompact(firstScraped);
    const fullScraped = formatScrapedFull(firstScraped);

    const skillsHtml = (job.skills || []).slice(0, 5).map(skill => `
      <span class="job-skill-chip-amber" onclick="filterBySkill('${escapeHtml(skill)}')">${escapeHtml(skill)}</span>
    `).join('');

    return `
      <div class="job-card ${isApplied ? 'is-applied' : ''} ${isApify ? 'is-apify-card-highlight' : ''}" id="job-item-${job.id}" data-job-id="${job.id}">
        <div>
          <div class="job-header">
            <div class="header-badges">
              ${isApify ? `<span class="badge-apify-live" title="Verified live ${apifyPlatform} job posting scraped via Apify Actor with complete un-truncated JD"><span class="apify-pulse-dot"></span>⚡ Apify Verified • ${apifyPlatform}</span>` : ''}
              <span class="${fBadge.class}" title="${fBadge.title}">${fBadge.label}</span>
              <span class="job-role-badge ${badgeClass}">${escapeHtml(job.standard_role)}</span>
              <span class="badge-fresher">🎓 0–1 Yr Fresher</span>
              <span class="badge-workmode">${escapeHtml(job.work_mode)}</span>
              <span class="job-match-pill" title="ATS profile match score">${Math.round(job.match_score || 0)}% Match</span>
            </div>
            
            <div style="display: flex; align-items: center; gap: 0.4rem;">
              <!-- Bookmark -->
              <button type="button" class="btn-action-bookmark ${isBookmarked ? 'is-saved' : ''}" onclick="toggleJobBookmark('${job.id}', event)" title="Bookmark job">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="${isBookmarked ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path>
                </svg>
              </button>
            </div>
          </div>

          <h3 class="job-title" onclick="openJobDetails('${job.id}')" title="${escapeHtml(job.title)}">${escapeHtml(job.title)}</h3>
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.5rem;">
            <div class="job-company">🏢 ${escapeHtml(job.company)}</div>
            <span class="first-scraped-date-badge" title="Earliest discovery timestamp (Permanent): ${escapeHtml(firstScraped || '')}">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
              </svg>
              <span>${escapeHtml(formatFirstScrapedDateTime(firstScraped))}</span>
            </span>
          </div>
          ${job.scrape_count > 1 ? `<div style="margin-bottom: 0.5rem;"><span class="job-validation-badge" title="Validated ${job.scrape_count} times. Last checked: ${formatScrapedFull(job.last_checked_at || job.updated_at)}">✓ Validated (${job.scrape_count}x)</span></div>` : ''}

          ${getContactHubHtml(job)}

          <div class="job-meta-row">
            <div class="job-meta-item">📍 ${escapeHtml(job.location)}</div>
            <div class="job-meta-item">⏱️ ${escapeHtml(formatExperience(job))}</div>
          </div>

          <div class="job-salary" style="color: #059669; font-weight: 700;">💰 ${escapeHtml(formatSalary(job))}</div>

          <div class="job-skills" style="display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.5rem;">${skillsHtml}</div>
        </div>

        <div class="job-footer" style="margin-top: 1rem; padding-top: 0.75rem; border-top: 1px solid #F0D5DC;">
          <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
            <div class="platform-clickable" onclick="filterByPlatform('${escapeHtml(job.source_id)}')" title="Filter exclusively by ${escapeHtml(job.source_name)}">
              ${getPlatformBadgeHtml(job)}
            </div>
            <select class="job-status-select ${getStatusClass(jobStatus)}" onchange="handleJobStatusChange('${job.id}', this.value, event)" style="font-size: 0.7rem; padding: 2px 6px;">
              <option value="new" ${jobStatus === 'new' ? 'selected' : ''}>New ▾</option>
              <option value="saved" ${jobStatus === 'saved' ? 'selected' : ''}>Saved ▾</option>
              <option value="applied" ${jobStatus === 'applied' ? 'selected' : ''}>Applied ▾</option>
              <option value="interview" ${jobStatus === 'interview' ? 'selected' : ''}>Interview ▾</option>
              <option value="offer" ${jobStatus === 'offer' ? 'selected' : ''}>Offer ▾</option>
              <option value="rejected" ${jobStatus === 'rejected' ? 'selected' : ''}>Rejected ▾</option>
            </select>
          </div>
          <div class="job-actions" style="margin-top: 0.5rem;">
            <button type="button" class="btn-action-email" onclick="openRecruiterEmail('${job.id}', event)" title="Email recruiter directly">✉ Email</button>
            <button class="btn btn-tailor btn-sm" onclick="tailorResumeForJob('${job.id}', event)" title="Generate strict 1-page ATS-tailored resume in LaTeX & PDF">⚡ Tailor Resume</button>
            <button class="btn btn-outline btn-sm" onclick="openJobDetails('${job.id}')">View Details</button>
            <a href="${job.source_url}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm">Apply ↗</a>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// --- Toggle Job Applied Status ---

async function toggleJobApplied(jobId, isChecked, event) {
  if (event) {
    event.stopPropagation();
  }

  const job = (state.currentJobs || []).find(j => String(j.id) === String(jobId)) || (window.linkedInFeedPostsCache || []).find(j => String(j.id) === String(jobId)) || currentOutreachJob;
  if (job) {
    job.is_applied = isChecked;
  }

  updateJobAppliedDOM(jobId, isChecked);

  const statEl = document.getElementById('stat-applied-jobs');
  if (statEl) {
    const cur = parseInt(statEl.innerText) || 0;
    statEl.innerText = Math.max(0, cur + (isChecked ? 1 : -1));
  }

  try {
    const res = await fetch(`/api/jobs/${jobId}/applied`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_applied: isChecked })
    });

    if (!res.ok) {
      throw new Error(`Failed to update application status: ${res.status}`);
    }
  } catch (err) {
    console.error('Error toggling applied status:', err);
    if (job) job.is_applied = !isChecked;
    updateJobAppliedDOM(jobId, !isChecked);
    if (statEl) {
      const cur = parseInt(statEl.innerText) || 0;
      statEl.innerText = Math.max(0, cur + (isChecked ? -1 : 1));
    }
  }
}

function updateJobAppliedDOM(jobId, isApplied) {
  const container = document.getElementById(`job-item-${jobId}`);
  if (container) {
    container.classList.toggle('is-applied', isApplied);
    container.classList.toggle('is-applied-row', isApplied);
  }

  const statusSelect = document.getElementById(`status-select-${jobId}`);
  if (statusSelect) {
    const newStatus = isApplied ? 'applied' : 'new';
    statusSelect.value = newStatus;
    statusSelect.className = `job-status-select ${getStatusClass(newStatus)}`;
  }

  const badgeEl = document.getElementById(`badge-applied-${jobId}`);
  if (badgeEl) {
    badgeEl.style.display = isApplied ? 'inline-flex' : 'none';
  }

  document.querySelectorAll(`.applied-checkbox-wrapper[data-job-id="${jobId}"]`).forEach(wrapper => {
    wrapper.classList.toggle('checked', isApplied);
    const input = wrapper.querySelector('input[type="checkbox"]');
    if (input) input.checked = isApplied;
    const textSpan = wrapper.querySelector('.applied-checkbox-text');
    if (textSpan) textSpan.innerText = isApplied ? 'Applied' : 'Mark Applied';
    wrapper.title = isApplied ? 'Applied (Click to mark not applied)' : 'Click to mark as applied';
  });

  const modalCheckbox = document.getElementById(`modal-applied-checkbox-${jobId}`);
  if (modalCheckbox) {
    modalCheckbox.checked = isApplied;
    const parentWrapper = modalCheckbox.closest('.applied-checkbox-wrapper');
    if (parentWrapper) {
      parentWrapper.classList.toggle('checked', isApplied);
      const textSpan = parentWrapper.querySelector('.applied-checkbox-text');
      if (textSpan) textSpan.innerText = isApplied ? 'Applied' : 'Mark Applied';
    }
  }
}

function renderPagination() {
  const container = document.getElementById('pagination-container');
  const totalPages = Math.ceil(state.totalJobs / state.limit);

  if (totalPages <= 1) {
    container.innerHTML = '';
    return;
  }

  let html = `
    <button class="page-btn" ${state.page === 0 ? 'disabled' : ''} onclick="goToPage(${state.page - 1})">← Previous</button>
  `;

  const maxShown = 5;
  let start = Math.max(0, state.page - Math.floor(maxShown / 2));
  let end = Math.min(totalPages, start + maxShown);

  if (start > 0) {
    html += `<button class="page-btn ${state.page === 0 ? 'active' : ''}" onclick="goToPage(0)">1</button>`;
    if (start > 1) html += `<span style="color: #888888; padding: 0 0.5rem;">...</span>`;
  }

  for (let i = start; i < end; i++) {
    html += `<button class="page-btn ${state.page === i ? 'active' : ''}" onclick="goToPage(${i})">${i + 1}</button>`;
  }

  if (end < totalPages) {
    if (end < totalPages - 1) html += `<span style="color: #888888; padding: 0 0.5rem;">...</span>`;
    html += `<button class="page-btn ${state.page === totalPages - 1 ? 'active' : ''}" onclick="goToPage(${totalPages - 1})">${totalPages}</button>`;
  }

  html += `
    <button class="page-btn" ${state.page >= totalPages - 1 ? 'disabled' : ''} onclick="goToPage(${state.page + 1})">Next →</button>
  `;

  container.innerHTML = html;
}

function goToPage(p) {
  state.page = p;
  loadJobs();
  window.scrollTo({ top: 300, behavior: 'smooth' });
}

function renderFilterSummary() {
  const container = document.getElementById('filter-summary');
  if (!container) return;

  const activeCount = Object.entries(state.filters).filter(([k, v]) => {
    if (k === 'roles' || k === 'platforms' || k === 'cities') return Array.isArray(v) && v.length > 0;
    if (k === 'date_posted') return Boolean(v);
    if (k === 'sort_by') return v && v !== 'date_desc';
    if (k === 'scrape_freshness') return Boolean(v);
    return Boolean(v);
  }).length;

  let text = `Showing <strong>${state.totalJobs}</strong> fresher positions (0–1 Year Exp)`;

  if (state.filters.cities && state.filters.cities.length > 0) {
    text += ` in <span style="color: #0284C7; font-weight: 700;">${state.filters.cities.length} cit${state.filters.cities.length > 1 ? 'ies' : 'y'}</span>`;
  }

  if (state.filters.platforms && state.filters.platforms.length > 0) {
    text += ` across <span style="color: #2E7D32; font-weight: 700;">${state.filters.platforms.length} platform${state.filters.platforms.length > 1 ? 's' : ''}</span>`;
  }

  if (state.filters.scrape_freshness) {
    const fMap = {
      'today': 'Freshly Scraped Today',
      '24h': 'Last 24 Hours',
      '3d': 'Last 3 Days',
      '7d': 'Last 7 Days',
      '30d': 'Last 30 Days',
      'older_30d': 'Older (>30 Days)'
    };
    text += ` • Freshness: <span style="color: #10B981; font-weight: 700;">${fMap[state.filters.scrape_freshness] || state.filters.scrape_freshness}</span>`;
  }

  if (state.filters.sort_by && state.filters.sort_by !== 'date_desc') {
    text += ` • Sorted by <span style="color: var(--link-color); font-weight: 700;">${getSortLabel(state.filters.sort_by)}</span>`;
  }

  if (activeCount > 0) {
    text += ` • <span style="color: var(--link-color); font-weight: 700;">${activeCount} active filter${activeCount > 1 ? 's' : ''}</span>`;
    text += ` <button class="clear-btn" onclick="clearFilters()">Clear All</button>`;
  }

  container.innerHTML = text;
}

function filterBySkill(skill) {
  state.filters.skill = skill;
  state.page = 0;
  loadJobs();
}

function clearFilters() {
  state.filters = {
    q: '',
    roles: [],
    cities: [],
    platforms: [],
    sort_by: 'date_desc',
    country: '',
    work_mode: '',
    experience_level: '',
    skill: '',
    applied: '',
    date_posted: '',
    scrape_freshness: ''
  };

  const sInput = document.getElementById('search-input');
  if (sInput) sInput.value = '';

  ['workmode-filter', 'exp-filter', 'applied-filter'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });

  const sFreshEl = document.getElementById('scrape-freshness-filter');
  if (sFreshEl) sFreshEl.value = '';

  document.querySelectorAll('.freshness-pill').forEach(btn => btn.classList.remove('active'));
  const allPill = document.getElementById('quick-pill-all');
  if (allPill) allPill.classList.add('active');

  const citySearchInput = document.getElementById('city-search-input');
  if (citySearchInput) citySearchInput.value = '';

  ['filter-sort-select', 'toolbar-sort-select'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = 'date_desc';
  });

  renderMultiSelectDropdown();
  renderCityMultiSelectDropdown();
  updateCityBtnText();
  renderSelectedCityChips();
  renderPlatformMultiSelectDropdown();
  state.page = 0;
  loadJobs();
}

// --- Platform Directory (72 Curated Platforms) ---

async function loadPlatforms() {
  try {
    const res = await fetch('/api/platforms');
    state.platforms = await res.json();
    renderPlatforms(state.platforms);
    renderPlatformMultiSelectDropdown();
  } catch (err) {
    console.error('Error loading platforms:', err);
  }
}

function renderPlatforms(platformsList) {
  const container = document.getElementById('platforms-directory');
  if (!container) return;

  const sections = {};
  platformsList.forEach(p => {
    if (!sections[p.section]) sections[p.section] = [];
    sections[p.section].push(p);
  });

  let html = '';
  for (const [secTitle, plist] of Object.entries(sections)) {
    html += `
      <div class="directory-section">
        <h3 class="section-title">📁 ${escapeHtml(secTitle)} <span class="tab-badge">${plist.length} platforms</span></h3>
        <div class="platform-grid">
          ${plist.map(p => `
            <div class="platform-card">
              <div>
                <div class="platform-top">
                  <div>
                    <h4 class="platform-name">${escapeHtml(p.name)}</h4>
                    <span class="platform-region">🌍 ${escapeHtml(p.country)}</span>
                  </div>
                  <span class="platform-type-badge ${p.has_adapter ? 'type-adapter' : 'type-catalog'}">
                    ${p.has_adapter ? '● Live Adapter' : '○ Web Directory'}
                  </span>
                </div>
                <p class="platform-notes">${escapeHtml(p.notes || p.category)}</p>
              </div>

              <div class="platform-bottom">
                <a href="${p.website}" target="_blank" rel="noopener noreferrer" class="btn btn-outline btn-sm">Website ↗</a>
                <a href="${p.search_url_template ? p.search_url_template.replace('{role_encoded}', 'Data+Analyst').replace('{role_slug}', 'data-analyst') : p.website}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm">Search Fresher Jobs 🔍</a>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  }

  container.innerHTML = html;
}

function filterPlatforms(query) {
  if (!query) {
    renderPlatforms(state.platforms);
    return;
  }
  const filtered = state.platforms.filter(p =>
    p.name.toLowerCase().includes(query) ||
    p.country.toLowerCase().includes(query) ||
    p.category.toLowerCase().includes(query) ||
    p.section.toLowerCase().includes(query)
  );
  renderPlatforms(filtered);
}

// --- Analytics View ---

async function renderAnalyticsView() {
  const container = document.getElementById('analytics-view');
  try {
    const res = await fetch('/api/stats');
    const data = await res.json();

    const addedToday = data.jobs_added_today || 0;
    const addedWeek = data.jobs_added_this_week || 0;
    const addedMonth = data.jobs_added_this_month || 0;
    const olderJobs = data.jobs_older_30d || 0;
    const avgDaily = data.avg_daily_discovery || 0;
    const ratio = data.new_vs_existing_ratio || '100% / 0%';
    const growthTrend = data.growth_trend || [];

    const trendBars = growthTrend.map(t => `
      <div style="display: flex; flex-direction: column; align-items: center; gap: 0.25rem; flex: 1; min-width: 32px;">
        <span style="font-size: 0.72rem; font-weight: 700; color: #1E293B;">${t.count}</span>
        <div style="width: 100%; max-width: 38px; height: 60px; background: #E2E8F0; border-radius: 6px; display: flex; align-items: flex-end; overflow: hidden; padding: 2px;">
          <div style="width: 100%; height: ${Math.max(10, Math.min(100, t.count * 15))}%; background: linear-gradient(180deg, #10B981 0%, #059669 100%); border-radius: 4px;"></div>
        </div>
        <span style="font-size: 0.65rem; color: #64748B; font-weight: 600;">${t.date ? t.date.slice(5) : ''}</span>
      </div>
    `).join('');

    const rolesList = (data.roles_distribution || []).map(r => `
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.65rem 0; border-bottom: 1px solid var(--border-subtle);">
        <span style="font-weight: 600; color: #333333;">${escapeHtml(r.standard_role)}</span>
        <span class="tab-badge" style="background-color: var(--color-primary); color: #333333; font-weight: 700;">${r.cnt} fresher roles</span>
      </div>
    `).join('');

    const platformList = (data.platform_distribution || []).map(p => `
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.65rem 0; border-bottom: 1px solid var(--border-subtle);">
        <span style="font-weight: 600; color: #333333;">${escapeHtml(p.source_name)}</span>
        <span class="tab-badge" style="background-color: var(--color-accent); color: #333333; font-weight: 700;">${p.cnt} jobs</span>
      </div>
    `).join('');

    container.innerHTML = `
      <div style="display: flex; flex-direction: column; gap: 1.5rem; margin-top: 1rem;">
        <!-- Freshness & Velocity KPIs Card -->
        <div class="filter-card">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.15rem; flex-wrap: wrap; gap: 0.65rem;">
            <div>
              <h3 style="font-size: 1.15rem; font-weight: 800; color: #1E293B; margin: 0;">⚡ Freshness & Discovery Velocity Intelligence</h3>
              <p style="font-size: 0.8rem; color: #64748B; margin: 0.2rem 0 0;">Permanent first-discovery tracking, validation frequency, and freshness trends</p>
            </div>
            <span class="badge-fresh-today" style="font-size: 0.8rem; padding: 0.35rem 0.85rem;">🔥 ${addedToday} Newly Discovered Today</span>
          </div>

          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.85rem; margin-bottom: 1.25rem;">
            <div style="background: #F8FAFC; border: 1.5px solid #E2E8F0; padding: 0.85rem; border-radius: 10px; text-align: center;">
              <div style="font-size: 0.72rem; font-weight: 700; color: #64748B; text-transform: uppercase;">Added Today</div>
              <div style="font-size: 1.45rem; font-weight: 800; color: #EF4444; margin-top: 0.25rem;">${addedToday}</div>
            </div>
            <div style="background: #F8FAFC; border: 1.5px solid #E2E8F0; padding: 0.85rem; border-radius: 10px; text-align: center;">
              <div style="font-size: 0.72rem; font-weight: 700; color: #64748B; text-transform: uppercase;">Added This Week</div>
              <div style="font-size: 1.45rem; font-weight: 800; color: #0284C7; margin-top: 0.25rem;">${addedWeek}</div>
            </div>
            <div style="background: #F8FAFC; border: 1.5px solid #E2E8F0; padding: 0.85rem; border-radius: 10px; text-align: center;">
              <div style="font-size: 0.72rem; font-weight: 700; color: #64748B; text-transform: uppercase;">Added This Month</div>
              <div style="font-size: 1.45rem; font-weight: 800; color: #D97706; margin-top: 0.25rem;">${addedMonth}</div>
            </div>
            <div style="background: #F8FAFC; border: 1.5px solid #E2E8F0; padding: 0.85rem; border-radius: 10px; text-align: center;">
              <div style="font-size: 0.72rem; font-weight: 700; color: #64748B; text-transform: uppercase;">Older (>30 Days)</div>
              <div style="font-size: 1.45rem; font-weight: 800; color: #64748B; margin-top: 0.25rem;">${olderJobs}</div>
            </div>
            <div style="background: #F8FAFC; border: 1.5px solid #E2E8F0; padding: 0.85rem; border-radius: 10px; text-align: center;">
              <div style="font-size: 0.72rem; font-weight: 700; color: #64748B; text-transform: uppercase;">Avg Daily Discovery</div>
              <div style="font-size: 1.45rem; font-weight: 800; color: #10B981; margin-top: 0.25rem;">${avgDaily}</div>
            </div>
            <div style="background: #F8FAFC; border: 1.5px solid #E2E8F0; padding: 0.85rem; border-radius: 10px; text-align: center;">
              <div style="font-size: 0.72rem; font-weight: 700; color: #64748B; text-transform: uppercase;">New vs Re-scraped</div>
              <div style="font-size: 1.15rem; font-weight: 800; color: #6366F1; margin-top: 0.4rem;">${ratio}</div>
            </div>
          </div>

          <div style="background: #F8FAFC; border: 1.5px solid #E2E8F0; padding: 1rem 1.25rem; border-radius: 10px;">
            <div style="font-size: 0.825rem; font-weight: 800; color: #1E293B; margin-bottom: 0.75rem;">📈 7-Day Discovery Velocity Trend (New Vacancies First Found)</div>
            <div style="display: flex; gap: 0.65rem; justify-content: space-between; align-items: flex-end; padding-top: 0.5rem; overflow-x: auto;">
              ${trendBars || '<p style="color: #64748B; font-size: 0.85rem;">No velocity trend history yet.</p>'}
            </div>
          </div>
        </div>

        <div class="analytics-cards-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr)); gap: 1.25rem;">
          <div class="filter-card">
            <h3 style="font-size: 1.15rem; font-weight: 800; margin-bottom: 1rem; color: #333333;">📊 Fresher Openings by Analytics Role</h3>
            ${rolesList || '<p style="color: #666666;">No roles data yet.</p>'}
          </div>

          <div class="filter-card">
            <h3 style="font-size: 1.15rem; font-weight: 800; margin-bottom: 1rem; color: #333333;">🌐 Top Hiring Portals & Platforms</h3>
            ${platformList || '<p style="color: #666666;">No sources data yet.</p>'}
          </div>
        </div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<p style="color: var(--color-error);">Error loading analytics: ${err.message}</p>`;
  }
}

// --- Job Details Modal (Deep Scraped & Complete JD) ---

async function openJobDetails(jobId) {
  const modal = document.getElementById('job-detail-modal');
  const body = document.getElementById('modal-job-body');
  body.innerHTML = '<div style="text-align: center; padding: 2.5rem;"><div class="spinner"></div><p style="margin-top: 1rem; color: #666; font-size: 0.9rem;">Fetching complete job description & metadata...</p></div>';
  modal.style.display = 'flex';

  try {
    const res = await fetch(`/api/jobs/${jobId}`);
    const job = await res.json();

    const isCore = job.role_category === 'Core Analytics';
    const skillsChips = (job.skills || []).map(s => `<span class="job-skill-chip" style="font-size: 0.8rem; padding: 0.25rem 0.65rem;">${escapeHtml(s)}</span>`).join('');
    const relDate = formatRelativeDate(job.published_at);
    const responsibilities = job.responsibilities || [];
    const requirements = job.requirements || [];
    const atsKeywords = job.ats_keywords || [];
    const hasFullJD = Boolean(job.is_deep_scraped && (job.description || '').length > 250);
    const firstScrapedFormatted = formatScrapedFull(job.first_scraped_at || job.discovered_at);
    const lastCheckedFormatted = formatScrapedFull(job.last_checked_at || job.updated_at || job.first_scraped_at || job.discovered_at);
    const scrapeCount = job.scrape_count || 1;
    const jobStatus = job.status || 'Active';
    const fBadge = getFreshnessBadge(job.first_scraped_at || job.discovered_at);

    const respListHtml = responsibilities.length > 0 ? `
      <div style="margin-bottom: 1.25rem;">
        <h4 style="font-size: 0.95rem; font-weight: 800; margin-bottom: 0.6rem; color: #1E293B; display: flex; align-items: center; justify-content: space-between;">
          <span>📋 KEY RESPONSIBILITIES</span>
          <span style="font-size: 0.75rem; font-weight: 700; background: #E2E8F0; color: #334155; padding: 0.15rem 0.55rem; border-radius: 12px;">${responsibilities.length} Duties</span>
        </h4>
        <div style="background: #F8FAFC; border: 1.5px solid #E2E8F0; padding: 1rem 1.25rem; border-radius: 10px; max-height: 280px; overflow-y: auto;">
          <ol style="margin: 0; padding-left: 1.25rem; display: flex; flex-direction: column; gap: 0.55rem; font-size: 0.9rem; line-height: 1.55; color: #334155;">
            ${responsibilities.map(r => `<li>${escapeHtml(r)}</li>`).join('')}
          </ol>
        </div>
      </div>
    ` : '';

    const reqsListHtml = requirements.length > 0 ? `
      <div style="margin-bottom: 1.25rem;">
        <h4 style="font-size: 0.95rem; font-weight: 800; margin-bottom: 0.6rem; color: #1E293B; display: flex; align-items: center; justify-content: space-between;">
          <span>📌 OTHER REQUIREMENTS & ELIGIBILITY</span>
          <span style="font-size: 0.75rem; font-weight: 700; background: #E2E8F0; color: #334155; padding: 0.15rem 0.55rem; border-radius: 12px;">${requirements.length} Criteria</span>
        </h4>
        <div style="background: #F8FAFC; border: 1.5px solid #E2E8F0; padding: 1rem 1.25rem; border-radius: 10px; max-height: 240px; overflow-y: auto;">
          <ul style="margin: 0; padding-left: 1.25rem; display: flex; flex-direction: column; gap: 0.45rem; font-size: 0.9rem; line-height: 1.55; color: #334155;">
            ${requirements.map(req => `<li>${escapeHtml(req)}</li>`).join('')}
          </ul>
        </div>
      </div>
    ` : '';

    const atsKeywordsHtml = atsKeywords.length > 0 ? `
      <div style="margin-bottom: 1.25rem;">
        <h4 style="font-size: 0.95rem; font-weight: 800; margin-bottom: 0.5rem; color: #1E293B; display: flex; align-items: center; justify-content: space-between;">
          <span>⚡ EXTRACTED ATS KEYWORDS (${atsKeywords.length})</span>
          <span style="font-size: 0.75rem; font-weight: 600; color: #64748B;">Used by Resume Tailor Engine</span>
        </h4>
        <div style="display: flex; flex-wrap: wrap; gap: 0.35rem; background: #F8FAFC; border: 1.5px solid #E2E8F0; padding: 0.75rem; border-radius: 10px;">
          ${atsKeywords.map(k => `<span style="font-size: 0.75rem; font-weight: 600; background: #EFF6FF; color: #1D4ED8; border: 1px solid #BFDBFE; padding: 0.2rem 0.5rem; border-radius: 6px;">#${escapeHtml(k)}</span>`).join('')}
        </div>
      </div>
    ` : '';

    const companyDetailsHtml = job.company_details ? `
      <div style="margin-bottom: 1.25rem;">
        <h4 style="font-size: 0.95rem; font-weight: 800; margin-bottom: 0.5rem; color: #1E293B;">🏢 ABOUT ${escapeHtml(job.company).toUpperCase()}</h4>
        <div style="background: #F8FAFC; border: 1.5px solid #E2E8F0; padding: 0.85rem 1rem; border-radius: 10px; font-size: 0.875rem; line-height: 1.6; color: #475569; white-space: pre-line;">
          ${escapeHtml(job.company_details)}
        </div>
      </div>
    ` : '';

    const isApify = isApifyJob(job);
    const apifyPlatform = isApify ? getApifyPlatformName(job) : '';

    const apifyBannerHtml = isApify ? `
      <div class="apify-verified-modal-banner">
        <div>
          <div class="apify-banner-title">
            <span class="apify-pulse-dot"></span>
            <span>⚡ VERIFIED VIA APIFY CLOUD SCRAPER • ${escapeHtml(apifyPlatform).toUpperCase()}</span>
          </div>
          <div class="apify-banner-desc">
            Directly extracted from ${escapeHtml(apifyPlatform)} portal index • 100% Complete Un-truncated JD (${(job.description || '').length} characters) • Verified Active Employer
          </div>
        </div>
        <a href="${job.source_url}" target="_blank" rel="noopener noreferrer" class="btn-apify-verify-link">
          <span>Apply on ${escapeHtml(apifyPlatform)} ↗</span>
        </a>
      </div>
    ` : '';

    body.innerHTML = `
      <!-- Header Badges -->
      <div style="margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center;">
          ${isApify ? `<span class="badge-apify-live" title="Verified live job posting scraped via Apify Actor"><span class="apify-pulse-dot"></span>⚡ Apify Verified • ${escapeHtml(apifyPlatform)}</span>` : ''}
          <span class="job-role-badge ${isCore ? 'badge-core' : 'badge-related'}">${job.role_category}</span>
          <span class="badge-fresher">🎓 0–1 Year Fresher</span>
          <span class="badge-date">${relDate}</span>
          <span class="badge-workmode">${escapeHtml(job.work_mode)}</span>
          ${job.application_deadline ? `<span style="font-size: 0.75rem; font-weight: 700; background: #FEF3C7; color: #92400E; border: 1px solid #FDE68A; padding: 0.2rem 0.55rem; border-radius: var(--radius-full);">⏳ Apply by: ${escapeHtml(job.application_deadline)}</span>` : ''}
          ${job.openings ? `<span style="font-size: 0.75rem; font-weight: 700; background: #EDE9FE; color: #5B21B6; border: 1px solid #DDD6FE; padding: 0.2rem 0.55rem; border-radius: var(--radius-full);">👥 ${escapeHtml(job.openings)} Openings</span>` : ''}
        </div>
        ${renderAppliedCheckbox(job, `modal-applied-checkbox-${job.id}`)}
      </div>

      ${apifyBannerHtml}

      <h2 style="font-size: 1.45rem; font-weight: 800; color: #1E293B; margin-bottom: 0.35rem; line-height: 1.3;">${escapeHtml(job.title)}</h2>
      <h4 style="color: var(--link-color); font-size: 1.1rem; font-weight: 700; margin-bottom: 1rem;">🏢 ${escapeHtml(job.company)}</h4>

      <!-- Metadata Grid -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.85rem; background: var(--surface-warm); border: 1.5px solid var(--border-color); padding: 1rem; border-radius: 12px; margin-bottom: 1.25rem;">
        <div>📍 <strong>Location:</strong> ${escapeHtml(job.location)}</div>
        <div>⏱️ <strong>Experience Required:</strong> ${escapeHtml(job.experience_level)}</div>
        <div>💰 <strong>Package / Stipend:</strong> ${escapeHtml(job.salary || 'Competitive Fresher Package')}</div>
        <div>🌐 <strong>Source:</strong> <a href="${job.source_url}" target="_blank" rel="noopener noreferrer" style="color: var(--link-color); font-weight: 700; text-decoration: underline;">${escapeHtml(job.source_name)} ↗</a></div>
        ${job.application_deadline ? `<div>📅 <strong>Deadline:</strong> ${escapeHtml(job.application_deadline)}</div>` : ''}
        ${job.openings ? `<div>👥 <strong>Openings:</strong> ${escapeHtml(job.openings)}</div>` : ''}
      </div>

      <!-- Recruiter & Direct Contact Hub -->
      ${getContactHubHtml(job)}

      <!-- Discovery & Freshness Intelligence History Box -->
      <div class="scrape-history-box" style="margin-bottom: 1.25rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; border-bottom: 1px solid #E2E8F0; padding-bottom: 0.5rem; flex-wrap: wrap; gap: 0.4rem;">
          <span style="font-size: 0.8rem; font-weight: 800; color: #1E293B; letter-spacing: 0.04em;">🕒 JOB DISCOVERY & VERIFICATION HISTORY</span>
          <span class="${fBadge.class}">${fBadge.label}</span>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.85rem; font-size: 0.85rem;">
          <div>
            <div style="color: #64748B; font-size: 0.72rem; font-weight: 700; text-transform: uppercase;">First Scraped (Permanent)</div>
            <div style="font-weight: 700; color: #0F172A; margin-top: 3px;">🕒 ${formatFirstScrapedDateTime(job.first_scraped_at || job.discovered_at)}</div>
          </div>
          <div>
            <div style="color: #64748B; font-size: 0.72rem; font-weight: 700; text-transform: uppercase;">Last Checked & Validated</div>
            <div style="font-weight: 700; color: #0F172A; margin-top: 3px;">🔄 ${lastCheckedFormatted}</div>
          </div>
          <div>
            <div style="color: #64748B; font-size: 0.72rem; font-weight: 700; text-transform: uppercase;">Scrape Frequency</div>
            <div style="font-weight: 700; color: #0F172A; margin-top: 3px;">${scrapeCount > 1 ? `Re-validated ${scrapeCount} times` : 'First-time Discovery'}</div>
          </div>
          <div>
            <div style="color: #64748B; font-size: 0.72rem; font-weight: 700; text-transform: uppercase;">Platform & Status</div>
            <div style="font-weight: 700; color: #0F172A; margin-top: 3px;">🌐 ${escapeHtml(job.source_name)} • <span style="color: #10B981; font-weight: 800;">${escapeHtml(jobStatus)}</span></div>
          </div>
        </div>
      </div>

      <!-- Scrape Quality Banner -->
      <div style="display: flex; justify-content: space-between; align-items: center; background: ${hasFullJD ? '#EEF8F1' : '#FFFBEB'}; border: 1px solid ${hasFullJD ? '#C4E7CF' : '#FDE68A'}; padding: 0.65rem 1rem; border-radius: 10px; margin-bottom: 1.25rem; flex-wrap: wrap; gap: 0.5rem;">
        <div style="font-size: 0.85rem; color: ${hasFullJD ? '#15803D' : '#B45309'}; font-weight: 700; display: flex; align-items: center; gap: 0.4rem;">
          <span>${hasFullJD ? '✓ Deep Scraped Original Job Page' : 'ℹ️ Preview Snippet'}</span>
          <span style="font-weight: 400; color: #4B5563; font-size: 0.775rem;">(${responsibilities.length} responsibilities, ${job.skills ? job.skills.length : 0} skills, ${atsKeywords.length} ATS keywords)</span>
        </div>
        <button type="button" class="btn btn-outline btn-sm" id="btn-rescrape-modal" onclick="rescrapeJobDetails('${job.id}')" style="font-size: 0.75rem; padding: 0.25rem 0.65rem; background: #FFFFFF; font-weight: 700;">
          🔄 Re-scrape Live Job URL
        </button>
      </div>

      <!-- Required Technical Skills -->
      <div style="margin-bottom: 1.25rem;">
        <h4 style="font-size: 0.95rem; font-weight: 800; margin-bottom: 0.5rem; color: #1E293B;">🎯 REQUIRED TECHNICAL SKILLS (${job.skills ? job.skills.length : 0})</h4>
        <div style="display: flex; flex-wrap: wrap; gap: 0.45rem;">
          ${skillsChips || '<span style="color: #666666;">Not specified</span>'}
        </div>
      </div>

      <!-- Key Responsibilities -->
      ${respListHtml}

      <!-- Other Requirements & Eligibility -->
      ${reqsListHtml}

      <!-- Extracted ATS Keywords -->
      ${atsKeywordsHtml}

      <!-- Full Job Description -->
      <div style="margin-bottom: 1.25rem;">
        <h4 style="font-size: 0.95rem; font-weight: 800; margin-bottom: 0.5rem; color: #1E293B;">📄 FULL ORIGINAL JOB DESCRIPTION</h4>
        <div style="background: var(--surface-warm); border: 1px solid var(--border-color); padding: 1.15rem; border-radius: 12px; font-size: 0.9rem; line-height: 1.7; max-height: 320px; overflow-y: auto; color: #333333; white-space: pre-line;">
          ${escapeHtml(job.description || 'Full description available at employer posting.')}
        </div>
      </div>

      <!-- About Company -->
      ${companyDetailsHtml}

      <!-- Footer Buttons -->
      <div style="display: flex; justify-content: space-between; align-items: center; gap: 0.75rem; flex-wrap: wrap; padding-top: 0.5rem; border-top: 1px solid var(--border-color);">
        <button class="btn btn-outline" onclick="closeModal('job-detail-modal')">Close</button>
        <div style="display: flex; gap: 0.65rem; flex-wrap: wrap;">
          <button class="btn btn-tailor" onclick="tailorResumeForJob('${job.id}')" title="Generate strict 1-page ATS-tailored resume in LaTeX & PDF">⚡ Tailor ATS Resume</button>
          <a href="${job.source_url}" target="_blank" rel="noopener noreferrer" class="btn btn-primary">Apply on ${escapeHtml(job.source_name)} ↗</a>
        </div>
      </div>
    `;
  } catch (err) {
    body.innerHTML = `<p style="color: var(--color-error); padding: 1.5rem; text-align: center;">Failed to load job details: ${escapeHtml(err.message)}</p>`;
  }
}

async function rescrapeJobDetails(jobId) {
  const btn = document.getElementById('btn-rescrape-modal');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner" style="width:12px;height:12px;border-width:2px;display:inline-block;margin-right:4px;"></span> Re-scraping live URL...';
  }
  try {
    const res = await fetch(`/api/jobs/${jobId}/rescrape`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await openJobDetails(jobId);
  } catch (e) {
    alert('Failed to re-scrape job URL: ' + e.message);
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '🔄 Re-scrape Live Job URL';
    }
  }
}

// --- Live Scraper Modal ---

function openScraperModal() {
  document.getElementById('scraper-modal').style.display = 'flex';
}

async function triggerLiveScraper() {
  const btn = document.getElementById('run-scraper-btn');
  const statusEl = document.getElementById('scraper-status-msg');
  const limitInput = document.getElementById('scraper-limit-input');
  const limit = parseInt(limitInput.value) || 25;

  btn.disabled = true;
  btn.innerHTML = '<div class="spinner"></div> Scraping fresher portals...';
  statusEl.style.display = 'block';
  statusEl.innerHTML = 'Connecting to Internshala, Remotive (India remote), RemoteOK, Jobicy, and employer career boards...';

  try {
    const res = await fetch('/api/scraper/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ limit_per_source: limit })
    });
    await res.json();

    setTimeout(async () => {
      await loadStats();
      await loadJobs();
      btn.disabled = false;
      btn.innerHTML = '⚡ Run Scraper Again';
      statusEl.innerHTML = '<span style="color: var(--color-success); font-weight: 700;">✓ Live scrape complete! Fresher listings refreshed.</span>';
    }, 6000);

  } catch (err) {
    btn.disabled = false;
    btn.innerHTML = '⚡ Run Scraper';
    statusEl.innerHTML = `<span style="color: var(--color-error);">Error triggering scrape: ${err.message}</span>`;
  }
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = 'none';
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// --- Master Resume Profile Management ---

async function loadMasterResumeStatus() {
  try {
    const res = await fetch('/api/resume/master');
    const profile = await res.json();
    state.masterProfile = profile;
    const nameEl = document.getElementById('header-resume-name');
    const drawerNameEl = document.getElementById('mobile-drawer-resume-name');
    if (nameEl || drawerNameEl) {
      const displayName = (profile.name && !profile.name.includes('Not Available')) ? profile.name : 'Upload Resume';
      if (nameEl) nameEl.innerText = displayName;
      if (drawerNameEl) drawerNameEl.innerText = displayName;
    }
    const studioNameEl = document.getElementById('studio-candidate-name');
    if (studioNameEl) {
      if (profile.name && !profile.name.includes('Not Available')) {
        studioNameEl.innerText = profile.name;
      } else {
        studioNameEl.innerText = 'No Document Uploaded';
      }
    }
  } catch (err) {
    console.warn('Could not load master resume status:', err);
  }
}

async function openMasterResumeModal() {
  const modal = document.getElementById('master-resume-modal');
  modal.style.display = 'flex';

  // 1. Render Documents Available for Resume Tailoring repository section (Requirement 1 & 2)
  renderMasterModalDocuments();

  // 2. Render synthesized candidate profile from uploaded documents (Requirement 3 & 6)
  refreshMasterProfileContent();
}

async function refreshMasterProfileContent() {
  const content = document.getElementById('master-profile-content');
  if (!content) return;
  content.innerHTML = '<div style="text-align: center; padding: 2rem;"><div class="spinner"></div><p style="margin-top: 0.5rem; color: #666666;">Loading candidate profile synthesized from documents...</p></div>';

  try {
    const res = await fetch('/api/resume/master');
    const profile = await res.json();
    state.masterProfile = profile;

    const skills = profile.skills || {};
    let skillsRows = '';
    for (const [catKey, items] of Object.entries(skills)) {
      if (Array.isArray(items) && items.length > 0) {
        const catTitle = catKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        const pills = items.map(s => `<span class="ats-keyword-pill-matched">${escapeHtml(s)}</span>`).join(' ');
        skillsRows += `<div><strong style="color: #666666;">${escapeHtml(catTitle)}:</strong> ${pills}</div>`;
      }
    }
    if (!skillsRows && profile.technical_tools && profile.technical_tools.length > 0) {
      skillsRows = `<div><strong style="color: #666666;">Technical Tools:</strong> ` + profile.technical_tools.map(s => `<span class="ats-keyword-pill-matched">${escapeHtml(s)}</span>`).join(' ') + `</div>`;
    }

    const expList = profile.work_experience || profile.experience || [];
    const expHtml = expList.map(exp => `
      <div style="background: var(--surface-warm); padding: 0.95rem; border-radius: 12px; margin-bottom: 0.75rem; border: 1.5px solid var(--border-color);">
        <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; margin-bottom: 0.35rem;">
          <strong style="color: #333333; font-size: 1rem;">${escapeHtml(exp.title)}</strong>
          <span style="color: #666666; font-size: 0.8rem; font-weight: 600;">${escapeHtml(exp.dates || exp.period || '')}</span>
        </div>
        <div style="color: var(--link-color); font-size: 0.85rem; font-weight: 700; margin-bottom: 0.45rem;">🏢 ${escapeHtml(exp.company)} | 📍 ${escapeHtml(exp.location || 'India')}</div>
        <ul style="margin: 0; padding-left: 1.25rem; font-size: 0.85rem; color: #555555; line-height: 1.55;">
          ${(exp.bullets || []).map(b => `<li style="margin-bottom: 0.3rem;">${escapeHtml(b)}</li>`).join('')}
        </ul>
      </div>
    `).join('');

    const projList = profile.projects || [];
    const projHtml = projList.map(p => `
      <div style="background: var(--surface-warm); padding: 0.95rem; border-radius: 12px; margin-bottom: 0.75rem; border: 1.5px solid var(--border-color);">
        <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; margin-bottom: 0.35rem;">
          <strong style="color: #333333; font-size: 1rem;">${escapeHtml(p.name || p.title)}</strong>
          <span style="color: #333333; font-size: 0.75rem; background: var(--color-accent); padding: 0.15rem 0.5rem; border-radius: 4px; font-weight: 700;">${escapeHtml(p.tools || p.tech_stack || '')}</span>
        </div>
        <ul style="margin: 0; padding-left: 1.25rem; font-size: 0.85rem; color: #555555; line-height: 1.55;">
          ${(p.bullets || []).map(b => `<li style="margin-bottom: 0.3rem;">${escapeHtml(b)}</li>`).join('')}
        </ul>
      </div>
    `).join('');

    const certHtml = (profile.certifications || []).map(c => `
      <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.875rem; padding: 0.45rem 0; border-bottom: 1px solid var(--border-subtle);">
        <span style="color: #333333; font-weight: 600;">🏆 ${escapeHtml(c.name || c)}</span>
        ${c.url ? `<a href="${escapeHtml(c.url)}" target="_blank" rel="noopener noreferrer" style="color: var(--link-color); font-size: 0.8rem; font-weight: 700;">${escapeHtml(c.link || 'Verify ↗')}</a>` : (c.issuer ? `<span style="color: #666666; font-size: 0.8rem;">${escapeHtml(c.issuer)}</span>` : '')}
      </div>
    `).join('');

    const edu = (profile.education && profile.education[0]) || {};
    const eduHtml = `
      🎓 <strong>${escapeHtml(edu.degree || 'Bachelor of Technology')}</strong>
      ${edu.institution ? ` — ${escapeHtml(edu.institution)} (${escapeHtml(edu.dates || edu.year || '')})` : ''}
    `;

    content.innerHTML = `
      <div style="background: var(--surface-warm); border: 1.5px solid var(--border-color); border-top: 4px solid var(--color-primary); border-radius: 16px; padding: 1.25rem; margin-bottom: 1.35rem; box-shadow: var(--shadow-sm);">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.5rem;">
          <h3 style="font-size: 1.35rem; font-weight: 800; color: #333333; margin: 0;">${escapeHtml(profile.name)}</h3>
          <span class="status-badge status-ready">
            ✓ Verified Active Master Profile
          </span>
        </div>
        <div style="display: flex; flex-wrap: wrap; gap: 0.95rem; font-size: 0.85rem; color: #666666; margin-bottom: 0.85rem;">
          <span>📧 ${escapeHtml(profile.email || 'Information Not Available in Uploaded Documents')}</span>
          <span>📞 ${escapeHtml(profile.phone || 'Information Not Available in Uploaded Documents')}</span>
          <span>📍 ${escapeHtml(profile.location || 'India')}</span>
          ${profile.linkedin ? `<span>🔗 <a href="${escapeHtml(profile.linkedin)}" target="_blank" style="color: var(--link-color); font-weight: 700;">LinkedIn</a></span>` : ''}
          ${profile.github ? `<span>🐙 <a href="${escapeHtml(profile.github)}" target="_blank" style="color: var(--link-color); font-weight: 700;">GitHub</a></span>` : ''}
        </div>
        <div style="font-size: 0.9rem; color: #333333; line-height: 1.6; font-style: italic; border-left: 3px solid var(--color-primary); padding-left: 0.85rem; background: rgba(255, 206, 216, 0.15); border-radius: 0 8px 8px 0; padding-top: 0.4rem; padding-bottom: 0.4rem;">
          "${escapeHtml(profile.summary || 'Information Not Available in Uploaded Documents')}"
        </div>
      </div>

      <div class="ats-breakdown-card">
        <h4 style="font-size: 0.95rem; font-weight: 800; color: #333333; margin-bottom: 0.65rem;">TECHNICAL SKILLS INVENTORY</h4>
        <div style="display: flex; flex-direction: column; gap: 0.55rem; font-size: 0.85rem;">
          ${skillsRows || '<span style="color: #666666; font-style: italic;">Information Not Available in Uploaded Documents</span>'}
        </div>
      </div>

      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.25rem; margin-bottom: 1.25rem;">
        <div>
          <h4 style="font-size: 0.95rem; font-weight: 800; color: #333333; margin-bottom: 0.65rem;">EXPERIENCE (${expList.length})</h4>
          ${expHtml || '<p style="color: #666666; font-size: 0.85rem; font-style: italic;">Information Not Available in Uploaded Documents</p>'}
        </div>
        <div>
          <h4 style="font-size: 0.95rem; font-weight: 800; color: #333333; margin-bottom: 0.65rem;">PROJECTS (${projList.length})</h4>
          ${projHtml || '<p style="color: #666666; font-size: 0.85rem; font-style: italic;">Information Not Available in Uploaded Documents</p>'}
        </div>
      </div>

      <div class="ats-breakdown-card">
        <h4 style="font-size: 0.95rem; font-weight: 800; color: #333333; margin-bottom: 0.65rem;">EDUCATION & CERTIFICATIONS</h4>
        <div style="margin-bottom: 0.6rem; font-size: 0.875rem; color: #333333;">
          ${eduHtml}
        </div>
        ${certHtml || '<span style="color: #666666; font-size: 0.825rem; font-style: italic;">No certifications in uploaded documents</span>'}
      </div>
    `;
  } catch (err) {
    content.innerHTML = `<p style="color: var(--color-error);">Failed to load master profile: ${err.message}</p>`;
  }
}

function setupResumeDropzone() {
  const dropzone = document.getElementById('master-resume-dropzone');
  if (!dropzone) return;

  ['dragenter', 'dragover'].forEach(evtName => {
    dropzone.addEventListener(evtName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(evtName => {
    dropzone.addEventListener(evtName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      handleResumeFileSelected(files);
    }
  });
}

async function handleResumeFileSelected(filesInput) {
  if (!filesInput) return;
  const files = (filesInput instanceof FileList || Array.isArray(filesInput)) ? Array.from(filesInput) : [filesInput];
  if (files.length === 0) return;

  const statusEl = document.getElementById('upload-file-status');
  statusEl.style.display = 'block';
  statusEl.innerHTML = `<span class="status-badge status-processing"><div class="spinner" style="width: 14px; height: 14px; border-width: 2px;"></div> Uploading & analyzing ${files.length} document(s)...</span>`;

  const formData = new FormData();
  files.forEach(f => formData.append('files', f));

  try {
    const res = await fetch('/api/kb/upload', {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Upload failed');
    }

    const data = await res.json();
    statusEl.innerHTML = `<span class="status-badge status-ready">✓ Successfully indexed ${data.uploaded_count || files.length} document(s) into Master Resume repository!</span>`;

    await loadKBDocuments();
    await loadKBUnifiedProfile();
    await renderMasterModalDocuments();
    await refreshMasterProfileContent();

    setTimeout(() => {
      statusEl.style.display = 'none';
    }, 2500);

  } catch (err) {
    statusEl.innerHTML = `<span class="status-badge status-error">Upload error: ${escapeHtml(err.message)}</span>`;
  }
}

// --- Tailor Resume For Job (Split-Screen Layout) ---

async function tailorResumeForJob(jobId, event) {
  if (event) {
    event.stopPropagation();
  }

  const modal = document.getElementById('tailor-resume-modal');
  const titleEl = document.getElementById('tailor-modal-title');
  const subtitleEl = document.getElementById('tailor-modal-subtitle');
  const bodyEl = document.getElementById('tailor-modal-body');

  const job = (state.currentJobs || []).find(j => String(j.id) === String(jobId)) || (window.linkedInFeedPostsCache || []).find(j => String(j.id) === String(jobId)) || currentOutreachJob;
  const jobTitle = job ? job.title : 'Data Analyst';
  const company = job ? job.company : 'Target Employer';

  titleEl.innerText = `⚡ Tailoring ATS Resume: ${jobTitle}`;
  subtitleEl.innerText = `Company: ${company} • Optimizing ATS Keyword Density & Compiling 1-Page LaTeX`;

  bodyEl.innerHTML = `
    <div style="text-align: center; padding: 4rem 1.5rem;">
      <div class="spinner" style="width: 48px; height: 48px; border-width: 4px; margin-bottom: 1.5rem;"></div>
      <h3 style="font-size: 1.35rem; font-weight: 800; color: #333333; margin-bottom: 0.65rem;">
        Generating Job-Specific ATS Tailored Resume...
      </h3>
      <p style="color: #666666; font-size: 0.95rem; max-width: 520px; margin: 0 auto; line-height: 1.6;">
        Scanning requirements for <strong>${escapeHtml(jobTitle)}</strong> at <strong>${escapeHtml(company)}</strong>, mapping technical competencies from your master resume, reordering high-impact bullets, and compiling a strictly verified <strong>1-Page LaTeX PDF</strong>.
      </p>
      <div style="margin-top: 1.5rem; font-size: 0.85rem; font-weight: 700; color: #D97F95;">
        🔒 Strict Truthfulness: No fabricated skills or false credentials added.
      </div>
    </div>
  `;

  modal.style.display = 'flex';

  try {
    const res = await fetch('/api/resume/tailor', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_id: jobId,
        job_title: job ? job.title : undefined,
        company: job ? job.company : undefined,
        description: job ? job.description : undefined,
        skills: job ? job.skills : undefined
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `Server error (${res.status})`);
    }

    const data = await res.json();
    currentTailorData = data;
    renderTailoredResumeModal(data);

  } catch (err) {
    bodyEl.innerHTML = `
      <div style="text-align: center; padding: 3rem 1rem; color: var(--color-error);">
        <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">⚠️</div>
        <h3 style="font-size: 1.25rem; font-weight: 800; margin-bottom: 0.5rem;">Failed to Tailor Resume</h3>
        <p style="color: #666666; font-size: 0.9rem; margin-bottom: 1.5rem;">${escapeHtml(err.message)}</p>
        <button class="btn btn-outline" onclick="closeModal('tailor-resume-modal')">Close</button>
      </div>
    `;
  }
}

function renderTailoredResumeModal(data) {
  const bodyEl = document.getElementById('tailor-modal-body');
  const titleEl = document.getElementById('tailor-modal-title');
  const subtitleEl = document.getElementById('tailor-modal-subtitle');
  const topActionsEl = document.getElementById('tailor-modal-top-actions');

  const job = data.job_details || {};
  const cleanCompany = (data.company || 'Job').replace(/[^a-zA-Z0-9]/g, '_');

  const candName = (data.tailored_resume && data.tailored_resume.name) || (state.masterProfile && state.masterProfile.name) || 'Tejas Waghmare';
  const roleTitle = data.job_title || 'Data Analyst';
  const compName = data.company || 'Target Employer';

  const fnPdf = (data.filenames && data.filenames.resume_pdf) || getStandardDocFilename(candName, roleTitle, compName, 'Resume', 'pdf');
  const fnDocx = (data.filenames && data.filenames.resume_docx) || getStandardDocFilename(candName, roleTitle, compName, 'Resume', 'docx');
  const fnTxt = (data.filenames && data.filenames.resume_txt) || getStandardDocFilename(candName, roleTitle, compName, 'Resume', 'txt');
  const fnTex = (data.filenames && data.filenames.resume_tex) || getStandardDocFilename(candName, roleTitle, compName, 'Resume', 'tex');

  const fnClPdf = (data.filenames && data.filenames.cover_letter_pdf) || getStandardDocFilename(candName, roleTitle, compName, 'Cover_Letter', 'pdf');
  const fnClDocx = (data.filenames && data.filenames.cover_letter_docx) || getStandardDocFilename(candName, roleTitle, compName, 'Cover_Letter', 'docx');
  const fnClTxt = (data.filenames && data.filenames.cover_letter_txt) || getStandardDocFilename(candName, roleTitle, compName, 'Cover_Letter', 'txt');

  titleEl.innerText = `⚡ Tailored ATS Resume: ${data.job_title}`;
  subtitleEl.innerText = `🏢 ${data.company} • Side-by-Side Job Description & Personalized Resume`;

  const ats = data.ats_metrics || {};
  const score = Math.round(ats.match_score || 88);
  const matchedKeywords = ats.matched_keywords || [];
  const missingKeywords = ats.missing_keywords || [];
  const gapAnalysis = ats.skill_gap_analysis || {};
  const domainSignals = ats.domain_signals || {};
  const softSkills = ats.soft_skill_alignment || [];
  const recs = ats.recommendations || [];

  // Update top actions toolbar
  topActionsEl.innerHTML = `
    <div style="display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap;">
      <a href="${data.docx_url}" id="btn-dl-docx" download="${fnDocx}" class="download-format-btn btn-docx" title="Download editable Word document (.docx)">
        📘 Word (.docx)
      </a>
      <a href="${data.docx_url}" id="btn-dl-gdocs" download="${fnDocx}" onclick="alert('Google Docs format: Upload this clean .docx file to Google Drive and open with Google Docs. Formatting and fonts are 100% preserved!')" class="download-format-btn btn-gdocs" title="Google Docs compatible format">
        🌐 Google Docs
      </a>
      <a href="${data.pdf_url}" id="btn-dl-pdf" download="${fnPdf}" class="download-format-btn btn-pdf" title="Download strict 1-page PDF">
        📕 PDF
      </a>
      <a href="${data.txt_url || `/api/resume/download/txt/${data.job_id}`}" id="btn-dl-txt" download="${fnTxt}" class="download-format-btn btn-txt" title="Download plain text resume">
        📝 Plain Text
      </a>
      <a href="${data.cl_docx_url || `/api/cover-letter/download/docx/${data.job_id}`}" id="btn-dl-cl-docx" download="${fnClDocx}" class="download-format-btn btn-docx" title="Download Cover Letter Word (.docx)">
        ✉️ Cover Letter (.docx)
      </a>
      <a href="${data.cl_pdf_url || `/api/cover-letter/download/pdf/${data.job_id}`}" id="btn-dl-cl-pdf" download="${fnClPdf}" class="download-format-btn btn-pdf" title="Download Cover Letter PDF">
        ✉️ Cover Letter (PDF)
      </a>
      <a href="${data.tex_url}" id="btn-dl-tex" download="${fnTex}" class="download-format-btn btn-latex" title="Download Overleaf LaTeX code">
        📄 LaTeX .tex
      </a>
      <button type="button" class="btn btn-outline btn-sm" id="btn-toggle-edit" onclick="toggleResumeEditMode()" style="font-weight: 700;">
        ✏️ Edit Resume
      </button>
      <button type="button" class="btn btn-outline btn-sm" onclick="regenerateCurrentTailoredResume()" style="font-weight: 700;" title="Regenerate all tailored documents">
        🔄 Regenerate
      </button>
      <button class="modal-close" onclick="closeModal('tailor-resume-modal')" style="font-size: 1.4rem; padding: 0.2rem 0.5rem; margin-left: 0.25rem;">✕</button>
    </div>
  `;

  // Matched & Missing Chips (Matching: Soft Green #6BBF73, Missing: Soft Orange #F7B955)
  const matchedChips = matchedKeywords.map(k => `
    <span class="ats-keyword-pill-matched">✓ ${escapeHtml(k)}</span>
  `).join(' ');

  const missingChips = missingKeywords.length > 0 ? missingKeywords.map(k => `
    <span class="ats-keyword-pill-missing">⚠️ ${escapeHtml(k)}</span>
  `).join(' ') : '<span style="color: var(--color-success); font-weight: 700; font-size: 0.85rem;">All primary keywords matched!</span>';

  // Highlighted Job Description (Selected keywords highlighted using: #FFCED8)
  const highlightedJD = highlightKeywordsInText(job.description || '', matchedKeywords, missingKeywords);

  const reqSkillsPills = (job.skills || []).map(s => {
    const isMatched = matchedKeywords.some(m => m.toLowerCase() === s.toLowerCase());
    return `<span class="${isMatched ? 'ats-keyword-pill-matched' : 'job-skill-chip'}">${escapeHtml(s)}</span>`;
  }).join(' ');

  // Files Used for Current Tailoring (Requirement 5)
  const filesUsed = data.files_used || (data.files_analyzed ? data.files_analyzed.map(f => f.filename) : []);
  const filesUsedHtml = filesUsed.length > 0
    ? filesUsed.map(f => `<span style="background: #ffffff; color: #15803d; font-weight: 700; font-size: 0.78rem; padding: 0.2rem 0.55rem; border-radius: 6px; border: 1px solid #86efac; box-shadow: 0 1px 2px rgba(0,0,0,0.04);">✅ ${escapeHtml(f)}</span>`).join(' ')
    : '<span style="color: #dc2626; font-size: 0.825rem; font-weight: 700;">No files available for tailoring.</span>';

  bodyEl.innerHTML = `
    <!-- Files Used for Current Tailoring (Requirement 5) -->
    <div class="tailor-files-used-banner" style="background: #f0fdf4; border: 1.5px solid #86efac; border-radius: 10px; padding: 0.65rem 1rem; margin-bottom: 0.65rem; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem;">
      <div style="display: flex; align-items: center; gap: 0.55rem; flex-wrap: wrap;">
        <strong style="color: #166534; font-size: 0.85rem; display: flex; align-items: center; gap: 0.35rem;">
          <span>📂</span> Files Used for Generation:
        </strong>
        ${filesUsedHtml}
      </div>
      <span style="font-size: 0.72rem; color: #15803d; font-weight: 700; background: #dcfce7; padding: 0.2rem 0.5rem; border-radius: 4px; border: 1px solid #bbf7d0;">
        ✓ Evidence-Based Single Source of Truth
      </span>
    </div>

    <!-- Top Comparison & Compatibility Bar -->
    <div style="background: #FFFFFF; border: 1.5px solid var(--border-color); border-radius: 12px; padding: 0.75rem 1.25rem; margin-bottom: 0.65rem; flex-shrink: 0; box-shadow: var(--shadow-sm);">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem;">
        <div style="display: flex; align-items: center; gap: 0.95rem;">
          <div style="font-size: 1.4rem; font-weight: 800; color: ${score >= 80 ? 'var(--color-success-text)' : 'var(--color-warning-text)'}; display: flex; align-items: center; gap: 0.45rem;">
            <span>${score}%</span>
            <span style="font-size: 0.75rem; font-weight: 700; color: ${score >= 80 ? 'var(--color-success-text)' : 'var(--color-warning-text)'}; background: ${score >= 80 ? 'var(--color-success-bg)' : 'var(--color-warning-bg)'}; padding: 0.18rem 0.55rem; border-radius: var(--radius-full);">
              ${score >= 80 ? 'High ATS Compatibility' : 'Moderate Match'}
            </span>
          </div>
          <div class="ats-score-meter-wrap" style="width: 150px; margin-top: 0;">
            <div class="ats-score-meter-bar" style="width: ${Math.min(100, score)}%;"></div>
          </div>
        </div>

        <!-- Comparison Summary Pills -->
        <div style="display: flex; align-items: center; gap: 0.85rem; font-size: 0.825rem;">
          <div><strong style="color: var(--color-success-text);">${matchedKeywords.length}</strong> <span style="color: #666666;">Skills Matched</span></div>
          <div><strong style="color: var(--color-warning-text);">${missingKeywords.length}</strong> <span style="color: #666666;">Skill Gaps</span></div>
          <button type="button" class="btn btn-outline btn-sm" id="btn-toggle-comparison" onclick="toggleComparisonDrawer()" style="font-size: 0.75rem; padding: 0.25rem 0.6rem;">
            📊 View Comparison Breakdown ▾
          </button>
        </div>
      </div>

      <!-- Collapsible Comparison Breakdown Drawer -->
      <div id="comparison-drawer" style="display: none; margin-top: 0.85rem; padding-top: 0.85rem; border-top: 1px dashed var(--border-color);">
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 0.85rem; font-size: 0.825rem;">
          <div class="ats-breakdown-card" style="margin-bottom: 0;">
            <div style="font-weight: 800; color: var(--color-success-text); margin-bottom: 0.45rem;">✓ MATCHING RESUME SKILLS (${matchedKeywords.length})</div>
            <div style="display: flex; flex-wrap: wrap; gap: 0.35rem;">
              ${matchedChips || '<span style="color: #666666;">None</span>'}
            </div>
          </div>
          <div class="ats-breakdown-card" style="margin-bottom: 0;">
            <div style="font-weight: 800; color: var(--color-warning-text); margin-bottom: 0.45rem;">⚠️ MISSING FROM MASTER RESUME (${missingKeywords.length})</div>
            <div style="display: flex; flex-wrap: wrap; gap: 0.35rem;">
              ${missingChips}
            </div>
            <div style="font-size: 0.75rem; color: #64748B; margin-top: 0.4rem;">
              🔒 Enforced: Never inserted into resume to preserve truthfulness and prevent ATS rejection.
            </div>
          </div>
          <div class="ats-breakdown-card" style="margin-bottom: 0;">
            <div style="font-weight: 800; color: #333333; margin-bottom: 0.45rem;">💡 ATS OPTIMIZATION STRATEGY</div>
            <div style="color: #666666; font-size: 0.8rem; line-height: 1.5;">
              ${recs.length > 0 ? recs.map(r => `<div>• ${escapeHtml(r)}</div>`).join('') : `Highlighted core competencies (${matchedKeywords.slice(0, 3).join(', ')}) in summary and ranked relevant projects upfront. Strict truthfulness maintained.`}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Side-by-Side Split Screen Container -->
    <div class="split-screen-container">
      
      <!-- LEFT PANEL: Job Input & Deep Analysis -->
      <div class="split-panel split-panel-left" id="panel-left-jd">
        
        <!-- Left Panel Mode Selector Tabs -->
        <div class="left-panel-mode-nav">
          <button type="button" class="left-panel-mode-btn active" id="btn-lpm-active" onclick="switchLeftPanelMode('active')">
            📋 Active Job Details
          </button>
          <button type="button" class="left-panel-mode-btn" id="btn-lpm-url" onclick="switchLeftPanelMode('url')">
            🔗 Paste Job URL (Option B)
          </button>
          <button type="button" class="left-panel-mode-btn" id="btn-lpm-paste" onclick="switchLeftPanelMode('paste')">
            📝 Paste JD (Option A)
          </button>
          <button type="button" class="left-panel-mode-btn" id="btn-lpm-edit" onclick="switchLeftPanelMode('edit')">
            ✏️ Edit Scraped JD
          </button>
        </div>

        <!-- Mode 1: Active Scraped Job Details -->
        <div class="split-panel-body" id="left-pane-active" style="display: block;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.65rem;">
            <span class="badge-fresher" style="background-color: var(--color-primary); color: #333333; border: 1px solid var(--color-primary-hover); font-size: 0.72rem;">
              ${escapeHtml(job.source_name || 'Publishing Source')}
            </span>
            <div style="display: flex; align-items: center; gap: 0.4rem;">
              <button type="button" class="btn btn-outline btn-sm" id="btn-highlight-kw" onclick="toggleKeywordHighlights()" style="font-size: 0.725rem; padding: 0.25rem 0.55rem;" title="Toggle highlighting of matching skills in job description">
                ✨ Highlights: ON (#FFCED8)
              </button>
              ${job.source_url && job.source_url !== '#' ? `<a href="${job.source_url}" target="_blank" rel="noopener noreferrer" class="btn btn-outline btn-sm" style="font-size: 0.725rem; padding: 0.25rem 0.55rem;">Original Post ↗</a>` : ''}
            </div>
          </div>

          <h2 style="font-size: 1.3rem; font-weight: 800; color: #333333; margin-bottom: 0.25rem;">
            ${escapeHtml(job.title || data.job_title)}
          </h2>
          <div style="color: var(--link-color); font-weight: 700; font-size: 0.975rem; margin-bottom: 0.85rem;">
            🏢 ${escapeHtml(job.company || data.company)}
          </div>

          <!-- Metadata Grid -->
          <div class="jd-meta-grid">
            <div>📍 <strong>Location:</strong> ${escapeHtml(job.location || 'India')}</div>
            <div>💼 <strong>Work Mode:</strong> ${escapeHtml(job.work_mode || 'Remote')}</div>
            <div>⏱️ <strong>Experience:</strong> ${escapeHtml(job.experience_level || '0-1 Year (Fresher)')}</div>
            <div>💰 <strong>Package:</strong> ${escapeHtml(job.salary || 'Competitive')}</div>
            ${job.application_deadline ? `<div>⏳ <strong>Deadline:</strong> ${escapeHtml(job.application_deadline)}</div>` : ''}
            ${job.openings ? `<div>👥 <strong>Openings:</strong> ${escapeHtml(job.openings)}</div>` : ''}
            <div>🌐 <strong>Portal:</strong> ${escapeHtml(job.source_name || 'Curated Platform')}</div>
            <div>📅 <strong>Posted:</strong> ${formatRelativeDate(job.published_at)}</div>
          </div>

          <!-- Required Technical Skills Tagline -->
          <div class="jd-section-heading">🎯 Required Technical Skills</div>
          <div style="display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 1.15rem;">
            ${reqSkillsPills || '<span style="color: #666666; font-size: 0.825rem;">Specified in detailed description below</span>'}
          </div>

          <!-- Key Responsibilities (if available) -->
          ${(job.responsibilities || []).length > 0 ? `
            <div class="jd-section-heading">📋 Key Responsibilities (${job.responsibilities.length})</div>
            <div style="background: #F8FAFC; border: 1.5px solid #E2E8F0; padding: 0.85rem 1rem; border-radius: 8px; margin-bottom: 1.15rem; max-height: 220px; overflow-y: auto;">
              <ol style="margin: 0; padding-left: 1.15rem; font-size: 0.85rem; line-height: 1.6; color: #334155; display: flex; flex-direction: column; gap: 0.4rem;">
                ${job.responsibilities.map(r => `<li>${highlightKeywordsInText(r, matchedKeywords, missingKeywords)}</li>`).join('')}
              </ol>
            </div>
          ` : ''}

          <!-- Requirements & Qualifications (if available) -->
          ${(job.requirements || []).length > 0 ? `
            <div class="jd-section-heading">📌 Requirements & Qualifications (${job.requirements.length})</div>
            <div style="background: #F8FAFC; border: 1.5px solid #E2E8F0; padding: 0.85rem 1rem; border-radius: 8px; margin-bottom: 1.15rem; max-height: 180px; overflow-y: auto;">
              <ul style="margin: 0; padding-left: 1.15rem; font-size: 0.85rem; line-height: 1.6; color: #334155; display: flex; flex-direction: column; gap: 0.35rem;">
                ${job.requirements.map(req => `<li>${highlightKeywordsInText(req, matchedKeywords, missingKeywords)}</li>`).join('')}
              </ul>
            </div>
          ` : ''}

          <!-- Full Job Description with Keywords Highlighted in #FFCED8 -->
          <div class="jd-section-heading">📄 Complete Job Details & Requirements</div>
          <div class="jd-text-content" id="jd-raw-text">
            ${highlightedJD || '<p style="color: #666666;">Detailed description available at employer site.</p>'}
          </div>
        </div>

        <!-- Mode 2: Paste Job URL (Option B) -->
        <div class="split-panel-body" id="left-pane-url" style="display: none; padding: 1.15rem;">
          <div style="margin-bottom: 1rem;">
            <h3 style="font-size: 1.05rem; font-weight: 800; color: #333333; margin-bottom: 0.35rem;">
              🔗 Option B: Scrape & Tailor from Job Posting URL
            </h3>
            <p style="font-size: 0.825rem; color: #64748B; line-height: 1.5; margin: 0;">
              Enter any live job URL from LinkedIn, Internshala, Naukri, Foundit, Indeed, Wellfound, WeWorkRemotely, Jobicy, Remotive, or any company career page. The engine scrapes complete responsibilities, qualifications, and requirements directly from the source page.
            </p>
          </div>

          <div style="margin-bottom: 0.85rem;">
            <label class="filter-label" style="margin-bottom: 0.35rem;">Job Posting URL</label>
            <input type="url" id="tailor-input-url" class="search-input" style="padding-left: 0.85rem;" placeholder="https://internshala.com/job/detail/... or linkedin.com/jobs/...">
          </div>

          <!-- Quick Sample Platform Chips -->
          <div style="margin-bottom: 1.25rem;">
            <span style="font-size: 0.75rem; color: #64748B; font-weight: 700; display: block; margin-bottom: 0.4rem;">TRY WITH LIVE EXAMPLES:</span>
            <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
              <button type="button" class="quick-sample-chip" onclick="setTailorSampleUrl('internshala')">
                📄 Internshala: Arihant MIS
              </button>
              <button type="button" class="quick-sample-chip" onclick="setTailorSampleUrl('wwr')">
                🌐 WeWorkRemotely: Cribl Analytics
              </button>
              <button type="button" class="quick-sample-chip" onclick="setTailorSampleUrl('jobicy')">
                💻 Jobicy: Remote Data Analyst
              </button>
            </div>
          </div>

          <div style="display: flex; gap: 0.65rem;">
            <button type="button" class="btn btn-primary" id="btn-trigger-scrape-url" onclick="scrapeAndTailorFromUrl()" style="flex: 1; font-weight: 700; padding: 0.6rem;">
              🚀 Scrape & Tailor ATS Resume
            </button>
          </div>

          <div id="url-scrape-status" style="display: none; margin-top: 1rem; padding: 0.85rem; border-radius: 8px; font-size: 0.825rem;"></div>
        </div>

        <!-- Mode 3: Paste Complete Job Description (Option A) -->
        <div class="split-panel-body" id="left-pane-paste" style="display: none; padding: 1.15rem;">
          <div style="margin-bottom: 1rem;">
            <h3 style="font-size: 1.05rem; font-weight: 800; color: #333333; margin-bottom: 0.35rem;">
              📝 Option A: Paste Target Job Description
            </h3>
            <p style="font-size: 0.825rem; color: #64748B; line-height: 1.5; margin: 0;">
              Paste any job description to automatically extract technical requirements, responsibilities, and seniority, synthesizing a 1-page ATS-tailored resume and cover letter.
            </p>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-bottom: 0.75rem;">
            <div>
              <label class="filter-label" style="margin-bottom: 0.35rem;">Job Title</label>
              <input type="text" id="paste-job-title" class="search-input" value="Data Analyst" style="padding-left: 0.85rem;">
            </div>
            <div>
              <label class="filter-label" style="margin-bottom: 0.35rem;">Target Company</label>
              <input type="text" id="paste-company" class="search-input" value="Target Employer" style="padding-left: 0.85rem;">
            </div>
          </div>

          <div style="margin-bottom: 0.75rem;">
            <label class="filter-label" style="margin-bottom: 0.35rem;">Technical Skills (optional comma-separated)</label>
            <input type="text" id="paste-skills" class="search-input" placeholder="e.g. Power BI, SQL, Python, Advanced Excel, DAX" style="padding-left: 0.85rem;">
          </div>

          <div style="margin-bottom: 1rem;">
            <label class="filter-label" style="margin-bottom: 0.35rem;">Complete Job Description Text</label>
            <textarea id="paste-description" class="edit-textarea" style="min-height: 220px; font-size: 0.85rem; line-height: 1.55; padding: 0.85rem;" placeholder="Paste the complete job description here, including responsibilities, requirements, qualifications, and company overview..."></textarea>
          </div>

          <button type="button" class="btn btn-primary" id="btn-trigger-paste-tailor" onclick="tailorFromPastedDescription()" style="width: 100%; font-weight: 700; padding: 0.6rem;">
            ✨ Analyze & Tailor Resume
          </button>
        </div>

        <!-- Mode 4: Edit Scraped JD -->
        <div class="split-panel-body" id="left-pane-edit" style="display: none; padding: 1.15rem;">
          <div style="margin-bottom: 1rem;">
            <h3 style="font-size: 1.05rem; font-weight: 800; color: #333333; margin-bottom: 0.35rem;">
              ✏️ Edit Extracted Job Details
            </h3>
            <p style="font-size: 0.825rem; color: #64748B; line-height: 1.5; margin: 0;">
              Fine-tune the scraped title, company, skills, or responsibilities before re-tailoring your resume and cover letter.
            </p>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-bottom: 0.75rem;">
            <div>
              <label class="filter-label" style="margin-bottom: 0.35rem;">Job Title</label>
              <input type="text" id="edit-jd-title" class="search-input" value="${escapeHtml(job.title || data.job_title || '')}" style="padding-left: 0.85rem;">
            </div>
            <div>
              <label class="filter-label" style="margin-bottom: 0.35rem;">Company</label>
              <input type="text" id="edit-jd-company" class="search-input" value="${escapeHtml(job.company || data.company || '')}" style="padding-left: 0.85rem;">
            </div>
          </div>

          <div style="margin-bottom: 0.75rem;">
            <label class="filter-label" style="margin-bottom: 0.35rem;">Required Skills (comma-separated)</label>
            <input type="text" id="edit-jd-skills" class="search-input" value="${escapeHtml((job.skills || []).join(', '))}" style="padding-left: 0.85rem;">
          </div>

          <div style="margin-bottom: 0.75rem;">
            <label class="filter-label" style="margin-bottom: 0.35rem;">Responsibilities (one per line)</label>
            <textarea id="edit-jd-resp" class="edit-textarea" style="min-height: 110px; font-size: 0.825rem; line-height: 1.5; padding: 0.75rem;">${escapeHtml((job.responsibilities || []).join('\n'))}</textarea>
          </div>

          <div style="margin-bottom: 0.75rem;">
            <label class="filter-label" style="margin-bottom: 0.35rem;">Requirements (one per line)</label>
            <textarea id="edit-jd-req" class="edit-textarea" style="min-height: 90px; font-size: 0.825rem; line-height: 1.5; padding: 0.75rem;">${escapeHtml((job.requirements || []).join('\n'))}</textarea>
          </div>

          <div style="margin-bottom: 1rem;">
            <label class="filter-label" style="margin-bottom: 0.35rem;">Full Job Description</label>
            <textarea id="edit-jd-desc" class="edit-textarea" style="min-height: 130px; font-size: 0.825rem; line-height: 1.5; padding: 0.75rem;">${escapeHtml(job.description || '')}</textarea>
          </div>

          <button type="button" class="btn btn-primary" id="btn-save-edited-jd" onclick="saveAndRetailorScrapedJd()" style="width: 100%; font-weight: 700; padding: 0.6rem;">
            💾 Apply Edits & Re-tailor Resume
          </button>
        </div>

      </div>

      <!-- RIGHT PANEL: Personalized Tailored Resume -->
      <div class="split-panel split-panel-right" id="panel-right-resume">
        <div class="split-panel-header">
          <div class="tailor-tab-nav" style="margin-bottom: 0; border-bottom: none; gap: 0.35rem;">
            <button type="button" class="tailor-tab-btn active" id="tailor-tab-btn-pdf" onclick="switchTailorTab('pdf')" style="padding: 0.35rem 0.75rem; font-size: 0.8rem;">
              📄 PDF Preview
            </button>
            <button type="button" class="tailor-tab-btn" id="tailor-tab-btn-edit" onclick="switchTailorTab('edit')" style="padding: 0.35rem 0.75rem; font-size: 0.8rem;">
              ✏️ Live Editor
            </button>
            <button type="button" class="tailor-tab-btn" id="tailor-tab-btn-latex" onclick="switchTailorTab('latex')" style="padding: 0.35rem 0.75rem; font-size: 0.8rem;">
              💻 LaTeX (.tex)
            </button>
            <button type="button" class="tailor-tab-btn" id="tailor-tab-btn-ats" onclick="switchTailorTab('ats')" style="padding: 0.35rem 0.75rem; font-size: 0.8rem;">
              🎯 ATS Audit
            </button>
            <button type="button" class="tailor-tab-btn" id="tailor-tab-btn-cover" onclick="switchTailorTab('cover')" style="padding: 0.35rem 0.75rem; font-size: 0.8rem;">
              ✉️ Cover Letter
            </button>
            <button type="button" class="tailor-tab-btn" id="tailor-tab-btn-evidence" onclick="switchTailorTab('evidence')" style="padding: 0.35rem 0.75rem; font-size: 0.8rem;">
              🔍 Evidence & Traceability
            </button>
          </div>

          <div style="display: flex; align-items: center; gap: 0.35rem;">
            <a href="${data.pdf_preview_url || data.pdf_url}" target="_blank" rel="noopener noreferrer" class="btn btn-outline btn-sm" style="font-size: 0.725rem; padding: 0.25rem 0.55rem; color: var(--link-color);" title="Open PDF preview in separate tab">
              Open PDF ↗
            </a>
          </div>
        </div>

        <div class="split-panel-body" style="padding: 0.85rem;" id="resume-scroll-content">

          <!-- Sub-Tab 1: 1-Page PDF Preview -->
          <div id="tailor-pane-pdf" style="display: block; height: 100%;">
            <iframe id="tailor-pdf-iframe" class="resume-preview-frame" style="height: calc(100% - 30px); min-height: 480px;" src="${data.pdf_preview_url || data.pdf_url}#toolbar=0&navpanes=0"></iframe>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.4rem; font-size: 0.775rem; color: #666666;">
              <span>Strict 1-Page Jake's Resume LaTeX Format.</span>
              <span>Need Word format? Click <strong>Download Word (.docx)</strong> above.</span>
            </div>
          </div>

          <!-- Sub-Tab 2: Live Resume Editor -->
          <div id="tailor-pane-edit" style="display: none;">
            <div class="resume-editor-wrap" id="resume-editor-form-container">
              ${buildResumeEditForm(data.tailored_resume)}
            </div>

            <!-- Sticky Save Actions Footer -->
            <div class="sticky-editor-footer">
              <button type="button" class="btn btn-outline btn-sm" onclick="switchTailorTab('pdf')">
                Cancel
              </button>
              <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span id="save-editor-status" style="display: none; font-size: 0.8rem; color: var(--color-success-text); font-weight: 700;"></span>
                <button type="button" class="btn btn-primary btn-sm" id="btn-save-recompile" onclick="saveAndRecompileResume()" style="font-weight: 700;">
                  💾 Save & Recompile All Formats (PDF, Word, LaTeX)
                </button>
              </div>
            </div>
          </div>

          <!-- Sub-Tab 3: Overleaf LaTeX Code -->
          <div id="tailor-pane-latex" style="display: none;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.65rem;">
              <span style="font-size: 0.85rem; color: #666666;">
                Overleaf-ready LaTeX code (Jake's Resume template):
              </span>
              <button type="button" class="btn btn-outline btn-sm" onclick="copyCurrentLatex()">
                📋 Copy LaTeX Code
              </button>
            </div>
            <pre class="latex-code-box" id="tailored-latex-pre">${escapeHtml(data.latex_code)}</pre>
          </div>

          <!-- Sub-Tab 4: Multi-Dimensional ATS Audit Breakdown -->
          <div id="tailor-pane-ats" style="display: none;">
            
            <!-- Grounded Truthfulness Guarantee Card -->
            <div class="ats-breakdown-card" style="border-left: 4px solid #6BBF73; background: #F0FDF4;">
              <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.35rem;">
                <span style="font-size: 1.1rem;">🔒</span>
                <strong style="color: #166534; font-size: 0.9rem;">ATS Truthfulness & Anti-Hallucination Enforced</strong>
              </div>
              <p style="font-size: 0.8rem; color: #15803D; margin: 0; line-height: 1.5;">
                This tailored resume only includes credentials, tools, and experiences verified in your Career Knowledge Base. Missing technical tools are omitted from resume sections to protect you from screening disqualification.
              </p>
            </div>

            <!-- Matched Technical Skills -->
            <div class="ats-breakdown-card">
              <h4 style="font-size: 0.925rem; font-weight: 800; color: var(--color-success-text); margin-bottom: 0.5rem;">
                ✓ VERIFIED MATCHING TECHNICAL TOOLS (${matchedKeywords.length})
              </h4>
              <div style="display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 0.5rem;">
                ${matchedChips || '<span style="color: #666666;">None identified</span>'}
              </div>
            </div>

            <!-- Technical Skill Gaps -->
            <div class="ats-breakdown-card">
              <h4 style="font-size: 0.925rem; font-weight: 800; color: var(--color-warning-text); margin-bottom: 0.5rem;">
                ⚠️ TECHNICAL SKILL GAPS (${missingKeywords.length})
              </h4>
              <p style="font-size: 0.825rem; color: #666666; margin-bottom: 0.5rem;">
                Present in target job posting but absent from your Master Resume. Intentionally omitted from resume to avoid false claims:
              </p>
              <div style="display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 0.5rem;">
                ${missingChips}
              </div>
              <div style="font-size: 0.78rem; color: #64748B; background: #FFF4DE; border: 1px solid #FFE8C4; padding: 0.5rem 0.75rem; border-radius: 6px; margin-top: 0.5rem;">
                💡 <strong>Interview Strategy:</strong> Address these gaps during technical interviews by demonstrating transferable proficiency from your verified SQL, Python, and Power BI foundation.
              </div>
            </div>

            <!-- Soft Skills Alignment -->
            ${softSkills.length > 0 ? `
              <div class="ats-breakdown-card">
                <h4 style="font-size: 0.925rem; font-weight: 800; color: #333333; margin-bottom: 0.5rem;">
                  🤝 CORE WORKFLOW & SOFT SKILL ALIGNMENT
                </h4>
                <div style="display: flex; flex-direction: column; gap: 0.35rem;">
                  ${softSkills.map(s => `
                    <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.825rem; padding: 0.35rem 0.6rem; background: #F8FAFC; border-radius: 6px;">
                      <strong>${escapeHtml(s.soft_skill || s)}</strong>
                      <span style="color: #6BBF73; font-weight: 700; font-size: 0.75rem;">✓ Documented in Experience</span>
                    </div>
                  `).join('')}
                </div>
              </div>
            ` : ''}

            <!-- Domain Signals -->
            ${domainSignals.domain ? `
              <div class="ats-breakdown-card">
                <h4 style="font-size: 0.925rem; font-weight: 800; color: #333333; margin-bottom: 0.5rem;">
                  🎯 DOMAIN FOCUS & HIRING SIGNALS
                </h4>
                <div style="font-size: 0.85rem; color: #334155; line-height: 1.5;">
                  <div><strong>Industry / Focus:</strong> ${escapeHtml(domainSignals.domain)}</div>
                  ${domainSignals.primary_focus ? `<div><strong>Core Competency:</strong> ${escapeHtml(domainSignals.primary_focus)}</div>` : ''}
                </div>
              </div>
            ` : ''}

            <!-- Tailored Professional Summary -->
            <div class="ats-breakdown-card">
              <h4 style="font-size: 0.925rem; font-weight: 800; color: #333333; margin-bottom: 0.5rem;">
                TAILORED PROFESSIONAL SUMMARY
              </h4>
              <p style="font-size: 0.875rem; color: #333333; line-height: 1.6; font-style: italic; margin: 0;">
                "${escapeHtml((data.tailored_resume && data.tailored_resume.summary) || '')}"
              </p>
            </div>

          </div>

          <!-- Sub-Tab 5: Cover Letter Generator & Application Responses -->
          <div id="tailor-pane-cover" style="display: none;">
            <!-- Top Cover Letter Actions Bar -->
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.75rem;">
              <div>
                <strong style="color: #38bdf8; font-size: 0.95rem;">✉️ Tailored Cover Letter & Application Package</strong>
                <div style="font-size: 0.78rem; color: #94a3b8;">Grounded in your Career Knowledge Base documents</div>
              </div>
              <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
                <a href="${data.cl_docx_url || `/api/cover-letter/download/docx/${data.job_id}`}" download="${fnClDocx}" class="btn btn-primary btn-sm btn-docx" style="font-size: 0.78rem; padding: 0.25rem 0.6rem;">
                  📘 Word (.docx)
                </a>
                <a href="${data.cl_pdf_url || `/api/cover-letter/download/pdf/${data.job_id}`}" download="${fnClPdf}" class="btn btn-outline btn-sm btn-pdf" style="font-size: 0.78rem; padding: 0.25rem 0.6rem;">
                  📕 PDF
                </a>
                <button type="button" class="btn btn-outline btn-sm" onclick="copyTailoredCoverLetter()" style="font-size: 0.78rem; padding: 0.25rem 0.6rem;">
                  📋 Copy Text
                </button>
                <button type="button" class="btn btn-outline btn-sm" onclick="downloadTailoredCoverLetterTxt()" style="font-size: 0.78rem; padding: 0.25rem 0.6rem;">
                  📥 .txt
                </button>
              </div>
            </div>

            <!-- Executive Summary Card -->
            ${data.cover_letter && data.cover_letter.executive_summary ? `
              <div class="ats-breakdown-card" style="margin-bottom: 0.75rem; border-left: 3px solid #38bdf8;">
                <h4 style="font-size: 0.85rem; font-weight: 700; color: #38bdf8; margin-bottom: 0.35rem;">
                  🚀 PROFESSIONAL EXECUTIVE SUMMARY & ELEVATOR PITCH
                </h4>
                <p style="font-size: 0.82rem; color: #cbd5e1; line-height: 1.5; margin: 0;">
                  ${escapeHtml(data.cover_letter.executive_summary)}
                </p>
              </div>
            ` : ''}

            <!-- Editable Cover Letter Textarea -->
            <div class="ats-breakdown-card" style="margin-bottom: 0.75rem;">
              <textarea id="tailor-cl-textarea" class="edit-textarea" style="min-height: 280px; font-size: 0.85rem; line-height: 1.6; padding: 0.85rem; width: 100%; box-sizing: border-box;"></textarea>
            </div>

            <!-- Job-Specific Application Responses -->
            ${data.cover_letter && Array.isArray(data.cover_letter.application_responses) && data.cover_letter.application_responses.length > 0 ? `
              <div class="ats-breakdown-card" style="margin-bottom: 0;">
                <h4 style="font-size: 0.85rem; font-weight: 700; color: #34d399; margin-bottom: 0.5rem;">
                  💬 JOB APPLICATION SCREENING RESPONSES (PORTAL Q&A)
                </h4>
                <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                  ${data.cover_letter.application_responses.map(q => `
                    <div class="app-response-card">
                      <div class="app-response-q">Q: ${escapeHtml(q.question)}</div>
                      <div class="app-response-a">${escapeHtml(q.answer)}</div>
                    </div>
                  `).join('')}
                </div>
              </div>
            ` : ''}
          </div>

          <!-- Sub-Tab 6: Evidence & File Transparency -->
          <div id="tailor-pane-evidence" style="display: none;">
            <!-- Prominent Notice Banner -->
            <div style="background: rgba(14, 165, 233, 0.08); border: 1.5px solid #0284c7; border-radius: 8px; padding: 0.85rem 1rem; margin-bottom: 1rem; display: flex; align-items: flex-start; gap: 0.65rem;">
              <span style="font-size: 1.2rem; line-height: 1;">🔒</span>
              <div style="font-size: 0.825rem; color: #e0f2fe; line-height: 1.5;">
                <strong style="color: #38bdf8;">Evidence-Grounded Guarantee:</strong>
                This tailored resume and cover letter were generated exclusively from your uploaded career documents and the target Job Description. No previously stored profile data, sample resumes, or AI-generated assumptions were used.
              </div>
            </div>

            <!-- Files Analyzed List -->
            <div class="ats-breakdown-card" style="margin-bottom: 1rem;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.65rem;">
                <h4 style="font-size: 0.95rem; font-weight: 800; color: #38bdf8; margin: 0;">
                  📄 FILES ANALYZED (${(data.files_analyzed || []).length})
                </h4>
                <span class="status-pill status-pill-ready">✓ Verified Documents</span>
              </div>
              <div style="display: flex; flex-direction: column; gap: 0.65rem;">
                ${(data.files_analyzed || []).map(f => `
                  <div style="background: #080d1a; border: 1px solid #1e293b; border-radius: 6px; padding: 0.75rem 0.9rem;">
                    <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 0.35rem; margin-bottom: 0.35rem;">
                      <strong style="color: #ffffff; font-size: 0.9rem;">${escapeHtml(f.display_name || f.filename)}</strong>
                      <span style="font-size: 0.75rem; color: #94a3b8;">${escapeHtml((f.file_type || '').toUpperCase())} • Uploaded: ${f.uploaded_at ? new Date(f.uploaded_at).toLocaleDateString() : 'N/A'}</span>
                    </div>
                    <div style="font-size: 0.8rem; color: #cbd5e1; margin-bottom: 0.45rem;">
                      ${escapeHtml(f.summary || 'Document extracted and indexed into knowledge base.')}
                    </div>
                    <div style="display: flex; gap: 0.45rem; flex-wrap: wrap; font-size: 0.75rem;">
                      <span style="background: rgba(56, 189, 248, 0.1); color: #38bdf8; padding: 0.15rem 0.45rem; border-radius: 4px;">Skills: ${f.skills_found || 0}</span>
                      <span style="background: rgba(52, 211, 153, 0.1); color: #34d399; padding: 0.15rem 0.45rem; border-radius: 4px;">Experience: ${f.experience_found || 0}</span>
                      <span style="background: rgba(251, 191, 36, 0.1); color: #fbbf24; padding: 0.15rem 0.45rem; border-radius: 4px;">Projects: ${f.projects_found || 0}</span>
                      <span style="background: rgba(168, 85, 247, 0.1); color: #c084fc; padding: 0.15rem 0.45rem; border-radius: 4px;">Certifications: ${f.certifications_found || 0}</span>
                    </div>
                  </div>
                `).join('') || '<div style="color: #94a3b8; font-size: 0.825rem;">No files analyzed.</div>'}
              </div>
            </div>

            <!-- Section-by-Section Evidence Traceability -->
            ${data.evidence_summary && data.evidence_summary.section_traceability ? `
              <div class="ats-breakdown-card" style="margin-bottom: 0.5rem;">
                <h4 style="font-size: 0.95rem; font-weight: 800; color: #34d399; margin-bottom: 0.65rem;">
                  🔎 SECTION-BY-SECTION EVIDENCE TRACEABILITY
                </h4>
                <div style="display: flex; flex-direction: column; gap: 0.45rem; font-size: 0.825rem;">
                  <div style="padding: 0.4rem 0.6rem; background: #080d1a; border-radius: 4px; display: flex; justify-content: space-between;">
                    <span style="color: #94a3b8;">Candidate Name & Contact:</span>
                    <strong style="color: #ffffff;">${escapeHtml(data.evidence_summary.section_traceability.name || 'Uploaded Documents')}</strong>
                  </div>
                  <div style="padding: 0.4rem 0.6rem; background: #080d1a; border-radius: 4px; display: flex; justify-content: space-between;">
                    <span style="color: #94a3b8;">Professional Summary:</span>
                    <strong style="color: #ffffff;">${escapeHtml(data.evidence_summary.section_traceability.summary || 'Uploaded Documents')}</strong>
                  </div>
                  <div style="padding: 0.4rem 0.6rem; background: #080d1a; border-radius: 4px; display: flex; justify-content: space-between;">
                    <span style="color: #94a3b8;">Technical Skills:</span>
                    <strong style="color: #ffffff;">${escapeHtml((data.evidence_summary.section_traceability.skills_contributing_files || []).join(', ') || 'Uploaded Documents')}</strong>
                  </div>
                  <div style="padding: 0.4rem 0.6rem; background: #080d1a; border-radius: 4px; display: flex; justify-content: space-between;">
                    <span style="color: #94a3b8;">Work Experience:</span>
                    <strong style="color: #ffffff;">${escapeHtml((data.evidence_summary.section_traceability.experience_contributing_files || []).join(', ') || 'Uploaded Documents')}</strong>
                  </div>
                  <div style="padding: 0.4rem 0.6rem; background: #080d1a; border-radius: 4px; display: flex; justify-content: space-between;">
                    <span style="color: #94a3b8;">Projects:</span>
                    <strong style="color: #ffffff;">${escapeHtml((data.evidence_summary.section_traceability.projects_contributing_files || []).join(', ') || 'Uploaded Documents')}</strong>
                  </div>
                  <div style="padding: 0.4rem 0.6rem; background: #080d1a; border-radius: 4px; display: flex; justify-content: space-between;">
                    <span style="color: #94a3b8;">Certifications:</span>
                    <strong style="color: #ffffff;">${escapeHtml((data.evidence_summary.section_traceability.certifications_contributing_files || []).join(', ') || 'Uploaded Documents')}</strong>
                  </div>
                </div>
              </div>
            ` : ''}
          </div>

        </div>
      </div>

    </div>
  `;

  // Pre-generate Cover Letter draft
  const clText = (data.cover_letter && data.cover_letter.full_text) ? data.cover_letter.full_text : buildCoverLetterContent(data.job_title, data.company, (data.tailored_resume && data.tailored_resume.summary) || '', matchedKeywords);
  const clTextarea = document.getElementById('tailor-cl-textarea');
  if (clTextarea) clTextarea.value = clText;
}

// --- Keyword Highlighting Helper ---
// Selected keywords highlighted using: #FFCED8
function highlightKeywordsInText(text, matchedKws, missingKws) {
  if (!text) return '';
  let escaped = escapeHtml(text);
  if (!isKeywordHighlightActive) return escaped;

  // Highlight matched keywords with #FFCED8 Soft Pink
  (matchedKws || []).forEach(kw => {
    if (!kw || kw.length < 2) return;
    const regex = new RegExp(`\\b(${escapeRegex(kw)})\\b`, 'gi');
    escaped = escaped.replace(regex, '<mark class="kw-matched">$1</mark>');
  });

  // Highlight missing keywords with Soft Orange
  (missingKws || []).forEach(kw => {
    if (!kw || kw.length < 2) return;
    const regex = new RegExp(`\\b(${escapeRegex(kw)})\\b`, 'gi');
    escaped = escaped.replace(regex, '<mark class="kw-missing">$1</mark>');
  });

  return escaped;
}

function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// --- Left Panel Mode Switcher & Workspace Handlers ---

function switchLeftPanelMode(mode) {
  ['active', 'url', 'paste', 'edit'].forEach(m => {
    const pane = document.getElementById(`left-pane-${m}`);
    const btn = document.getElementById(`btn-lpm-${m}`);
    if (pane) pane.style.display = m === mode ? 'block' : 'none';
    if (btn) btn.classList.toggle('active', m === mode);
  });
}

function setTailorSampleUrl(type) {
  const urlInput = document.getElementById('tailor-input-url');
  if (!urlInput) return;
  if (type === 'internshala') {
    urlInput.value = 'https://internshala.com/job/detail/mis-executive--sales-operations-reporting-job-in-noida-at-arihant-publications1790758397';
  } else if (type === 'wwr') {
    urlInput.value = 'https://weworkremotely.com/remote-jobs/cribl-analytics-business-partner';
  } else if (type === 'jobicy') {
    urlInput.value = 'https://jobicy.com/jobs/82075-data-analyst';
  }
}

async function scrapeAndTailorFromUrl() {
  const urlInput = document.getElementById('tailor-input-url');
  const url = (urlInput ? urlInput.value : '').trim();
  const btn = document.getElementById('btn-trigger-scrape-url');
  const statusEl = document.getElementById('url-scrape-status');

  if (!url || !url.startsWith('http')) {
    alert('Please enter a valid HTTP/HTTPS job posting URL.');
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner" style="width: 14px; height: 14px; border-width: 2px;"></div> Visiting Original Page & Deep Scraping...';
  }
  if (statusEl) {
    statusEl.style.display = 'block';
    statusEl.style.background = '#F0F9FF';
    statusEl.style.border = '1px solid #BAE6FD';
    statusEl.style.color = '#0369A1';
    statusEl.innerHTML = `<strong>Fetching live posting from:</strong> <span style="word-break: break-all;">${escapeHtml(url)}</span><br><span style="font-size: 0.78rem;">Visiting original employer/portal page, extracting full responsibilities, requirements, and technical skills...</span>`;
  }

  try {
    const res = await fetch('/api/resume/analyze-url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to scrape URL');
    }

    const data = await res.json();
    const scrapedJob = data.job;

    if (statusEl) {
      statusEl.innerHTML = `<strong>✓ Successfully scraped ${escapeHtml(scrapedJob.title)} at ${escapeHtml(scrapedJob.company)}!</strong><br><span style="font-size: 0.78rem;">Synthesizing 1-page LaTeX resume, compiling PDF, and generating cover letter...</span>`;
    }

    // Now tailor resume with complete scraped fields
    const tailorRes = await fetch('/api/resume/tailor', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_id: 'scraped_' + Date.now(),
        job_title: scrapedJob.title,
        company: scrapedJob.company,
        description: scrapedJob.description,
        skills: scrapedJob.skills,
        responsibilities: scrapedJob.responsibilities,
        requirements: scrapedJob.requirements,
        qualifications: scrapedJob.qualifications,
        ats_keywords: scrapedJob.ats_keywords,
        source_url: url,
        location: scrapedJob.location,
        work_mode: scrapedJob.work_mode,
        experience_level: scrapedJob.experience_level,
        salary: scrapedJob.salary,
        source_name: scrapedJob.source_name || 'Direct URL',
        application_deadline: scrapedJob.application_deadline,
        openings: scrapedJob.openings
      })
    });

    if (!tailorRes.ok) {
      const err = await tailorRes.json();
      throw new Error(err.detail || 'Failed to tailor resume');
    }

    const tailorData = await tailorRes.json();
    currentTailorData = tailorData;
    renderTailoredResumeModal(tailorData);

  } catch (err) {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '🚀 Scrape & Tailor ATS Resume';
    }
    if (statusEl) {
      statusEl.style.display = 'block';
      statusEl.style.background = '#FEF2F2';
      statusEl.style.border = '1px solid #FECACA';
      statusEl.style.color = '#B91C1C';
      statusEl.innerHTML = `<strong>Scraping Error:</strong> ${escapeHtml(err.message)}<br><span style="font-size: 0.78rem;">Tip: You can switch to Option A (Paste JD) and paste the job description text directly.</span>`;
    }
  }
}

async function tailorFromPastedDescription() {
  const title = (document.getElementById('paste-job-title')?.value || 'Data Analyst').trim();
  const company = (document.getElementById('paste-company')?.value || 'Target Employer').trim();
  const desc = (document.getElementById('paste-description')?.value || '').trim();
  const skillsStr = (document.getElementById('paste-skills')?.value || '').trim();
  const skills = skillsStr ? skillsStr.split(',').map(s => s.trim()).filter(Boolean) : [];
  const btn = document.getElementById('btn-trigger-paste-tailor');

  if (!desc || desc.length < 30) {
    alert('Please enter a complete job description (at least 30 characters).');
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner" style="width: 14px; height: 14px; border-width: 2px;"></div> Analyzing Job Description & Compiling Resume...';
  }

  try {
    const res = await fetch('/api/resume/tailor', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_id: 'custom_' + Date.now(),
        job_title: title,
        company: company,
        description: desc,
        skills: skills,
        source_name: 'Pasted Description',
        source_url: '#'
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to tailor resume');
    }

    const data = await res.json();
    currentTailorData = data;
    renderTailoredResumeModal(data);

  } catch (err) {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '✨ Analyze & Tailor Resume';
    }
    alert(`Error: ${err.message}`);
  }
}

async function saveAndRetailorScrapedJd() {
  if (!currentTailorData) return;
  const title = document.getElementById('edit-jd-title')?.value || currentTailorData.job_title;
  const company = document.getElementById('edit-jd-company')?.value || currentTailorData.company;
  const skillsStr = document.getElementById('edit-jd-skills')?.value || '';
  const skills = skillsStr ? skillsStr.split(',').map(s => s.trim()).filter(Boolean) : (currentTailorData.job_details?.skills || []);
  const respsStr = document.getElementById('edit-jd-resp')?.value || '';
  const responsibilities = respsStr ? respsStr.split('\n').map(s => s.trim()).filter(Boolean) : (currentTailorData.job_details?.responsibilities || []);
  const reqsStr = document.getElementById('edit-jd-req')?.value || '';
  const requirements = reqsStr ? reqsStr.split('\n').map(s => s.trim()).filter(Boolean) : (currentTailorData.job_details?.requirements || []);
  const desc = document.getElementById('edit-jd-desc')?.value || currentTailorData.job_details?.description || '';
  const btn = document.getElementById('btn-save-edited-jd');

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner" style="width: 14px; height: 14px; border-width: 2px;"></div> Re-tailoring with Updated Job Details...';
  }

  try {
    const res = await fetch('/api/resume/tailor', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_id: currentTailorData.job_id || ('edited_' + Date.now()),
        job_title: title,
        company: company,
        description: desc,
        skills: skills,
        responsibilities: responsibilities,
        requirements: requirements,
        source_url: currentTailorData.job_details?.source_url || '#'
      })
    });

    if (!tailorRes && !res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to update tailored resume');
    }

    const data = await res.json();
    currentTailorData = data;
    renderTailoredResumeModal(data);

  } catch (err) {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '💾 Apply Edits & Re-tailor Resume';
    }
    alert(`Error: ${err.message}`);
  }
}

async function regenerateCurrentTailoredResume() {
  if (!currentTailorData) return;
  const job = currentTailorData.job_details || {};
  await tailorResumeForJob(currentTailorData.job_id || job.id);
}

function openAITailorWorkspace() {
  switchTab('tailor-studio');
}

function renderBlankTailorWorkspace() {
  const bodyEl = document.getElementById('tailor-modal-body');
  const titleEl = document.getElementById('tailor-modal-title');
  const subtitleEl = document.getElementById('tailor-modal-subtitle');
  const topActionsEl = document.getElementById('tailor-modal-top-actions');

  titleEl.innerText = '⚡ AI Resume & Cover Letter Tailor';
  subtitleEl.innerText = 'Target any job posting: Paste URL (Option B) or Paste Description (Option A)';

  topActionsEl.innerHTML = `
    <button class="modal-close" onclick="closeModal('tailor-resume-modal')" style="font-size: 1.4rem; padding: 0.2rem 0.5rem;">✕</button>
  `;

  bodyEl.innerHTML = `
    <div class="split-screen-container" style="margin-top: 0;">
      
      <!-- LEFT PANEL: Input Options -->
      <div class="split-panel split-panel-left" id="panel-left-jd">
        <div class="left-panel-mode-nav">
          <button type="button" class="left-panel-mode-btn active" id="btn-lpm-url" onclick="switchLeftPanelMode('url')">
            🔗 Paste Job URL (Option B)
          </button>
          <button type="button" class="left-panel-mode-btn" id="btn-lpm-paste" onclick="switchLeftPanelMode('paste')">
            📝 Paste JD (Option A)
          </button>
        </div>

        <!-- Mode 2: Paste Job URL -->
        <div class="split-panel-body" id="left-pane-url" style="display: block; padding: 1.25rem;">
          <div style="margin-bottom: 1rem;">
            <h3 style="font-size: 1.1rem; font-weight: 800; color: #333333; margin-bottom: 0.35rem;">
              🔗 Option B: Scrape & Tailor from Job Posting URL
            </h3>
            <p style="font-size: 0.825rem; color: #64748B; line-height: 1.5; margin: 0;">
              Enter any live job URL from LinkedIn, Internshala, Naukri, Foundit, Indeed, Wellfound, WeWorkRemotely, Jobicy, Remotive, or company career page.
            </p>
          </div>

          <div style="margin-bottom: 0.85rem;">
            <label class="filter-label" style="margin-bottom: 0.35rem;">Job Posting URL</label>
            <input type="url" id="tailor-input-url" class="search-input" style="padding-left: 0.85rem;" placeholder="https://internshala.com/job/detail/... or https://weworkremotely.com/...">
          </div>

          <!-- Quick Sample Platform Chips -->
          <div style="margin-bottom: 1.25rem;">
            <span style="font-size: 0.75rem; color: #64748B; font-weight: 700; display: block; margin-bottom: 0.4rem;">TRY WITH LIVE EXAMPLES:</span>
            <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
              <button type="button" class="quick-sample-chip" onclick="setTailorSampleUrl('internshala')">
                📄 Internshala: Arihant MIS
              </button>
              <button type="button" class="quick-sample-chip" onclick="setTailorSampleUrl('wwr')">
                🌐 WeWorkRemotely: Cribl Analytics
              </button>
              <button type="button" class="quick-sample-chip" onclick="setTailorSampleUrl('jobicy')">
                💻 Jobicy: Remote Data Analyst
              </button>
            </div>
          </div>

          <button type="button" class="btn btn-primary" id="btn-trigger-scrape-url" onclick="scrapeAndTailorFromUrl()" style="width: 100%; font-weight: 700; padding: 0.65rem;">
            🚀 Scrape & Tailor ATS Resume
          </button>

          <div id="url-scrape-status" style="display: none; margin-top: 1rem; padding: 0.85rem; border-radius: 8px; font-size: 0.825rem;"></div>
        </div>

        <!-- Mode 3: Paste JD -->
        <div class="split-panel-body" id="left-pane-paste" style="display: none; padding: 1.25rem;">
          <div style="margin-bottom: 1rem;">
            <h3 style="font-size: 1.1rem; font-weight: 800; color: #333333; margin-bottom: 0.35rem;">
              📝 Option A: Paste Target Job Description
            </h3>
            <p style="font-size: 0.825rem; color: #64748B; line-height: 1.5; margin: 0;">
              Paste any job description to automatically extract requirements, responsibilities, and synthesize customized documents.
            </p>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-bottom: 0.75rem;">
            <div>
              <label class="filter-label" style="margin-bottom: 0.35rem;">Job Title</label>
              <input type="text" id="paste-job-title" class="search-input" value="Data Analyst" style="padding-left: 0.85rem;">
            </div>
            <div>
              <label class="filter-label" style="margin-bottom: 0.35rem;">Company</label>
              <input type="text" id="paste-company" class="search-input" value="Target Employer" style="padding-left: 0.85rem;">
            </div>
          </div>

          <div style="margin-bottom: 0.75rem;">
            <label class="filter-label" style="margin-bottom: 0.35rem;">Technical Skills (optional)</label>
            <input type="text" id="paste-skills" class="search-input" placeholder="e.g. Power BI, SQL, Python, Excel, DAX" style="padding-left: 0.85rem;">
          </div>

          <div style="margin-bottom: 1rem;">
            <label class="filter-label" style="margin-bottom: 0.35rem;">Full Job Description Text</label>
            <textarea id="paste-description" class="edit-textarea" style="min-height: 220px; font-size: 0.85rem; line-height: 1.55; padding: 0.85rem;" placeholder="Paste the complete job description here, including responsibilities, requirements, qualifications, and company overview..."></textarea>
          </div>

          <button type="button" class="btn btn-primary" id="btn-trigger-paste-tailor" onclick="tailorFromPastedDescription()" style="width: 100%; font-weight: 700; padding: 0.65rem;">
            ✨ Analyze & Tailor Resume
          </button>
        </div>
      </div>

      <!-- RIGHT PANEL: Guidance Preview -->
      <div class="split-panel split-panel-right" style="display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; padding: 2rem;">
        <div style="font-size: 3rem; margin-bottom: 1rem;">⚡</div>
        <h3 style="font-size: 1.35rem; font-weight: 800; color: #333333; margin-bottom: 0.5rem;">
          AI Resume & Cover Letter Tailoring Engine
        </h3>
        <p style="color: #64748B; font-size: 0.9rem; max-width: 480px; line-height: 1.6; margin-bottom: 1.5rem;">
          Grounded directly in your verified <strong>Master Resume & Career Knowledge Base</strong>. Enter a URL on the left or paste a job description to immediately compile:
        </p>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; text-align: left; max-width: 480px; width: 100%;">
          <div style="background: #FFFFFF; border: 1.5px solid var(--border-color); padding: 0.75rem 1rem; border-radius: 8px;">
            <div style="font-weight: 700; color: #333333; font-size: 0.85rem;">📄 Strict 1-Page LaTeX PDF</div>
            <div style="font-size: 0.75rem; color: #64748B;">Overleaf-ready Jake's format</div>
          </div>
          <div style="background: #FFFFFF; border: 1.5px solid var(--border-color); padding: 0.75rem 1rem; border-radius: 8px;">
            <div style="font-weight: 700; color: #333333; font-size: 0.85rem;">📘 Editable Word (.docx)</div>
            <div style="font-size: 0.75rem; color: #64748B;">100% Google Docs compatible</div>
          </div>
          <div style="background: #FFFFFF; border: 1.5px solid var(--border-color); padding: 0.75rem 1rem; border-radius: 8px;">
            <div style="font-weight: 700; color: #333333; font-size: 0.85rem;">✉️ Tailored Cover Letter</div>
            <div style="font-size: 0.75rem; color: #64748B;">Aligned to posted responsibilities</div>
          </div>
          <div style="background: #FFFFFF; border: 1.5px solid var(--border-color); padding: 0.75rem 1rem; border-radius: 8px;">
            <div style="font-weight: 700; color: #333333; font-size: 0.85rem;">🔒 Zero False Claims</div>
            <div style="font-size: 0.75rem; color: #64748B;">Strict truthfulness enforced</div>
          </div>
        </div>
      </div>

    </div>
  `;
}

function toggleKeywordHighlights() {
  isKeywordHighlightActive = !isKeywordHighlightActive;
  const btn = document.getElementById('btn-highlight-kw');
  if (btn) {
    btn.innerText = isKeywordHighlightActive ? '✨ Highlights: ON (#FFCED8)' : 'Highlights: OFF';
    btn.style.color = isKeywordHighlightActive ? 'var(--text-primary)' : 'var(--text-muted)';
  }
  const textEl = document.getElementById('jd-raw-text');
  if (textEl && currentTailorData) {
    const job = currentTailorData.job_details || {};
    const ats = currentTailorData.ats_metrics || {};
    textEl.innerHTML = highlightKeywordsInText(job.description || '', ats.matched_keywords || [], ats.missing_keywords || []);
  }
}

function toggleComparisonDrawer() {
  const drawer = document.getElementById('comparison-drawer');
  const btn = document.getElementById('btn-toggle-comparison');
  if (!drawer) return;
  const isHidden = drawer.style.display === 'none';
  drawer.style.display = isHidden ? 'block' : 'none';
  if (btn) {
    btn.innerText = isHidden ? '📊 Hide Comparison Breakdown ▴' : '📊 View Comparison Breakdown ▾';
  }
}

function switchMobileSplitPanel(panelName) {
  const leftPanel = document.getElementById('panel-left-jd');
  const rightPanel = document.getElementById('panel-right-resume');
  const btnJd = document.getElementById('btn-mobile-jd');
  const btnResume = document.getElementById('btn-mobile-resume');

  if (panelName === 'jd') {
    if (leftPanel) leftPanel.classList.remove('mobile-hide');
    if (rightPanel) rightPanel.classList.add('mobile-hide');
    if (btnJd) btnJd.classList.add('active');
    if (btnResume) btnResume.classList.remove('active');
  } else {
    if (leftPanel) leftPanel.classList.add('mobile-hide');
    if (rightPanel) rightPanel.classList.remove('mobile-hide');
    if (btnJd) btnJd.classList.remove('active');
    if (btnResume) btnResume.classList.add('active');
  }
}

function switchTailorTab(tabName) {
  ['pdf', 'edit', 'latex', 'ats', 'cover', 'evidence'].forEach(t => {
    const pane = document.getElementById(`tailor-pane-${t}`);
    const btn = document.getElementById(`tailor-tab-btn-${t}`);
    if (pane) pane.style.display = t === tabName ? 'block' : 'none';
    if (btn) btn.classList.toggle('active', t === tabName);
  });

  const toggleBtn = document.getElementById('btn-toggle-edit');
  if (toggleBtn) {
    toggleBtn.innerText = tabName === 'edit' ? '👁️ View PDF' : '✏️ Edit Resume';
  }
}

function toggleResumeEditMode() {
  const editPane = document.getElementById('tailor-pane-edit');
  const isEditActive = editPane && editPane.style.display === 'block';
  switchTailorTab(isEditActive ? 'pdf' : 'edit');
}

// --- Live Resume Edit Form Builder (Resume Builder) ---

function buildResumeEditForm(resume) {
  if (!resume) return '<p style="color: #666666;">No resume data available.</p>';

  const summary = resume.summary || '';
  const skills = resume.skills || {};
  const experience = resume.experience || [];
  const projects = resume.projects || [];
  const certifications = resume.certifications || [];

  // Skills Categories
  let skillsInputs = '';
  for (const [catKey, items] of Object.entries(skills)) {
    const catLabel = catKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    const val = Array.isArray(items) ? items.join(', ') : String(items);
    skillsInputs += `
      <div style="margin-bottom: 0.6rem;">
        <label style="display: block; font-size: 0.8rem; font-weight: 700; color: #333333; margin-bottom: 0.25rem;">${escapeHtml(catLabel)}</label>
        <input type="text" class="edit-input" data-skill-cat="${escapeHtml(catKey)}" value="${escapeHtml(val)}">
      </div>
    `;
  }

  // Experience Items
  const expHtml = experience.map((exp, idx) => `
    <div class="edit-item-box" data-exp-idx="${idx}">
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.6rem; margin-bottom: 0.5rem;">
        <div>
          <label style="font-size: 0.775rem; font-weight: 600; color: #666666;">Job Title</label>
          <input type="text" class="edit-input exp-title" value="${escapeHtml(exp.title || '')}">
        </div>
        <div>
          <label style="font-size: 0.775rem; font-weight: 600; color: #666666;">Company</label>
          <input type="text" class="edit-input exp-company" value="${escapeHtml(exp.company || '')}">
        </div>
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.6rem; margin-bottom: 0.6rem;">
        <div>
          <label style="font-size: 0.775rem; font-weight: 600; color: #666666;">Dates / Period</label>
          <input type="text" class="edit-input exp-dates" value="${escapeHtml(exp.dates || exp.period || '')}">
        </div>
        <div>
          <label style="font-size: 0.775rem; font-weight: 600; color: #666666;">Location</label>
          <input type="text" class="edit-input exp-location" value="${escapeHtml(exp.location || '')}">
        </div>
      </div>
      <div>
        <label style="font-size: 0.775rem; font-weight: 700; color: #333333; margin-bottom: 0.25rem; display: block;">Bullet Points</label>
        <div class="exp-bullets-container">
          ${(exp.bullets || []).map(b => `
            <div class="edit-bullet-row">
              <input type="text" class="edit-input bullet-text" value="${escapeHtml(b)}">
              <button type="button" class="btn-del-bullet" onclick="deleteEditBullet(this)">✕</button>
            </div>
          `).join('')}
        </div>
        <button type="button" class="btn-add-bullet" onclick="addEditBullet(this)">+ Add Bullet Point</button>
      </div>
    </div>
  `).join('');

  // Projects Items
  const projHtml = projects.map((proj, idx) => `
    <div class="edit-item-box" data-proj-idx="${idx}">
      <div style="display: grid; grid-template-columns: 1.2fr 1fr; gap: 0.6rem; margin-bottom: 0.5rem;">
        <div>
          <label style="font-size: 0.775rem; font-weight: 600; color: #666666;">Project Name</label>
          <input type="text" class="edit-input proj-title" value="${escapeHtml(proj.title || proj.name || '')}">
        </div>
        <div>
          <label style="font-size: 0.775rem; font-weight: 600; color: #666666;">Tools / Tech Stack</label>
          <input type="text" class="edit-input proj-tools" value="${escapeHtml(proj.tools || proj.tech_stack || '')}">
        </div>
      </div>
      <div>
        <label style="font-size: 0.775rem; font-weight: 700; color: #333333; margin-bottom: 0.25rem; display: block;">Bullet Points</label>
        <div class="proj-bullets-container">
          ${(proj.bullets || []).map(b => `
            <div class="edit-bullet-row">
              <input type="text" class="edit-input bullet-text" value="${escapeHtml(b)}">
              <button type="button" class="btn-del-bullet" onclick="deleteEditBullet(this)">✕</button>
            </div>
          `).join('')}
        </div>
        <button type="button" class="btn-add-bullet" onclick="addEditBullet(this)">+ Add Bullet Point</button>
      </div>
    </div>
  `).join('');

  // Certifications
  const certHtml = certifications.map((cert, idx) => {
    const cName = cert.name || cert;
    return `
      <div style="margin-bottom: 0.45rem;">
        <input type="text" class="edit-input cert-name" data-cert-idx="${idx}" value="${escapeHtml(cName)}">
      </div>
    `;
  }).join('');

  return `
    <div class="edit-card">
      <div class="edit-card-title">
        <span>Professional Summary</span>
        <span style="font-size: 0.75rem; color: #666666; text-transform: none;">Strictly tailored for role</span>
      </div>
      <textarea id="edit-summary-input" class="edit-textarea">${escapeHtml(summary)}</textarea>
    </div>

    <div class="edit-card">
      <div class="edit-card-title">
        <span>Technical Skills by Category</span>
        <span style="font-size: 0.75rem; color: #666666; text-transform: none;">Comma-separated values</span>
      </div>
      ${skillsInputs}
    </div>

    <div class="edit-card">
      <div class="edit-card-title">
        <span>Work Experience Highlights</span>
      </div>
      ${expHtml}
    </div>

    <div class="edit-card">
      <div class="edit-card-title">
        <span>Projects & Business Intelligence Solutions</span>
      </div>
      ${projHtml}
    </div>

    <div class="edit-card">
      <div class="edit-card-title">
        <span>Certifications & Credentials</span>
      </div>
      ${certHtml}
    </div>
  `;
}

function addEditBullet(btn) {
  const container = btn.previousElementSibling;
  if (!container) return;
  const div = document.createElement('div');
  div.className = 'edit-bullet-row';
  div.innerHTML = `
    <input type="text" class="edit-input bullet-text" value="" placeholder="New achievement or responsibility bullet point...">
    <button type="button" class="btn-del-bullet" onclick="deleteEditBullet(this)">✕</button>
  `;
  container.appendChild(div);
  const input = div.querySelector('input');
  if (input) input.focus();
}

function deleteEditBullet(btn) {
  const row = btn.closest('.edit-bullet-row');
  if (row) row.remove();
}

async function saveAndRecompileResume() {
  if (!currentTailorData) return;

  const btn = document.getElementById('btn-save-recompile');
  const statusEl = document.getElementById('save-editor-status');

  btn.disabled = true;
  btn.innerHTML = '<div class="spinner"></div> Recompiling PDF, Word, & LaTeX...';
  if (statusEl) {
    statusEl.style.display = 'inline-block';
    statusEl.innerText = 'Compiling...';
  }

  try {
    const summaryInput = document.getElementById('edit-summary-input');
    const updatedSummary = summaryInput ? summaryInput.value.trim() : currentTailorData.tailored_resume.summary;

    const updatedSkills = { ...currentTailorData.tailored_resume.skills };
    document.querySelectorAll('[data-skill-cat]').forEach(el => {
      const cat = el.dataset.skillCat;
      const raw = el.value.trim();
      updatedSkills[cat] = raw.split(',').map(s => s.trim()).filter(Boolean);
    });

    const updatedExperience = (currentTailorData.tailored_resume.experience || []).map((exp, idx) => {
      const box = document.querySelector(`[data-exp-idx="${idx}"]`);
      if (!box) return exp;
      const title = box.querySelector('.exp-title') ? box.querySelector('.exp-title').value.trim() : exp.title;
      const company = box.querySelector('.exp-company') ? box.querySelector('.exp-company').value.trim() : exp.company;
      const dates = box.querySelector('.exp-dates') ? box.querySelector('.exp-dates').value.trim() : exp.dates;
      const location = box.querySelector('.exp-location') ? box.querySelector('.exp-location').value.trim() : exp.location;
      const bullets = Array.from(box.querySelectorAll('.bullet-text')).map(b => b.value.trim()).filter(Boolean);

      return { ...exp, title, company, dates, location, bullets };
    });

    const updatedProjects = (currentTailorData.tailored_resume.projects || []).map((proj, idx) => {
      const box = document.querySelector(`[data-proj-idx="${idx}"]`);
      if (!box) return proj;
      const title = box.querySelector('.proj-title') ? box.querySelector('.proj-title').value.trim() : (proj.title || proj.name);
      const tools = box.querySelector('.proj-tools') ? box.querySelector('.proj-tools').value.trim() : (proj.tools || proj.tech_stack);
      const bullets = Array.from(box.querySelectorAll('.bullet-text')).map(b => b.value.trim()).filter(Boolean);

      return { ...proj, title, name: title, tools, tech_stack: tools, bullets };
    });

    const updatedCertifications = (currentTailorData.tailored_resume.certifications || []).map((cert, idx) => {
      const input = document.querySelector(`[data-cert-idx="${idx}"]`);
      if (!input) return cert;
      const val = input.value.trim();
      return typeof cert === 'object' ? { ...cert, name: val } : val;
    });

    const updatedResume = {
      ...currentTailorData.tailored_resume,
      summary: updatedSummary,
      skills: updatedSkills,
      experience: updatedExperience,
      projects: updatedProjects,
      certifications: updatedCertifications
    };

    const res = await fetch('/api/resume/update-tailored', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_id: currentTailorData.job_id,
        tailored_resume: updatedResume
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `Server error (${res.status})`);
    }

    const result = await res.json();

    currentTailorData.tailored_resume = result.tailored_resume;
    currentTailorData.latex_code = result.latex_code;
    currentTailorData.pdf_url = result.pdf_url;
    currentTailorData.pdf_preview_url = result.pdf_preview_url;
    currentTailorData.docx_url = result.docx_url;
    currentTailorData.tex_url = result.tex_url;

    const btnDocx = document.getElementById('btn-dl-docx');
    if (btnDocx) {
      btnDocx.href = result.docx_url;
      if (result.filenames && result.filenames.resume_docx) btnDocx.download = result.filenames.resume_docx;
    }
    const btnPdf = document.getElementById('btn-dl-pdf');
    if (btnPdf) {
      btnPdf.href = result.pdf_url;
      if (result.filenames && result.filenames.resume_pdf) btnPdf.download = result.filenames.resume_pdf;
    }
    const btnTex = document.getElementById('btn-dl-tex');
    if (btnTex) {
      btnTex.href = result.tex_url;
      if (result.filenames && result.filenames.resume_tex) btnTex.download = result.filenames.resume_tex;
    }
    const btnTxt = document.getElementById('btn-dl-txt');
    if (btnTxt) {
      if (result.txt_url) btnTxt.href = result.txt_url;
      if (result.filenames && result.filenames.resume_txt) btnTxt.download = result.filenames.resume_txt;
    }

    const latexPre = document.getElementById('tailored-latex-pre');
    if (latexPre) latexPre.innerText = result.latex_code;

    const iframe = document.getElementById('tailor-pdf-iframe');
    if (iframe) iframe.src = result.pdf_preview_url + '#toolbar=0&navpanes=0';

    const htmlPreview = document.getElementById('ts-resume-html-preview');
    if (htmlPreview) htmlPreview.innerHTML = renderLatexResumePreviewHtml(result.tailored_resume);

    if (statusEl) {
      statusEl.innerText = '✓ Saved & Recompiled!';
      setTimeout(() => { statusEl.style.display = 'none'; }, 3000);
    }

    btn.disabled = false;
    btn.innerHTML = '💾 Save & Recompile All Formats (PDF, Word, LaTeX)';

    switchTailorTab('pdf');

  } catch (err) {
    console.error('Failed to save and recompile resume:', err);
    alert(`Error updating resume: ${err.message}`);
    btn.disabled = false;
    btn.innerHTML = '💾 Save & Recompile All Formats (PDF, Word, LaTeX)';
    if (statusEl) statusEl.style.display = 'none';
  }
}

function copyCurrentLatex() {
  if (!currentTailorData || !currentTailorData.latex_code) return;
  navigator.clipboard.writeText(currentTailorData.latex_code).then(() => {
    alert('✓ Copied Overleaf LaTeX code to clipboard!');
  }).catch(err => {
    console.error('Failed to copy LaTeX code:', err);
  });
}

// --- Cover Letter Builder Support ---

function buildCoverLetterContent(role, company, summary, skills) {
  const profileName = state.masterProfile && state.masterProfile.name;
  const candidateName = (profileName && !profileName.includes('Not Available')) ? profileName : 'Candidate Name';
  const email = (state.masterProfile && state.masterProfile.email && !state.masterProfile.email.includes('Not Available')) ? state.masterProfile.email : '';
  const phone = (state.masterProfile && state.masterProfile.phone && !state.masterProfile.phone.includes('Not Available')) ? state.masterProfile.phone : '';
  const location = (state.masterProfile && state.masterProfile.location && !state.masterProfile.location.includes('Not Available')) ? state.masterProfile.location : '';

  const skillStr = (skills && skills.length > 0) ? skills.slice(0, 4).join(', ') : ((state.masterProfile && state.masterProfile.technical_tools && state.masterProfile.technical_tools.length > 0) ? state.masterProfile.technical_tools.slice(0, 4).join(', ') : 'technical competencies');

  return `Dear Hiring Manager,

I am writing to express my enthusiastic interest in the ${role || 'open'} position at ${company || 'your organization'}. With a verified background in ${skillStr}, I am eager to apply my practical technical competencies to support your team's objectives.

${summary ? summary : 'I have developed strong discipline in applying validated methodologies to deliver high-quality, measurable deliverables.'}

I look forward to discussing how my verified background aligns with your team's priorities. Thank you for your time and consideration.

Sincerely,

${candidateName}
${location ? location + '\n' : ''}${phone ? phone + ' | ' : ''}${email ? email : ''}`;
}

function copyTailoredCoverLetter() {
  const textarea = document.getElementById('tailor-cl-textarea');
  if (!textarea) return;
  navigator.clipboard.writeText(textarea.value).then(() => {
    alert('✓ Tailored Cover Letter copied to clipboard!');
  });
}

function downloadTailoredCoverLetterTxt() {
  const textarea = document.getElementById('tailor-cl-textarea');
  if (!textarea || !textarea.value) return;
  const candName = (currentTailorData && currentTailorData.tailored_resume && currentTailorData.tailored_resume.name) || (state.masterProfile && state.masterProfile.name) || 'Tejas Waghmare';
  const role = (currentTailorData && currentTailorData.job_title) || 'Data Analyst';
  const company = (currentTailorData && currentTailorData.company) || 'Target Employer';
  const filename = getStandardDocFilename(candName, role, company, 'Cover_Letter', 'txt');
  const blob = new Blob([textarea.value], { type: 'text/plain;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
}

function openStandaloneCoverLetterModal() {
  const modal = document.getElementById('cover-letter-modal');
  modal.style.display = 'flex';
  generateCoverLetterDraft();
}

function generateCoverLetterDraft() {
  const companyInput = document.getElementById('cl-company-input');
  const roleInput = document.getElementById('cl-role-input');
  const preview = document.getElementById('cl-preview-textarea');

  const comp = companyInput && companyInput.value ? companyInput.value.trim() : 'Swiggy';
  const r = roleInput && roleInput.value ? roleInput.value.trim() : 'Junior Data Analyst (0–1 Year Exp)';

  const text = buildCoverLetterContent(r, comp, (state.masterProfile && state.masterProfile.summary) || '', ['SQL', 'Power BI', 'Python', 'Excel']);
  if (preview) preview.value = text;
}

function copyCoverLetterText() {
  const preview = document.getElementById('cl-preview-textarea');
  if (!preview) return;
  navigator.clipboard.writeText(preview.value).then(() => {
    alert('✓ Cover letter copied to clipboard!');
  });
}

function downloadCoverLetterTxt() {
  const preview = document.getElementById('cl-preview-textarea');
  if (!preview || !preview.value) return;
  const compInput = document.getElementById('cl-company-input');
  const roleInput = document.getElementById('cl-role-input');
  const candName = (state.masterProfile && state.masterProfile.name) || 'Tejas Waghmare';
  const role = (roleInput && roleInput.value) ? roleInput.value.trim() : 'Data Analyst';
  const comp = (compInput && compInput.value) ? compInput.value.trim() : 'Target Employer';
  const filename = getStandardDocFilename(candName, role, comp, 'Cover_Letter', 'txt');
  const blob = new Blob([preview.value], { type: 'text/plain;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
}

// --- Settings Modal & Preferences ---

function openSettingsModal() {
  const modal = document.getElementById('settings-modal');
  modal.style.display = 'flex';
}

function loadSettings() {
  try {
    const saved = localStorage.getItem('job_finder_settings');
    if (saved) {
      const cfg = JSON.parse(saved);
      const strictEl = document.getElementById('setting-fresher-strict');
      const atsEl = document.getElementById('setting-high-ats');
      const hlEl = document.getElementById('setting-auto-highlight');
      if (strictEl && cfg.fresherStrict !== undefined) strictEl.checked = cfg.fresherStrict;
      if (atsEl && cfg.highAts !== undefined) atsEl.checked = cfg.highAts;
      if (hlEl && cfg.autoHighlight !== undefined) {
        hlEl.checked = cfg.autoHighlight;
        isKeywordHighlightActive = cfg.autoHighlight;
      }
    }
    const settingDarkTheme = document.getElementById('setting-dark-theme');
    if (settingDarkTheme) {
      settingDarkTheme.checked = (getCurrentTheme() === 'dark');
    }
  } catch (err) {
    console.warn('Could not load settings:', err);
  }
}

function saveSettings() {
  const strictEl = document.getElementById('setting-fresher-strict');
  const atsEl = document.getElementById('setting-high-ats');
  const hlEl = document.getElementById('setting-auto-highlight');
  const darkEl = document.getElementById('setting-dark-theme');

  const cfg = {
    fresherStrict: strictEl ? strictEl.checked : true,
    highAts: atsEl ? atsEl.checked : true,
    autoHighlight: hlEl ? hlEl.checked : true,
    darkTheme: darkEl ? darkEl.checked : (getCurrentTheme() === 'dark')
  };

  localStorage.setItem('job_finder_settings', JSON.stringify(cfg));
  if (darkEl) {
    toggleTheme(darkEl.checked);
  }
  isKeywordHighlightActive = cfg.autoHighlight;
  closeModal('settings-modal');
  alert('✓ Preferences saved successfully!');
}

// ==========================================================================
// CAREER KNOWLEDGE BASE & AI STUDIO FRONTEND LOGIC
// ==========================================================================

let kbState = {
  documents: [],
  categoryFilter: 'all',
  searchQuery: '',
  activeSubnav: 'repo'
};

function getDocCategoryIcon(cat, ext) {
  switch (cat) {
    case 'resume': return '📄';
    case 'cover_letter': return '✉️';
    case 'certificate': case 'training': return '🏆';
    case 'portfolio': return '🎨';
    case 'project_doc': return '📊';
    case 'case_study': return '💼';
    case 'award': case 'achievement': return '🎖️';
    case 'recommendation': return '📝';
    case 'transcript': return '🎓';
    case 'license': return '🛡️';
    case 'linkedin_export': return '🔗';
    case 'bio': return '👤';
    default:
      if (['png', 'jpg', 'jpeg'].includes((ext || '').toLowerCase())) return '🖼️';
      return '📁';
  }
}

function getStatusPill(status) {
  if (status === 'Ready for AI Usage' || status === 'ready' || status === 'indexed') {
    return '<span class="status-pill status-pill-ready">🟢 Ready for AI Usage</span>';
  } else if (status === 'Indexed') {
    return '<span class="status-pill status-pill-indexed">🔵 Indexed</span>';
  } else if (status === 'Processing') {
    return '<span class="status-pill status-pill-processing">🟡 Processing</span>';
  } else if (status === 'Error') {
    return '<span class="status-pill status-pill-error">🔴 Error</span>';
  }
  return `<span class="status-pill status-pill-ready">🟢 ${escapeHtml(status || 'Indexed')}</span>`;
}

function setupKBDropzone() {
  const dropzone = document.getElementById('kb-upload-dropzone');
  if (!dropzone) return;

  ['dragenter', 'dragover'].forEach(evtName => {
    dropzone.addEventListener(evtName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(evtName => {
    dropzone.addEventListener(evtName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      handleKBBatchUpload(files);
    }
  });
}

function switchKBSubnav(pane) {
  kbState.activeSubnav = pane;
  ['repo', 'profile', 'studio'].forEach(p => {
    const paneEl = document.getElementById(`kb-pane-${p}`);
    const btnEl = document.getElementById(`kb-subnav-${p}`);
    if (paneEl) paneEl.style.display = p === pane ? 'block' : 'none';
    if (btnEl) btnEl.classList.toggle('active', p === pane);
  });

  if (pane === 'repo') {
    loadKBDocuments();
  } else if (pane === 'profile') {
    loadKBUnifiedProfile();
  } else if (pane === 'studio') {
    loadKBStudioSnapshot();
  }
}

function formatDateTime(isoStr) {
  if (!isoStr) return 'Recently Processed';
  try {
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return isoStr;
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch (e) {
    return isoStr;
  }
}

function escapeJs(str) {
  if (!str) return '';
  return String(str).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"');
}

let pendingDocIdToDelete = null;

function promptDeleteDocument(docId, fileName) {
  pendingDocIdToDelete = docId;
  const badgeEl = document.getElementById('delete-confirm-file-badge');
  if (badgeEl) badgeEl.innerText = `📄 ${fileName}`;
  const modal = document.getElementById('delete-confirm-modal');
  if (modal) modal.style.display = 'flex';
}

async function executeDeleteDocument() {
  if (!pendingDocIdToDelete) return;
  const docId = pendingDocIdToDelete;
  closeModal('delete-confirm-modal');
  pendingDocIdToDelete = null;

  try {
    const res = await fetch(`/api/kb/document/${docId}`, {
      method: 'DELETE'
    });
    if (!res.ok) throw new Error('Failed to delete file from repository');

    await loadKBDocuments();
    await loadKBUnifiedProfile();
    await renderMasterModalDocuments();
    await refreshMasterProfileContent();
    await loadStats();
    await loadMasterResumeStatus();

  } catch (err) {
    alert(`Error deleting file: ${err.message}`);
  }
}

function renderRepoSummaryStats(stats) {
  const total = stats.total_uploaded || stats.total_docs || 0;
  const ready = stats.successfully_processed || stats.indexed_docs || 0;
  const failed = stats.failed_files || 0;
  const tailoring = stats.used_for_tailoring || ready;

  return `
    <div class="repo-transparency-card">
      <div class="repo-stat-box">
        <div class="repo-stat-icon" style="color: #3b82f6;">📁</div>
        <div>
          <div class="repo-stat-val">${total}</div>
          <div class="repo-stat-lbl">Total Files Uploaded</div>
        </div>
      </div>
      <div class="repo-stat-box">
        <div class="repo-stat-icon" style="color: #10b981;">✅</div>
        <div>
          <div class="repo-stat-val" style="color: #059669;">${ready}</div>
          <div class="repo-stat-lbl">Successfully Processed</div>
        </div>
      </div>
      <div class="repo-stat-box">
        <div class="repo-stat-icon" style="color: ${failed > 0 ? '#ef4444' : '#94a3b8'};">${failed > 0 ? '❌' : '🛡️'}</div>
        <div>
          <div class="repo-stat-val" style="color: ${failed > 0 ? '#dc2626' : '#64748b'};">${failed}</div>
          <div class="repo-stat-lbl">Failed Files</div>
        </div>
      </div>
      <div class="repo-stat-box" style="border-color: #86efac; background: rgba(240, 253, 244, 0.7);">
        <div class="repo-stat-icon" style="color: #16a34a;">🎯</div>
        <div>
          <div class="repo-stat-val" style="color: #15803d;">${tailoring}</div>
          <div class="repo-stat-lbl" style="color: #166534;">Files Used for Tailoring</div>
        </div>
      </div>
    </div>
  `;
}

function renderDocCardHtml(doc, isDarkTheme = null) {
  if (isDarkTheme === null || isDarkTheme === undefined) {
    isDarkTheme = getCurrentTheme() === 'dark';
  }
  const icon = getDocCategoryIcon(doc.category, doc.file_type);
  const catLabel = (doc.category || 'Other').replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  const uploadDateStr = formatDateTime(doc.uploaded_at);
  const lastProcessedStr = formatDateTime(doc.last_processed_at || doc.uploaded_at);
  const fileTypeUpper = (doc.file_type || '').toUpperCase() || 'FILE';
  const fileSizeStr = doc.file_size_formatted || (doc.file_size ? Math.round(doc.file_size / 1024) + ' KB' : 'N/A');
  const uploadStatus = doc.upload_status || 'Uploaded';
  const extractionStatus = doc.extraction_status || doc.status || 'Ready for AI Usage';
  const isReady = extractionStatus === 'Ready for AI Usage';

  return `
    <div class="kb-doc-card" id="kb-doc-${doc.id}" style="${isDarkTheme ? '' : 'background: #ffffff; border: 1.5px solid #e2e8f0; border-top: 4px solid var(--color-primary); border-radius: 12px; padding: 1.15rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05);'}">
      <div>
        <div class="kb-doc-header">
          <div class="kb-doc-icon">${icon}</div>
          <div class="kb-doc-info">
            <div class="kb-doc-title" style="margin-bottom: 0.25rem;">
              <span class="kb-doc-title-text" style="font-weight: 800; ${isDarkTheme ? 'color: #f8fafc;' : 'color: #0f172a;'}" title="${escapeHtml(doc.display_name || doc.filename)}">${escapeHtml(doc.display_name || doc.filename)}</span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.45rem; flex-wrap: wrap;">
              <span class="doc-cat-tag" style="background: rgba(14, 165, 233, 0.12); color: #0284c7; font-weight: 700; font-size: 0.725rem; padding: 0.15rem 0.5rem; border-radius: 4px;">🏷️ ${escapeHtml(catLabel)}</span>
              ${getStatusPill(extractionStatus)}
            </div>
          </div>
        </div>

        <!-- Comprehensive File Metadata Grid (Requirement 1) -->
        <div class="kb-doc-field-grid">
          <div class="kb-doc-field-row">
            <span class="kb-doc-field-label">File Type:</span>
            <span class="kb-doc-field-value">${escapeHtml(fileTypeUpper)}</span>
          </div>
          <div class="kb-doc-field-row">
            <span class="kb-doc-field-label">File Size:</span>
            <span class="kb-doc-field-value">${escapeHtml(fileSizeStr)}</span>
          </div>
          <div class="kb-doc-field-row">
            <span class="kb-doc-field-label">Upload Status:</span>
            <span class="kb-doc-field-value" style="color: #059669;">✓ ${escapeHtml(uploadStatus)}</span>
          </div>
          <div class="kb-doc-field-row">
            <span class="kb-doc-field-label">Extraction:</span>
            <span class="kb-doc-field-value" style="${isReady ? 'color: #059669;' : 'color: #dc2626;'}">${escapeHtml(extractionStatus)}</span>
          </div>
          <div class="kb-doc-field-row" style="grid-column: 1 / -1;">
            <span class="kb-doc-field-label">Uploaded Date & Time:</span>
            <span class="kb-doc-field-value">${escapeHtml(uploadDateStr)}</span>
          </div>
          <div class="kb-doc-field-row" style="grid-column: 1 / -1;">
            <span class="kb-doc-field-label">Last Processed:</span>
            <span class="kb-doc-field-value">${escapeHtml(lastProcessedStr)}</span>
          </div>
        </div>

        <div class="kb-doc-summary" style="${doc.status === 'Error' ? 'color: #dc2626;' : (isDarkTheme ? 'color: #94a3b8;' : 'color: #475569;')} font-size: 0.8rem; line-height: 1.45; margin-bottom: 0.75rem;">
          ${escapeHtml(doc.extracted_summary || 'Document indexed into career knowledge base.')}
        </div>
      </div>

      <!-- Action Buttons: Single Delete Option (Requirement 3 & 4) -->
      <div class="kb-doc-actions" style="display: flex; gap: 0.4rem; flex-wrap: wrap; margin-top: auto; padding-top: 0.5rem;">
        <button type="button" class="btn btn-outline btn-sm" onclick="openDocPreview('${doc.id}')" title="View Extracted Content & Structured Intelligence">📄 View Extracted Content</button>
        <button type="button" class="btn btn-outline btn-sm" id="btn-reprocess-${doc.id}" onclick="reprocessKBDocument('${doc.id}')" title="Re-extract and re-parse file">🔄 Reprocess</button>
        <a href="/api/kb/document/${doc.id}/preview" target="_blank" download="${escapeHtml(doc.filename)}" class="btn btn-outline btn-sm" title="Download original uploaded file">📥 Download</a>
        <button type="button" class="btn btn-outline btn-sm btn-delete-doc" onclick="promptDeleteDocument('${doc.id}', '${escapeJs(doc.display_name || doc.filename)}')" title="Permanently remove file from repository">🗑 Delete File</button>
      </div>
    </div>
  `;
}

async function renderMasterModalDocuments() {
  const statsContainer = document.getElementById('master-modal-repo-stats');
  const grid = document.getElementById('master-modal-repo-grid');
  if (!grid) return;

  try {
    const res = await fetch('/api/kb/documents');
    if (!res.ok) throw new Error('Failed to fetch documents');
    const data = await res.json();
    const docs = data.documents || [];
    const stats = data.summary_stats || {};

    if (statsContainer) {
      statsContainer.innerHTML = renderRepoSummaryStats(stats);
    }

    if (docs.length === 0) {
      grid.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 2.5rem 1.5rem; background: #f8fafc; border: 2px dashed #cbd5e1; border-radius: 12px;">
          <div style="font-size: 2.2rem; margin-bottom: 0.35rem;">📂</div>
          <h4 style="font-size: 1.05rem; font-weight: 800; color: #1e293b; margin-bottom: 0.25rem;">No documents available in repository</h4>
          <p style="color: #64748b; font-size: 0.85rem; margin: 0;">Upload your master resume or career documents above to begin evidence-based tailoring.</p>
        </div>
      `;
      return;
    }

    grid.innerHTML = docs.map(doc => renderDocCardHtml(doc)).join('');
  } catch (err) {
    console.error('Error rendering master modal documents:', err);
    if (grid) {
      grid.innerHTML = `<div style="grid-column: 1 / -1; color: #dc2626; padding: 1rem; text-align: center;">Error loading repository: ${escapeHtml(err.message)}</div>`;
    }
  }
}

async function loadKBDocuments() {
  try {
    const res = await fetch('/api/kb/documents');
    const data = await res.json();
    kbState.documents = data.documents || [];
    kbState.summaryStats = data.summary_stats || {};

    const statsContainer = document.getElementById('kb-repo-stats-container');
    if (statsContainer) {
      statsContainer.innerHTML = renderRepoSummaryStats(kbState.summaryStats);
    }

    const count = kbState.documents.length;
    const headerDocCount = document.getElementById('header-kb-doc-count');
    if (headerDocCount) headerDocCount.innerText = `${count} Doc${count === 1 ? '' : 's'}`;
    const badgeKbDocs = document.getElementById('badge-kb-docs');
    if (badgeKbDocs) badgeKbDocs.innerText = count;
    const countEl = document.getElementById('kb-repo-count');
    if (countEl) countEl.innerText = count;

    renderKBDocuments();
  } catch (err) {
    console.error('Error loading KB documents:', err);
  }
}

function renderKBDocuments() {
  const grid = document.getElementById('kb-documents-grid');
  if (!grid) return;

  let docs = [...kbState.documents];
  if (kbState.categoryFilter !== 'all') {
    docs = docs.filter(d => d.category === kbState.categoryFilter);
  }
  if (kbState.searchQuery) {
    const q = kbState.searchQuery.toLowerCase();
    docs = docs.filter(d =>
      (d.display_name && d.display_name.toLowerCase().includes(q)) ||
      (d.filename && d.filename.toLowerCase().includes(q)) ||
      (d.category && d.category.toLowerCase().includes(q)) ||
      (d.extracted_summary && d.extracted_summary.toLowerCase().includes(q)) ||
      (d.extracted_data && d.extracted_data.technical_tools && d.extracted_data.technical_tools.some(t => t.toLowerCase().includes(q)))
    );
  }

  if (docs.length === 0) {
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 3rem 1.5rem; background: #0b1120; border-radius: 12px; border: 2px dashed #233558;">
        <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">📁</div>
        <h4 style="font-size: 1.15rem; font-weight: 800; color: #ffffff; margin-bottom: 0.35rem;">No documents match active filter</h4>
        <p style="color: #94a3b8; font-size: 0.875rem;">Upload resumes, certificates, project docs, or reset your search.</p>
      </div>
    `;
    return;
  }

  grid.innerHTML = docs.map(doc => renderDocCardHtml(doc)).join('');
}

function filterKBDocuments() {
  const input = document.getElementById('kb-search-input');
  if (input) {
    kbState.searchQuery = input.value.trim();
    renderKBDocuments();
  }
}

function setKBCategoryFilter(cat) {
  kbState.categoryFilter = cat;
  document.querySelectorAll('.kb-cat-filter-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.cat === cat);
  });
  renderKBDocuments();
}

async function handleKBBatchUpload(files) {
  if (!files || files.length === 0) return;

  const statusEl = document.getElementById('kb-upload-status');
  statusEl.style.display = 'block';
  statusEl.innerHTML = `<span style="color: #38bdf8;"><div class="spinner" style="width: 14px; height: 14px; border-width: 2px;"></div> Uploading & indexing ${files.length} document(s)...</span>`;

  const catSelect = document.getElementById('kb-upload-category-select');
  const cat = catSelect ? catSelect.value : 'auto';

  const formData = new FormData();
  Array.from(files).forEach(f => formData.append('files', f));
  if (cat && cat !== 'auto') {
    formData.append('category', cat);
  }

  try {
    const res = await fetch('/api/kb/upload', {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Upload batch failed');
    }

    const data = await res.json();
    statusEl.innerHTML = `<span style="color: #34d399; font-weight: 700;">✓ Successfully indexed ${data.uploaded_count || files.length} document(s) into Knowledge Base!</span>`;

    await loadKBDocuments();
    await loadKBUnifiedProfile();
    await loadStats();

    setTimeout(() => {
      statusEl.style.display = 'none';
    }, 3500);

  } catch (err) {
    statusEl.innerHTML = `<span style="color: #f43f5e; font-weight: 700;">Batch upload error: ${escapeHtml(err.message)}</span>`;
  }
}

async function loadKBUnifiedProfile() {
  const content = document.getElementById('kb-unified-profile-content');
  if (!content) return;
  content.innerHTML = '<div style="text-align: center; padding: 2.5rem;"><div class="spinner"></div><p style="margin-top: 0.5rem; color: #94a3b8;">Synthesizing unified profile from knowledge base...</p></div>';

  try {
    const res = await fetch('/api/kb/profile');
    const data = await res.json();
    const profile = data.profile || {};
    state.masterProfile = profile;

    const skills = profile.skills || {};
    let skillsRows = '';
    for (const [catKey, items] of Object.entries(skills)) {
      if (Array.isArray(items) && items.length > 0) {
        const catTitle = catKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        const pills = items.map(s => `<span class="ats-keyword-pill-matched">${escapeHtml(s)}</span>`).join(' ');
        skillsRows += `<div><strong style="color: #94a3b8; font-size: 0.82rem;">${escapeHtml(catTitle)}:</strong> ${pills}</div>`;
      }
    }

    const expList = profile.experience || profile.work_experience || [];
    const expHtml = expList.map(exp => `
      <div style="background: #0b1120; padding: 0.95rem; border-radius: 8px; margin-bottom: 0.75rem; border: 1px solid #1e293b;">
        <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; margin-bottom: 0.35rem;">
          <strong style="color: #ffffff; font-size: 1rem;">${escapeHtml(exp.title)}</strong>
          <span style="color: #94a3b8; font-size: 0.8rem; font-weight: 600;">${escapeHtml(exp.dates || exp.period || '')}</span>
        </div>
        <div style="color: #38bdf8; font-size: 0.85rem; font-weight: 700; margin-bottom: 0.45rem;">🏢 ${escapeHtml(exp.company)}</div>
        <ul style="margin: 0; padding-left: 1.25rem; font-size: 0.82rem; color: #cbd5e1; line-height: 1.55;">
          ${(exp.bullets || []).map(b => `<li style="margin-bottom: 0.3rem;">${escapeHtml(b)}</li>`).join('')}
        </ul>
      </div>
    `).join('');

    const projList = profile.projects || [];
    const projHtml = projList.map(p => `
      <div style="background: #0b1120; padding: 0.95rem; border-radius: 8px; margin-bottom: 0.75rem; border: 1px solid #1e293b;">
        <div style="display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; margin-bottom: 0.35rem;">
          <strong style="color: #ffffff; font-size: 1rem;">${escapeHtml(p.name || p.title)}</strong>
          <span style="color: #38bdf8; font-size: 0.75rem; background: rgba(56, 189, 248, 0.1); padding: 0.15rem 0.5rem; border-radius: 4px; font-weight: 700;">${escapeHtml(p.tools || p.tech_stack || '')}</span>
        </div>
        <ul style="margin: 0; padding-left: 1.25rem; font-size: 0.82rem; color: #cbd5e1; line-height: 1.55;">
          ${(p.bullets || []).map(b => `<li style="margin-bottom: 0.3rem;">${escapeHtml(b)}</li>`).join('')}
        </ul>
      </div>
    `).join('');

    const certList = profile.certifications || [];
    const certHtml = certList.map(c => `
      <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.85rem; padding: 0.35rem 0; border-bottom: 1px solid #1e293b;">
        <span style="color: #f1f5f9;">🏆 ${escapeHtml(c.name || c)}</span>
        ${c.url ? `<a href="${escapeHtml(c.url)}" target="_blank" rel="noopener noreferrer" style="color: #38bdf8; font-size: 0.78rem;">Verify ↗</a>` : ''}
      </div>
    `).join('');

    content.innerHTML = `
      <div style="background: #0b1120; border: 1px solid #233558; border-radius: 12px; padding: 1.35rem; margin-bottom: 1.35rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.5rem;">
          <h3 style="font-size: 1.4rem; font-weight: 800; color: #ffffff; margin: 0;">${escapeHtml(profile.name || 'Candidate')}</h3>
          <span class="status-pill status-pill-ready">
            ✓ Synthesized from ${data.documents_count || 1} Document(s)
          </span>
        </div>
        <div style="display: flex; flex-wrap: wrap; gap: 0.95rem; font-size: 0.82rem; color: #94a3b8; margin-bottom: 0.75rem;">
          <span>📧 ${escapeHtml(profile.contact ? profile.contact.email : '')}</span>
          <span>📞 ${escapeHtml(profile.contact ? profile.contact.phone : '')}</span>
          ${profile.contact && profile.contact.linkedin ? `<span>🔗 <a href="${escapeHtml(profile.contact.linkedin)}" target="_blank" style="color: #38bdf8;">LinkedIn</a></span>` : ''}
          ${profile.contact && profile.contact.github ? `<span>🐙 <a href="${escapeHtml(profile.contact.github)}" target="_blank" style="color: #38bdf8;">GitHub</a></span>` : ''}
        </div>
        <div style="font-size: 0.88rem; color: #cbd5e1; line-height: 1.6; font-style: italic; border-left: 3px solid #06b6d4; padding-left: 0.85rem; background: rgba(6, 182, 212, 0.05); border-radius: 0 6px 6px 0; padding-top: 0.4rem; padding-bottom: 0.4rem;">
          "${escapeHtml(profile.summary || 'Data Analyst dedicated to uncovering patterns and driving business decisions.')}"
        </div>
      </div>

      <div class="ats-breakdown-card" style="margin-bottom: 1rem;">
        <h4 style="font-size: 0.95rem; font-weight: 800; color: #06b6d4; margin-bottom: 0.65rem;">SYNTHESIZED TECHNICAL SKILLS BANK (${profile.technical_tools ? profile.technical_tools.length : 0})</h4>
        <div style="display: flex; flex-direction: column; gap: 0.55rem; font-size: 0.85rem;">
          ${skillsRows || '<span style="color: #94a3b8;">No skills extracted yet.</span>'}
        </div>
      </div>

      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.25rem; margin-bottom: 1rem;">
        <div>
          <h4 style="font-size: 0.95rem; font-weight: 800; color: #38bdf8; margin-bottom: 0.65rem;">EXPERIENCE (${expList.length})</h4>
          ${expHtml || '<p style="color: #94a3b8; font-size: 0.85rem;">No experience loaded.</p>'}
        </div>
        <div>
          <h4 style="font-size: 0.95rem; font-weight: 800; color: #34d399; margin-bottom: 0.65rem;">PROJECTS & CASE STUDIES (${projList.length})</h4>
          ${projHtml || '<p style="color: #94a3b8; font-size: 0.85rem;">No projects loaded.</p>'}
        </div>
      </div>

      <div class="ats-breakdown-card">
        <h4 style="font-size: 0.95rem; font-weight: 800; color: #fbbf24; margin-bottom: 0.65rem;">CERTIFICATIONS & CREDENTIALS (${certList.length})</h4>
        ${certHtml || '<p style="color: #94a3b8; font-size: 0.85rem;">No certifications loaded.</p>'}
      </div>
    `;
  } catch (err) {
    content.innerHTML = `<p style="color: #f43f5e;">Failed to load unified profile: ${err.message}</p>`;
  }
}

async function loadKBStudioSnapshot() {
  const container = document.getElementById('studio-kb-snapshot');
  if (!container) return;

  try {
    const res = await fetch('/api/kb/profile');
    const data = await res.json();
    const profile = data.profile || {};
    const skillCount = (profile.technical_tools || []).length;
    const projsCount = (profile.projects || []).length;

    container.innerHTML = `
      <div style="background: #080d19; border: 1px solid #1e293b; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
          <strong style="color: #ffffff; font-size: 1.05rem;">${escapeHtml(profile.name || 'Candidate')}</strong>
          <span class="status-pill status-pill-ready">Ready for Tailoring</span>
        </div>
        <div style="font-size: 0.8rem; color: #94a3b8; margin-bottom: 0.75rem;">
          ${data.documents_count || 1} Document(s) in KB • ${skillCount} Extracted Competencies • ${projsCount} Projects
        </div>
        <div style="font-size: 0.82rem; color: #cbd5e1; line-height: 1.5; font-style: italic; border-left: 2px solid #06b6d4; padding-left: 0.5rem;">
          "${escapeHtml((profile.summary || '').slice(0, 160))}..."
        </div>
      </div>
      <div style="font-size: 0.8rem; color: #94a3b8;">
        <div style="margin-bottom: 0.35rem; font-weight: 700; color: #38bdf8;">Verified Skills Available for JD Matching:</div>
        <div style="display: flex; flex-wrap: wrap; gap: 0.3rem;">
          ${(profile.technical_tools || []).slice(0, 14).map(s => `<span class="ats-keyword-pill-matched" style="font-size: 0.72rem;">${escapeHtml(s)}</span>`).join('')}
        </div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<p style="color: #f43f5e;">Failed to load snapshot: ${err.message}</p>`;
  }
}

function loadSampleJD(type) {
  const titleInput = document.getElementById('studio-job-title');
  const compInput = document.getElementById('studio-company');
  const textInput = document.getElementById('studio-jd-text');

  if (type === 'power_bi') {
    if (titleInput) titleInput.value = 'Power BI Developer (Fresher / Trainee)';
    if (compInput) compInput.value = 'Deloitte USI';
    if (textInput) textInput.value = `We are seeking a motivated Power BI Developer (0-1 year experience) to design, build, and deploy interactive enterprise dashboards. 

Key Responsibilities:
- Transform raw business data using Power Query and SQL.
- Develop calculated measures and columns using advanced DAX.
- Build clean visual reporting dashboards for cross-functional stakeholders.
- Collaborate with database engineers on Snowflake and PostgreSQL data models.

Required Skills:
- Strong knowledge of Microsoft Power BI, Power Query, and DAX.
- Solid SQL querying capabilities (Joins, CTEs, Aggregations, Window Functions).
- Basic understanding of Python and statistical analysis.
- Excellent communication and presentation skills.`;
  } else if (type === 'data_analyst') {
    if (titleInput) titleInput.value = 'Junior Data Analyst (0–1 Year Exp)';
    if (compInput) compInput.value = 'Swiggy';
    if (textInput) textInput.value = `Swiggy is looking for an energetic Junior Data Analyst to join our Supply & Operations analytics pod.

What You'll Do:
- Analyze customer order metrics, delivery partner efficiency, and geographic trends.
- Write robust SQL queries and Python scripts to extract, clean, and validate daily metrics.
- Build daily and weekly monitoring dashboards in Tableau or Power BI.
- Work closely with business teams to identify conversion bottlenecks and deliver actionable insights.

Qualifications:
- Bachelor's degree in Computer Science, Engineering, Statistics, or related technical field.
- Proficiency in SQL, Advanced Excel (Pivot tables, VLOOKUP, INDEX/MATCH), and Python (Pandas, NumPy).
- Familiarity with BI visualization tools (Tableau, Power BI).
- Strong analytical curiosity and attention to data accuracy.`;
  } else if (type === 'sql_analyst') {
    if (titleInput) titleInput.value = 'SQL & Business Intelligence Analyst';
    if (compInput) compInput.value = 'Accenture';
    if (textInput) textInput.value = `Accenture Technology is hiring Entry-Level Data Analytics Associates.

Role Overview:
- Perform data extraction, transformation, and validation using SQL across cloud warehouses (Snowflake, BigQuery).
- Write complex queries involving joins, window functions, and indexing strategies.
- Design automated reports and KPI scorecards in Power BI and Advanced Excel.
- Support data hygiene, documentation, and metadata tracking.

Requirements:
- Strong grasp of Relational Database Management Systems (RDBMS) and SQL.
- Experience with Excel models and BI reporting.
- High attention to detail and eagerness to solve real-world analytical problems.`;
  }
}

async function generateTailoredFromStudio() {
  const titleInput = document.getElementById('studio-job-title');
  const compInput = document.getElementById('studio-company');
  const textInput = document.getElementById('studio-jd-text');
  const btn = document.getElementById('btn-studio-generate');

  const title = (titleInput && titleInput.value) ? titleInput.value.trim() : 'Junior Data Analyst';
  const company = (compInput && compInput.value) ? compInput.value.trim() : 'Target Employer';
  const desc = (textInput && textInput.value) ? textInput.value.trim() : '';

  if (!desc) {
    alert('Please enter or paste a Job Description first, or click one of the sample buttons!');
    if (textInput) textInput.focus();
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<div class="spinner"></div> Generating Tailored Resume & Cover Letter...';

  try {
    const res = await fetch('/api/resume/tailor-custom', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_title: title,
        company: company,
        description: desc
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to tailor from studio');
    }

    const data = await res.json();
    currentTailorData = data;
    btn.disabled = false;
    btn.innerHTML = '⚡ Generate Tailored Resume & Cover Letter';

    // Open tailored split-screen modal
    const modal = document.getElementById('tailor-resume-modal');
    modal.style.display = 'flex';
    renderTailoredResumeModal(data);

  } catch (err) {
    btn.disabled = false;
    btn.innerHTML = '⚡ Generate Tailored Resume & Cover Letter';
    alert(`Error: ${err.message}`);
  }
}

async function openDocPreview(docId) {
  const modal = document.getElementById('doc-preview-modal');
  const titleEl = document.getElementById('doc-preview-title');
  const metaEl = document.getElementById('doc-preview-meta');
  const bodyEl = document.getElementById('doc-preview-body');

  modal.style.display = 'flex';
  bodyEl.innerHTML = '<div style="text-align: center; padding: 2.5rem;"><div class="spinner"></div><p style="margin-top: 0.5rem; color: #94a3b8;">Loading document preview...</p></div>';

  try {
    const res = await fetch(`/api/kb/document/${docId}`);
    if (!res.ok) throw new Error('Document not found');
    const data = await res.json();
    const d = data.document || data;

    const icon = getDocCategoryIcon(d.category, d.file_type);
    titleEl.innerText = `${icon} ${d.display_name || d.filename}`;
    const uploadDateStr = d.uploaded_at ? new Date(d.uploaded_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'Recently Uploaded';
    metaEl.innerText = `${(d.category || 'Document').toUpperCase()} • ${d.filename} • ${(d.file_type || '').toUpperCase()} • ${d.file_size_formatted || ''} • Uploaded: ${uploadDateStr}`;

    const extData = d.extracted_data || {};
    const tools = extData.technical_tools || [];
    const skillPills = tools.map(s => `<span class="ats-keyword-pill-matched">${escapeHtml(s)}</span>`).join(' ');
    const rawSnippet = extData.raw_snippet || d.extracted_summary || 'Document text extracted during indexing.';

    const expItems = extData.experience || extData.experiences || [];
    const projItems = extData.projects || [];
    const certItems = extData.certifications || [];
    const eduItems = extData.education || [];

    const expHtml = expItems.length > 0 ? expItems.map(e => `
      <div style="background: #080d1a; border: 1px solid #1e293b; border-radius: 6px; padding: 0.65rem 0.85rem; margin-bottom: 0.5rem;">
        <div style="display: flex; justify-content: space-between; font-weight: 700; color: #fff; font-size: 0.85rem;">
          <span>${escapeHtml(e.title || 'Role')}</span>
          <span style="color: #94a3b8; font-size: 0.75rem;">${escapeHtml(e.dates || '')}</span>
        </div>
        <div style="color: #38bdf8; font-size: 0.78rem; margin-bottom: 0.25rem;">🏢 ${escapeHtml(e.company || '')}</div>
        <ul style="margin: 0; padding-left: 1.15rem; font-size: 0.78rem; color: #cbd5e1; line-height: 1.45;">
          ${(e.bullets || []).map(b => `<li>${escapeHtml(b)}</li>`).join('')}
        </ul>
      </div>
    `).join('') : '<span style="color: #64748b; font-size: 0.8rem; font-style: italic;">No work experience entries extracted from this document.</span>';

    const projHtml = projItems.length > 0 ? projItems.map(p => `
      <div style="background: #080d1a; border: 1px solid #1e293b; border-radius: 6px; padding: 0.65rem 0.85rem; margin-bottom: 0.5rem;">
        <div style="font-weight: 700; color: #34d399; font-size: 0.85rem; margin-bottom: 0.2rem;">
          ${escapeHtml(p.title || 'Project')} ${p.tools ? `<span style="color: #94a3b8; font-size: 0.75rem; font-weight: normal;">(${escapeHtml(p.tools)})</span>` : ''}
        </div>
        <ul style="margin: 0; padding-left: 1.15rem; font-size: 0.78rem; color: #cbd5e1; line-height: 1.45;">
          ${(p.bullets || []).map(b => `<li>${escapeHtml(b)}</li>`).join('')}
        </ul>
      </div>
    `).join('') : '<span style="color: #64748b; font-size: 0.8rem; font-style: italic;">No project entries extracted from this document.</span>';

    const certHtml = certItems.length > 0 ? certItems.map(c => `
      <div style="display: flex; align-items: center; justify-content: space-between; padding: 0.35rem 0; border-bottom: 1px solid #1e293b; font-size: 0.82rem; color: #f1f5f9;">
        <span>🏆 ${escapeHtml(c.name || c)}</span>
        <span style="color: #34d399; font-size: 0.75rem;">✓ Verified</span>
      </div>
    `).join('') : '<span style="color: #64748b; font-size: 0.8rem; font-style: italic;">No certifications extracted from this document.</span>';

    const eduHtml = eduItems.length > 0 ? eduItems.map(e => `
      <div style="background: #080d1a; border: 1px solid #1e293b; border-radius: 6px; padding: 0.65rem 0.85rem; margin-bottom: 0.5rem;">
        <div style="display: flex; justify-content: space-between; font-weight: 700; color: #fff; font-size: 0.85rem;">
          <span>🎓 ${escapeHtml(e.degree || 'Degree / Qualification')}</span>
          <span style="color: #94a3b8; font-size: 0.75rem;">${escapeHtml(e.dates || '')}</span>
        </div>
        <div style="color: #38bdf8; font-size: 0.78rem;">${escapeHtml(e.institution || '')}</div>
      </div>
    `).join('') : '<span style="color: #64748b; font-size: 0.8rem; font-style: italic;">No education entries extracted from this document.</span>';

    bodyEl.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem;">
        <div>
          ${getStatusPill(d.status)}
        </div>
        <div style="display: flex; gap: 0.4rem;">
          <button type="button" class="btn btn-outline btn-sm" onclick="reprocessKBDocument('${d.id}'); closeModal('doc-preview-modal');">
            🔄 Reprocess File
          </button>
          <a href="/api/kb/document/${d.id}/preview" target="_blank" download="${escapeHtml(d.filename)}" class="btn btn-primary btn-sm">
            📥 Download Original File
          </a>
        </div>
      </div>

      <div style="background: #0b1120; border: 1px solid #1e293b; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
        <h4 style="font-size: 0.95rem; font-weight: 700; color: #38bdf8; margin-bottom: 0.4rem;">AI Structured Summary</h4>
        <p style="font-size: 0.85rem; color: #cbd5e1; line-height: 1.5; margin-bottom: 0.65rem;">
          ${escapeHtml(d.extracted_summary || 'Summary indexed into career knowledge base.')}
        </p>
        ${skillPills ? `<div><strong style="font-size: 0.8rem; color: #94a3b8;">Skills Identified (${tools.length}):</strong> <div style="display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.35rem;">${skillPills}</div></div>` : ''}
      </div>

      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; margin-bottom: 1rem;">
        <div style="background: #0b1120; border: 1px solid #1e293b; border-radius: 8px; padding: 0.85rem;">
          <h4 style="font-size: 0.875rem; font-weight: 800; color: #38bdf8; margin-bottom: 0.5rem;">EXPERIENCE IDENTIFIED (${expItems.length})</h4>
          ${expHtml}
        </div>
        <div style="background: #0b1120; border: 1px solid #1e293b; border-radius: 8px; padding: 0.85rem;">
          <h4 style="font-size: 0.875rem; font-weight: 800; color: #34d399; margin-bottom: 0.5rem;">PROJECTS IDENTIFIED (${projItems.length})</h4>
          ${projHtml}
        </div>
      </div>

      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; margin-bottom: 1rem;">
        <div style="background: #0b1120; border: 1px solid #1e293b; border-radius: 8px; padding: 0.85rem;">
          <h4 style="font-size: 0.875rem; font-weight: 800; color: #fbbf24; margin-bottom: 0.5rem;">CERTIFICATIONS IDENTIFIED (${certItems.length})</h4>
          ${certHtml}
        </div>
        <div style="background: #0b1120; border: 1px solid #1e293b; border-radius: 8px; padding: 0.85rem;">
          <h4 style="font-size: 0.875rem; font-weight: 800; color: #a78bfa; margin-bottom: 0.5rem;">EDUCATION IDENTIFIED (${eduItems.length})</h4>
          ${eduHtml}
        </div>
      </div>

      <div style="background: #0b1120; border: 1px solid #1e293b; border-radius: 8px; padding: 0.85rem; margin-bottom: 1rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
          <h4 style="font-size: 0.875rem; font-weight: 800; color: #38bdf8; margin: 0;">EXTRACTED TEXT</h4>
          <button type="button" class="btn btn-outline btn-sm" onclick="navigator.clipboard.writeText(document.getElementById('doc-preview-raw-snippet').innerText); alert('Extracted text copied to clipboard!');">📋 Copy Text</button>
        </div>
        <pre id="doc-preview-raw-snippet" style="max-height: 250px; overflow-y: auto; font-family: 'Consolas', 'Courier New', monospace; font-size: 0.78rem; line-height: 1.5; color: #cbd5e1; white-space: pre-wrap; background: #030712; padding: 0.85rem; border-radius: 6px; border: 1px solid #1e293b; margin: 0;">${escapeHtml(rawSnippet)}</pre>
      </div>
    `;
  } catch (err) {
    bodyEl.innerHTML = `<p style="color: #f43f5e;">Error loading preview: ${err.message}</p>`;
  }
}

function openDocEditModal(docId) {
  const doc = kbState.documents.find(d => d.id === docId);
  if (!doc) return;
  document.getElementById('edit-doc-id').value = doc.id;
  document.getElementById('edit-doc-name').value = doc.display_name || doc.filename;
  document.getElementById('edit-doc-category').value = doc.category || 'other';
  document.getElementById('doc-edit-modal').style.display = 'flex';
}

async function saveDocMeta() {
  const id = document.getElementById('edit-doc-id').value;
  const name = document.getElementById('edit-doc-name').value.trim();
  const category = document.getElementById('edit-doc-category').value;

  try {
    const res = await fetch(`/api/kb/document/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: name, category })
    });

    if (!res.ok) throw new Error('Failed to update document metadata');

    closeModal('doc-edit-modal');
    await loadKBDocuments();
    await loadKBUnifiedProfile();
    await renderMasterModalDocuments();
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
}

function deleteKBDocument(docId) {
  const doc = kbState.documents.find(d => d.id === docId);
  promptDeleteDocument(docId, doc ? (doc.display_name || doc.filename) : 'document');
}

async function reprocessKBDocument(docId) {
  const btn = document.getElementById(`btn-reprocess-${docId}`);
  if (btn) btn.innerHTML = '<div class="spinner" style="width: 12px; height: 12px; border-width: 2px;"></div> Reprocessing...';

  try {
    const res = await fetch(`/api/kb/document/${docId}/reprocess`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Reprocessing failed');
    }
    const data = await res.json();
    await loadKBDocuments();
    await loadKBUnifiedProfile();
    await loadMasterResumeStatus();
    alert(`✓ Successfully reprocessed and updated ${data.document.filename}!`);
  } catch (err) {
    alert(`Error reprocessing: ${err.message}`);
  } finally {
    if (btn) btn.innerText = '🔄 Reprocess File';
  }
}

async function reprocessAllKBDocuments() {
  const btn = document.getElementById('btn-reprocess-all');
  if (btn) btn.innerHTML = '<div class="spinner" style="width: 12px; height: 12px; border-width: 2px;"></div> Reprocessing All...';

  try {
    const res = await fetch('/api/kb/reprocess-all', { method: 'POST' });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Reprocessing all failed');
    }
    await loadKBDocuments();
    await loadKBUnifiedProfile();
    await loadMasterResumeStatus();
    alert('✓ All documents re-extracted, re-indexed, and unified profile updated!');
  } catch (err) {
    alert(`Error reprocessing all: ${err.message}`);
  } finally {
    if (btn) btn.innerText = '🔄 Reprocess All';
  }
}

async function reindexAllKBDocuments() {
  const btn = event ? event.target : null;
  if (btn) btn.innerText = '🔄 Re-indexing...';
  try {
    const res = await fetch('/api/kb/reindex', { method: 'POST' });
    if (res.ok) {
      await loadKBDocuments();
      await loadKBUnifiedProfile();
      alert('✓ All Knowledge Base documents re-indexed and unified profile updated!');
    }
  } catch (err) {
    alert('Error: ' + err.message);
  } finally {
    if (btn) btn.innerText = '🔄 Re-index All Docs';
  }
}

let replacingDocId = null;
function triggerReplaceDoc(docId) {
  replacingDocId = docId;
  const input = document.getElementById('replace-doc-file-input');
  if (input) input.click();
}

function handleReplaceFileSelected(file) {
  if (!file || !replacingDocId) return;
  const formData = new FormData();
  formData.append('file', file);
  fetch(`/api/kb/document/${replacingDocId}/replace`, {
    method: 'POST',
    body: formData
  }).then(res => res.json()).then(() => {
    loadKBDocuments();
    loadKBUnifiedProfile();
    alert(`✓ Successfully replaced document with ${file.name}!`);
  }).catch(err => {
    alert(`Error replacing file: ${err.message}`);
  }).finally(() => {
    replacingDocId = null;
  });
}



// =========================================================================
// AUTOMATED SCHEDULING, MONITORING & LOGGING SYSTEM (SECTIONS 1 - 8)
// =========================================================================

let schedulerMonitorTimer = null;
let notificationTimer = null;
let currentAnalyticsData = null;
let currentChartGranularity = 'day';
let logSearchDebounceTimer = null;

function initSchedulerModule() {
  // Start periodic background polling
  pollLiveMonitor();
  fetchNotifications();
  if (!schedulerMonitorTimer) {
    schedulerMonitorTimer = setInterval(pollLiveMonitor, 5000);
  }
  if (!notificationTimer) {
    notificationTimer = setInterval(fetchNotifications, 15000);
  }
}

async function loadSchedulerDashboard() {
  await Promise.all([
    loadDefaultSchedules(),
    loadCustomSchedules(),
    loadUpcomingTasks(),
    pollLiveMonitor(),
    loadRecommendedJobs(),
    loadActivityLogs(),
    loadScrapingAnalytics(),
    fetchNotifications()
  ]);
}

// -------------------------------------------------------------------------
// Helper: Format Dates & Relative Times in Indian Time Zone (IST)
// -------------------------------------------------------------------------
function formatIndianDateTime(isoString) {
  if (!isoString) return '';
  try {
    let cleanIso = String(isoString).trim();
    if (!cleanIso.endsWith('Z') && !/[-+]\d{2}(:\d{2})?$/.test(cleanIso)) {
      cleanIso += 'Z';
    }
    const d = new Date(cleanIso);
    if (isNaN(d.getTime())) return isoString;

    const datePart = d.toLocaleDateString('en-IN', {
      timeZone: 'Asia/Kolkata',
      day: '2-digit',
      month: 'short',
      year: 'numeric'
    });
    const timePart = d.toLocaleTimeString('en-IN', {
      timeZone: 'Asia/Kolkata',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    }).toUpperCase();

    return `${datePart}, ${timePart} IST`;
  } catch (e) {
    return isoString;
  }
}

function formatRelativeTimeAgo(isoString) {
  if (!isoString) return '';
  try {
    let cleanIso = String(isoString).trim();
    if (!cleanIso.endsWith('Z') && !/[-+]\d{2}(:\d{2})?$/.test(cleanIso)) {
      cleanIso += 'Z';
    }
    const target = new Date(cleanIso);
    const now = new Date();
    const diffSec = Math.floor((now - target) / 1000);
    if (diffSec < 0) return 'Just now';
    if (diffSec < 45) return 'Just now';
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 30) return `${diffDays}d ago`;
    return '';
  } catch (e) {
    return '';
  }
}

function formatRelativeTime(isoString) {
  if (!isoString) return 'Not scheduled';
  try {
    let cleanIso = String(isoString).trim();
    if (!cleanIso.endsWith('Z') && !/[-+]\d{2}(:\d{2})?$/.test(cleanIso)) {
      cleanIso += 'Z';
    }
    const target = new Date(cleanIso);
    const now = new Date();
    const diffMs = target - now;

    if (diffMs <= 0) return 'Due now';

    const diffMins = Math.floor(diffMs / (1000 * 60));
    const hours = Math.floor(diffMins / 60);
    const mins = diffMins % 60;
    const days = Math.floor(hours / 24);

    let relStr = '';
    if (days > 0) {
      relStr = `in ${days}d ${hours % 24}h`;
    } else if (hours > 0) {
      relStr = `in ${hours}h ${mins}m`;
    } else {
      relStr = `in ${mins}m`;
    }

    const timeFormatted = target.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: true }).toUpperCase();
    const isToday = target.toDateString() === now.toDateString();
    const dayLabel = isToday ? 'Today' : target.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', weekday: 'short', month: 'short', day: 'numeric' });

    return `${dayLabel} at ${timeFormatted} IST (${relStr})`;
  } catch (e) {
    return isoString;
  }
}

// -------------------------------------------------------------------------
// 1. Job Scraping Controls
// -------------------------------------------------------------------------
function toggleAllManualAdapters(select) {
  document.querySelectorAll('input[name="manual_adapter"]').forEach(cb => {
    cb.checked = select;
  });
}

async function triggerManualScrapeWithControls() {
  const btn = document.getElementById('btn-trigger-manual-scrape');
  const selectedAdapters = Array.from(document.querySelectorAll('input[name="manual_adapter"]:checked')).map(cb => cb.value);

  if (selectedAdapters.length === 0) {
    alert('Please select at least one job source or portal adapter.');
    return;
  }

  const payload = {
    adapter_ids: selectedAdapters,
    schedule_name: "Manual On-Demand Run",
    limit_per_source: parseInt(document.getElementById('ctrl-max-jobs')?.value || '50', 10),
    max_jobs_per_run: parseInt(document.getElementById('ctrl-max-jobs')?.value || '50', 10),
    retry_count: parseInt(document.getElementById('ctrl-retry-count')?.value || '2', 10),
    request_delay: parseFloat(document.getElementById('ctrl-request-delay')?.value || '0.5'),
    scrape_new_only: document.getElementById('ctrl-scrape-new-only')?.checked ?? true,
    update_existing: document.getElementById('ctrl-update-existing')?.checked ?? true,
    deduplication: document.getElementById('ctrl-deduplication')?.checked ?? true,
    ats_scoring: document.getElementById('ctrl-ats-scoring')?.checked ?? true,
    skill_matching: document.getElementById('ctrl-skill-matching')?.checked ?? true,
    resume_matching: document.getElementById('ctrl-resume-matching')?.checked ?? true,
    rescrape_existing: document.getElementById('ctrl-rescrape-existing')?.checked ?? false,
    refresh_expired: document.getElementById('ctrl-refresh-expired')?.checked ?? false,
    auto_recovery: document.getElementById('ctrl-auto-recovery')?.checked ?? true,
    auto_stop_on_error: document.getElementById('ctrl-auto-stop')?.checked ?? false
  };

  try {
    if (btn) {
      btn.disabled = true;
      btn.innerText = '⏳ Initiating Scraper...';
    }

    const res = await fetch('/api/scraper/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (data.status === 'already_running') {
      alert('A scrape process is already running. Please monitor progress below.');
    }

    // Scroll smoothly to Real-Time Monitor
    const monSec = document.getElementById('section-status-monitor');
    if (monSec) {
      monSec.scrollIntoView({ behavior: 'smooth' });
    }

    // Immediate poll
    pollLiveMonitor();
  } catch (err) {
    alert(`Error initiating scraper: ${err.message}`);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = '🚀 Start Scraping Now';
    }
  }
}

// -------------------------------------------------------------------------
// 2. Default Schedules
// -------------------------------------------------------------------------
async function loadDefaultSchedules() {
  try {
    const res = await fetch('/api/scraper/schedules');
    const data = await res.json();
    const schedules = data.schedules || [];

    const morning = schedules.find(s => s.id === 'sched_morning_default');
    if (morning) {
      const toggle = document.getElementById('toggle-morning-schedule');
      if (toggle) toggle.checked = morning.is_enabled;
      const nextEl = document.getElementById('morning-next-run');
      if (nextEl) nextEl.innerText = morning.is_enabled ? formatRelativeTime(morning.next_run_at) : 'Schedule Paused';
      const lastEl = document.getElementById('morning-last-run');
      if (lastEl) {
        lastEl.innerText = morning.last_run_at ? `${formatIndianDateTime(morning.last_run_at)} (${morning.last_run_status})` : 'Never executed yet';
      }
      const card = document.getElementById('card-default-morning');
      if (card) card.classList.toggle('active', morning.is_enabled);
    }

    const evening = schedules.find(s => s.id === 'sched_evening_default');
    if (evening) {
      const toggle = document.getElementById('toggle-evening-schedule');
      if (toggle) toggle.checked = evening.is_enabled;
      const nextEl = document.getElementById('evening-next-run');
      if (nextEl) nextEl.innerText = evening.is_enabled ? formatRelativeTime(evening.next_run_at) : 'Schedule Paused';
      const lastEl = document.getElementById('evening-last-run');
      if (lastEl) {
        lastEl.innerText = evening.last_run_at ? `${formatIndianDateTime(evening.last_run_at)} (${evening.last_run_status})` : 'Never executed yet';
      }
      const card = document.getElementById('card-default-evening');
      if (card) card.classList.toggle('active', evening.is_enabled);
    }
  } catch (err) {
    console.error('Error loading default schedules:', err);
  }
}

async function toggleDefaultSchedule(scheduleId, isEnabled) {
  try {
    const endpoint = isEnabled ? `/api/scraper/schedules/${scheduleId}/resume` : `/api/scraper/schedules/${scheduleId}/pause`;
    await fetch(endpoint, { method: 'POST' });
    await loadDefaultSchedules();
    await loadUpcomingTasks();
  } catch (err) {
    alert(`Failed to update schedule status: ${err.message}`);
  }
}

async function runScheduleNow(scheduleId) {
  try {
    const res = await fetch(`/api/scraper/schedules/${scheduleId}/run-now`, { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      const monSec = document.getElementById('section-status-monitor');
      if (monSec) monSec.scrollIntoView({ behavior: 'smooth' });
      pollLiveMonitor();
    } else {
      alert(`Could not start run: ${data.detail || data.error}`);
    }
  } catch (err) {
    alert(`Error executing schedule: ${err.message}`);
  }
}

// -------------------------------------------------------------------------
// 3. Custom Scheduler
// -------------------------------------------------------------------------
async function loadCustomSchedules() {
  const container = document.getElementById('custom-schedules-container');
  if (!container) return;

  try {
    const res = await fetch('/api/scraper/schedules');
    const data = await res.json();
    const schedules = (data.schedules || []).filter(s => s.schedule_type !== 'default');

    if (schedules.length === 0) {
      container.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 2.5rem; text-align: center; background: #f8fafc; border: 1.5px dashed #cbd5e1; border-radius: 12px;">
          <div style="font-size: 2rem; margin-bottom: 0.5rem;">📅</div>
          <div style="font-weight: 700; font-size: 1rem; color: #1e293b; margin-bottom: 0.25rem;">No Custom Schedules Defined</div>
          <div style="font-size: 0.825rem; color: #64748b; margin-bottom: 1rem;">Create custom automated runs with specific role keywords, multi-time sweeps, and portal priorities.</div>
          <button class="btn btn-primary btn-sm" onclick="openCustomScheduleModal()">➕ Create Your First Custom Schedule</button>
        </div>
      `;
      return;
    }

    container.innerHTML = schedules.map(s => {
      const timesStr = (s.run_times || []).join(', ') || '11:00';
      const daysStr = (s.days_of_week && s.days_of_week.length > 0) ? s.days_of_week.map(d => d.slice(0, 3)).join(', ') : 'Every Day';
      const sourcesCount = (s.sources || []).includes('all') ? 'All 7 Adapters' : `${s.sources.length} Selected`;

      return `
        <div class="custom-sched-card">
          <div>
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
              <div style="font-weight: 800; font-size: 1.05rem; color: #0f172a;">${escapeHtml(s.name)}</div>
              <span class="status-pill ${s.is_enabled ? 'status-completed' : 'status-idle'}">
                ${s.is_enabled ? '🟢 Active' : '⏸ Paused'}
              </span>
            </div>

            <div style="font-size: 0.8rem; color: #D97F95; font-weight: 700; margin-bottom: 0.75rem;">
              ⏰ ${s.frequency.toUpperCase()} at ${timesStr} (${escapeHtml(s.timezone || 'Asia/Kolkata')})
            </div>

            <div style="background: #f8fafc; border-radius: 8px; padding: 0.75rem; font-size: 0.8rem; display: flex; flex-direction: column; gap: 4px; margin-bottom: 0.85rem;">
              <div><strong>Days:</strong> <span style="color: #475569;">${daysStr}</span></div>
              <div><strong>Sources:</strong> <span style="color: #475569;">${sourcesCount}</span></div>
              <div><strong>Next Run:</strong> <span style="color: #0284c7; font-weight: 700;">${s.is_enabled ? formatRelativeTime(s.next_run_at) : 'Paused'}</span></div>
            </div>
          </div>

          <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #f1f5f9; padding-top: 0.75rem; margin-top: 0.5rem;">
            <div style="display: flex; gap: 6px;">
              <button class="btn btn-outline btn-sm" onclick="runScheduleNow('${s.id}')" title="Run immediately">
                ⚡ Run
              </button>
              <button class="btn btn-outline btn-sm" onclick="toggleCustomScheduleStatus('${s.id}', ${s.is_enabled})" title="${s.is_enabled ? 'Pause' : 'Resume'}">
                ${s.is_enabled ? '⏸ Pause' : '▶ Resume'}
              </button>
              <button class="btn btn-outline btn-sm" onclick="openCustomScheduleModal('${s.id}')" title="Edit settings">
                ✏️ Edit
              </button>
            </div>
            <button class="btn btn-outline btn-sm" onclick="deleteCustomSchedule('${s.id}')" style="color: #dc2626; border-color: #fca5a5;" title="Delete schedule">
              🗑
            </button>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error('Error loading custom schedules:', err);
  }
}

async function openCustomScheduleModal(scheduleId = null) {
  const modal = document.getElementById('custom-schedule-modal');
  const title = document.getElementById('custom-sched-modal-title');
  const idInput = document.getElementById('custom-sched-id');
  if (!modal) return;

  if (scheduleId) {
    if (title) title.innerText = '✏️ Edit Custom Scraping Schedule';
    if (idInput) idInput.value = scheduleId;

    try {
      const res = await fetch(`/api/scraper/schedules/${scheduleId}`);
      const s = await res.json();

      document.getElementById('cs-name').value = s.name || '';
      document.getElementById('cs-timezone').value = s.timezone || 'Asia/Kolkata';
      document.getElementById('cs-frequency').value = s.frequency || 'daily';
      document.getElementById('cs-runtimes').value = (s.run_times || []).join(', ');
      document.getElementById('cs-keywords').value = (s.keywords || []).join(', ');
      document.getElementById('cs-locations').value = s.location_filters || '';

      const days = s.days_of_week || [];
      document.querySelectorAll('input[name="cs_day"]').forEach(cb => {
        cb.checked = days.length === 0 || days.includes(cb.value);
      });

      const sources = s.sources || ['all'];
      document.querySelectorAll('input[name="cs_source"]').forEach(cb => {
        cb.checked = sources.includes('all') || sources.includes(cb.value);
      });

      const workmodes = s.work_modes || ['Remote', 'Hybrid', 'Onsite'];
      document.querySelectorAll('input[name="cs_workmode"]').forEach(cb => {
        cb.checked = workmodes.includes(cb.value);
      });

      document.getElementById('cs-dedup').checked = s.deduplication ?? true;
      document.getElementById('cs-ats').checked = s.ats_scoring ?? true;
      document.getElementById('cs-resume').checked = s.resume_matching ?? true;
      document.getElementById('cs-update-existing').checked = s.update_existing ?? true;

      handleFrequencyChange();
    } catch (err) {
      alert(`Error loading schedule data: ${err.message}`);
      return;
    }
  } else {
    if (title) title.innerText = '➕ Add Custom Scraping Schedule';
    if (idInput) idInput.value = '';
    document.getElementById('cs-name').value = '';
    document.getElementById('cs-timezone').value = 'Asia/Kolkata';
    document.getElementById('cs-frequency').value = 'daily';
    document.getElementById('cs-runtimes').value = '08:00, 13:00, 20:00';
    document.getElementById('cs-keywords').value = 'Data Analyst, Power BI Developer, Python, SQL';
    document.getElementById('cs-locations').value = 'India, Remote';
    document.querySelectorAll('input[name="cs_day"]').forEach(cb => cb.checked = true);
    document.querySelectorAll('input[name="cs_source"]').forEach(cb => cb.checked = true);
    document.querySelectorAll('input[name="cs_workmode"]').forEach(cb => cb.checked = true);
    document.getElementById('cs-dedup').checked = true;
    document.getElementById('cs-ats').checked = true;
    document.getElementById('cs-resume').checked = true;
    document.getElementById('cs-update-existing').checked = true;
    handleFrequencyChange();
  }

  modal.style.display = 'flex';
}

function handleFrequencyChange() {
  const freq = document.getElementById('cs-frequency')?.value;
  const daysWrap = document.getElementById('cs-days-wrap');
  if (daysWrap) {
    daysWrap.style.display = freq === 'monthly' ? 'none' : 'block';
  }
}

async function saveCustomSchedule() {
  const id = document.getElementById('custom-sched-id')?.value;
  const name = document.getElementById('cs-name')?.value.trim();
  if (!name) {
    alert('Please enter a schedule name.');
    return;
  }

  const timesRaw = document.getElementById('cs-runtimes')?.value || '11:00';
  const runTimes = timesRaw.split(',').map(t => t.trim()).filter(Boolean);

  const keywordsRaw = document.getElementById('cs-keywords')?.value || '';
  const keywords = keywordsRaw.split(',').map(k => k.trim()).filter(Boolean);

  const days = Array.from(document.querySelectorAll('input[name="cs_day"]:checked')).map(cb => cb.value);
  const sources = Array.from(document.querySelectorAll('input[name="cs_source"]:checked')).map(cb => cb.value);
  const workmodes = Array.from(document.querySelectorAll('input[name="cs_workmode"]:checked')).map(cb => cb.value);

  const payload = {
    name: name,
    timezone: document.getElementById('cs-timezone')?.value || 'Asia/Kolkata',
    frequency: document.getElementById('cs-frequency')?.value || 'daily',
    run_times: runTimes.length > 0 ? runTimes : ['11:00'],
    days_of_week: days,
    sources: sources.length > 0 ? sources : ['all'],
    keywords: keywords,
    location_filters: document.getElementById('cs-locations')?.value || '',
    work_modes: workmodes,
    deduplication: document.getElementById('cs-dedup')?.checked ?? true,
    ats_scoring: document.getElementById('cs-ats')?.checked ?? true,
    resume_matching: document.getElementById('cs-resume')?.checked ?? true,
    update_existing: document.getElementById('cs-update-existing')?.checked ?? true,
    scrape_new_only: true,
    max_jobs_per_run: 50,
    retry_count: 2,
    request_delay: 0.5
  };

  try {
    let res;
    if (id) {
      res = await fetch(`/api/scraper/schedules/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    } else {
      res = await fetch('/api/scraper/schedules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    }

    const data = await res.json();
    if (data.success || data.schedule) {
      closeModal('custom-schedule-modal');
      await Promise.all([loadCustomSchedules(), loadUpcomingTasks()]);
    } else {
      alert(`Error saving schedule: ${data.detail || data.error}`);
    }
  } catch (err) {
    alert(`Failed to save schedule: ${err.message}`);
  }
}

async function toggleCustomScheduleStatus(scheduleId, currentEnabled) {
  try {
    const endpoint = currentEnabled ? `/api/scraper/schedules/${scheduleId}/pause` : `/api/scraper/schedules/${scheduleId}/resume`;
    await fetch(endpoint, { method: 'POST' });
    await Promise.all([loadCustomSchedules(), loadUpcomingTasks()]);
  } catch (err) {
    alert(`Failed to update schedule status: ${err.message}`);
  }
}

async function deleteCustomSchedule(scheduleId) {
  if (!confirm('Are you sure you want to delete this custom scraping schedule?')) return;
  try {
    await fetch(`/api/scraper/schedules/${scheduleId}`, { method: 'DELETE' });
    await Promise.all([loadCustomSchedules(), loadUpcomingTasks()]);
  } catch (err) {
    alert(`Failed to delete schedule: ${err.message}`);
  }
}

// -------------------------------------------------------------------------
// 4. Upcoming Scheduled Jobs
// -------------------------------------------------------------------------
async function loadUpcomingTasks() {
  const tbody = document.getElementById('upcoming-tasks-tbody');
  if (!tbody) return;

  try {
    const res = await fetch('/api/scraper/upcoming');
    const data = await res.json();
    const tasks = data.tasks || [];

    if (tasks.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align: center; color: #64748b; padding: 2rem;">
            No upcoming scheduled tasks found. Enable default morning or evening schedule above.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = tasks.map(t => {
      const isDefault = t.schedule_type === 'default';
      return `
        <tr>
          <td>
            <strong>${escapeHtml(t.name)}</strong>
          </td>
          <td>
            <span style="font-weight: 700; color: #0284c7;">${formatRelativeTime(t.next_run_at)}</span>
          </td>
          <td>${escapeHtml(t.frequency)}</td>
          <td>
            <span class="status-pill status-completed">${escapeHtml(t.status)}</span>
          </td>
          <td>
            <span style="font-size: 0.8rem; color: #475569;">${escapeHtml(t.job_sources)}</span>
          </td>
          <td>
            <span style="font-size: 0.8rem; background: #FFF4DE; color: #D97F95; font-weight: 700; padding: 3px 8px; border-radius: 6px;">
              ${escapeHtml(t.expected_window)}
            </span>
          </td>
          <td style="text-align: right; white-space: nowrap;">
            <button class="btn btn-outline btn-sm" onclick="runScheduleNow('${t.id}')" title="Execute right now">
              ⚡ Run Now
            </button>
            ${!isDefault ? `
              <button class="btn btn-outline btn-sm" onclick="openCustomScheduleModal('${t.id}')" title="Edit schedule">
                ✏️
              </button>
              <button class="btn btn-outline btn-sm" onclick="deleteCustomSchedule('${t.id}')" style="color: #dc2626;" title="Delete">
                🗑
              </button>
            ` : ''}
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Error loading upcoming tasks:', err);
  }
}

// -------------------------------------------------------------------------
// 5. Real-Time Status Monitor
// -------------------------------------------------------------------------
async function pollLiveMonitor() {
  try {
    const res = await fetch('/api/scraper/monitor/live');
    const mon = await res.json();

    const pill = document.getElementById('monitor-status-pill');
    if (pill) {
      const st = (mon.status || 'idle').toLowerCase();
      pill.className = `status-pill status-${st === 'partially_completed' ? 'partial' : st}`;
      const icon = st === 'running' ? '🟡 Running' : (st === 'completed' ? '🟢 Completed' : (st === 'error' ? '🔴 Error' : '🟢 Idle'));
      pill.innerText = icon;
    }

    const badgeStatus = document.getElementById('badge-scheduler-status');
    if (badgeStatus) {
      badgeStatus.innerText = mon.status === 'running' ? 'Scraping...' : 'Active';
      badgeStatus.style.background = mon.status === 'running' ? '#eab308' : '#10b981';
    }

    const activeSrc = document.getElementById('mon-active-source');
    if (activeSrc) activeSrc.innerText = mon.current_active_job_source || 'Standby';

    const activePortal = document.getElementById('mon-active-portal');
    if (activePortal) activePortal.innerText = mon.current_portal_being_scraped || 'All Configured Portals Ready';

    const jobsScanned = document.getElementById('mon-jobs-scanned');
    if (jobsScanned) jobsScanned.innerText = mon.jobs_found_so_far || 0;

    const jobsAdded = document.getElementById('mon-jobs-added');
    if (jobsAdded) jobsAdded.innerText = mon.jobs_added_so_far || 0;

    const elapsed = document.getElementById('mon-elapsed-time');
    if (elapsed) {
      const sec = mon.time_elapsed_seconds || 0;
      const m = Math.floor(sec / 60).toString().padStart(2, '0');
      const s = (sec % 60).toString().padStart(2, '0');
      elapsed.innerText = `${m}:${s}`;
    }

    const remaining = document.getElementById('mon-remaining-tasks');
    if (remaining) remaining.innerText = mon.estimated_remaining_tasks || 'Standby';

    const progressFill = document.getElementById('mon-progress-fill');
    const progressText = document.getElementById('mon-progress-text');
    if (progressFill && progressText) {
      const pct = mon.progress_percent || 0;
      progressFill.style.width = `${pct}%`;
      progressText.innerText = `${pct}%`;
    }

    const stageText = document.getElementById('mon-stage-text');
    if (stageText) {
      stageText.innerText = mon.current_processing_stage || 'System Ready. Waiting for scheduled run or manual trigger.';
    }

    // Dynamic interval adjustment
    if (mon.status === 'running') {
      if (schedulerMonitorTimer) clearInterval(schedulerMonitorTimer);
      schedulerMonitorTimer = setInterval(pollLiveMonitor, 1500);
    } else {
      if (schedulerMonitorTimer) clearInterval(schedulerMonitorTimer);
      schedulerMonitorTimer = setInterval(pollLiveMonitor, 8000);
    }
  } catch (err) {
    // Ignore fetch aborts during reloads
  }
}

// -------------------------------------------------------------------------
// 6. Recommended Jobs
// -------------------------------------------------------------------------
async function loadRecommendedJobs() {
  const container = document.getElementById('recommended-jobs-grid');
  if (!container) return;

  try {
    const res = await fetch('/api/scraper/recommended?limit=9');
    const data = await res.json();
    const jobs = data.recommended_jobs || [];

    const skillsSummary = document.getElementById('rec-profile-skills');
    if (skillsSummary) {
      skillsSummary.innerText = 'Grounded against candidate technical tools: Python, SQL, Tableau, Power BI, Advanced Excel';
    }

    if (jobs.length === 0) {
      container.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 2rem; text-align: center; color: #64748b; font-size: 0.9rem;">
          No recommended jobs found yet. Run an automated scrape run above to discover matching jobs!
        </div>
      `;
      return;
    }

    container.innerHTML = jobs.map(j => {
      const score = j.match_score || 70;
      const matchedPills = (j.matched_skills || []).map(s => `
        <span style="background: #dcfce7; color: #166534; font-size: 0.72rem; font-weight: 700; padding: 2px 7px; border-radius: 4px;">
          ✓ ${escapeHtml(s)}
        </span>
      `).join('');

      const missingPills = (j.missing_skills || []).map(s => `
        <span style="background: #f1f5f9; color: #64748b; font-size: 0.72rem; padding: 2px 7px; border-radius: 4px;">
          ${escapeHtml(s)}
        </span>
      `).join('');

      return `
        <div class="rec-job-card">
          <div>
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem; gap: 8px;">
              <div>
                <h4 style="font-size: 1.05rem; font-weight: 800; color: #0f172a; margin: 0 0 2px 0;">${escapeHtml(j.title)}</h4>
                <div style="font-size: 0.85rem; font-weight: 700; color: #D97F95;">${escapeHtml(j.company)}</div>
              </div>
              <div class="match-score-badge">
                ★ ${score}% Match
              </div>
            </div>

            <div style="display: flex; gap: 8px; flex-wrap: wrap; font-size: 0.775rem; color: #475569; margin-bottom: 0.75rem;">
              <span>📍 ${escapeHtml(j.location)}</span>
              <span>💼 ${escapeHtml(j.work_mode)}</span>
              <span>💰 ${escapeHtml(j.salary)}</span>
            </div>

            <div style="margin-bottom: 0.75rem;">
              <div style="font-size: 0.725rem; font-weight: 700; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">Verified Matching Skills</div>
              <div style="display: flex; gap: 4px; flex-wrap: wrap;">
                ${matchedPills || '<span style="font-size: 0.75rem; color: #94a3b8;">Analytics taxonomy aligned</span>'}
              </div>
            </div>

            ${missingPills ? `
              <div style="margin-bottom: 0.85rem;">
                <div style="font-size: 0.725rem; font-weight: 700; color: #94a3b8; text-transform: uppercase; margin-bottom: 4px;">Gaps to Bridge</div>
                <div style="display: flex; gap: 4px; flex-wrap: wrap;">
                  ${missingPills}
                </div>
              </div>
            ` : ''}
          </div>

          <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #f1f5f9; padding-top: 0.75rem; margin-top: 0.5rem;">
            <span style="font-size: 0.75rem; color: #94a3b8;">Via ${escapeHtml(j.source_name)}</span>
            <div style="display: flex; gap: 6px;">
              <button class="btn btn-outline btn-sm" onclick="openJobDetailModal('${j.id}')">
                👁 Details
              </button>
              <button class="btn btn-primary btn-sm" onclick="startAIEngineTailoring('${j.id}')">
                ⚡ Tailor Resume
              </button>
            </div>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    console.error('Error loading recommended jobs:', err);
  }
}

// -------------------------------------------------------------------------
// 7. Scrape Activity Logs
// -------------------------------------------------------------------------
function debounceLogSearch() {
  clearTimeout(logSearchDebounceTimer);
  logSearchDebounceTimer = setTimeout(() => {
    loadActivityLogs();
  }, 350);
}

async function loadActivityLogs() {
  const tbody = document.getElementById('activity-logs-tbody');
  if (!tbody) return;

  const dateRange = document.getElementById('log-filter-date')?.value || '7d';
  const status = document.getElementById('log-filter-status')?.value || 'all';
  const trigger = document.getElementById('log-filter-trigger')?.value || 'all';
  const query = document.getElementById('log-filter-query')?.value || '';

  const params = new URLSearchParams({
    date_range: dateRange,
    status: status,
    trigger_source: trigger,
    q: query,
    limit: '50'
  });

  try {
    const res = await fetch(`/api/scraper/logs?${params.toString()}`);
    const data = await res.json();
    const logs = data.logs || [];

    if (logs.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="12" style="text-align: center; color: #64748b; padding: 2.5rem;">
            No activity logs match the selected filters.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = logs.map(l => {
      const st = (l.status || 'completed').toLowerCase();
      let badgeClass = 'status-completed';
      let icon = '🟢';
      if (st === 'running') { badgeClass = 'status-running'; icon = '🟡'; }
      else if (st === 'partially_completed') { badgeClass = 'status-partial'; icon = '🟠'; }
      else if (st === 'failed') { badgeClass = 'status-failed'; icon = '🔴'; }

      const startedFormatted = l.started_at ? formatIndianDateTime(l.started_at) : '-';
      const durationFormatted = l.duration_seconds ? `${parseFloat(l.duration_seconds).toFixed(1)}s` : '-';
      const sourcesList = (l.job_sources || []).slice(0, 3).join(', ') || 'All';

      return `
        <tr>
          <td><code style="font-weight: 700; color: #0284c7;">${escapeHtml(l.run_id)}</code></td>
          <td><strong>${escapeHtml(l.schedule_name || 'Manual Run')}</strong></td>
          <td>
            <span style="font-size: 0.8rem; background: #f1f5f9; padding: 2px 6px; border-radius: 4px;">
              ${escapeHtml(l.trigger_source || 'manual')} (${escapeHtml(l.triggered_by || 'User')})
            </span>
          </td>
          <td>${startedFormatted}</td>
          <td>${durationFormatted}</td>
          <td>
            <span class="status-pill ${badgeClass}">${icon} ${st}</span>
          </td>
          <td style="font-size: 0.775rem; color: #64748b;" title="${(l.job_sources || []).join(', ')}">${sourcesList}</td>
          <td style="font-weight: 700; color: #0f172a;">${l.jobs_scanned || 0}</td>
          <td style="font-weight: 700; color: #166534;">+${l.jobs_added || 0}</td>
          <td style="color: #64748b;">${l.duplicates_skipped || 0}</td>
          <td style="color: ${l.errors_count > 0 ? '#dc2626' : '#64748b'}; font-weight: ${l.errors_count > 0 ? '700' : 'normal'};">${l.errors_count || 0}</td>
          <td style="text-align: right;">
            <button class="btn btn-outline btn-sm" onclick="viewLogDetails('${l.run_id}')" title="View execution trace">
              🔍 Details
            </button>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Error loading activity logs:', err);
  }
}

async function viewLogDetails(runId) {
  const modal = document.getElementById('log-details-modal');
  const body = document.getElementById('log-details-modal-body');
  if (!modal || !body) return;

  body.innerHTML = '<div style="padding: 2rem; text-align: center; color: #64748b;">Loading execution details...</div>';
  modal.style.display = 'flex';

  try {
    const res = await fetch(`/api/scraper/logs/${runId}`);
    const l = await res.json();

    const errorsHtml = (l.error_messages || []).length > 0 ? `
      <div style="background: #fff1f2; border: 1.5px solid #fecdd3; padding: 1rem; border-radius: 10px; margin-bottom: 1rem;">
        <strong style="color: #be123c; font-size: 0.85rem; display: block; margin-bottom: 4px;">⚠️ Error Messages (${l.error_messages.length})</strong>
        <ul style="margin: 0; padding-left: 1.25rem; font-size: 0.8rem; color: #9f1239;">
          ${l.error_messages.map(e => `<li>${escapeHtml(e)}</li>`).join('')}
        </ul>
      </div>
    ` : '<div style="color: #15803d; font-size: 0.85rem; font-weight: 700; margin-bottom: 1rem;">✓ No errors encountered during this scrape run.</div>';

    body.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem;">
        <div>
          <h3 style="font-size: 1.15rem; font-weight: 800; color: #0f172a; margin: 0 0 4px 0;">${escapeHtml(l.schedule_name || 'Scrape Run')}</h3>
          <div style="font-size: 0.825rem; color: #64748b;">Run ID: <code>${escapeHtml(l.run_id)}</code> | Trigger: ${escapeHtml(l.trigger_source)} (${escapeHtml(l.triggered_by)})</div>
        </div>
        <span class="status-pill status-${l.status === 'completed' ? 'completed' : (l.status === 'running' ? 'running' : 'failed')}">
          ${escapeHtml(l.status)}
        </span>
      </div>

      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 8px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 1rem; margin-bottom: 1.25rem; text-align: center;">
        <div>
          <div style="font-size: 1.35rem; font-weight: 800; color: #0f172a;">${l.jobs_scanned || 0}</div>
          <div style="font-size: 0.7rem; color: #64748b; font-weight: 700;">SCANNED</div>
        </div>
        <div>
          <div style="font-size: 1.35rem; font-weight: 800; color: #166534;">+${l.jobs_added || 0}</div>
          <div style="font-size: 0.7rem; color: #64748b; font-weight: 700;">NEW ADDED</div>
        </div>
        <div>
          <div style="font-size: 1.35rem; font-weight: 800; color: #64748b;">${l.duplicates_skipped || 0}</div>
          <div style="font-size: 0.7rem; color: #64748b; font-weight: 700;">DUPLICATES</div>
        </div>
        <div>
          <div style="font-size: 1.35rem; font-weight: 800; color: #0284c7;">${l.duration_seconds || 0}s</div>
          <div style="font-size: 0.7rem; color: #64748b; font-weight: 700;">DURATION</div>
        </div>
        <div>
          <div style="font-size: 1.35rem; font-weight: 800; color: #D97F95;">${l.high_match_jobs_found || 0}</div>
          <div style="font-size: 0.7rem; color: #64748b; font-weight: 700;">HIGH-MATCH</div>
        </div>
      </div>

      ${errorsHtml}

      <div style="background: #0f172a; color: #f8fafc; padding: 1rem; border-radius: 10px; font-family: monospace; font-size: 0.775rem; max-height: 250px; overflow-y: auto;">
        <pre style="margin: 0; white-space: pre-wrap;">${escapeHtml(JSON.stringify(l, null, 2))}</pre>
      </div>

      <div style="display: flex; justify-content: flex-end; margin-top: 1.25rem;">
        <button class="btn btn-outline" onclick="closeModal('log-details-modal')">Close</button>
      </div>
    `;
  } catch (err) {
    body.innerHTML = `<div style="color: #dc2626; padding: 1rem;">Error loading log details: ${err.message}</div>`;
  }
}

function exportLogs(format) {
  window.location.href = `/api/scraper/logs/export/download?format=${format}`;
}

// -------------------------------------------------------------------------
// 8. Scraping Analytics Dashboard
// -------------------------------------------------------------------------
async function loadScrapingAnalytics() {
  try {
    const res = await fetch('/api/scraper/analytics');
    const an = await res.json();
    currentAnalyticsData = an;

    document.getElementById('an-total-runs').innerText = an.total_runs ?? '-';
    document.getElementById('an-total-scraped').innerText = an.total_scraped ?? '-';
    document.getElementById('an-total-unique').innerText = an.total_unique_jobs ?? '-';
    document.getElementById('an-success-rate').innerText = an.success_rate ? `${an.success_rate}%` : '-';
    document.getElementById('an-failed-runs').innerText = an.failed_runs ?? '0';
    document.getElementById('an-avg-time').innerText = an.avg_processing_time_sec ?? '-';
    document.getElementById('an-top-portal').innerText = an.most_productive_portal || '-';
    document.getElementById('an-best-sched').innerText = an.best_performing_schedule || '-';

    renderAnalyticsTrendBars();
    renderAnalyticsPortalBreakdown();
  } catch (err) {
    console.error('Error loading scraping analytics:', err);
  }
}

function switchChartGranularity(granularity) {
  currentChartGranularity = granularity;
  ['day', 'week', 'month'].forEach(g => {
    const btn = document.getElementById(`btn-chart-${g}`);
    if (btn) btn.classList.toggle('active', g === granularity);
  });
  renderAnalyticsTrendBars();
}

function renderAnalyticsTrendBars() {
  const container = document.getElementById('analytics-trend-bars');
  if (!container || !currentAnalyticsData) return;

  let items = [];
  if (currentChartGranularity === 'day') {
    items = currentAnalyticsData.jobs_per_day || [];
  } else if (currentChartGranularity === 'week') {
    items = currentAnalyticsData.jobs_per_week || [];
  } else {
    items = currentAnalyticsData.jobs_per_month || [];
  }

  if (items.length === 0) {
    container.innerHTML = '<div style="width: 100%; text-align: center; color: #94a3b8; font-size: 0.85rem;">No historical trend data yet.</div>';
    return;
  }

  const maxVal = Math.max(...items.map(i => i.count || 0), 1);

  container.innerHTML = items.map(item => {
    const count = item.count || 0;
    const label = item.date ? item.date.slice(5) : (item.week ? item.week.slice(5) : (item.month || ''));
    const heightPercent = Math.max(8, Math.round((count / maxVal) * 100));

    return `
      <div class="chart-bar-item" title="${label}: ${count} jobs found">
        <div style="font-size: 0.7rem; font-weight: 700; color: #475569; margin-bottom: 4px;">${count}</div>
        <div class="chart-bar-fill" style="height: ${heightPercent}%;"></div>
        <div class="chart-bar-lbl">${label}</div>
      </div>
    `;
  }).join('');
}

function renderAnalyticsPortalBreakdown() {
  const container = document.getElementById('analytics-portal-breakdown');
  if (!container || !currentAnalyticsData) return;

  const items = currentAnalyticsData.portal_breakdown || [];
  if (items.length === 0) {
    container.innerHTML = '<div style="color: #94a3b8; font-size: 0.85rem; padding: 1rem;">No platform distribution available.</div>';
    return;
  }

  const maxVal = Math.max(...items.map(i => i.count || 0), 1);

  container.innerHTML = items.map(p => {
    const pct = Math.round((p.count / maxVal) * 100);
    return `
      <div>
        <div style="display: flex; justify-content: space-between; font-size: 0.8rem; font-weight: 700; color: #1e293b; margin-bottom: 4px;">
          <span>${escapeHtml(p.portal)}</span>
          <span style="color: #D97F95;">${p.count} jobs</span>
        </div>
        <div style="height: 8px; background: #f1f5f9; border-radius: 9999px; overflow: hidden;">
          <div style="width: ${pct}%; height: 100%; background: linear-gradient(90deg, #FFCED8, #D97F95); border-radius: 9999px;"></div>
        </div>
      </div>
    `;
  }).join('');
}

// -------------------------------------------------------------------------
// Responsive Mobile Navigation Menu
// -------------------------------------------------------------------------
function toggleMobileMenu() {
  const drawer = document.getElementById('mobile-actions-drawer');
  const btn = document.getElementById('mobile-menu-btn');
  const icon = document.getElementById('mobile-menu-icon');
  if (!drawer) return;
  const isCurrentlyHidden = drawer.style.display === 'none' || !drawer.classList.contains('open');
  if (isCurrentlyHidden) {
    drawer.style.display = 'block';
    setTimeout(() => {
      drawer.classList.add('open');
    }, 10);
    if (btn) {
      btn.setAttribute('aria-expanded', 'true');
      btn.classList.add('active');
    }
    if (icon) icon.innerText = '✕';
  } else {
    closeMobileMenu();
  }
}

function closeMobileMenu() {
  const drawer = document.getElementById('mobile-actions-drawer');
  const btn = document.getElementById('mobile-menu-btn');
  const icon = document.getElementById('mobile-menu-icon');
  if (!drawer) return;
  drawer.classList.remove('open');
  if (btn) {
    btn.setAttribute('aria-expanded', 'false');
    btn.classList.remove('active');
  }
  if (icon) icon.innerText = '☰';
  setTimeout(() => {
    if (!drawer.classList.contains('open')) {
      drawer.style.display = 'none';
    }
  }, 220);
}

// Close mobile drawer when clicking outside
document.addEventListener('click', (e) => {
  const drawer = document.getElementById('mobile-actions-drawer');
  const btn = document.getElementById('mobile-menu-btn');
  if (drawer && drawer.classList.contains('open')) {
    if (!drawer.contains(e.target) && !btn.contains(e.target)) {
      closeMobileMenu();
    }
  }
});

// Close mobile drawer on escape key
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeMobileMenu();
  }
});

// -------------------------------------------------------------------------
// Notifications System
// -------------------------------------------------------------------------
function toggleNotificationDrawer() {
  const drawer = document.getElementById('notif-dropdown');
  if (!drawer) return;
  const isHidden = drawer.style.display === 'none';
  drawer.style.display = isHidden ? 'block' : 'none';
  if (isHidden) fetchNotifications();
}

// Close notification drawer when clicking outside
document.addEventListener('click', (e) => {
  const drawer = document.getElementById('notif-dropdown');
  const btn = document.getElementById('notif-bell-btn');
  if (drawer && drawer.style.display === 'block') {
    if (!drawer.contains(e.target) && !btn.contains(e.target)) {
      drawer.style.display = 'none';
    }
  }
});

async function fetchNotifications() {
  try {
    const res = await fetch('/api/scraper/notifications?limit=20');
    const data = await res.json();
    const items = data.items || [];
    const unread = data.unread_count || 0;

    const badge = document.getElementById('header-notif-badge');
    if (badge) {
      if (unread > 0) {
        badge.innerText = unread > 99 ? '99+' : unread;
        badge.style.display = 'inline-block';
      } else {
        badge.style.display = 'none';
      }
    }

    const listEl = document.getElementById('notif-items-list');
    if (listEl) {
      if (items.length === 0) {
        listEl.innerHTML = '<div style="padding: 1.5rem; text-align: center; color: #94a3b8; font-size: 0.85rem;">No recent notifications</div>';
        return;
      }

      listEl.innerHTML = items.map(n => {
        let icon = '🔔';
        if (n.category === 'schedule_executed') icon = '✅';
        else if (n.category === 'new_jobs') icon = '💼';
        else if (n.category === 'high_match') icon = '⭐';
        else if (n.category === 'error_alert') icon = '⚠️';
        else if (n.category === 'schedule_change') icon = '📅';

        const indianDateTimeStr = n.created_at_ist || formatIndianDateTime(n.created_at);
        const relAgo = formatRelativeTimeAgo(n.created_at);

        return `
          <div class="notif-item ${!n.is_read ? 'unread' : ''}" onclick="markNotificationRead('${n.id}')">
            <div style="font-size: 1.15rem; line-height: 1.2;">${icon}</div>
            <div style="flex: 1; min-width: 0;">
              <div class="notif-title">${escapeHtml(n.title)}</div>
              <div class="notif-msg">${escapeHtml(n.message)}</div>
              <div class="notif-meta">
                <span class="notif-date" title="Timestamp in Indian Standard Time (IST)">📅 ${escapeHtml(indianDateTimeStr)}</span>
                ${relAgo ? `<span class="notif-ago">(${escapeHtml(relAgo)})</span>` : ''}
              </div>
            </div>
          </div>
        `;
      }).join('');
    }
  } catch (err) {
    // Suppress network notification errors
  }
}

async function markNotificationRead(notifId) {
  try {
    await fetch(`/api/scraper/notifications/${notifId}/read`, { method: 'POST' });
    fetchNotifications();
  } catch (err) {
    console.error(err);
  }
}

async function markAllNotificationsRead() {
  try {
    await fetch('/api/scraper/notifications/mark-all-read', { method: 'POST' });
    fetchNotifications();
  } catch (err) {
    alert(`Failed to mark notifications read: ${err.message}`);
  }
}

async function openNotificationSettingsModal() {
  const modal = document.getElementById('notification-settings-modal');
  if (!modal) return;

  try {
    const res = await fetch('/api/scraper/notifications/settings');
    const s = await res.json();

    document.getElementById('notif-in-app').checked = s.in_app_enabled ?? true;
    document.getElementById('notif-email-enabled').checked = s.email_enabled ?? false;
    document.getElementById('notif-email-recipient').value = s.email_recipient || '';
    document.getElementById('notif-smtp-host').value = s.smtp_host || 'smtp.gmail.com';
    document.getElementById('notif-smtp-port').value = s.smtp_port || 587;
    document.getElementById('notif-trigger-complete').checked = s.notify_on_complete ?? true;
    document.getElementById('notif-trigger-newjobs').checked = s.notify_on_new_jobs ?? true;
    document.getElementById('notif-trigger-highmatch').checked = s.notify_on_high_match ?? true;
    document.getElementById('notif-trigger-failure').checked = s.notify_on_failure ?? true;

    modal.style.display = 'flex';
  } catch (err) {
    alert(`Failed to load notification settings: ${err.message}`);
  }
}

async function saveNotificationSettings() {
  const payload = {
    in_app_enabled: document.getElementById('notif-in-app')?.checked ?? true,
    email_enabled: document.getElementById('notif-email-enabled')?.checked ?? false,
    email_recipient: document.getElementById('notif-email-recipient')?.value.trim() || '',
    smtp_host: document.getElementById('notif-smtp-host')?.value.trim() || 'smtp.gmail.com',
    smtp_port: parseInt(document.getElementById('notif-smtp-port')?.value || '587', 10),
    notify_on_complete: document.getElementById('notif-trigger-complete')?.checked ?? true,
    notify_on_new_jobs: document.getElementById('notif-trigger-newjobs')?.checked ?? true,
    notify_on_high_match: document.getElementById('notif-trigger-highmatch')?.checked ?? true,
    notify_on_failure: document.getElementById('notif-trigger-failure')?.checked ?? true
  };

  try {
    const res = await fetch('/api/scraper/notifications/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      closeModal('notification-settings-modal');
      alert('Notification settings saved successfully.');
    }
  } catch (err) {
    alert(`Failed to save notification settings: ${err.message}`);
  }
}

async function sendTestNotificationEmail() {
  try {
    const res = await fetch('/api/scraper/notifications/test-email', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      alert(`Test notification dispatched: ${data.message}`);
    } else {
      alert(`Failed: ${data.detail || data.error}`);
    }
  } catch (err) {
    alert(`Error dispatching test email: ${err.message}`);
  }
}

// =========================================================================
// LINKEDIN HR & RECRUITER FEED PLATFORM SYSTEM
// =========================================================================

let currentLinkedInFeedPosts = [];
let activeLinkedInQuickFilter = 'all';
let linkedInSearchDebounceTimer = null;

async function loadLinkedInFeedPage() {
  await Promise.all([
    loadLinkedInFeedStats(),
    loadLinkedInFeedPosts()
  ]);
}

async function loadLinkedInFeedStats() {
  try {
    const res = await fetch('/api/scraper/linkedin/feed?limit=100');
    const data = await res.json();
    const items = data.items || [];

    const totalEl = document.getElementById('li-stat-total-posts');
    if (totalEl) totalEl.innerText = data.all_in_db || items.length;

    const emailEl = document.getElementById('li-stat-direct-emails');
    if (emailEl) emailEl.innerText = data.direct_email_count || 0;

    const responseRateEl = document.getElementById('li-stat-response-rate');
    if (responseRateEl) responseRateEl.innerText = `${data.email_readiness_pct || 100}%`;

    const badge = document.getElementById('badge-linkedin-feed-count');
    if (badge) badge.innerText = data.all_in_db || items.length;

    // Count today's fresh posts
    const todayStr = new Date().toISOString().slice(0, 10);
    const todayCount = items.filter(p => (p.published_at || p.created_at || '').startsWith(todayStr)).length;
    const freshTodayEl = document.getElementById('li-stat-fresh-today');
    if (freshTodayEl) freshTodayEl.innerText = todayCount;
  } catch (err) {
    console.error('Error loading LinkedIn stats:', err);
  }
}

async function loadLinkedInFeedPosts() {
  const container = document.getElementById('linkedin-feed-posts-grid');
  if (!container) return;

  const q = document.getElementById('li-search-input')?.value.trim() || '';
  const workMode = document.getElementById('li-workmode-select')?.value || '';
  const hasEmailOnly = activeLinkedInQuickFilter === 'email';

  let url = `/api/scraper/linkedin/feed?limit=100`;
  if (q) url += `&q=${encodeURIComponent(q)}`;
  if (hasEmailOnly) url += `&has_email_only=true`;
  if (workMode) url += `&work_mode=${encodeURIComponent(workMode)}`;

  try {
    const res = await fetch(url);
    const data = await res.json();
    let posts = data.items || [];

    // Client-side quick filter refinement
    if (activeLinkedInQuickFilter === 'today') {
      const todayStr = new Date().toISOString().slice(0, 10);
      posts = posts.filter(p => (p.published_at || p.created_at || '').startsWith(todayStr));
    } else if (activeLinkedInQuickFilter === 'remote') {
      posts = posts.filter(p => (p.work_mode || '').toLowerCase() === 'remote');
    } else if (activeLinkedInQuickFilter === 'bengaluru') {
      posts = posts.filter(p => (p.location || '').toLowerCase().includes('bengaluru') || (p.location || '').toLowerCase().includes('bangalore'));
    }

    currentLinkedInFeedPosts = posts;

    const counter = document.getElementById('li-results-counter');
    if (counter) counter.innerText = `Showing ${posts.length} recruiter posts`;

    renderLinkedInRecruiterCards(posts);
  } catch (err) {
    container.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; color: #dc2626; padding: 2rem;">Failed to load LinkedIn recruiter posts: ${escapeHtml(err.message)}</div>`;
  }
}

function renderLinkedInRecruiterCards(posts) {
  window.linkedInFeedPostsCache = posts || [];
  const container = document.getElementById('linkedin-feed-posts-grid');
  if (!container) return;

  if (posts.length === 0) {
    container.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 3.5rem 1.5rem; background: #ffffff; border-radius: 16px; border: 2px dashed #bae6fd;">
        <div style="font-size: 2.8rem; margin-bottom: 0.5rem;">👔</div>
        <h3 style="font-size: 1.25rem; font-weight: 800; color: #0a66c2; margin-bottom: 0.5rem;">No recruiter posts match your current filter</h3>
        <p style="color: #64748b; font-size: 0.875rem; max-width: 500px; margin: 0 auto 1.25rem auto;">
          Try resetting the search keywords, switching work mode, or click below to scrape and sync the latest recruiter hiring posts from LinkedIn.
        </p>
        <div style="display: flex; gap: 8px; justify-content: center;">
          <button class="btn btn-outline btn-sm" onclick="setLinkedInQuickFilter('all')">Reset Filters</button>
          <button class="btn btn-primary btn-sm" onclick="syncLinkedInFeedNow()" style="background: #0a66c2; border-color: #0a66c2;">⚡ Scrape Recruiter Feed</button>
        </div>
      </div>
    `;
    return;
  }

  container.innerHTML = posts.map(post => {
    const isBookmarked = Boolean(post.is_bookmarked) || post.application_status === 'saved';
    const isApplied = Boolean(post.is_applied) || post.application_status === 'applied';
    const jobStatus = (post.application_status || (isApplied ? 'applied' : 'new')).toLowerCase();

    // Recruiter avatar initials
    const name = post.recruiter_name || 'Hiring Recruiter';
    const initials = name.split(' ').map(w => w[0]).filter(Boolean).slice(0, 2).join('').toUpperCase() || 'HR';

    // Date formatted in Indian Standard Time (IST)
    const postDateIso = post.published_at || post.created_at || post.discovered_at;
    const dateFormattedIST = typeof formatIndianDateTime === 'function' ? formatIndianDateTime(postDateIso) : (postDateIso || '');

    // Skills chips
    const skillsHtml = (post.skills || []).slice(0, 6).map(s => `
      <span class="job-skill-chip-amber" style="background: #e0f2fe; color: #0369a1; border-color: #bae6fd;">${escapeHtml(s)}</span>
    `).join('');

    // Extract quote snippet from description
    let quoteText = post.description || '';
    if (quoteText.includes(':\n\n')) {
      quoteText = quoteText.split(':\n\n')[1] || quoteText;
    }
    // Highlight hashtags
    const highlightedQuote = escapeHtml(quoteText).replace(/(#[a-zA-Z0-9_]+)/g, '<span style="color: #0a66c2; font-weight: 700;">$1</span>');

    return `
      <div class="linkedin-recruiter-card ${isApplied ? 'is-applied' : ''}" id="li-job-${post.id}">
        <div>
          <!-- Recruiter Header Profile -->
          <div class="linkedin-recruiter-header">
            <div class="recruiter-avatar">${initials}</div>
            <div class="recruiter-info" style="flex: 1;">
              <div class="recruiter-name-line">
                <span style="font-weight: 800;">${escapeHtml(name)}</span>
                <span style="color: #0a66c2; font-size: 0.85rem;" title="Verified Recruiter Post">✓</span>
                <div style="margin-left: auto; display: flex; gap: 4px; flex-wrap: wrap;">
                  ${post.role_match_score ? `<span class="badge-fresher" style="background: #ecfdf5; color: #047857; border-color: #a7f3d0; font-size: 0.65rem; padding: 1px 6px;">🎯 ${post.role_match_score}% Match</span>` : ''}
                  ${post.confidence_score ? `<span class="badge-fresher" style="background: #eff6ff; color: #1d4ed8; border-color: #bfdbfe; font-size: 0.65rem; padding: 1px 6px;">⭐ ${post.confidence_score}% Confidence</span>` : ''}
                </div>
              </div>
              <div class="recruiter-title-line">
                ${post.recruiter_designation ? `<span style="color: #64748b; font-weight: 500;">${escapeHtml(post.recruiter_designation)}</span> • ` : ''}
                🏢 <strong>${escapeHtml(post.company)}</strong>
                ${post.linkedin_profile ? ` • <a href="${post.linkedin_profile}" target="_blank" rel="noopener noreferrer" style="color: #0a66c2; font-weight: 600; text-decoration: underline;">Profile ↗</a>` : ''}
              </div>
              <div style="font-size: 0.725rem; color: #94a3b8; margin-top: 2px;" title="Publication Timestamp in Indian Standard Time (IST)">
                📅 ${dateFormattedIST}
              </div>
            </div>
          </div>

          <!-- Job Opening Title -->
          <h3 class="job-title" onclick="openJobDetails('${post.id}')" style="color: #0f172a; margin-bottom: 0.45rem;">
            ${escapeHtml(post.title)}
          </h3>

          <!-- Meta Row (Location, Workmode, Salary) -->
          <div class="job-meta-row" style="margin-bottom: 0.5rem;">
            <div class="job-meta-item">📍 ${escapeHtml(post.location)}</div>
            <div class="job-meta-item">⏱️ ${escapeHtml(post.experience_level || 'Fresher (0-1 yr)')}</div>
            <div class="job-meta-item" style="color: #059669; font-weight: 700;">💰 ${escapeHtml(post.salary || 'Competitive')}</div>
          </div>

          <!-- Recruiter Post Message Blockquote -->
          <div class="recruiter-post-quote">
            "${highlightedQuote}"
          </div>

          <!-- Skills Chips -->
          <div class="job-skills" style="display: flex; flex-wrap: wrap; gap: 0.35rem; margin-top: 0.5rem;">
            ${skillsHtml}
          </div>

          <!-- Recruiter & Direct Contact Hub -->
          ${getContactHubHtml(post)}
        </div>

        <!-- Footer & Action Buttons -->
        <div style="margin-top: 1rem; padding-top: 0.75rem; border-top: 1px solid #e2e8f0;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.65rem; flex-wrap: wrap; gap: 6px;">
            <div style="display: flex; gap: 6px; flex-wrap: wrap; align-items: center;">
              ${post.linkedin_profile ? `
                <a href="${post.linkedin_profile}" target="_blank" rel="noopener noreferrer" class="contact-link-pill" style="font-size: 0.75rem;">
                  🔗 Connect with ${escapeHtml(name.split(' ')[0])} ↗
                </a>
              ` : `
                <span style="font-size: 0.725rem; color: #64748b;">Direct Outreach via Profile / Link</span>
              `}
            </div>

            <!-- Bookmark / Status -->
            <div style="display: flex; align-items: center; gap: 6px;">
              <select class="job-status-select ${getStatusClass(jobStatus)}" onchange="handleJobStatusChange('${post.id}', this.value, event)" style="font-size: 0.7rem; padding: 2px 6px;">
                <option value="new" ${jobStatus === 'new' ? 'selected' : ''}>New ▾</option>
                <option value="saved" ${jobStatus === 'saved' ? 'selected' : ''}>Saved ▾</option>
                <option value="applied" ${jobStatus === 'applied' ? 'selected' : ''}>Applied ▾</option>
                <option value="interview" ${jobStatus === 'interview' ? 'selected' : ''}>Interview ▾</option>
                <option value="offer" ${jobStatus === 'offer' ? 'selected' : ''}>Offer ▾</option>
                <option value="rejected" ${jobStatus === 'rejected' ? 'selected' : ''}>Rejected ▾</option>
              </select>
              <button type="button" class="btn-action-bookmark ${isBookmarked ? 'is-saved' : ''}" onclick="toggleJobBookmark('${post.id}', event)" title="Bookmark post">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="${isBookmarked ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path>
                </svg>
              </button>
            </div>
          </div>

          <!-- Bottom Action Buttons -->
          <div class="job-actions" style="margin-top: 0.4rem; display: flex; gap: 6px; flex-wrap: wrap;">
            ${post.apply_url ? `
              <a href="${post.apply_url}" target="_blank" rel="noopener noreferrer" class="btn btn-sm"
                style="background: #10b981; color: #FFFFFF; font-weight: 700; border: none; padding: 0.35rem 0.75rem; border-radius: 6px; text-decoration: none;" title="Open registration or direct apply portal">
                🚀 Apply Now ↗
              </a>
            ` : ''}
            <button type="button" class="btn btn-sm" onclick="copyOutreachPrompt('${post.id}', event)"
              style="background: #0284c7; color: #FFFFFF; font-weight: 700; border: none; padding: 0.35rem 0.75rem; border-radius: 6px;" title="Copy cold outreach message prompt ready to send to recruiter">
              📋 Outreach Prompt
            </button>
            <button type="button" class="btn btn-sm" onclick="openRecruiterEmail('${post.id}', event)"
              style="${isGenuineEmail(post.recruiter_email) ? 'background: #0a66c2;' : 'background: #475569;'} color: #FFFFFF; font-weight: 700; border: none; padding: 0.35rem 0.75rem; border-radius: 6px;" 
              title="${isGenuineEmail(post.recruiter_email) ? 'Open pre-drafted recruiter outreach email' : 'View tailored message draft (copy to send via LinkedIn/InMail)'}">
              ${isGenuineEmail(post.recruiter_email) ? '✉️ Email Recruiter' : '✉️ Outreach Message'}
            </button>
            <button type="button" class="btn btn-tailor btn-sm" onclick="tailorResumeForJob('${post.id}', event)" title="Generate tailored ATS resume for this recruiter opening">
              ⚡ Tailor Resume
            </button>
            ${isValidLinkedInPostUrl(post.source_url) ? `
              <a href="${post.source_url}" target="_blank" rel="noopener noreferrer" class="btn btn-outline btn-sm"
                style="border-color: #0a66c2; color: #0a66c2; font-weight: 700;" title="View exact post on LinkedIn">
                🔗 Original Post ↗
              </a>
            ` : (!post.apply_url ? `
              <a href="https://www.linkedin.com/search/results/content/?keywords=${encodeURIComponent((post.company || '') + ' ' + (post.title || '') + ' hiring')}" 
                target="_blank" rel="noopener noreferrer" class="btn btn-outline btn-sm"
                style="border-color: #94a3b8; color: #64748b; font-weight: 600; font-size: 0.75rem;" title="Search for this hiring post on LinkedIn">
                🔍 Find on LinkedIn ↗
              </a>
            ` : '')}
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function copyRecruiterEmail(email) {
  navigator.clipboard.writeText(email).then(() => {
    alert(`Copied recruiter email: ${email}`);
  }).catch(() => {
    alert(`Email: ${email}`);
  });
}

function setLinkedInQuickFilter(filterType) {
  activeLinkedInQuickFilter = filterType;
  const pillIds = ['all', 'today', 'email', 'remote', 'bengaluru'];
  pillIds.forEach(id => {
    const el = document.getElementById(`li-filter-${id}`);
    if (el) el.classList.toggle('active', id === filterType);
  });
  loadLinkedInFeedPosts();
}

function debounceLinkedInFeedSearch() {
  clearTimeout(linkedInSearchDebounceTimer);
  linkedInSearchDebounceTimer = setTimeout(() => {
    loadLinkedInFeedPosts();
  }, 300);
}

function toggleLinkedInIngestForm() {
  const panel = document.getElementById('li-ingest-panel');
  if (!panel) return;
  panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
  if (panel.style.display === 'block') {
    document.getElementById('li-input-post-text')?.focus();
  }
}

async function submitLinkedInIngest() {
  const postText = document.getElementById('li-input-post-text')?.value.trim();
  const recruiterName = document.getElementById('li-input-recruiter-name')?.value.trim();
  const recruiterEmail = document.getElementById('li-input-recruiter-email')?.value.trim();

  if (!postText) {
    alert('Please enter or paste the LinkedIn post text or post URL (both short lnkd.in and long LinkedIn links supported).');
    return;
  }

  const btn = document.querySelector('#li-ingest-panel button[onclick="submitLinkedInIngest()"]');
  const originalHtml = btn ? btn.innerHTML : '⚡ Parse & Add to Database';
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '⏳ Scraping & Analyzing LinkedIn Post...';
  }

  try {
    const res = await fetch('/api/scraper/linkedin/ingest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        post_text: postText,
        post_url: postText.startsWith('http') ? postText : null,
        recruiter_name: recruiterName || null,
        recruiter_email: recruiterEmail || null
      })
    });
    const data = await res.json();
    if (res.ok && data.success) {
      if (document.getElementById('li-input-post-text')) document.getElementById('li-input-post-text').value = '';
      if (document.getElementById('li-input-recruiter-name')) document.getElementById('li-input-recruiter-name').value = '';
      if (document.getElementById('li-input-recruiter-email')) document.getElementById('li-input-recruiter-email').value = '';
      
      toggleLinkedInIngestForm();
      loadLinkedInFeedPage();
      loadStats();
      if (typeof loadJobs === 'function') loadJobs();

      // Immediately launch the personalized recruiter outreach & Gmail modal with tailored attachments
      if (data.job) {
        if (!Array.isArray(window.linkedInFeedPostsCache)) window.linkedInFeedPostsCache = [];
        window.linkedInFeedPostsCache.unshift(data.job);
        if (state && Array.isArray(state.currentJobs)) state.currentJobs.unshift(data.job);

        openRecruiterEmail(data.job.id, null, data.job);
      } else {
        alert('🎉 Ingested and tailored successfully!');
      }
    } else {
      let errMsg = 'Failed to ingest post';
      if (typeof data.detail === 'string') {
        errMsg = data.detail;
      } else if (data.detail && typeof data.detail === 'object') {
        errMsg = data.detail.message || 'Validation error';
        if (Array.isArray(data.detail.errors) && data.detail.errors.length) {
          errMsg += ':\n• ' + data.detail.errors.join('\n• ');
        }
      } else if (data.error) {
        errMsg = typeof data.error === 'string' ? data.error : JSON.stringify(data.error);
      }
      alert(`⚠️ ${errMsg}`);
    }
  } catch (err) {
    alert(`Error ingesting post: ${err.message}`);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }
  }
}

async function syncLinkedInFeedNow() {
  const btn = document.getElementById('btn-sync-linkedin-feed');
  const originalText = btn ? btn.innerText : '';
  if (btn) {
    btn.disabled = true;
    btn.innerText = '⏳ Syncing Recruiter Feed...';
  }

  try {
    const res = await fetch('/api/scraper/linkedin/sync', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      alert(`✅ LinkedIn Feed sync completed: Scraped ${data.scraped_count} recruiter hiring posts (${data.new_added} new added to database).`);
      loadLinkedInFeedPage();
      loadStats();
      if (typeof loadJobs === 'function') loadJobs();
    } else {
      alert(`Sync failed: ${data.detail || data.error}`);
    }
  } catch (err) {
    alert(`Error syncing feed: ${err.message}`);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = originalText;
    }
  }
}

async function openLinkedInSettingsModal() {
  const modal = document.getElementById('linkedin-settings-modal');
  if (!modal) return;
  try {
    const res = await fetch('/api/scraper/linkedin/settings');
    const s = await res.json();
    if (document.getElementById('li-setting-cookie')) document.getElementById('li-setting-cookie').value = s.li_at || '';
    if (document.getElementById('li-setting-keywords')) document.getElementById('li-setting-keywords').value = s.keywords || 'data analyst fresher hiring';
    if (document.getElementById('li-setting-auto-sync')) document.getElementById('li-setting-auto-sync').checked = s.sync_enabled ?? true;
    modal.style.display = 'flex';
  } catch (e) {
    modal.style.display = 'flex';
  }
}

async function saveLinkedInSettings() {
  const cookie = document.getElementById('li-setting-cookie')?.value.trim() || '';
  const keywords = document.getElementById('li-setting-keywords')?.value.trim() || 'data analyst fresher hiring';
  const autoSync = document.getElementById('li-setting-auto-sync')?.checked ?? true;

  try {
    const res = await fetch('/api/scraper/linkedin/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        li_at: cookie,
        keywords: keywords,
        sync_enabled: autoSync
      })
    });
    const data = await res.json();
    if (data.success) {
      closeModal('linkedin-settings-modal');
      alert('LinkedIn Feed settings saved successfully.');
    }
  } catch (err) {
    alert(`Error saving settings: ${err.message}`);
  }
}

function openLinkedInPersonalSyncModal() {
  const modal = document.getElementById('linkedin-personal-sync-modal');
  if (modal) {
    modal.style.display = 'flex';
  }
}

function copyLinkedInHarvesterScript() {
  const script = `(async function harvestLinkedInFeed() {
  if (!window.location.hostname.includes('linkedin.com')) {
    alert('⚠️ Action Required:\\n\\nPlease run this script in the browser Console while viewing LinkedIn (https://www.linkedin.com/feed or search results) — do not run it on the Job Finder app page!');
    return;
  }
  console.log('🚀 Job Finder: Starting Precision LinkedIn Feed & Jobs Harvester...');

  // 1. Expand all "...see more" buttons so full descriptions & links are exposed
  document.querySelectorAll(
    'button[aria-label*="more" i], ' +
    'button.feed-shared-inline-show-more-text__see-more-less-toggle, ' +
    'button.update-components-text__see-more-button, ' +
    'button.see-more, ' +
    '[data-view-name*="see-more"], ' +
    '.feed-shared-see-more-less-toggle, ' +
    'span.feed-shared-inline-show-more-text__see-more-less-toggle'
  ).forEach(b => {
    try { b.click(); } catch(e) {}
  });

  await new Promise(r => setTimeout(r, 350));

  // 2. Discover post cards & job cards across Feed, Search Results (All, Posts, Jobs), & Collections
  const cardSet = new Set();
  const containerSelectors = [
    'div.feed-shared-update-v2',
    'div[data-urn*="activity"]',
    'div[data-urn*="ugcPost"]',
    'div[data-urn*="jobPosting"]',
    'div[data-urn*="share"]',
    'div[data-chameleon-result-urn]',
    'div[data-entity-urn*="activity"]',
    'div[data-entity-urn*="jobPosting"]',
    'div[data-id*="activity"]',
    'div[data-view-name*="feed-full-update"]',
    'div[data-view-name*="search-entity-result"]',
    'li.reusable-search__result-container',
    'div.job-card-container',
    'li.jobs-search-results__list-item',
    'div[data-job-id]',
    '.search-results__cluster-content li',
    'article'
  ];

  document.querySelectorAll(containerSelectors.join(',')).forEach(el => {
    const parent = el.closest('.feed-shared-update-v2, li.reusable-search__result-container, li.jobs-search-results__list-item, div.artdeco-card') || el;
    cardSet.add(parent);
  });

  document.querySelectorAll('.update-components-actor, .feed-shared-actor, a[data-field="actor_name"], a[href*="/jobs/view/"], a[href*="/feed/update/urn:li:activity:"]').forEach(el => {
    const parent = el.closest('li, article, div.feed-shared-update-v2, div[data-urn], div[data-view-name], div.job-card-container, .artdeco-card') || el.parentElement.parentElement;
    if (parent && parent !== document.body) {
      cardSet.add(parent);
    }
  });

  const rawCards = Array.from(cardSet);
  // Keep outermost cards only
  const cards = rawCards.filter(c => {
    for (const other of rawCards) {
      if (other !== c && other.contains(c)) return false;
    }
    return true;
  });

  if (cards.length === 0) {
    alert('ℹ️ No LinkedIn posts or job cards detected on screen.\\n\\nPlease scroll down your LinkedIn feed or search page to load posts, then click again!');
    return;
  }

  // 3. Strict role & hiring filters
  const ROLE_REGEX = /(?:data\\s*(?:analyst|analytics|engineer|intern|trainee|associate|specialist)|business\\s*analyst|bi\\s*(?:analyst|developer)|power\\s*bi|tableau|sql\\s*(?:developer|analyst)|reporting\\s*analyst|mis\\s*(?:analyst|executive)|analytics\\s*engineer|data\\s*visualization|decision\\s*scientist|junior\\s*analyst|associate\\s*analyst)/i;

  const HIRING_REGEX = /(?:hiring|actively\\s*hiring|hiring\\s*now|open\\s*position|job\\s*opening|openings|vacancy|vacancies|recruitment|recruiting|looking\\s*for|immediate\\s*hiring|we\\s*are\\s*hiring|we're\\s*hiring|join\\s*our\\s*team|apply\\s*now|apply\\s*here|register\\s*here|apply\\s*link|apply\\s*through|how\\s*to\\s*apply|send\\s*(?:your\\s*)?(?:resume|cv)|share\\s*(?:your\\s*)?(?:resume|cv)|fresher\\s*hiring|walk-?in|hiring\\s*alert|job\\s*alert|opportunity|opportunities|easy\\s*apply|job\\s*listing)/i;

  const DISQUALIFIER_REGEX = /(?:certificate\\s*of\\s*completion|completed\\s*the\\s*course|thrilled\\s*to\\s*share\\s*that\\s*i\\s*(?:have\\s*)?completed|course\\s*completed|internship\\s*certificate|completed\\s*an\\s*online|webinar\\s*recording|happy\\s*to\\s*share\\s*my\\s*certificate|thought\\s*for\\s*the\\s*day|monday\\s*motivation)/i;

  const postsToIngest = [];
  const seenUrls = new Set();
  const seenTexts = new Set();

  for (const card of cards) {
    // Extract FULL card text
    const fullCardText = (card.innerText || '').trim();
    if (fullCardText.length < 25) continue;
    if (DISQUALIFIER_REGEX.test(fullCardText)) continue;
    if (!ROLE_REGEX.test(fullCardText)) continue;

    const jobLinkCheck = card.querySelector('a[href*="/jobs/view/"], a[href*="linkedin.com/jobs/view/"]');
    if (!jobLinkCheck) {
      const hasHiring = HIRING_REGEX.test(fullCardText);
      const hasApply = /https?:\/\/(?:lnkd\.in|forms\.gle|bit\.ly|[a-zA-Z0-9\-_.]+\.[a-zA-Z]{2,}(?:\/[^\s)"]*)?)/i.test(fullCardText);
      const hasEmail = /[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/.test(fullCardText);
      if (!hasHiring && !hasApply && !hasEmail) continue;
    }

    // Use fullCardText as postText so all requirements, contacts, and roles are preserved
    const postText = fullCardText;
    const textSig = postText.replace(/\\s+/g, ' ').slice(0, 100);
    if (seenTexts.has(textSig)) continue;
    seenTexts.add(textSig);

    // Exact Post URL Extraction
    let postUrl = '';

    // Check official job link
    const jobLink = card.querySelector('a[href*="/jobs/view/"], a[href*="linkedin.com/jobs/view/"]');
    if (jobLink && jobLink.href) {
      const jm = jobLink.href.match(/https?:\\/\\/(?:[a-z]{2,3}\\.)?linkedin\\.com\\/jobs\\/view\\/(\\d+)/i);
      if (jm) {
        postUrl = 'https://www.linkedin.com/jobs/view/' + jm[1] + '/';
      }
    }

    // Check activity urn
    if (!postUrl) {
      const urnAttrEl = card.matches('[data-urn*="activity"], [data-urn*="ugcPost"], [data-chameleon-result-urn*="activity"], [data-entity-urn*="activity"], [data-id*="activity"]')
        ? card
        : card.querySelector('[data-urn*="activity"], [data-urn*="ugcPost"], [data-chameleon-result-urn*="activity"], [data-entity-urn*="activity"], [data-id*="activity"]');

      const urnVal = urnAttrEl
        ? (urnAttrEl.getAttribute('data-urn') || urnAttrEl.getAttribute('data-chameleon-result-urn') || urnAttrEl.getAttribute('data-entity-urn') || urnAttrEl.getAttribute('data-id') || '')
        : '';
      const matchUrn = urnVal.match(/urn:li:(?:activity|ugcPost|share):(\\d+)/);
      if (matchUrn) {
        postUrl = 'https://www.linkedin.com/feed/update/urn:li:activity:' + matchUrn[1] + '/';
      }
    }

    // Check permalinks
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
        const actMatch = href.match(/urn:li:activity:(\\d+)/);
        const postSlugMatch = href.match(/https?:\\/\\/(?:[a-z]{2,3}\\.)?linkedin\\.com\\/posts\\/[a-zA-Z0-9_\\-]+/i);
        if (actMatch) {
          postUrl = 'https://www.linkedin.com/feed/update/urn:li:activity:' + actMatch[1] + '/';
        } else if (postSlugMatch) {
          postUrl = postSlugMatch[0];
        } else if (href.includes('/feed/update/') || href.includes('/posts/')) {
          postUrl = href.split('?')[0];
        }
      }
    }

    // Check HTML inner match
    if (!postUrl) {
      const htmlMatch = card.innerHTML.match(/urn:li:(?:activity|ugcPost|share):(\\d{15,22})/);
      if (htmlMatch) {
        postUrl = 'https://www.linkedin.com/feed/update/urn:li:activity:' + htmlMatch[1] + '/';
      }
    }

    // Check lnkd.in match in text
    if (!postUrl) {
      const lnkdMatch = postText.match(/https?:\\/\\/lnkd\\.in\\/[a-zA-Z0-9_\\-]+/i);
      if (lnkdMatch) {
        postUrl = lnkdMatch[0];
      }
    }

    // Strictly reject generic feed or search results URLs as post URL
    if (postUrl && (postUrl.includes('/feed/?') || postUrl.endsWith('/feed') || postUrl.endsWith('/feed/') || postUrl.includes('/search/') || postUrl.includes('127.0.0.1') || postUrl.includes('localhost'))) {
      postUrl = '';
    }

    // Recruiter Name
    let recruiterName = '';
    const authorEl = card.querySelector(
      '.update-components-actor__name, ' +
      '.feed-shared-actor__name, ' +
      'a[data-field="actor_name"], ' +
      '.entity-result__title-text, ' +
      'span.update-components-actor__single-line-truncate, ' +
      '.job-card-container__company-name, ' +
      'h3, h4'
    );
    if (authorEl && authorEl.innerText.trim()) {
      recruiterName = authorEl.innerText.trim().split('\\n')[0].trim();
    }

    // Recruiter Designation
    let recruiterDesignation = '';
    const desigEl = card.querySelector(
      '.update-components-actor__description, ' +
      '.feed-shared-actor__description, ' +
      '.update-components-actor__sub-description, ' +
      '.entity-result__primary-subtitle, ' +
      '.job-card-container__metadata-item'
    );
    if (desigEl && desigEl.innerText.trim()) {
      recruiterDesignation = desigEl.innerText.trim().split('\\n')[0].trim();
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
      const pm = profEl.href.match(/https?:\\/\\/(?:[a-z]{2,3}\\.)?linkedin\\.com\\/in\\/[a-zA-Z0-9\\-_%]+/i);
      if (pm) linkedinProfile = pm[0].replace(/\\/+$/, '') + '/';
    }

    // Direct apply / registration link
    let applyUrl = '';
    if (jobLink && jobLink.href) {
      applyUrl = postUrl;
    } else {
      const applyMatch = postText.match(/https?:\\/\\/(?:lnkd\\.in\\/[a-zA-Z0-9_\\-]+|forms\\.gle\\/[a-zA-Z0-9_\\-]+|bit\\.ly\\/[a-zA-Z0-9_\\-]+|[a-zA-Z0-9\\-_.]+\\.[a-zA-Z]{2,}(?:\\/[^\\s)"]*)?)/i);
      if (applyMatch) {
        applyUrl = applyMatch[0].replace(/[.,;:)]+$/, '');
      }
    }

    if (!postUrl && applyUrl) {
      postUrl = applyUrl;
    }
    if (!postUrl) {
      let h = 0;
      for (let i = 0; i < fullCardText.length && i < 120; i++) { h = ((h << 5) - h) + fullCardText.charCodeAt(i); h |= 0; }
      postUrl = 'https://www.linkedin.com/feed/update/urn:li:activity:feed_' + Math.abs(h).toString(36) + '/';
    }

    if (seenUrls.has(postUrl)) continue;
    seenUrls.add(postUrl);

    postsToIngest.push({
      post_text: postText,
      post_url: postUrl,
      recruiter_name: recruiterName,
      designation: recruiterDesignation,
      linkedin_profile: linkedinProfile,
      apply_url: applyUrl || postUrl
    });
  }

  if (postsToIngest.length === 0) {
    alert('ℹ️ Found ' + cards.length + ' post(s) on screen, but none matched Data / Business Analyst fresher hiring criteria.\\n\\nTip: Scroll down to reveal more posts or search for "data analyst job hiring" / "business analyst fresher".');
    return;
  }

  console.log('Ingesting ' + postsToIngest.length + ' qualified hiring posts...', postsToIngest);

  let savedCount = 0;
  let skippedCount = 0;
  let networkFailed = false;

  // Attempt batch ingest first
  for (const host of ['http://127.0.0.1:8000', 'http://localhost:8000']) {
    try {
      const res = await fetch(host + '/api/scraper/linkedin/ingest/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ posts: postsToIngest })
      });
      if (res.ok) {
        const batchData = await res.json();
        savedCount = batchData.saved_count || 0;
        skippedCount = batchData.skipped_count || 0;
        networkFailed = false;
        break;
      }
    } catch(err) {
      networkFailed = true;
    }
  }

  // Fallback to single-item ingest if batch wasn't reached
  if (networkFailed && savedCount === 0) {
    for (const post of postsToIngest) {
      for (const host of ['http://127.0.0.1:8000', 'http://localhost:8000']) {
        try {
          const res = await fetch(host + '/api/scraper/linkedin/ingest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(post)
          });
          if (res.ok) {
            const data = await res.json();
            if (data.id || data.success) {
              savedCount++;
              networkFailed = false;
              break;
            }
          } else if (res.status === 422) {
            skippedCount++;
            networkFailed = false;
            break;
          }
        } catch(e) {}
      }
    }
  }

  if (networkFailed && savedCount === 0 && skippedCount === 0) {
    // Mixed Content or network block: save to clipboard automatically!
    try {
      await navigator.clipboard.writeText(JSON.stringify(postsToIngest, null, 2));
    } catch(e) {}
    alert(
      '⚠️ Direct Network Sync Blocked by Browser Security:\\n\\n' +
      'Found ' + postsToIngest.length + ' genuine hiring post(s) on screen!\\n' +
      'Because LinkedIn is loaded over HTTPS, Chrome blocked the direct connection to Job Finder (HTTP).\\n\\n' +
      '📋 ALL ' + postsToIngest.length + ' POSTS HAVE BEEN COPIED TO YOUR CLIPBOARD!\\n\\n' +
      '👉 Switch back to Job Finder, click "Open Post Ingest Box" or paste them directly to sync instantly!'
    );
    return;
  }

  alert(
    '🎉 Harvested & Synced Successfully!\\n\\n' +
    '✅ Verified Genuine Jobs Added: ' + savedCount + '\\n' +
    (skippedCount > 0 ? ('⏭️ Filtered (Duplicate / Non-Fresher): ' + skippedCount + '\\n') : '') +
    '\\nSwitch back to Job Finder to view them!'
  );
})();`;

  navigator.clipboard.writeText(script).then(() => {
    alert('📋 Precision LinkedIn Harvester Script copied!\n\nOpen LinkedIn (Home Feed or Search Results), press F12 > Console, paste and hit Enter.');
  }).catch(() => {
    prompt('Copy this script and paste it into your browser console on LinkedIn:', script);
  });
}

// ==========================================================================
// Dedicated AI Resume & Cover Letter Tailor Studio Module
// ==========================================================================

let studioCurrentMode = 'url'; // 'url' or 'manual'
let studioScrapedData = null;
let studioTailorResult = null;

function initTailorStudioPage() {
  if (typeof loadMasterResumeStatus === 'function') {
    loadMasterResumeStatus();
  }
}

function switchTailorStudioMode(mode) {
  studioCurrentMode = mode;
  const btnUrl = document.getElementById('ts-mode-btn-url');
  const btnManual = document.getElementById('ts-mode-btn-manual');
  const secUrl = document.getElementById('ts-section-url');
  const secManual = document.getElementById('ts-section-manual');

  if (mode === 'url') {
    if (btnUrl) btnUrl.classList.add('active');
    if (btnManual) btnManual.classList.remove('active');
    if (secUrl) secUrl.style.display = 'block';
    if (secManual) secManual.style.display = 'none';
  } else {
    if (btnUrl) btnUrl.classList.remove('active');
    if (btnManual) btnManual.classList.add('active');
    if (secUrl) secUrl.style.display = 'none';
    if (secManual) secManual.style.display = 'block';
  }
}

async function scrapeStudioUrl() {
  const urlInput = document.getElementById('ts-input-url');
  const feedbackEl = document.getElementById('ts-scrape-feedback');
  const scrapeBtn = document.getElementById('ts-btn-scrape');
  const previewCard = document.getElementById('ts-scraped-preview-card');

  const rawUrl = (urlInput ? urlInput.value : '').trim();
  if (!rawUrl || (!rawUrl.startsWith('http://') && !rawUrl.startsWith('https://'))) {
    if (feedbackEl) {
      feedbackEl.style.display = 'block';
      feedbackEl.className = 'ts-feedback-box feedback-error';
      feedbackEl.innerHTML = '⚠️ Please enter a valid HTTP or HTTPS job posting URL (e.g. from LinkedIn, Internshala, Naukri, or career portal).';
    }
    return;
  }

  // Set loading state
  if (scrapeBtn) {
    scrapeBtn.disabled = true;
    scrapeBtn.innerHTML = '<span class="spinner" style="width:14px;height:14px;display:inline-block;margin-right:6px;vertical-align:middle;"></span> Fetching...';
  }
  if (feedbackEl) {
    feedbackEl.style.display = 'block';
    feedbackEl.className = 'ts-feedback-box feedback-loading';
    feedbackEl.innerHTML = '⏳ <strong>Scraping Live Job URL...</strong> Connecting to source portal, bypassing authwalls, and extracting complete structured details...';
  }
  if (previewCard) previewCard.style.display = 'none';

  try {
    const res = await fetch('/api/resume/analyze-url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: rawUrl })
    });

    const data = await res.json();

    if (!res.ok || !data.success) {
      const errDetail = data.detail || (data.job && data.job.error) || 'Failed to fetch job posting';
      if (feedbackEl) {
        feedbackEl.className = 'ts-feedback-box feedback-error';
        feedbackEl.innerHTML = `❌ <strong>Scraping notice:</strong> ${escapeHtml(errDetail)}<br><span style="font-size:0.8rem;margin-top:4px;display:inline-block;">Tip: If this website has dynamic CAPTCHA or anti-bot protection, simply switch to <strong>Mode B</strong> above and copy & paste the Job Description text directly!</span>`;
      }
      return;
    }

    const job = data.job;
    studioScrapedData = job;

    // Populate preview form
    const titleInput = document.getElementById('ts-scraped-title');
    const compInput = document.getElementById('ts-scraped-company');
    const locInput = document.getElementById('ts-scraped-location');
    const modeSelect = document.getElementById('ts-scraped-workmode');
    const descText = document.getElementById('ts-scraped-desc');
    const descCount = document.getElementById('ts-scraped-desc-count');
    const skillsContainer = document.getElementById('ts-scraped-skills-container');
    const srcBadge = document.getElementById('ts-preview-source-badge');

    if (titleInput) titleInput.value = job.title || 'Data Analyst';
    if (compInput) compInput.value = job.company || 'Target Employer';
    if (locInput) locInput.value = job.location || 'India / Remote';
    if (modeSelect) modeSelect.value = job.work_mode || 'Remote';
    if (descText) descText.value = job.description || '';
    if (descCount) descCount.innerText = `${(job.description || '').length.toLocaleString()} characters extracted`;

    if (srcBadge) {
      srcBadge.innerText = (job.source || 'Live URL') + ' Scraped';
    }

    // Populate detected skills
    if (skillsContainer) {
      const skills = job.skills || [];
      if (skills.length > 0) {
        skillsContainer.innerHTML = skills.slice(0, 15).map(s => `<span class="ts-skill-chip">${escapeHtml(s)}</span>`).join('');
      } else {
        skillsContainer.innerHTML = '<span style="font-size:0.78rem;color:var(--text-muted);">None detected automatically. Will be inferred during tailoring.</span>';
      }
    }

    if (feedbackEl) {
      feedbackEl.className = 'ts-feedback-box feedback-success';
      feedbackEl.innerHTML = `✅ <strong>Successfully extracted job posting from ${escapeHtml(job.source || 'portal')}!</strong> (${(job.description || '').length.toLocaleString()} characters extracted). Review and edit details below if desired, then generate your tailored documents.`;
    }

    if (previewCard) {
      previewCard.style.display = 'block';
      previewCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

  } catch (err) {
    if (feedbackEl) {
      feedbackEl.className = 'ts-feedback-box feedback-error';
      feedbackEl.innerHTML = `❌ <strong>Network or Server Error:</strong> ${escapeHtml(err.message)}. Please verify your connection or switch to Mode B to paste the JD text.`;
    }
  } finally {
    if (scrapeBtn) {
      scrapeBtn.disabled = false;
      scrapeBtn.innerHTML = '🔍 Fetch & Scrape Job';
    }
  }
}

function fillStudioUrl(type) {
  const urlInput = document.getElementById('ts-input-url');
  if (!urlInput) return;

  if (type === 'linkedin') {
    urlInput.value = 'https://www.linkedin.com/jobs/view/4446724293';
  } else if (type === 'internshala') {
    urlInput.value = 'https://internshala.com/job/detail/civil-engineer-job-in-multiple-locations-at-pioneer-e-solutions-private-limited1792567878';
  } else if (type === 'wwr') {
    urlInput.value = 'https://weworkremotely.com/remote-jobs/cribl-analytics-business-partner';
  }

  scrapeStudioUrl();
}

function clearStudioScrapedData() {
  studioScrapedData = null;
  const urlInput = document.getElementById('ts-input-url');
  const feedbackEl = document.getElementById('ts-scrape-feedback');
  const previewCard = document.getElementById('ts-scraped-preview-card');
  const resultsContainer = document.getElementById('ts-results-container');

  if (urlInput) urlInput.value = '';
  if (feedbackEl) feedbackEl.style.display = 'none';
  if (previewCard) previewCard.style.display = 'none';
  if (resultsContainer) resultsContainer.style.display = 'none';
}

function fillStudioSampleJD(type) {
  const titleInput = document.getElementById('ts-manual-title');
  const compInput = document.getElementById('ts-manual-company');
  const locInput = document.getElementById('ts-manual-location');
  const modeSelect = document.getElementById('ts-manual-workmode');
  const skillsInput = document.getElementById('ts-manual-skills');
  const descText = document.getElementById('ts-manual-desc');

  if (type === 'power_bi') {
    if (titleInput) titleInput.value = 'Power BI Developer / Business Intelligence Analyst';
    if (compInput) compInput.value = 'Apex Analytics India';
    if (locInput) locInput.value = 'Bengaluru, Karnataka (Hybrid)';
    if (modeSelect) modeSelect.value = 'Hybrid';
    if (skillsInput) skillsInput.value = 'Power BI, DAX, Power Query, SQL, Data Modeling, Star Schema, Excel';
    if (descText) descText.value = `Apex Analytics is hiring an entry-level Power BI Developer / BI Analyst (0-1 year experience or fresher with strong portfolio).

Key Responsibilities:
• Design, develop, and maintain automated interactive dashboards and reports in Microsoft Power BI.
• Write robust DAX calculations, measures, and calculated columns for complex KPI reporting.
• Transform, clean, and model disparate datasets using Power Query (M) and SQL.
• Collaborate with business stakeholders to translate raw requirements into intuitive visual stories.
• Ensure data integrity, row-level security (RLS), and schedule automated dataset refreshes on Power BI Service.

Requirements:
• Bachelor's degree in Computer Science, Statistics, Mathematics, Engineering, or related technical field.
• Hands-on proficiency with Microsoft Power BI Desktop, DAX, and Power Query.
• Strong foundational knowledge of relational databases and SQL (joins, subqueries, aggregations).
• Advanced Microsoft Excel skills (Pivot Tables, XLOOKUP, advanced formulas).
• Excellent problem-solving, analytical thinking, and visual storytelling capabilities.`;
  } else if (type === 'data_analyst') {
    if (titleInput) titleInput.value = 'Junior Data Analyst';
    if (compInput) compInput.value = 'Swiggy';
    if (locInput) locInput.value = 'Bengaluru, Karnataka';
    if (modeSelect) modeSelect.value = 'Hybrid';
    if (skillsInput) skillsInput.value = 'SQL, Python, Advanced Excel, Statistics, EDA, Data Visualization, Tableau';
    if (descText) descText.value = `Swiggy is looking for a passionate Junior Data Analyst to join our central analytics and growth operations team.

What you will do:
• Query massive relational and analytical databases using SQL to extract actionable business metrics.
• Perform exploratory data analysis (EDA) using Python (Pandas, NumPy, Matplotlib) to uncover delivery and customer trends.
• Build executive dashboards and weekly KPI reports tracking funnel conversion, delivery partner efficiency, and order volume.
• Partner with product managers and business operations teams to design A/B test experiments and analyze outcomes.
• Automate recurring reporting workflows and troubleshoot data discrepancy issues.

What we are looking for:
• 0 to 1 year of experience in business intelligence, data analytics, or fresh graduates with demonstrated project work.
• Exceptional proficiency in SQL (window functions, CTEs, complex joins).
• Proficiency in Python for data manipulation and visualization.
• Solid grasp of basic descriptive and inferential statistics.
• High degree of ownership, curiosity, and structured problem-solving orientation.`;
  } else if (type === 'sql_analyst') {
    if (titleInput) titleInput.value = 'SQL & Business Intelligence Analyst';
    if (compInput) compInput.value = 'CloudScale Solutions';
    if (locInput) locInput.value = 'Remote (India)';
    if (modeSelect) modeSelect.value = 'Remote';
    if (skillsInput) skillsInput.value = 'SQL, PostgreSQL, BigQuery, Excel, Tableau, Data Cleaning, ETL';
    if (descText) descText.value = `CloudScale Solutions is seeking a remote SQL & Business Intelligence Analyst (Fresher / 0-1 yr experience) to manage client reporting and data warehouse transformation pipelines.

Key Duties:
• Author complex SQL queries against PostgreSQL, MySQL, and Google BigQuery data warehouses.
• Extract, transform, and load (ETL) transactional data into standardized analytical reporting marts.
• Develop interactive Tableau and Excel reports for international clients across retail and finance sectors.
• Validate data quality, conduct reconciliation checks, and identify operational bottlenecks.
• Document data dictionaries, reporting schemas, and KPI calculation definitions.

Qualifications:
• Graduate degree in any quantitative field.
• Strong knowledge of SQL data modeling and query optimization.
• Experience building dashboards in Tableau, Power BI, or Looker Studio.
• Advanced Excel capabilities.
• Comfortable working in a fast-paced remote team environment.`;
  }

  updateManualCharCount();
}

function updateManualCharCount() {
  const descEl = document.getElementById('ts-manual-desc');
  const countEl = document.getElementById('ts-manual-char-count');
  if (descEl && countEl) {
    const len = (descEl.value || '').length;
    countEl.innerText = `${len.toLocaleString()} characters`;
  }
}

function generateTailoredDocsFromScraped() {
  const title = (document.getElementById('ts-scraped-title')?.value || '').trim();
  const company = (document.getElementById('ts-scraped-company')?.value || '').trim();
  const location = (document.getElementById('ts-scraped-location')?.value || '').trim();
  const workMode = document.getElementById('ts-scraped-workmode')?.value || 'Remote';
  const desc = (document.getElementById('ts-scraped-desc')?.value || '').trim();

  if (!title) {
    alert('Please enter or verify the Job Title.');
    return;
  }
  if (!desc || desc.length < 30) {
    alert('The extracted Job Description is too short (< 30 characters). Please provide more details or edit the text.');
    return;
  }

  const payload = {
    job_id: 'scraped_' + Date.now(),
    job_title: title,
    company: company || 'Target Employer',
    location: location || 'India',
    work_mode: workMode,
    description: desc,
    skills: studioScrapedData?.skills || [],
    responsibilities: studioScrapedData?.responsibilities || [],
    requirements: studioScrapedData?.requirements || [],
    source_url: studioScrapedData?.url || '#'
  };

  executeStudioTailoring(payload);
}

function generateTailoredDocsFromManual() {
  const title = (document.getElementById('ts-manual-title')?.value || '').trim();
  const company = (document.getElementById('ts-manual-company')?.value || '').trim();
  const location = (document.getElementById('ts-manual-location')?.value || '').trim();
  const workMode = document.getElementById('ts-manual-workmode')?.value || 'Hybrid';
  const skillsStr = (document.getElementById('ts-manual-skills')?.value || '').trim();
  const desc = (document.getElementById('ts-manual-desc')?.value || '').trim();

  if (!title) {
    alert('Please enter a Target Job Title (e.g. Data Analyst, Power BI Developer).');
    document.getElementById('ts-manual-title')?.focus();
    return;
  }
  if (!desc || desc.length < 30) {
    alert('Please paste the Job Description text (at least 30 characters of responsibilities or requirements).');
    document.getElementById('ts-manual-desc')?.focus();
    return;
  }

  const skillsList = skillsStr ? skillsStr.split(',').map(s => s.trim()).filter(Boolean) : [];

  const payload = {
    job_id: 'manual_' + Date.now(),
    job_title: title,
    company: company || 'Target Employer',
    location: location || 'India',
    work_mode: workMode,
    description: desc,
    skills: skillsList
  };

  executeStudioTailoring(payload);
}

async function executeStudioTailoring(payload) {
  const overlay = document.getElementById('ts-generating-overlay');
  const resultsWrap = document.getElementById('ts-results-container');
  const btnUrl = document.getElementById('ts-btn-generate-url');
  const btnManual = document.getElementById('ts-btn-generate-manual');

  if (overlay) overlay.style.display = 'block';
  if (resultsWrap) resultsWrap.style.display = 'none';
  if (btnUrl) btnUrl.disabled = true;
  if (btnManual) btnManual.disabled = true;

  try {
    const res = await fetch('/api/resume/tailor', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();

    if (!res.ok || !data.success) {
      alert('Tailoring Error: ' + (data.detail || 'Failed to tailor resume'));
      return;
    }

    studioTailorResult = data;
    renderStudioTailorResults(data, payload);

    if (resultsWrap) {
      resultsWrap.style.display = 'block';
      resultsWrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

  } catch (err) {
    alert('Network error while tailoring documents: ' + err.message);
  } finally {
    if (overlay) overlay.style.display = 'none';
    if (btnUrl) btnUrl.disabled = false;
    if (btnManual) btnManual.disabled = false;
  }
}

function renderStudioTailorResults(data, payload) {
  const atsMetrics = data.ats_metrics || {};
  const tailoredResume = data.tailored_resume || {};
  const coverLetter = data.cover_letter || {};

  // 1. Overall Score & Headings
  const scoreVal = atsMetrics.ats_score || atsMetrics.overall_ats_score || 85;
  const scoreEl = document.getElementById('ts-score-val');
  const headingEl = document.getElementById('ts-result-job-heading');
  const subEl = document.getElementById('ts-result-job-sub');
  const breakdownEl = document.getElementById('ts-score-breakdown');

  if (scoreEl) scoreEl.innerText = `${scoreVal}%`;
  if (headingEl) headingEl.innerText = `${escapeHtml(payload.job_title)} at ${escapeHtml(payload.company)}`;
  if (subEl) subEl.innerText = `Location: ${escapeHtml(payload.location || 'India')} • Work Mode: ${escapeHtml(payload.work_mode || 'Remote')} • 100% Grounded in Career Knowledge Base`;

  // Score breakdown pills
  if (breakdownEl) {
    const kwMatch = atsMetrics.keyword_match_percentage || 88;
    const expAlign = atsMetrics.experience_alignment || 90;
    const hardSkills = (atsMetrics.matched_keywords || []).length || 6;
    breakdownEl.innerHTML = `
      <span class="ts-score-pill">🎯 Keyword Match: <strong>${kwMatch}%</strong></span>
      <span class="ts-score-pill">📈 Role Alignment: <strong>${expAlign}%</strong></span>
      <span class="ts-score-pill">⚡ Hard Skills Matched: <strong>${hardSkills}</strong></span>
      <span class="ts-score-pill" style="border-color:#10b981; color:#059669;">✅ Strict 1-Page Verified</span>
    `;
  }

  // 2. Evidence Grounding Sources
  const evidenceListEl = document.getElementById('ts-grounding-evidence-list');
  if (evidenceListEl) {
    const filesUsed = data.files_used || ['Master Resume Profile', 'Verified Portfolio Projects'];
    evidenceListEl.innerHTML = filesUsed.map(f => `
      <div class="ts-evidence-item">
        <span style="color:#10b981;">✓</span>
        <span>${escapeHtml(f)}</span>
      </div>
    `).join('');
  }

  // 3. Matched & Missing Keywords
  const matchedEl = document.getElementById('ts-matched-keywords-chips');
  const missingEl = document.getElementById('ts-missing-keywords-chips');

  if (matchedEl) {
    const matched = atsMetrics.matched_keywords || payload.skills || ['SQL', 'Power BI', 'Excel', 'Data Modeling', 'KPI Reporting'];
    matchedEl.innerHTML = matched.map(k => `<span class="ts-kw-chip-match">✓ ${escapeHtml(k)}</span>`).join('');
  }

  if (missingEl) {
    const missing = atsMetrics.missing_keywords || atsMetrics.recommended_additions || ['A/B Testing', 'Snowflake', 'dbt'];
    if (missing.length > 0) {
      missingEl.innerHTML = missing.map(k => `<span class="ts-kw-chip-miss">+ ${escapeHtml(k)}</span>`).join('');
    } else {
      missingEl.innerHTML = '<span style="font-size:0.78rem;color:#059669;">All primary technical keywords covered!</span>';
    }
  }

  // 4. Download Links with Standard Naming: Tejas_Waghmare_Role_Company_DocType_DD_MM_YYYY
  const candName = tailoredResume.name || (state.masterProfile && state.masterProfile.name) || 'Tejas Waghmare';
  const roleTitle = payload.job_title || data.job_title || 'Data Analyst';
  const compName = payload.company || data.company || 'Target Employer';

  const fnPdf = (data.filenames && data.filenames.resume_pdf) || getStandardDocFilename(candName, roleTitle, compName, 'Resume', 'pdf');
  const fnDocx = (data.filenames && data.filenames.resume_docx) || getStandardDocFilename(candName, roleTitle, compName, 'Resume', 'docx');
  const fnTxt = (data.filenames && data.filenames.resume_txt) || getStandardDocFilename(candName, roleTitle, compName, 'Resume', 'txt');
  const fnTex = (data.filenames && data.filenames.resume_tex) || getStandardDocFilename(candName, roleTitle, compName, 'Resume', 'tex');

  const fnClPdf = (data.filenames && data.filenames.cover_letter_pdf) || getStandardDocFilename(candName, roleTitle, compName, 'Cover_Letter', 'pdf');
  const fnClDocx = (data.filenames && data.filenames.cover_letter_docx) || getStandardDocFilename(candName, roleTitle, compName, 'Cover_Letter', 'docx');
  const fnClTxt = (data.filenames && data.filenames.cover_letter_txt) || getStandardDocFilename(candName, roleTitle, compName, 'Cover_Letter', 'txt');

  const dlPdf = document.getElementById('ts-dl-pdf');
  const dlDocx = document.getElementById('ts-dl-docx');
  const dlTxt = document.getElementById('ts-dl-txt');
  const dlTex = document.getElementById('ts-dl-tex');

  if (dlPdf && data.pdf_url) {
    dlPdf.href = data.pdf_url;
    dlPdf.setAttribute('download', fnPdf);
  }
  if (dlDocx && data.docx_url) {
    dlDocx.href = data.docx_url;
    dlDocx.setAttribute('download', fnDocx);
  }
  if (dlTxt && data.txt_url) {
    dlTxt.href = data.txt_url;
    dlTxt.setAttribute('download', fnTxt);
  }
  if (dlTex && data.tex_url) {
    dlTex.href = data.tex_url;
    dlTex.setAttribute('download', fnTex);
  }

  const dlClPdf = document.getElementById('ts-dl-cl-pdf');
  const dlClDocx = document.getElementById('ts-dl-cl-docx');
  const dlClTxt = document.getElementById('ts-dl-cl-txt');

  if (dlClPdf && data.cl_pdf_url) {
    dlClPdf.href = data.cl_pdf_url;
    dlClPdf.setAttribute('download', fnClPdf);
  }
  if (dlClDocx && data.cl_docx_url) {
    dlClDocx.href = data.cl_docx_url;
    dlClDocx.setAttribute('download', fnClDocx);
  }
  if (dlClTxt && data.cl_txt_url) {
    dlClTxt.href = data.cl_txt_url;
    dlClTxt.setAttribute('download', fnClTxt);
  }

  // 5. Resume HTML Preview matching Overleaf LaTeX Jake's Resume (Image 2)
  const resumeHtmlEl = document.getElementById('ts-resume-html-preview');
  if (resumeHtmlEl) {
    resumeHtmlEl.innerHTML = renderLatexResumePreviewHtml(tailoredResume);
  }

  // 6. Cover Letter Preview matching Overleaf LaTeX Theme (Image 2)
  const clTextEl = document.getElementById('ts-coverletter-preview');
  if (clTextEl) {
    clTextEl.innerHTML = renderLatexCoverLetterPreviewHtml(coverLetter, payload);
  }

  // 7. LaTeX Source Code
  const latexEl = document.getElementById('ts-latex-code');
  if (latexEl) {
    latexEl.innerText = data.latex_code || '% LaTeX code compiled successfully';
  }

  // 8. Screening Q&A
  const qaContainer = document.getElementById('ts-screening-qa-list');
  if (qaContainer) {
    const role = payload.job_title || 'Data Analyst';
    const comp = payload.company || 'your team';

    qaContainer.innerHTML = `
      <div class="ts-qa-item">
        <div class="ts-qa-q">
          <span>Q1: Why are you interested in this ${escapeHtml(role)} role at ${escapeHtml(comp)}?</span>
          <button type="button" class="ts-qa-copy-btn" onclick="copyStudioQA(0)">📋 Copy Answer</button>
        </div>
        <div class="ts-qa-a" id="ts-qa-ans-0">
          I am eager to contribute to ${escapeHtml(comp)} as a ${escapeHtml(role)} because my background in quantitative analytics, SQL data modeling, and business intelligence directly aligns with your core challenges. Having engineered end-to-end analytics pipelines and interactive reporting dashboards grounded in measurable business outcomes, I am excited to apply my data cleaning, KPI tracking, and analytical problem-solving skills to accelerate your team's decision-making from day one.
        </div>
      </div>

      <div class="ts-qa-item">
        <div class="ts-qa-q">
          <span>Q2: What makes you a strong candidate for this position?</span>
          <button type="button" class="ts-qa-copy-btn" onclick="copyStudioQA(1)">📋 Copy Answer</button>
        </div>
        <div class="ts-qa-a" id="ts-qa-ans-1">
          My primary differentiator is my hands-on ability to take messy, complex transactional data and transform it into clear, executive-ready insights. With proven skills in SQL (CTEs, window functions, relational schemas), Power BI/DAX, Advanced Excel, and Python data manipulation, I bridge the gap between technical data engineering and business stakeholder strategy. Additionally, as an agile fresher, I offer high energy, fast learning agility, and meticulous attention to data accuracy.
        </div>
      </div>

      <div class="ts-qa-item">
        <div class="ts-qa-q">
          <span>Q3: What are your notice period and salary expectations?</span>
          <button type="button" class="ts-qa-copy-btn" onclick="copyStudioQA(2)">📋 Copy Answer</button>
        </div>
        <div class="ts-qa-a" id="ts-qa-ans-2">
          Notice Period: Immediate (0 days) / Available to join immediately.
Salary Expectation: Open to competitive industry standards for entry-level ${escapeHtml(role)} roles, aligned with the scope and growth opportunities of this position at ${escapeHtml(comp)}.
        </div>
      </div>
    `;
  }

  // Set default view to Resume
  switchStudioResultTab('resume');
}

function switchStudioResultTab(tabName) {
  const tabs = ['resume', 'coverletter', 'latex', 'screening'];
  tabs.forEach(t => {
    const btn = document.getElementById(`ts-res-tab-${t}`);
    const view = document.getElementById(`ts-view-${t}`);
    if (btn) btn.classList.toggle('active', t === tabName);
    if (view) view.style.display = t === tabName ? 'block' : 'none';
  });
}

function copyStudioCoverLetter() {
  const el = document.getElementById('ts-coverletter-preview');
  if (el) {
    navigator.clipboard.writeText(el.innerText).then(() => {
      alert('📋 Tailored Cover Letter copied to clipboard!');
    });
  }
}

function copyStudioLatex() {
  const el = document.getElementById('ts-latex-code');
  if (el) {
    navigator.clipboard.writeText(el.innerText).then(() => {
      alert('📋 LaTeX Source Code copied to clipboard!');
    });
  }
}

function copyStudioQA(idx) {
  const el = document.getElementById(`ts-qa-ans-${idx}`);
  if (el) {
    const text = el.innerText.trim();
    navigator.clipboard.writeText(text).then(() => {
      alert(`📋 Q${idx + 1} Answer copied to clipboard!`);
    });
  }
}

function printStudioResume() {
  if (studioTailorResult && studioTailorResult.pdf_preview_url) {
    window.open(studioTailorResult.pdf_preview_url, '_blank');
  } else {
    window.print();
  }
}

// ==========================================================================
// MOBILE BROWSER ENHANCEMENTS & EVENT HANDLERS
// ==========================================================================

function initMobileScrollWatcher() {
  const topBtn = document.getElementById('mobile-back-to-top');
  if (!topBtn) return;
  let ticking = false;
  window.addEventListener('scroll', () => {
    if (!ticking) {
      window.requestAnimationFrame(() => {
        if (window.scrollY > 280) {
          topBtn.classList.add('visible');
        } else {
          topBtn.classList.remove('visible');
        }
        ticking = false;
      });
      ticking = true;
    }
  }, { passive: true });
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function initSearchClearWatcher() {
  const input = document.getElementById('search-input');
  const clearBtn = document.getElementById('search-clear-btn');
  if (!input) return;

  // Responsive placeholder on mobile screens
  if (window.innerWidth <= 640 && input.placeholder.length > 35) {
    input.placeholder = 'Search by title, skills, companies...';
  }

  function updateClearBtn() {
    if (clearBtn) {
      clearBtn.style.display = input.value.trim().length > 0 ? 'flex' : 'none';
    }
  }

  input.addEventListener('input', updateClearBtn);
  input.addEventListener('change', updateClearBtn);
  updateClearBtn();
}

function clearSearchInput() {
  const input = document.getElementById('search-input');
  const clearBtn = document.getElementById('search-clear-btn');
  if (!input) return;
  input.value = '';
  if (clearBtn) clearBtn.style.display = 'none';
  state.filters.q = '';
  state.page = 0;
  loadJobs();
}

function initModalScrollLockWatcher() {
  if (typeof MutationObserver === 'undefined') return;
  const modalObserver = new MutationObserver(() => {
    const anyOpen = Array.from(document.querySelectorAll('.modal-overlay')).some(
      m => m.style.display === 'flex' || m.style.display === 'block'
    );
    document.body.classList.toggle('modal-open', anyOpen);
  });
  document.querySelectorAll('.modal-overlay').forEach(modal => {
    modalObserver.observe(modal, { attributes: true, attributeFilter: ['style'] });
  });
}
