import sqlite3

def clean_database():
    conn = sqlite3.connect('data/jobs.db')
    c = conn.cursor()

    c.execute("SELECT count(*) FROM jobs WHERE source_id = 'linkedin_feed'")
    before = c.fetchone()[0]
    print(f"Feed jobs count before cleanup: {before}")

    # Delete junk rows
    c.execute("""
    DELETE FROM jobs 
    WHERE source_id = 'linkedin_feed' 
    AND (
        source_url LIKE '%127.0.0.1%'
        OR source_url LIKE '%localhost%'
        OR source_url LIKE 'javascript:%'
        OR source_url LIKE '%linkedin.com/search%'
        OR source_url LIKE '%999999999%'
        OR source_url = 'Post URL Extraction Failed'
        OR company IN (
            'Outreach Direct', 'Outreach\n          Direct', 'Found a great', 'Saw a recruiter', 
            'all visible recruiter', 'Extract', 'can query live feed', 'by EXL is actively',
            'my connections. I am not', 'LinkedIn', 'LinkedIn Freshers', 'Hugo Lu',
            'Data Engineer comes in...', 'Direct fresher', 'Premium tech', 'Tech & data analytics',
            'Corporate', 'Curated digital nomad jobs', 'intern analytics', 'analyst',
            'Mass campus & fresher', 'and graduate analyst', 'business operations', 'Job Description\n\nWe are'
        )
        OR company LIKE '%Outreach Direct%'
        OR description LIKE '%Recruiter Direct Outreach%'
        OR description LIKE '%Drag the button below to your Chrome%'
        OR description LIKE '%Found a great hiring post on your feed%'
    )
    """)
    deleted = c.rowcount
    print(f"Purged {deleted} junk jobs from jobs.db.")

    # Remove duplicate Cognizant job
    c.execute("DELETE FROM jobs WHERE id = 'li_feed_ee73f0869f'")

    # Clean up Zubair job details
    c.execute("""
    UPDATE jobs 
    SET 
        title = 'Data Analyst (Fresher & Experienced)',
        company = 'Elevate Career Services',
        recruiter_name = 'Md. Zubair',
        recruiter_designation = 'Talent Sourcing Specialist',
        recruiter_email = 'Elevatecareer02@gmail.com',
        contact_phone = '+91 9012503980',
        location = 'Bengaluru, Karnataka (On-site)',
        work_mode = 'On-Site',
        salary = '₹3,00,000 - ₹6,00,000 / year'
    WHERE id = 'li_feed_f3dcc69f09'
    """)

    conn.commit()

    c.execute("SELECT count(*) FROM jobs WHERE source_id = 'linkedin_feed'")
    after = c.fetchone()[0]
    print(f"Feed jobs count after cleanup: {after}")

    print("\n--- Remaining Clean Genuine Feed Jobs ---")
    c.execute("SELECT id, title, company, recruiter_name, recruiter_email, source_url FROM jobs WHERE source_id = 'linkedin_feed'")
    for r in c.fetchall():
        print(f"{r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5][:60]}")

    conn.close()

if __name__ == '__main__':
    clean_database()
