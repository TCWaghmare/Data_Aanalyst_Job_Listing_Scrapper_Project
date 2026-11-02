import sqlite3
import re

def audit_jd_experience():
    conn = sqlite3.connect('data/jobs.db')
    c = conn.cursor()
    c.execute('SELECT id, title, company, experience_level, location, description, source_name FROM jobs')
    rows = c.fetchall()
    
    # Negative patterns: senior titles or high experience in description
    senior_title_patterns = [
        r'\b(sr\.?|senior|lead|principal|director|head|vp|architect|manager)\b',
        r'\b(team\s+lead|project\s+manager|engineering\s+manager)\b',
        r'\b(ii|iii|iv)\b' # Level 2, 3, 4
    ]
    
    # Description experience patterns requiring > 1-2 years
    exp_req_patterns = [
        r'\b(2\+|3\+|4\+|5\+|6\+|7\+|8\+|10\+)\s*(years?|yrs?)\b',
        r'\b(2|3|4|5|6|7|8|9|10)\s*(to|-)\s*\d+\s*(years?|yrs?)\b',
        r'\bminimum\s+(of\s+)?(2|3|4|5|6|7|8)\s*(years?|yrs?)\b',
        r'\bat\s+least\s+(2|3|4|5|6|7|8)\s*(years?|yrs?)\b',
        r'\brequire(s|d)?\s+(2|3|4|5|6|7|8)\s*(years?|yrs?)\b',
        r'\b(2|3|4|5|6|7|8)\s*(years?|yrs?)\s+of\s+(relevant\s+)?experience\b',
        r'\b(2|3|4|5|6|7|8)\s*(years?|yrs?)\s+prior\s+experience\b',
    ]

    disqualified = []
    fresher_confirmed = []
    
    for r in rows:
        jid, title, company, exp_level, loc, desc, src = r
        full_text = f"{title}\n{desc or ''}".lower()
        title_lower = (title or '').lower()
        
        reason = None
        # Check senior title
        for p in senior_title_patterns:
            if re.search(p, title_lower):
                if not re.search(r'\b(fresher|trainee|intern|junior|entry)\b', title_lower):
                    reason = f"Title contains seniority: {p}"
                    break
        
        # Check description experience
        if not reason and desc:
            for ep in exp_req_patterns:
                m = re.search(ep, full_text)
                if m:
                    matched_str = m.group(0)
                    reason = f"JD requires experience: {matched_str}"
                    break
                    
        if reason:
            disqualified.append((jid, title, company, loc, src, reason))
        else:
            fresher_confirmed.append((jid, title, company, loc, src))
            
    print(f"Total jobs audited: {len(rows)}")
    print(f"Jobs disqualified (Requires experience / Senior): {len(disqualified)}")
    print(f"Jobs confirmed strictly Fresher (0-1 yr): {len(fresher_confirmed)}")
    print("\nSample Disqualified Listings:")
    for d in disqualified[:20]:
        print(f"  ❌ [{d[4]}] {d[1]} @ {d[2]} ({d[3]}) -> Reason: {d[5]}")

if __name__ == '__main__':
    audit_jd_experience()
