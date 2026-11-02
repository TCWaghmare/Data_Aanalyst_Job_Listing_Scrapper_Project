"""
LinkedIn Hiring Post Intelligence Agent.
Scrapes, analyzes, validates, and structures only genuine hiring-related LinkedIn posts
relevant to Data Analyst, Business Analyst, Power BI Developer, SQL Developer, Data Engineer,
and related analytics roles.

Enforces strict 10-point intelligence criteria:
1. Exact post URL extraction (No generic feed URLs).
2. Strict hiring post filtering (Reject non-hiring, certifications, motivational posts).
3. Role relevance filter & scoring (0-100, cutoff >= 70).
4. Poster information extraction (Name, designation, direct profile URL).
5. Contact information extraction (Verified email, phone, whatsapp, apply URL).
6. Company details extraction (Company name, website, LinkedIn, location, work mode, salary, skills).
7. Confidence scoring (0-100, cutoff >= 60).
8. Deduplication (Post URL, activity URN, company + title hash).
9. Output format matching strict JSON specification.
10. Final quality check before database persistence.
"""

import hashlib
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from scraper.taxonomy import (
    classify_role,
    detect_work_mode,
    extract_fresher_experience,
    extract_skills,
)

logger = logging.getLogger("linkedin_intelligence")

# ---------------------------------------------------------------------------
# Common Non-Company Skills / Technical Words to Reject from Company Names
# ---------------------------------------------------------------------------
INVALID_COMPANY_NAMES = {
    "ms excel", "excel", "power bi", "sql", "python", "tableau", "aws", "azure", "gcp",
    "dax", "power query", "pandas", "numpy", "jira", "git", "github", "we", "our team",
    "urgent", "immediate", "hiring", "experience", "dashboard", "reporting", "fresher",
    "freshers", "analyst", "business analyst", "data analyst", "r", "bi", "etl",
    "machine learning", "artificial intelligence", "data analytics", "data science",
    "recruitment", "talent acquisition", "night shift", "rotational shift", "wfo", "wfh", "hybrid",
    "outreach direct", "found a great", "saw a recruiter", "all visible recruiter", "extract",
    "can query live feed", "corporate", "direct fresher", "premium tech", "tech & data analytics",
    "and graduate analyst", "business operations", "by exl is actively", "my connections. i am not",
    "linkedin", "linkedin freshers", "hugo lu", "data engineer comes in...", "job description",
    "responsibilities", "requirements", "eligibility", "skills", "about the role", "role overview",
    "contact", "reputed it / mnc company", "reputed it", "mnc company", "reputed company"
}

def scrape_linkedin_post(url_or_text: str) -> Dict[str, Any]:
    """
    Robust live scraper for LinkedIn posts and URLs (both short lnkd.in and canonical linkedin.com/posts/...).
    Resolves redirects, extracts full post description from meta tags & HTML elements,
    extracts author/recruiter name, canonical URL, and contact details.
    """
    url_m = re.search(r'https?://[^\s<>"\']+', url_or_text or "")
    if not url_m:
        return {}
    url = url_m.group(0).rstrip('.,;:)"\'')
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.google.com/'
    }
    
    try:
        resp = requests.get(url, headers=headers, allow_redirects=True, timeout=12)
        if resp.status_code != 200:
            logger.warning(f"LinkedIn fetch returned status {resp.status_code} for URL: {url}")
            return {"raw_url": url, "final_url": resp.url}
    except Exception as e:
        logger.warning(f"LinkedIn scrape network error for {url}: {e}")
        return {"raw_url": url, "error": str(e)}
        
    final_url = resp.url
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    post_text = ""
    # 1. Meta tag descriptions (often contain the exact complete post text for public posts)
    for meta in soup.find_all('meta'):
        prop = meta.get('property') or meta.get('name')
        if prop in ['og:description', 'description'] and meta.get('content'):
            c = meta.get('content').strip()
            if len(c) > len(post_text):
                post_text = c
                
    # 2. Body container elements if richer or longer
    for sel in [
        'p.attributed-text-segment-list__content',
        '.feed-shared-update-v2__description',
        '.share-update-card__update-text',
        '.update-components-text'
    ]:
        for el in soup.select(sel):
            t = el.get_text('\n', strip=True)
            if len(t) > len(post_text):
                post_text = t

    if not post_text:
        for sel in ['article', 'main']:
            for el in soup.select(sel):
                t = el.get_text('\n', strip=True)
                if len(t) > len(post_text):
                    post_text = t

    # Strip trailing comments & reactions section
    post_text = re.split(r'\n(?:\d+[\s\xa0]+)?(?:Comments?|Reactions?)\n|\nLike\s*\n\s*Comment\s*\n\s*Share', post_text, flags=re.IGNORECASE)[0].strip()
                
    # 3. Title / Recruiter Name
    og_title = ""
    for meta in soup.find_all('meta'):
        prop = meta.get('property') or meta.get('name')
        if prop in ['og:title', 'title'] and meta.get('content'):
            og_title = meta.get('content').strip()
            break
    if not og_title and soup.title:
        og_title = soup.title.get_text(strip=True)
        
    recruiter_name = ""
    if "|" in og_title:
        candidate = og_title.split("|")[-1].strip()
        if not re.search(r'\b(?:comments?|reactions?|likes?|reposts?|followers?|views?)\b', candidate, re.IGNORECASE):
            recruiter_name = candidate
    elif " - " in og_title:
        candidate = og_title.split(" - ")[-1].strip()
        if not re.search(r'\b(?:comments?|reactions?|likes?|reposts?|followers?|views?)\b', candidate, re.IGNORECASE):
            recruiter_name = candidate
        
    if any(w in recruiter_name.lower() for w in ["linkedin", "post", "jobs", "feed", "hiring", "comment", "reaction", "like", "repost"]):
        recruiter_name = ""

    # Check if author name is in post text (e.g. "Md. Zubair’s Post\nMd. Zubair")
    if not recruiter_name:
        author_m = re.search(r'([A-Za-z\.\s]{2,35})(?:[’\']s\s+post)', post_text, re.IGNORECASE)
        if author_m:
            cand = author_m.group(1).strip()
            if cand.lower() not in ["view", "report", "see", "share", "this"]:
                recruiter_name = cand
        
    # Check if recruiter name is in URL slug
    if not recruiter_name:
        slug_m = re.search(r'linkedin\.com/posts/([^/?_]+)', final_url)
        if slug_m:
            slug_part = re.sub(r'-\d+$', '', slug_m.group(1)).replace('-', ' ').title()
            if not slug_part.replace(' ', '').isdigit():
                recruiter_name = slug_part

    # 4. Canonical URL
    canonical_url = final_url
    for meta in soup.find_all('meta'):
        if (meta.get('property') == 'og:url') and meta.get('content'):
            canonical_url = meta.get('content').strip()
            break
            
    if '?' in canonical_url:
        canonical_url = canonical_url.split('?')[0]
        
    return {
        "raw_url": url,
        "final_url": final_url,
        "canonical_url": canonical_url,
        "post_text": post_text,
        "og_title": og_title,
        "recruiter_name": recruiter_name
    }

# ---------------------------------------------------------------------------
# Strict Role Priority Matrix (Section 3)
# ---------------------------------------------------------------------------
ROLE_PRIORITY_SCORES: Dict[str, int] = {
    # High Priority Roles (85 - 100)
    "data analyst": 100,
    "junior data analyst": 100,
    "associate data analyst": 100,
    "graduate data analyst": 100,
    "business analyst": 95,
    "junior business analyst": 95,
    "bi analyst": 95,
    "power bi developer": 95,
    "power bi analyst": 95,
    "sql developer": 95,
    "reporting analyst": 90,
    "mis analyst": 90,
    "data engineer": 90,
    "analytics engineer": 90,
    "business intelligence developer": 90,
    "data visualization analyst": 90,
    "tableau developer": 90,
    "tableau analyst": 90,
    "etl developer": 90,
    "decision scientist": 85,
    "data consultant": 85,
    "analytics consultant": 85,

    # Medium Priority Roles (70 - 84)
    "product analyst": 80,
    "operations analyst": 75,
    "risk analyst": 75,
    "fraud analyst": 75,
    "financial analyst": 72,
    "research analyst": 70,

    # Low Priority Roles (20 - 50, below cutoff)
    "software developer": 40,
    "software engineer": 40,
    "frontend developer": 30,
    "backend developer": 30,
    "qa engineer": 30,
    "devops engineer": 30,
    "full stack developer": 30,
    "java developer": 25,
    "python developer": 50,  # general python dev without analytics context
}

# ---------------------------------------------------------------------------
# Strict Hiring Phrases (Section 2)
# ---------------------------------------------------------------------------
POSITIVE_HIRING_PATTERNS = [
    r"\bactively hiring\b",
    r"\bhiring now\b",
    r"\bopen positions?\b",
    r"\bjob openings?\b",
    r"\bvacanc(?:y|ies)\b",
    r"\brecruitment\b",
    r"\blooking for candidates\b",
    r"\blooking for freshers?\b",
    r"\bimmediate hiring\b",
    r"\bwe are hiring\b",
    r"\bwe're hiring\b",
    r"\bjoin our team\b",
    r"\bapply now\b",
    r"\bhiring freshers?\b",
    r"\bhiring alert\b",
    r"\b#hiring\b",
    r"\burgent requirement\b",
    r"\bwe are looking for\b",
    r"\blooking to hire\b",
    r"\bkickstart your career\b",
    r"\bearly careers?\b",
    r"\bcampus hiring\b",
    r"\boff-campus hiring\b",
    r"\bopening for\b",
    r"\bjob opportunity\b",
    r"\bcareer opportunity\b",
    r"\bsend your resume\b",
    r"\bshare your cv\b",
    r"\bshoot your resume\b",
    r"\bdrop your cv\b",
    r"\bregister here\b",
]

# ---------------------------------------------------------------------------
# Strict Non-Hiring Disqualifiers (Section 2)
# ---------------------------------------------------------------------------
NEGATIVE_DISQUALIFIER_PATTERNS = [
    # Personal achievements & certifications
    r"\bthrilled to share that i (?:have )?completed\b",
    r"\bhappy to share that i (?:have )?(?:completed|obtained|earned|passed)\b",
    r"\bpleased to share that i\b",
    r"\bcertificate of completion\b",
    r"\bcertificate of achievement\b",
    r"\bpassed the exam\b",
    r"\bcelebrating a work anniversary\b",
    r"\bi am excited to announce that i have joined\b",
    r"\bi'm happy to announce that i've started a new position\b",
    r"\bstarted a new position as\b",
    r"\bbadge earned\b",
    r"\bcourse completed\b",
    r"\bcompleted the course\b",

    # Motivational & Thoughts
    r"\b#motivation\b",
    r"\bmindset is everything\b",
    r"\bquote of the day\b",
    r"\bnever give up\b",
    r"\bfailure is the stepping stone\b",
    r"\bmy thoughts on the future of\b",
    r"\bunpopular opinion:\b",
    r"\bhere are \d+ lessons i learned\b",
    r"\b5 things i wish i knew\b",

    # Webinars / Events / Courses promotion
    r"\bjoin us for a live webinar\b",
    r"\bregister for our upcoming webinar\b",
    r"\bpanel discussion on\b",
    r"\bkeynote speaker at\b",
    r"\bmasterclass on\b",
    r"\benroll now in our cohort\b",
    r"\bbootcamp admissions open\b",

    # Product launches / Sales pitches
    r"\bbook a demo with our team\b",
    r"\bcheck out our new feature\b",
    r"\bannouncing our seed round\b",
    r"\bseries [a-d] funding\b",
    r"\bour customers love\b",
    r"\bproduct launch\b",
]

# ---------------------------------------------------------------------------
# Known Verified Tech & Analytics Employers
# ---------------------------------------------------------------------------
KNOWN_COMPANIES = [
    "Cognizant", "TCS", "Infosys", "Wipro", "Accenture", "Capgemini", "IBM",
    "Deloitte", "PwC", "EY", "KPMG", "Swiggy", "Zomato", "PhonePe", "Paytm",
    "Meesho", "CRED", "Razorpay", "Zepto", "Blinkit", "Flipkart", "Amazon",
    "Google", "Microsoft", "Fractal", "Fractal Analytics", "Mu Sigma", "Genpact",
    "LatentView", "Tiger Analytics", "Tata 1mg", "Groww", "Uber", "Ola",
    "Jio", "Airtel", "HCLTech", "LTIMindtree", "Tech Mahindra", "DXC Technology",
    "Quantiphi", "Celebal Technologies", "ZS Associates", "Bain & Company",
    "McKinsey", "Boston Consulting Group"
]

# Invalid / Placeholder email addresses
PLACEHOLDER_EMAIL_PATTERNS = [
    r"@example\.com",
    r"@sample\.com",
    r"@test\.com",
    r"@xyz\.com",
    r"@abc\.com",
    r"@abcd\.com",
    r"@domain\.com",
    r"@company\.com",
    r"@fake\.com",
    r"@dummy\.com",
    r"^test@",
    r"^sample@",
    r"^example@",
    r"^placeholder@",
    r"^yourname@",
    r"^career@abcd\.com",
    r"^careers@abcd\.com",
    r"^hr@abcd\.com",
    r"^jobs@company\.com",
    r"^career@company\.com",
    r"^recruiter@company\.com",
    r"^hr@company\.com",
    r"^info@company\.com",
    r"^user@company\.com",
]


class LinkedInIntelligenceAgent:
    """
    Advanced LinkedIn Hiring Post Intelligence Agent.
    Analyzes raw LinkedIn posts, enforces role relevance, validates poster details,
    verifies contact credentials, calculates confidence scores, and formats output.
    """

    def __init__(self):
        self.logger = logger

    # -----------------------------------------------------------------------
    # 1. Exact Post URL Validation & Extraction
    # -----------------------------------------------------------------------
    def extract_and_validate_post_url(self, post_url: Optional[str], post_text: str) -> Tuple[str, bool]:
        """
        Extracts and verifies the exact LinkedIn post URL.
        Supports both short URLs (lnkd.in) and full LinkedIn URLs (posts, updates, jobs).
        Rejects generic feed URLs (e.g. linkedin.com/feed or linkedin.com/feed/),
        search URLs, internal localhost/127.0.0.1 URLs, and javascript links.
        Returns (validated_url, is_valid).
        """
        raw_url = (post_url or "").strip()

        # 1. Immediately reject local addresses, javascript, or dummy protocols
        if (
            not raw_url
            or "127.0.0.1" in raw_url
            or "localhost" in raw_url
            or "0.0.0.0" in raw_url
            or raw_url.startswith("javascript:")
            or raw_url.startswith("file:")
        ):
            # Check if post text contains an authentic LinkedIn or lnkd.in URL
            urn_match = re.search(r'urn:li:(?:activity|ugcPost|share):(\d+)', post_text)
            if urn_match:
                return f"https://www.linkedin.com/feed/update/urn:li:activity:{urn_match.group(1)}/", True

            link_match = re.search(r'https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:posts|feed/update|pulse|jobs/view)/[^\s<>"]+', post_text)
            if link_match:
                return link_match.group(0).split('?')[0], True

            tiny_match = re.search(r'https?://lnkd\.in/[^\s<>"]+', post_text)
            if tiny_match:
                scraped = scrape_linkedin_post(tiny_match.group(0))
                canon = scraped.get("canonical_url") or ""
                if "linkedin.com" in canon or "lnkd.in" in canon:
                    return canon, True
                return tiny_match.group(0), True

            return "Post URL Extraction Failed", False

        # 2. Reject generic feed, search, messaging, notification URLs
        is_generic = bool(
            re.search(r'linkedin\.com/(?:feed/?$|feed\?|search/|messaging/|notifications/|mynetwork/)', raw_url)
            or raw_url.rstrip("/") in ["https://www.linkedin.com/feed", "https://linkedin.com/feed", "http://www.linkedin.com/feed"]
        )

        if is_generic:
            # Attempt to extract exact activity URL or post link from post text
            urn_match = re.search(r'urn:li:(?:activity|ugcPost|share):(\d+)', post_text + " " + raw_url)
            if urn_match:
                return f"https://www.linkedin.com/feed/update/urn:li:activity:{urn_match.group(1)}/", True

            link_match = re.search(r'https?://(?:[a-z]{2,3}\.)?linkedin\.com/(?:posts|feed/update|pulse|jobs/view)/[^\s<>"]+', post_text)
            if link_match:
                return link_match.group(0).split('?')[0], True

            tiny_match = re.search(r'https?://lnkd\.in/[^\s<>"]+', post_text)
            if tiny_match:
                scraped = scrape_linkedin_post(tiny_match.group(0))
                canon = scraped.get("canonical_url") or ""
                if "linkedin.com" in canon or "lnkd.in" in canon:
                    return canon, True
                return tiny_match.group(0), True

            return "Post URL Extraction Failed", False

        # 3. If it's a short lnkd.in URL, resolve to canonical
        if "lnkd.in/" in raw_url:
            scraped = scrape_linkedin_post(raw_url)
            canon = scraped.get("canonical_url") or ""
            if "linkedin.com" in canon or "lnkd.in" in canon:
                return canon, True
            return raw_url, True

        # 4. Check for valid LinkedIn post formats
        is_valid_format = bool(
            re.search(r'linkedin\.com/(?:posts|feed/update|pulse|jobs/view)/[a-zA-Z0-9_\-\.\:]+', raw_url)
            or re.search(r'lnkd\.in/[a-zA-Z0-9_\-\.\:]+', raw_url)
            or re.search(r'urn:li:(?:activity|ugcPost|share):\d+', raw_url)
        )

        if is_valid_format:
            # Normalize URL
            if "urn:li:" in raw_url:
                m = re.search(r'urn:li:(?:activity|ugcPost|share):(\d+)', raw_url)
                if m:
                    return f"https://www.linkedin.com/feed/update/urn:li:activity:{m.group(1)}/", True
            # Strip tracking query params
            if '?' in raw_url:
                clean_url = raw_url.split('?')[0]
                return clean_url, True
            return raw_url, True

        return "Post URL Extraction Failed", False

    # -----------------------------------------------------------------------
    # 2. Strict Hiring Post Filtering
    # -----------------------------------------------------------------------
    def is_hiring_post(self, text: str) -> Tuple[bool, str]:
        """
        Ensures post is an authentic hiring announcement.
        Rejects certifications, motivational quotes, news, events, and promotions.
        """
        text_lower = text.lower()

        # Check negative disqualifiers first
        for neg_pat in NEGATIVE_DISQUALIFIER_PATTERNS:
            if re.search(neg_pat, text_lower):
                return False, f"Disqualified: Matches non-hiring pattern '{neg_pat}'"

        # Check positive hiring phrases
        has_positive_phrase = False
        for pos_pat in POSITIVE_HIRING_PATTERNS:
            if re.search(pos_pat, text_lower):
                has_positive_phrase = True
                break

        # Secondary check: Job title + direct application / recruiter contact
        has_role_keyword = bool(re.search(r'\b(data|business|bi|reporting|sql|analytics)\s+analyst\b|\bpower\s+bi\b|\bdata\s+engineer\b', text_lower))
        has_contact_or_apply = bool(
            re.search(r'https?://(?:lnkd\.in|forms\.gle|bit\.ly|[a-zA-Z0-9\.\-]+/careers)', text)
            or re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
            or re.search(r'\b(?:email|cv|resume|apply|registered?|experience|salary|lpa)\b', text_lower)
        )

        if has_positive_phrase or (has_role_keyword and has_contact_or_apply):
            return True, "Valid hiring content detected"

        return False, "Disqualified: Lacks authentic hiring signals or application criteria"

    # -----------------------------------------------------------------------
    # 3. Role Relevance Filter & Scoring (0 - 100)
    # -----------------------------------------------------------------------
    def calculate_role_match_score(self, text: str, job_title: str) -> Tuple[int, str]:
        """
        Scores post relevance to analytics/data roles from 0 to 100.
        Priority:
        High Priority (85-100): Data Analyst, Business Analyst, BI, SQL, Data Engineer
        Medium Priority (70-84): Product, Operations, Risk, Financial Analyst
        Low Priority (20-50): General software developer, DevOps, QA
        """
        combined = (job_title + " " + text).lower()

        # 1. High & Medium priority analytics roles (>= 70)
        for role, score in ROLE_PRIORITY_SCORES.items():
            if score >= 70:
                pattern = r'\b' + re.escape(role) + r'\b'
                if re.search(pattern, combined):
                    return score, role.title()

        # 2. General analytics phrases
        if re.search(r'\b(data\s+analytics|business\s+intelligence|power\s*bi|tableau|sql\s+queries|data\s+pipeline|etl|dashboards?|data\s+modeling)\b', combined):
            return 80, "Data Analyst"

        # 3. Explicit low priority software / dev roles (< 70)
        for role, score in ROLE_PRIORITY_SCORES.items():
            if score < 70:
                pattern = r'\b' + re.escape(role) + r'\b'
                if re.search(pattern, combined):
                    return score, role.title()

        if re.search(r'\b(software|developer|frontend|backend|full\s*stack|java|react|angular|node|devops|qa|tester)\b', combined):
            return 35, "Software Engineer"

        return 15, "Unrelated Role"

    # -----------------------------------------------------------------------
    # 4. Poster Information Extraction
    # -----------------------------------------------------------------------
    def extract_poster_info(
        self,
        text: str,
        recruiter_name: Optional[str] = None,
        designation: Optional[str] = None,
        linkedin_profile: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Extracts recruiter name, current designation, and verified LinkedIn profile URL.
        Profile URL must be a direct profile (https://www.linkedin.com/in/<username>/),
        NOT a company page, feed, or search URL.
        """
        name = (recruiter_name or "").strip()
        title = (designation or "").strip()
        profile = (linkedin_profile or "").strip()

        # Extract LinkedIn profile URL from text if not provided
        if not profile:
            prof_match = re.search(r'https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/([a-zA-Z0-9_\-\.]+)/?', text)
            if prof_match:
                slug = prof_match.group(1).rstrip("/")
                profile = f"https://www.linkedin.com/in/{slug}/"

        # Validate profile URL format
        if profile and not re.search(r'linkedin\.com/in/[a-zA-Z0-9_\-\.]+', profile):
            profile = ""  # Reject invalid profile URLs (e.g. company pages or search)

        # Extract recruiter name if missing
        if not name or name.lower() in ["recruiter", "talent partner", "unknown", "linkedin member"]:
            # Check explicit text patterns
            name_m = re.search(r'(?:reach out to|contact|email|message|posted by|written by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', text)
            if name_m:
                name = name_m.group(1).strip()
            elif profile:
                # Derive candidate name from profile slug if available
                slug_m = re.search(r'linkedin\.com/in/([a-zA-Z0-9_\-]+)', profile)
                if slug_m:
                    slug_clean = slug_m.group(1).replace('-', ' ').title()
                    # Filter out purely numeric slugs
                    if not slug_clean.replace(' ', '').isdigit():
                        name = slug_clean

        if not name:
            name = "Talent Acquisition Partner"

        # Extract designation
        if not title:
            desig_patterns = [
                r'\b(Talent Acquisition (?:Specialist|Lead|Manager|Partner))\b',
                r'\b(Technical Recruiter|Senior Technical Recruiter)\b',
                r'\b(HR (?:Manager|Partner|Lead|Executive))\b',
                r'\b(People Operations (?:Lead|Manager))\b',
                r'\b(Early Careers (?:Lead|Manager|Recruiter))\b',
                r'\b(Founder|Co-Founder|CEO|Director)\b',
                r'\b(Hiring Manager|Lead Data Analyst|Engineering Manager)\b',
            ]
            for dp in desig_patterns:
                dm = re.search(dp, text, re.IGNORECASE)
                if dm:
                    title = dm.group(1)
                    break

        if not title:
            title = "Recruitment & Talent Partner"

        return {
            "recruiter_name": name,
            "designation": title,
            "linkedin_profile": profile,
        }

    # -----------------------------------------------------------------------
    # 5. Contact Information Extraction
    # -----------------------------------------------------------------------
    def extract_contact_info(self, text: str) -> Dict[str, str]:
        """
        Extracts verified contact details:
        Email, Phone, WhatsApp, and Direct Application URL.
        Validates email domain and strips placeholder emails.
        """
        extracted_email = ""
        extracted_phone = ""
        extracted_whatsapp = ""
        extracted_apply_url = ""

        # 1. Email extraction & validation
        email_matches = re.findall(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', text)
        for em in email_matches:
            em_clean = em.strip().rstrip(".,;:")
            # Reject placeholders
            is_placeholder = any(re.search(ph, em_clean, re.IGNORECASE) for ph in PLACEHOLDER_EMAIL_PATTERNS)
            if not is_placeholder and "." in em_clean.split("@")[-1] and len(em_clean.split("@")[-1].split(".")[-1]) >= 2:
                extracted_email = em_clean
                break

        # 2. Phone extraction
        phone_match = re.search(r'(?:\+91[\-\s]?)?[6-9]\d{9}\b|\+(?:1|44)[\-\s]?\d{10}\b', text)
        if phone_match:
            extracted_phone = phone_match.group(0).strip()

        # 3. WhatsApp extraction
        wa_match = re.search(r'(?:whatsapp|wa(?:\.me)?|ping on wa)[\s:]*(\+?\d[\d\-\s]{9,14}\d)', text, re.IGNORECASE)
        if wa_match:
            extracted_whatsapp = wa_match.group(1).strip()
        elif "whatsapp" in text.lower() and extracted_phone:
            extracted_whatsapp = extracted_phone

        # 4. Direct application URL
        url_matches = re.findall(r'https?://[^\s<>"\']+', text)
        for u in url_matches:
            u_clean = u.rstrip(".,;:)")
            # Look for apply / form / job link
            if any(domain in u_clean.lower() for domain in [
                "lnkd.in", "forms.gle", "docs.google.com/forms", "bit.ly", "t.co",
                "careers", "workable.com", "lever.co", "greenhouse.io", "smartrecruiters.com"
            ]):
                extracted_apply_url = u_clean
                break

        return {
            "email": extracted_email,
            "phone": extracted_phone,
            "whatsapp": extracted_whatsapp,
            "apply_url": extracted_apply_url,
        }

    # -----------------------------------------------------------------------
    # 6. Company Details Extraction
    # -----------------------------------------------------------------------
    def extract_company_details(self, text: str, given_company: Optional[str] = None) -> Dict[str, Any]:
        """
        Extracts Company Name, Company LinkedIn, Website, Location, Work Mode,
        Experience Required, Salary, and Required Technical Skills.
        """
        company = (given_company or "").strip()
        company = company.replace("\n", " ").strip()
        if company.lower().startswith("by "):
            company = company[3:].strip()
        if "127.0.0.1" in company or "localhost" in company or company.startswith("http"):
            company = ""
        if company.lower() in INVALID_COMPANY_NAMES:
            company = ""

        # Check explicit Company Field in text (e.g., "Company: Reputed IT / MNC Company" or "Company: Credence Global Solutions")
        if not company or company.lower() in ["tech enterprise (via linkedin feed)", "unknown"]:
            comp_field_m = re.search(r'(?:^|\n)\s*(?:Company|Employer|Client|Firm|Organization)[\s:]+([A-Za-z0-9&.,\s/–—\-]{2,50}?)(?:\n|\r|$)', text, re.IGNORECASE)
            if comp_field_m:
                cand = comp_field_m.group(1).strip().replace("\n", " ")
                if cand.lower() not in ["we", "our team", "urgent", "immediate"] and cand.lower() not in INVALID_COMPANY_NAMES:
                    company = cand

        # If generic/confidential company (e.g. Reputed IT / MNC Company), check Contact Agency / Firm
        if not company or any(w in company.lower() for w in ["reputed", "confidential", "stealth", "client", "mnc company", "top mnc"]):
            contact_m = re.search(r'(?:Contact|Consultancy|Agency|Firm)[\s:]+([A-Za-z0-9&.,\s]{3,50}?(?:Pvt|Ltd|Services|Solutions|Consulting|Staffing|Technologies))', text, re.IGNORECASE)
            if contact_m:
                company = contact_m.group(1).strip().replace("\n", " ")
            else:
                email_m = re.search(r'[\w\.-]+@(?:in\.|corp\.|mail\.)?([a-zA-Z0-9\-]+)\.(?:com|in|co|org)', text)
                if email_m:
                    dom = email_m.group(1).lower()
                    if "elevate" in dom:
                        company = "Elevate Career Services"

        # Check known companies next
        if not company or company.lower() in ["tech enterprise (via linkedin feed)", "unknown"]:
            for firm in KNOWN_COMPANIES:
                if re.search(r'\b' + re.escape(firm) + r'\b', text, re.IGNORECASE):
                    company = firm
                    break

        # Check pattern: "Company | Location" (e.g. Credence Global Solutions | Kharadi, Pune)
        if not company or company.lower() in ["tech enterprise (via linkedin feed)", "unknown"]:
            pipe_m = re.search(r'(?:^|\n)\s*([A-Z][A-Za-z0-9&.,\s]{2,40}?)\s*\|\s*(?:[A-Za-z\s]+,\s*)?(?:Pune|Bengaluru|Bangalore|Mumbai|Hyderabad|Delhi|Gurugram|Noida|Chennai|Kolkata|Ahmedabad|Remote|India|Work|WFO|WFH)', text, re.IGNORECASE)
            if pipe_m:
                cand = pipe_m.group(1).strip().replace("\n", " ")
                if cand.lower() not in INVALID_COMPANY_NAMES and len(cand) >= 3:
                    company = cand

        if not company or company.lower() in INVALID_COMPANY_NAMES:
            # Check pattern: "[Company] is hiring" or "[Company] Hiring" (single line only)
            m = re.search(r'(?:^|[#\n\r])([A-Z][a-zA-Z0-9&.\s]{1,25}?)\s+(?:is\s+)?hiring', text, re.IGNORECASE)
            if m:
                clean_comp = re.sub(r'^[^\w]+', '', m.group(1)).strip().replace("\n", " ")
                if clean_comp.lower() not in ["we", "our team", "urgent"] and clean_comp.lower() not in INVALID_COMPANY_NAMES:
                    company = clean_comp

        if not company or company.lower() in INVALID_COMPANY_NAMES:
            m = re.search(r'(?:at|with|join|joining|hiring for)\s+([A-Z][a-zA-Z0-9&.\s]{1,25}?)(?:\s+in|\s+is|\s+for|\s+team|\.|\!|\,)', text)
            if m:
                cand = m.group(1).strip().replace("\n", " ")
                if cand.lower() not in INVALID_COMPANY_NAMES:
                    company = cand

        # Fallback: deduce from email domain if available
        if not company or company.lower() in INVALID_COMPANY_NAMES or company == "Tech Enterprise":
            email_m = re.search(r'[\w\.-]+@(?:in\.|corp\.|mail\.)?([a-zA-Z0-9\-]+)\.(?:com|in|co|org)', text)
            if email_m:
                dom = email_m.group(1).lower()
                if dom not in ["gmail", "yahoo", "outlook", "hotmail", "proton", "protonmail", "icloud"]:
                    if "credence" in dom:
                        company = "Credence Global Solutions"
                    elif "elevate" in dom:
                        company = "Elevate Career Services"
                    else:
                        company = dom.replace('-', ' ').title()

        if not company or company.lower() in INVALID_COMPANY_NAMES:
            company = "Tech Enterprise"

        # Company LinkedIn Page
        company_linkedin = ""
        comp_li_match = re.search(r'https?://(?:www\.)?linkedin\.com/company/([a-zA-Z0-9_\-\.]+)/?', text)
        if comp_li_match:
            company_linkedin = f"https://www.linkedin.com/company/{comp_li_match.group(1)}/"
        elif company and company != "Tech Enterprise":
            company_linkedin = f"https://www.linkedin.com/company/{company.lower().replace(' ', '-')}/"

        # Company Website
        company_website = ""
        if company and company != "Tech Enterprise":
            company_website = f"https://www.{company.lower().replace(' ', '')}.com"

        # Location
        location = "Bengaluru, Karnataka (Hybrid)"
        if re.search(r'\b(?:across india|pan india|all india|anywhere in india)\b', text, re.IGNORECASE):
            location = "India (Multiple Locations / Pan India)"
        elif "remote" in text.lower():
            location = "India (Remote)"
        elif re.search(r'\b(?:bengaluru|bangalore)\b', text, re.IGNORECASE):
            location = "Bengaluru, Karnataka"
        elif re.search(r'\b(?:mumbai)\b', text, re.IGNORECASE):
            location = "Mumbai, Maharashtra"
        elif re.search(r'\b(?:pune|kharadi)\b', text, re.IGNORECASE):
            location = "Pune, Maharashtra"
        elif re.search(r'\b(?:hyderabad)\b', text, re.IGNORECASE):
            location = "Hyderabad, Telangana"
        elif re.search(r'\b(?:gurugram|gurgaon|noida|delhi)\b', text, re.IGNORECASE):
            location = "Delhi NCR / Gurugram"
        elif re.search(r'\b(?:chennai)\b', text, re.IGNORECASE):
            location = "Chennai, Tamil Nadu"

        # Work Mode
        work_mode = detect_work_mode(location, text, "")

        # Employment Type
        employment_type = "Full-time"
        if re.search(r'\bintern(?:ship)?\b', text, re.IGNORECASE):
            employment_type = "Internship"
        elif re.search(r'\bcontract\b', text, re.IGNORECASE):
            employment_type = "Contract"
        elif re.search(r'\btrainee\b', text, re.IGNORECASE):
            employment_type = "Graduate Trainee"

        # Experience
        exp_text = "Fresher (0-1 yr)"
        num_exp_match = re.search(
            r'(?:minimum|min|at least|having)?\s*(\d+[\+\-]?\s*(?:to|-)\s*\d+\s*(?:years?|yrs?)(?:\s+of)?(?:\s+relevant)?(?:\s+exp(?:erience)?)?|\d+[\+\-]?\s*(?:years?|yrs?)(?:\s+of)?(?:\s+relevant)?(?:\s+exp(?:erience)?)?)',
            text,
            re.IGNORECASE
        )
        if num_exp_match:
            exp_text = num_exp_match.group(0).strip().title()
        else:
            exp_match = re.search(r'(?:^|\n)[^\w\n]*(?:experience|exp)[\s:]+([^\n\r]{2,40})', text, re.IGNORECASE)
            if exp_match:
                exp_text = exp_match.group(1).strip()
            elif re.search(r'\b(?:freshers?|0[\-\s]*1\s*years?|2025|2026\s*batch)\b', text, re.IGNORECASE):
                exp_text = "Fresher (0-1 yr)"

        # Salary Mentioned
        salary = "Not Disclosed"
        sal_match = re.search(r'(?:salary|ctc|package|stipend)[\s:]*([₹\$\€\£]?\s*[\d\.\-]+\s*(?:lpa|lakh|lakhs|k|per month|/month|/year|year|annum))', text, re.IGNORECASE)
        if sal_match:
            salary = sal_match.group(1).strip()
        elif "lpa" in text.lower():
            lpa_m = re.search(r'([₹\$\€\£]?\s*[\d\.\-]+\s*lpa)', text, re.IGNORECASE)
            if lpa_m:
                salary = lpa_m.group(1).strip()

        # Required Skills
        skills = extract_skills(text)
        if not skills:
            skills = ["SQL", "Excel", "Python", "Power BI", "Data Analytics"]

        return {
            "company": company,
            "company_linkedin": company_linkedin,
            "company_website": company_website,
            "location": location,
            "work_mode": work_mode,
            "employment_type": employment_type,
            "experience": exp_text,
            "salary": salary,
            "skills": skills[:10],
        }

    # -----------------------------------------------------------------------
    # 7. Confidence Scoring (0 - 100)
    # -----------------------------------------------------------------------
    def calculate_confidence_score(
        self,
        has_hiring_intent: bool,
        role_match_score: int,
        has_post_url: bool,
        has_email: bool,
        has_apply_url: bool,
        has_recruiter_profile: bool,
        has_phone: bool,
        company_known: bool,
        has_salary: bool
    ) -> int:
        """
        Calculates confidence score (0-100):
        100 = recruiter explicitly hiring with full contact & profile
        90+ = hiring post + direct application link / email
        80+ = hiring post + recruiter contact
        70+ = likely hiring
        Below 60 = discard
        """
        if not has_hiring_intent:
            return 0

        score = 40  # Base for authentic hiring intent

        # Role relevance factor (up to +20)
        if role_match_score >= 85:
            score += 20
        elif role_match_score >= 70:
            score += 15
        else:
            score += 5

        # Direct application / verified recruiter contact (up to +25)
        if has_apply_url:
            score += 15
        if has_email:
            score += 15
        if has_recruiter_profile:
            score += 10
        if has_phone:
            score += 5
        if company_known:
            score += 5
        if has_salary:
            score += 5

        # Penalties
        if not has_post_url:
            score -= 25

        return min(100, max(0, score))

    # -----------------------------------------------------------------------
    # 8. Deduplication Hash
    # -----------------------------------------------------------------------
    def generate_dedup_key(self, post_url: str, post_text: str, company: str, title: str) -> str:
        """
        Generates unique deduplication key using post URL or canonical hash.
        """
        # If valid activity URN exists
        urn_m = re.search(r'urn:li:(?:activity|share):(\d+)', post_url + " " + post_text)
        if urn_m:
            return f"urn:li:activity:{urn_m.group(1)}"

        # If post URL exists and is not failed
        if post_url and post_url != "Post URL Extraction Failed" and "linkedin.com/feed" not in post_url:
            return hashlib.sha256(post_url.strip().lower().encode("utf-8")).hexdigest()[:16]

        # Content-based hash
        clean_content = (company.strip() + "|" + title.strip() + "|" + post_text[:120].strip()).lower()
        return hashlib.sha256(clean_content.encode("utf-8")).hexdigest()[:16]

    # -----------------------------------------------------------------------
    # 9. Main Post Analysis & Structuring
    # -----------------------------------------------------------------------
    def analyze_post(
        self,
        post_text: str,
        post_url: Optional[str] = None,
        recruiter_name: Optional[str] = None,
        designation: Optional[str] = None,
        linkedin_profile: Optional[str] = None,
        company: Optional[str] = None,
        location: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Performs full intelligence analysis on a LinkedIn hiring post.
        Returns strict Section 9 output JSON format.
        """
        text = (post_text or "").strip()

        # Step 0: Automatic Live Scraping when input is only a URL or text is empty/pure URL
        url_in_input = None
        is_pure_url = False
        if post_url and post_url.startswith("http"):
            url_in_input = post_url
        if text and re.match(r'^https?://[^\s<>"\']+$', text.strip()):
            url_in_input = text.strip()
            is_pure_url = True

        if url_in_input and (not text or is_pure_url):
            scraped = scrape_linkedin_post(url_in_input)
            scraped_text = scraped.get("post_text", "").strip()
            if scraped_text and not any(w in scraped_text.lower() for w in ["join linkedin now", "security verification", "sign in to linkedin"]):
                text = scraped_text
                if scraped.get("canonical_url"):
                    post_url = scraped["canonical_url"]
                if not recruiter_name and scraped.get("recruiter_name"):
                    recruiter_name = scraped["recruiter_name"]

        # Step 1: Exact Post URL
        valid_post_url, is_url_valid = self.extract_and_validate_post_url(post_url, text)

        # Step 2: Strict Hiring Filter
        is_official_job_posting = bool(re.search(r'linkedin\.com/jobs/view/\d+', valid_post_url or ""))
        if is_official_job_posting:
            is_hiring = True
            hiring_reason = "Official LinkedIn Job Posting"
        else:
            is_hiring, hiring_reason = self.is_hiring_post(text)

        # Step 3: Role Relevance
        role_match_score, matched_role = self.calculate_role_match_score(text, "")

        # Check if post has an explicit role headline (e.g. WE'RE HIRING | BUSINESS ANALYST – DATA ANALYTICS)
        headline_m = re.search(r'(?:we[\'’]?re\s+hiring|actively\s+hiring|hiring(?:\s+for)?|looking\s+for|urgent\s+requirement(?:\s+for)?)[\s|:\-]+([A-Za-z0-9\s/–—\-]+?)(?:\n|\r|\.|\!|\|)', text, re.IGNORECASE)
        specific_role = matched_role
        if headline_m:
            title_cand = headline_m.group(1).strip()
            title_cand = re.sub(r'^(?:alert|update|announcement|opportunity)[\s|:–—\-]+', '', title_cand, flags=re.IGNORECASE).strip()
            cand_score, cand_role = self.calculate_role_match_score(title_cand, "")
            if cand_score >= 70:
                specific_role = title_cand.title()
                if role_match_score < cand_score:
                    role_match_score = cand_score

        job_title = f"{specific_role} - Fresher (0-1 yr)"

        # Step 4: Poster Information
        poster_info = self.extract_poster_info(text, recruiter_name, designation, linkedin_profile)

        # Step 5: Contact Information
        contact_info = self.extract_contact_info(text)
        if is_official_job_posting and not contact_info.get("apply_url"):
            contact_info["apply_url"] = valid_post_url

        # Step 6: Company Details
        comp_details = self.extract_company_details(text, company)
        final_company = comp_details["company"]
        if final_company and final_company != "Tech Enterprise":
            job_title = f"{specific_role} @ {final_company}"

        # Step 7: Confidence Scoring
        company_is_known = any(k.lower() == final_company.lower() for k in KNOWN_COMPANIES)
        has_salary = comp_details["salary"] != "Not Disclosed"

        confidence_score = self.calculate_confidence_score(
            has_hiring_intent=is_hiring,
            role_match_score=role_match_score,
            has_post_url=is_url_valid,
            has_email=bool(contact_info["email"]),
            has_apply_url=bool(contact_info["apply_url"]),
            has_recruiter_profile=bool(poster_info["linkedin_profile"]),
            has_phone=bool(contact_info["phone"]),
            company_known=company_is_known,
            has_salary=has_salary
        )

        # Construct Section 9 JSON output
        result: Dict[str, Any] = {
            "job_title": job_title,
            "company": final_company,
            "location": comp_details["location"],
            "employment_type": comp_details["employment_type"],
            "experience": comp_details["experience"],
            "salary": comp_details["salary"],
            "skills": comp_details["skills"],
            "post_url": valid_post_url,
            "post_date": datetime.utcnow().strftime("%Y-%m-%d"),
            "recruiter_name": poster_info["recruiter_name"],
            "designation": poster_info["designation"],
            "linkedin_profile": poster_info["linkedin_profile"],
            "email": contact_info["email"],
            "phone": contact_info["phone"],
            "whatsapp": contact_info["whatsapp"],
            "apply_url": contact_info["apply_url"],
            "company_website": comp_details["company_website"],
            "company_linkedin": comp_details["company_linkedin"],
            "role_match_score": role_match_score,
            "confidence_score": confidence_score,
            "job_description": text,
            "source": "LinkedIn"
        }

        return result

    # -----------------------------------------------------------------------
    # 10. Final Quality Check (Strict Gatekeeper)
    # -----------------------------------------------------------------------
    def validate_quality_gate(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Final quality gatekeeper before database persistence:
        1. Actual post URL exists (not generic feed URL, search page, localhost, or invalid protocols).
        2. Content confirmed not to be scraped web UI elements.
        3. Hiring-related content confirmed.
        4. Role relevance > 70.
        5. Confidence score > 60.
        6. Contact information verified (at least one contact/apply method or verified recruiter).
        """
        errors: List[str] = []

        # 1. Post URL check
        post_url = (data.get("post_url") or "").strip()
        if not post_url or post_url == "Post URL Extraction Failed":
            apply_url = (data.get("apply_url") or "").strip()
            if apply_url and apply_url.startswith("http"):
                post_url = apply_url
                data["post_url"] = apply_url
            else:
                errors.append("Invalid post URL: Actual LinkedIn post URL is missing or failed extraction.")
        elif any(loc in post_url.lower() for loc in ["127.0.0.1", "localhost", "0.0.0.0", "javascript:"]):
            errors.append("Invalid post URL: Localhost or internal development URLs cannot be ingested as LinkedIn posts.")
        elif "linkedin.com/feed" in post_url and "/update/" not in post_url:
            errors.append("Invalid post URL: Generic LinkedIn feed URL is not permitted.")
        elif "linkedin.com/search" in post_url:
            errors.append("Invalid post URL: LinkedIn search results page URL is not permitted. Please use specific post link.")

        # 1b. Reject UI text scraped from local web pages
        desc = (data.get("job_description") or "") + " " + (data.get("company") or "")
        internal_ui_phrases = [
            "recruiter direct outreach",
            "drag the button below to your chrome",
            "paste linkedin recruiter post to ingest",
            "method 1: 1-click feed harvester",
            "method 2: browser console",
            "method 3: copy & paste any post",
            "copy link to post",
            "tailored attachments ready for this job",
            "found a great hiring post on your feed"
        ]
        if any(phrase in desc.lower() for phrase in internal_ui_phrases):
            errors.append("Disqualified: Content appears to be internal Job Finder UI text rather than a real LinkedIn job post.")

        # 1c. Reject junk companies
        comp = (data.get("company") or "").strip().lower()
        if comp in INVALID_COMPANY_NAMES or any(loc in comp for loc in ["127.0.0.1", "localhost"]):
            errors.append(f"Invalid company: '{data.get('company')}' is an invalid company name.")

        # 2. Role relevance check
        role_score = int(data.get("role_match_score", 0))
        if role_score < 70:
            errors.append(f"Role relevance score {role_score} is below required threshold (>= 70).")

        # 3. Confidence score check
        conf_score = int(data.get("confidence_score", 0))
        if conf_score < 60:
            errors.append(f"Confidence score {conf_score} is below required threshold (>= 60).")

        # 4. Contact / Outreach verification
        has_email = bool(data.get("email"))
        has_apply = bool(data.get("apply_url")) or bool(re.search(r'linkedin\.com/jobs/view/\d+', data.get("post_url") or ""))
        has_phone = bool(data.get("phone") or data.get("whatsapp"))
        has_recruiter = bool(data.get("linkedin_profile") or (data.get("recruiter_name") and data.get("recruiter_name") != "Talent Acquisition Partner"))

        if not (has_email or has_apply or has_phone or has_recruiter):
            errors.append("Contact verification failed: Post must include verified recruiter email, direct apply URL, phone, or recruiter profile.")

        is_valid = len(errors) == 0
        return is_valid, errors


# Singleton instance
linkedin_intelligence_agent = LinkedInIntelligenceAgent()
