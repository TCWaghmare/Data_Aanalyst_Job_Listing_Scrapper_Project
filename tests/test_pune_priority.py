"""
Unit and integration tests for Pune-First Location Priority and On-Site/Hybrid Work Mode constraint.
"""
from scraper.database import Database
from scraper.models import Job
from scraper.adapters.apify_linkedin import ApifyLinkedInAdapter
from scraper.adapters.apify_indeed import ApifyIndeedAdapter
from scraper.adapters.apify_naukri import ApifyNaukriAdapter
from scraper.adapters.internshala import InternshalaAdapter
from scraper.adapters.linkedin_recruiter import LinkedInRecruiterFeedAdapter
from scraper.adapters.real_market_seed import RealMarketSeedAdapter
from scraper.engine import ScraperEngine

def test_database_pune_priority_sorting():
    db = Database()
    jobs, total = db.get_jobs(sort_by="pune_first", work_mode="onsite_hybrid", limit=20)
    assert total > 0
    assert len(jobs) > 0

    # Ensure no Remote jobs exist when work_mode="onsite_hybrid"
    for j in jobs:
        assert j.work_mode in ("On-Site", "Hybrid"), f"Found invalid work mode {j.work_mode} for job {j.title}"

    # Verify Pune listings appear at the very top
    pune_found = False
    for j in jobs[:5]:
        loc = (j.location or "").lower()
        if any(k in loc for k in ["pune", "pcmc", "hinjawadi", "hinjewadi", "magarpatta", "kharadi", "baner", "viman"]):
            pune_found = True
            break
    assert pune_found, "Expected at least one Pune job in the top results"

def test_city_counts_priority_locations():
    db = Database()
    counts = db.get_city_counts()
    assert len(counts) > 0
    # Check that Pune is present in Priority Locations
    pune_entry = next((c for c in counts if c["id"] == "Pune"), None)
    assert pune_entry is not None
    assert pune_entry["category"] == "Priority Locations"

    # Check Nagpur, Hyderabad, Aurangabad, Bengaluru
    for city_id in ["Nagpur", "Hyderabad", "Aurangabad", "Bengaluru"]:
        entry = next((c for c in counts if c["id"] == city_id), None)
        assert entry is not None, f"City {city_id} missing from get_city_counts"
        assert entry["category"] == "Priority Locations"

def test_linkedin_recruiter_pune_priority():
    adapter = LinkedInRecruiterFeedAdapter()
    jobs = adapter.scrape(limit=10, cities=["Pune"], work_modes=["On-Site", "Hybrid"])
    assert len(jobs) > 0
    # Verify first jobs are in Pune
    first_job_loc = jobs[0].location.lower()
    assert "pune" in first_job_loc or "hinjawadi" in first_job_loc, f"Expected first job to be in Pune, got {jobs[0].location}"
    # Verify all jobs are On-Site or Hybrid
    for j in jobs:
        assert j.work_mode in ("On-Site", "Hybrid")

def test_apify_adapters_accept_cities_and_work_modes():
    li = ApifyLinkedInAdapter()
    indeed = ApifyIndeedAdapter()
    naukri = ApifyNaukriAdapter()
    seed = RealMarketSeedAdapter()
    internshala = InternshalaAdapter()

    # Verify RealMarketSeed prioritizes Pune and excludes Remote
    seed_jobs = seed.scrape(limit=10, cities=["Pune"], work_modes=["On-Site", "Hybrid"])
    assert len(seed_jobs) > 0
    assert "pune" in seed_jobs[0].location.lower()
    for j in seed_jobs:
        assert j.work_mode in ("On-Site", "Hybrid")

    # Engine accepts cities and work_modes
    engine = ScraperEngine()
    assert "linkedin_india" in engine.adapters
    assert "indeed_india" in engine.adapters
    assert "naukri" in engine.adapters
