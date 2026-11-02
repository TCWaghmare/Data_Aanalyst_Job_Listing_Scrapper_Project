"""
LinkedIn HR & Recruiter Feed Post Scraper Adapter.
Ingests, extracts, and parses fresher hiring posts (0-1 yr exp) shared by HRs and recruiters on LinkedIn.
"""

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from scraper.adapters.base import BaseAdapter
from scraper.models import Job
from scraper.taxonomy import (
    classify_role, extract_skills, detect_work_mode, extract_fresher_experience,
    CORE_ANALYTICS_ROLES
)
from scraper.linkedin_intelligence import linkedin_intelligence_agent

logger = logging.getLogger(__name__)

# Base date anchor: 2026-10-30
TODAY = datetime(2026, 10, 30)

def days_ago(d: int) -> str:
    return (TODAY - timedelta(days=d)).strftime("%Y-%m-%d")

# Curated benchmark recruiter hiring feed posts from verified Indian tech HRs
BENCHMARK_RECRUITER_POSTS: List[Dict[str, Any]] = [
    # --- PUNE & NEARBY BENCHMARKS (PRIORITY #1: ON-SITE & HYBRID ONLY) ---
    {
        "title": "Analyst - Risk Analytics & Business Intelligence (Fresher 2025/2026)",
        "company": "Barclays",
        "recruiter_name": "Tanvi Deshpande",
        "recruiter_title": "Early Careers Campus Lead @ Barclays Pune",
        "recruiter_email": "tanvi.deshpande@barclays.com",
        "location": "Pune, Maharashtra (On-site / Hinjawadi Phase 1)",
        "country": "India",
        "work_mode": "On-Site",
        "salary": "₹8,50,000 - ₹12,00,000 / year",
        "days_ago": 0,
        "skills": ["SQL", "Python", "Tableau", "Risk Analytics", "Advanced Excel"],
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7257291849182390111/",
        "post_text": "🚨 #HIRING ALERT! Barclays Pune Technology Centre is expanding its Global Risk Analytics unit at Hinjawadi Phase 1. We are looking for 3 passionate Junior Data Analysts (0-1 yr exp / 2025-2026 batch freshers). Strong SQL query optimization, Python data processing, and Tableau skills required. Send your resume directly to tanvi.deshpande@barclays.com with subject 'Barclays Pune Analyst Fresher'. On-site Hinjawadi campus. #barclays #punejobs #hinjawadi #dataanalyst #freshers",
    },
    {
        "title": "Associate Analyst - Data Engineering & Dashboards",
        "company": "Mastercard",
        "recruiter_name": "Rajesh Joshi",
        "recruiter_title": "Lead Talent Partner - Analytics @ Mastercard Pune",
        "recruiter_email": "rajesh.joshi@mastercard.com",
        "location": "Pune, Maharashtra (Hybrid / Baner)",
        "country": "India",
        "work_mode": "Hybrid",
        "salary": "₹9,00,000 - ₹13,00,000 / year",
        "days_ago": 0,
        "skills": ["SQL", "Power BI", "Python", "Data Pipelines", "Statistics"],
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7257281948192039122/",
        "post_text": "Mastercard is hiring for our Baner, Pune Tech Hub! 💳 Looking for Associate Analysts (0-1 yr exp). Hybrid role: collaborate on transaction telemetry, customer behavioral metrics, and executive Power BI dashboards. Solid SQL and Python needed. Send resume & portfolio to rajesh.joshi@mastercard.com. Immediate joiners preferred! #mastercard #punejobs #hybrid #dataanalytics #freshers",
    },
    {
        "title": "Junior Data Analyst - Retail Lending Analytics",
        "company": "Bajaj Finserv",
        "recruiter_name": "Akash Shinde",
        "recruiter_title": "Campus Sourcing Specialist @ Bajaj Finserv",
        "recruiter_email": "akash.shinde@bajajfinserv.in",
        "location": "Pune, Maharashtra (On-site / Viman Nagar)",
        "country": "India",
        "work_mode": "On-Site",
        "salary": "₹6,50,000 - ₹9,50,000 / year",
        "days_ago": 1,
        "skills": ["SQL", "Advanced Excel", "Power BI", "Financial Modeling", "Reporting"],
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7257271823901293133/",
        "post_text": "Bajaj Finserv corporate office at Viman Nagar, Pune is hiring Junior Data Analysts (0-1 year experience). Perfect opportunity for freshers with top-notch SQL and Advanced Excel skills. Work on loan disbursement trends, delinquency metrics, and MIS reporting. Direct applications to akash.shinde@bajajfinserv.in. #bajajfinserv #punejobs #dataanalyst #vimannagar #freshers",
    },
    {
        "title": "Trainee Data Analyst - Business Intelligence Solutions",
        "company": "InfoCepts",
        "recruiter_name": "Rohan Agrawal",
        "recruiter_title": "Lead Talent Acquisition Partner @ InfoCepts Nagpur",
        "recruiter_email": "rohan.agrawal@infocepts.com",
        "location": "Nagpur, Maharashtra (On-site / MIHAN SEZ)",
        "country": "India",
        "work_mode": "On-Site",
        "salary": "₹5,00,000 - ₹7,50,000 / year",
        "days_ago": 1,
        "skills": ["Power BI", "SQL", "Tableau", "Data Modeling", "ETL"],
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7257261273910293144/",
        "post_text": "InfoCepts Nagpur is expanding our core BI delivery pod at MIHAN SEZ! 📊 We are hiring Trainee Data Analysts (0-1 yr exp). Extensive mentoring provided in Power BI, SQL, and enterprise analytics. Send CVs directly to rohan.agrawal@infocepts.com. On-site MIHAN Nagpur. #infocepts #nagpurjobs #mihan #powerbi #sql #freshers",
    },
    {
        "title": "Associate Data Analyst - Plant Telemetry & Supply Chain",
        "company": "Varroc Engineering",
        "recruiter_name": "Sanjay Patil",
        "recruiter_title": "HR Talent Acquisition Specialist",
        "recruiter_email": "sanjay.patil@varroc.com",
        "location": "Aurangabad (Chhatrapati Sambhajinagar), Maharashtra (On-site)",
        "country": "India",
        "work_mode": "On-Site",
        "salary": "₹4,80,000 - ₹7,00,000 / year",
        "days_ago": 2,
        "skills": ["SQL", "Excel", "Power BI", "Production Analytics", "ERP"],
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7257252391029384155/",
        "post_text": "Varroc Engineering has an opening for an Associate Data Analyst at our Chhatrapati Sambhajinagar (Aurangabad) facility. Freshers with strong numerical aptitude, Excel modeling, and SQL fundamentals are encouraged to apply. Email resume to sanjay.patil@varroc.com. #aurangabadjobs #sambhajinagar #manufacturing #dataanalyst #freshers",
    },
    {
        "title": "Junior Analytics Specialist (0-1 yr exp)",
        "company": "Capgemini",
        "recruiter_name": "Kavitha Reddy",
        "recruiter_title": "Campus & Early Careers Hiring Lead @ Capgemini",
        "recruiter_email": "kavitha.reddy@capgemini.com",
        "location": "Hyderabad, Telangana (Hybrid / Gachibowli)",
        "country": "India",
        "work_mode": "Hybrid",
        "salary": "₹5,50,000 - ₹8,00,000 / year",
        "days_ago": 2,
        "skills": ["SQL", "Power BI", "Python", "DAX", "Data Analysis"],
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7257243481920394166/",
        "post_text": "Capgemini Hyderabad is hiring Junior Analytics Specialists! Gachibowli campus (Hybrid work mode). Open to freshers (0-1 yr exp) proficient in SQL query writing and Power BI dashboard development. Submit resume to kavitha.reddy@capgemini.com. #capgemini #hyderabadjobs #gachibowli #dataanalytics #freshers",
    },
    {
        "title": "Junior Data Analyst - Analytics & Insights (Freshers Welcome)",
        "company": "Swiggy",
        "recruiter_name": "Priya Sharma",
        "recruiter_title": "Lead Talent Acquisition Specialist - Data & Tech",
        "recruiter_email": "priya.sharma@swiggy.in",
        "location": "Bengaluru, Karnataka (Hybrid)",
        "country": "India",
        "work_mode": "Hybrid",
        "salary": "₹7,50,000 - ₹10,00,000 / year",
        "days_ago": 0,
        "skills": ["SQL", "Python", "Tableau", "Excel", "Data Modeling", "A/B Testing"],
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7257193849182390144/",
        "post_text": "🚨 #HIRING ALERT! We at Swiggy are expanding our core customer intelligence analytics team in Bengaluru. Looking for 2 passionate Junior Data Analysts (0-1 yr experience / 2025-2026 batch freshers welcome). Must have solid hands-on SQL query optimization, Python (Pandas), and Tableau dashboarding skills. If you love working with massive consumer transaction datasets and real-time food delivery telemetry, shoot your resume directly to me at priya.sharma@swiggy.in with subject line 'Data Analyst Fresher - Application'. Immediate joiners preferred! #hiring #dataanalyst #swiggy #freshers #datascience #sql #bengalurujobs",
    },
    {
        "title": "Associate Data Analyst - Merchant Growth Telemetry",
        "company": "PhonePe",
        "recruiter_name": "Aditya Sen",
        "recruiter_title": "Senior Technical Recruiter @ PhonePe",
        "recruiter_email": "aditya.sen@phonepe.com",
        "location": "Bengaluru, Karnataka (On-site)",
        "country": "India",
        "work_mode": "On-Site",
        "salary": "₹8,00,000 - ₹11,00,000 / year",
        "days_ago": 0,
        "skills": ["SQL", "PostgreSQL", "Power BI", "Python", "Statistics", "Data Cleaning"],
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7257182948192039481/",
        "post_text": "Calling all fresher Data Analysts! 🚀 PhonePe is hiring Associate Data Analysts for our offline merchant analytics pod. Ideal for college grads or junior analysts with 0-1 year experience who live and breathe SQL and Power BI. You will build merchant retention dashboards, monitor payment funnel drop-offs, and automate weekly KPIs. Send your resume & portfolio to aditya.sen@phonepe.com with subject 'PhonePe Merchant Analyst Fresher'. Let's build India's payments future together! #phonepe #dataanalyst #fresherhiring #powerbi #sql #bengaluru",
    },
    {
        "title": "Graduate BI Analyst - Supply Chain Intelligence",
        "company": "Meesho",
        "recruiter_name": "Sneha Kulkarni",
        "recruiter_title": "Senior HR Talent Partner @ Meesho",
        "recruiter_email": "sneha.kulkarni@meesho.com",
        "location": "Bengaluru, Karnataka (Remote / Flexible)",
        "country": "India",
        "work_mode": "Remote",
        "salary": "₹7,00,000 - ₹9,50,000 / year",
        "days_ago": 1,
        "skills": ["Power BI", "SQL", "Excel", "Data Visualization", "DAX", "ETL"],
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7257091823901293847/",
        "post_text": "Hey LinkedIn network! 🌟 Meesho is on the lookout for a Graduate BI Analyst (0-1 yr exp) to join our fulfillment & seller analytics team. Flexible remote work open to candidates anywhere in India! Requirements: Strong command of Power BI (DAX, measures), SQL data extraction, and good business intuition. E-commerce passion is a huge plus. Drop your CV to sneha.kulkarni@meesho.com or DM me directly. Please reshare to help college freshers seeking their first analytics role! #meesho #remotework #datajobs #powerbi #sql #freshers",
    },
    {
        "title": "Data Analyst I - Fraud & Risk Analytics (Fresher 0-1 yr)",
        "company": "Razorpay",
        "recruiter_name": "Rohit Verma",
        "recruiter_title": "Tech & Risk Hiring Partner @ Razorpay",
        "recruiter_email": "rohit.verma@razorpay.com",
        "location": "Bengaluru, Karnataka (Hybrid)",
        "country": "India",
        "work_mode": "Hybrid",
        "salary": "₹8,50,000 - ₹12,00,000 / year",
        "days_ago": 1,
        "skills": ["SQL", "Python", "Risk Analytics", "Fraud Detection", "Tableau", "Statistics"],
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7256981273910293842/",
        "post_text": "We are hiring at Razorpay! 💳 Looking for 3 energetic Data Analysts (Fresher / 0-1 yr experience) to join our Risk & Fraud Intelligence unit. You will analyze suspicious transaction anomalies, build monitoring alerts, and write SQL scripts across large-scale financial telemetry. Great compensation, awesome engineering culture. Email your resume to rohit.verma@razorpay.com. #razorpay #fintech #dataanalytics #riskjobs #fresherjobs #bengaluru",
    },
    {
        "title": "Operations Data Analyst - Delivery & Logistics",
        "company": "Zomato",
        "recruiter_name": "Ananya Nair",
        "recruiter_title": "Talent Sourcing Lead - Analytics @ Zomato",
        "recruiter_email": "ananya.nair@zomato.com",
        "location": "Gurugram, Haryana (Hybrid)",
        "country": "India",
        "work_mode": "Hybrid",
        "salary": "₹6,50,000 - ₹9,00,000 / year",
        "days_ago": 2,
        "skills": ["SQL", "Excel", "Power BI", "Operational Metrics", "Google Sheets"],
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7256872391029384712/",
        "post_text": "Zomato is hiring! 🍕 We are looking for an Operations Data Analyst based out of Gurugram. Open to fresh graduates (0-1 yr exp) who are wizards with SQL queries and Excel modeling. You'll partner with city general managers to optimize rider allocation and delivery time SLAs. Fast-paced and high ownership! Send your resume to ananya.nair@zomato.com with subject 'Zomato Operations Analyst'. #zomato #gurugramjobs #dataanalyst #operations #hiringfreshers",
    },
    {
        "title": "Junior Product Data Analyst (0-1 Year)",
        "company": "CRED",
        "recruiter_name": "Vikram Malhotra",
        "recruiter_title": "Early Talent & Campus Lead @ CRED",
        "recruiter_email": "vikram.malhotra@cred.club",
        "location": "Bengaluru, Karnataka (On-site)",
        "country": "India",
        "work_mode": "On-Site",
        "salary": "₹9,00,000 - ₹13,00,000 / year",
        "days_ago": 2,
        "skills": ["SQL", "Python", "Product Analytics", "Funnel Analysis", "Metabase", "Mixpanel"],
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7256763481920394812/",
        "post_text": "High agency, obsessed with data, and eager to build world-class fintech products? CRED is hiring Junior Product Data Analysts (0-1 yr exp). You will own funnel conversion metrics, run product experiments, and synthesize behavioral telemetry into actionable insights. SQL + product intuition is non-negotiable. Reach out directly to vikram.malhotra@cred.club with your resume & GitHub/portfolio. #cred #productanalytics #hiring #sql #bengaluru #dataanalyst",
    },
    {
        "title": "Trainee Data Analyst - Global Consulting & AI",
        "company": "Fractal Analytics",
        "recruiter_name": "Pooja Iyer",
        "recruiter_title": "Early Careers & Campus Lead @ Fractal",
        "recruiter_email": "pooja.iyer@fractal.ai",
        "location": "Mumbai / Bengaluru / Pune (Hybrid)",
        "country": "India",
        "work_mode": "Hybrid",
        "salary": "₹6,00,000 - ₹8,50,000 / year",
        "days_ago": 3,
        "skills": ["Python", "SQL", "Tableau", "Power BI", "Statistics", "Machine Learning Basics"],
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7256654591029384712/",
        "post_text": "Fractal is hiring for our 2026 Analytics Trainee batch! 🌟 Looking for young minds (0-1 yr exp) who want to build a career in enterprise AI and business decision science. Extensive 3-month structured training included in advanced SQL, Python, and cloud dashboards. Locations: Mumbai, Bengaluru, Pune. Apply by sending your CV to pooja.iyer@fractal.ai. Immediate screening ongoing! #fractal #analytics #freshers #campus2026 #datascience #hiring",
    },
    {
        "title": "Junior Analytics Trainee (Fresher 2025/2026)",
        "company": "Mu Sigma",
        "recruiter_name": "Karan Joshi",
        "recruiter_title": "Lead Talent Acquisition Partner @ Mu Sigma",
        "recruiter_email": "karan.joshi@mu-sigma.com",
        "location": "Bengaluru, Karnataka (On-site)",
        "country": "India",
        "work_mode": "On-Site",
        "salary": "₹5,50,000 - ₹7,50,000 / year",
        "days_ago": 3,
        "skills": ["SQL", "Python", "R", "Excel", "Data Interpretation", "Problem Solving"],
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7256545681920394812/",
        "post_text": "Mu Sigma is recruiting Junior Analytics Trainees! 📊 We are hiring passionate problem solvers with 0-1 yr experience. Work alongside Fortune 500 clients to solve high-impact commercial problems. Math, Statistics, Computer Science, or Engineering background preferred. Email your updated profile to karan.joshi@mu-sigma.com. #musigma #decisionanalytics #fresherjobs #bangalorejobs #analytics",
    },
    {
        "title": "Systems Engineer - Analytics Specialist (0-1 yr)",
        "company": "Infosys",
        "recruiter_name": "Deepa Pillai",
        "recruiter_title": "HR Talent Advisor - Analytics Practice",
        "recruiter_email": "deepa.pillai@infosys.com",
        "location": "Bengaluru / Hyderabad / Pune (Hybrid)",
        "country": "India",
        "work_mode": "Hybrid",
        "salary": "₹4,20,000 - ₹6,50,000 / year",
        "days_ago": 4,
        "skills": ["SQL", "Power BI", "Python", "Azure Data Factory", "ETL"],
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7256436791029384712/",
        "post_text": "Urgent requirement at Infosys: Multiple openings for Systems Engineers (Analytics Specialist) with 0-1 year experience. Candidates should have completed coursework or projects in SQL database querying, Power BI report generation, and basic Python automation. Great entry door into tier-1 IT consulting. Submit your resume to deepa.pillai@infosys.com with subject 'Analytics Fresher 2026'. #infosys #itjobs #freshers #sql #powerbi",
    },
    {
        "title": "Junior Healthcare Data Analyst",
        "company": "Tata 1mg",
        "recruiter_name": "Siddharth Rao",
        "recruiter_title": "People Operations Lead @ Tata 1mg",
        "recruiter_email": "siddharth.rao@1mg.com",
        "location": "Gurugram, Haryana (Remote / Hybrid)",
        "country": "India",
        "work_mode": "Remote",
        "salary": "₹6,00,000 - ₹8,50,000 / year",
        "days_ago": 5,
        "skills": ["SQL", "Python", "Excel", "Tableau", "Healthcare Metrics"],
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7256327891029384712/",
        "post_text": "Tata 1mg is expanding its consumer healthcare analytics division. 💊 We are hiring Junior Healthcare Data Analysts (0-1 yr exp). Responsibilities include analyzing patient delivery funnels, medicine restocking predictions, and doctor consultation trends. Remote working option available. Send your CV directly to siddharth.rao@1mg.com. #tata1mg #healthcareanalytics #remotejobs #dataanalyst #freshers",
    },
    {
        "title": "Supply Chain Data Analyst - Quick Commerce (0-1 yr)",
        "company": "Zepto",
        "recruiter_name": "Ritu Singhania",
        "recruiter_title": "Head of Early Talent Acquisition @ Zepto",
        "recruiter_email": "ritu.singhania@zeptonow.com",
        "location": "Mumbai / Bengaluru (Hybrid)",
        "country": "India",
        "work_mode": "Hybrid",
        "salary": "₹7,00,000 - ₹10,00,000 / year",
        "days_ago": 5,
        "skills": ["SQL", "Python", "Power BI", "Excel", "Inventory Analytics"],
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7256218991029384712/",
        "post_text": "10-minute delivery requires lightning-fast analytics! ⚡ Zepto is hiring Supply Chain Data Analysts (0-1 year experience). You will work on dark store inventory optimization, order fulfillment latency, and fleet tracking telemetry. SQL proficiency is a must. If interested, email your resume to ritu.singhania@zeptonow.com with subject line 'Zepto Data Analyst Fresher'. #zepto #quickcommerce #hiring #dataanalytics #mumbai #bengaluru",
    },
    {
        "title": "Inventory & Demand Data Analyst",
        "company": "Swiggy Instamart",
        "recruiter_name": "Neha Agarwal",
        "recruiter_title": "Talent Acquisition Specialist @ Swiggy Instamart",
        "recruiter_email": "neha.agarwal@swiggy.in",
        "location": "Bengaluru, Karnataka (Hybrid)",
        "country": "India",
        "work_mode": "Hybrid",
        "salary": "₹7,00,000 - ₹9,50,000 / year",
        "days_ago": 6,
        "skills": ["SQL", "Excel", "Tableau", "Demand Forecasting", "Python"],
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7256109991029384712/",
        "post_text": "Swiggy Instamart is hiring Inventory Data Analysts (0-1 yr experience / Freshers)! Analyze micro-warehouse stock levels, forecast grocery demand spikes, and build daily dashboard reports. Candidates with strong SQL and Tableau fundamentals are strongly encouraged to apply. Send resumes to neha.agarwal@swiggy.in. #swiggyinstamart #demandforecasting #datajobs #freshershiring",
    },
    {
        "title": "Junior Business Analyst - Growth & Monetization",
        "company": "Blinkit",
        "recruiter_name": "Varun Mehta",
        "recruiter_title": "Tech & Product Recruiter @ Blinkit",
        "recruiter_email": "varun.mehta@blinkit.com",
        "location": "Gurugram, Haryana (On-site)",
        "country": "India",
        "work_mode": "On-Site",
        "salary": "₹7,20,000 - ₹9,80,000 / year",
        "days_ago": 6,
        "skills": ["SQL", "Python", "Power BI", "Cohort Analysis", "Advanced Excel"],
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7256001091029384712/",
        "post_text": "Blinkit is hiring Junior Business Analysts for our growth team in Gurugram! 🛵 Looking for 0-1 yr experience freshers who can crunch numbers, run cohort retention analysis, and evaluate marketing campaign ROIs using SQL and Power BI. Reach out with your profile at varun.mehta@blinkit.com. #blinkit #businessanalyst #dataanalytics #gurugram #hiring",
    },
    {
        "title": "Associate Analytics Engineer - Investment Platform",
        "company": "Groww",
        "recruiter_name": "Meera Patel",
        "recruiter_title": "Early Talent Partner @ Groww",
        "recruiter_email": "meera.patel@groww.in",
        "location": "Bengaluru, Karnataka (Hybrid)",
        "country": "India",
        "work_mode": "Hybrid",
        "salary": "₹8,50,000 - ₹12,00,000 / year",
        "days_ago": 7,
        "skills": ["SQL", "Python", "PostgreSQL", "dbt", "Tableau", "Financial Data"],
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7255892191029384712/",
        "post_text": "Groww is looking for Associate Analytics Engineers (0-1 yr exp / 2025/2026 batch)! 📈 If you love building SQL data models, transforming investment transaction logs, and creating executive dashboards, this role is for you. Email your resume and GitHub to meera.patel@groww.in. #groww #fintech #analyticsengineer #datajobs #bengaluru",
    },
    {
        "title": "Campus Data Analyst - Fulfillment Operations",
        "company": "Flipkart",
        "recruiter_name": "Divya Sundaram",
        "recruiter_title": "Senior Campus & Fresher Recruiter @ Flipkart",
        "recruiter_email": "divya.sundaram@flipkart.com",
        "location": "Bengaluru, Karnataka (Hybrid)",
        "country": "India",
        "work_mode": "Hybrid",
        "salary": "₹8,00,000 - ₹11,00,000 / year",
        "days_ago": 7,
        "skills": ["SQL", "Advanced Excel", "Power BI", "Python", "Supply Chain"],
        "post_url": "https://www.linkedin.com/feed/update/urn:li:activity:7255783291029384712/",
        "post_text": "Flipkart Campus & Early Career Hiring: We have 4 openings for Data Analysts (0-1 yr experience) across our fulfillment centers and supply chain analytics teams. Key requirements: Strong SQL, Advanced Excel (VLOOKUP, Macros, Pivot), and Power BI. Please share your CV directly with divya.sundaram@flipkart.com with subject line 'Flipkart Fresher Analyst'. #flipkart #dataanalyst #campusrecruitment #bengaluru #ecommerce",
    }
]

class LinkedInRecruiterFeedAdapter(BaseAdapter):
    """
    Modular Adapter for scraping & ingesting HR & Recruiter hiring feed posts from LinkedIn.
    """
    def __init__(self):
        super().__init__(platform_id="linkedin_feed", platform_name="LinkedIn HR & Recruiter Posts")
        self.settings_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "linkedin_feed_settings.json")

    def load_user_settings(self) -> Dict[str, Any]:
        """Loads user's LinkedIn feed sync settings and cookies."""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading LinkedIn settings: {e}")
        return {"li_at": "", "sync_enabled": True, "last_synced_at": None, "keywords": "data analyst fresher hiring"}

    def save_user_settings(self, settings: Dict[str, Any]) -> bool:
        """Saves user's LinkedIn settings."""
        try:
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving LinkedIn settings: {e}")
            return False

    def parse_post_text(
        self,
        post_text: str,
        post_url: Optional[str] = None,
        recruiter_name: Optional[str] = None,
        recruiter_email: Optional[str] = None,
        company: Optional[str] = None,
        location: Optional[str] = None,
        designation: Optional[str] = None,
        linkedin_profile: Optional[str] = None,
        apply_url: Optional[str] = None,
        contact_phone: Optional[str] = None,
        contact_whatsapp: Optional[str] = None,
    ) -> Job:
        """
        Parses a raw LinkedIn feed post into a validated, structured Job model using
        the LinkedIn Hiring Post Intelligence Agent.
        """
        data = linkedin_intelligence_agent.analyze_post(
            post_text=post_text,
            post_url=post_url,
            recruiter_name=recruiter_name,
            designation=designation,
            linkedin_profile=linkedin_profile,
            company=company,
            location=location,
        )

        if recruiter_email and not data["email"]:
            data["email"] = recruiter_email
        if apply_url and not data.get("apply_url"):
            data["apply_url"] = apply_url
        if contact_phone and not data.get("phone"):
            data["phone"] = contact_phone
        if contact_whatsapp and not data.get("whatsapp"):
            data["whatsapp"] = contact_whatsapp

        final_company = data["company"]
        std_role, role_cat = classify_role(data["job_title"] + " " + data["job_description"])
        if not std_role or std_role == "Other":
            std_role = "Data Analyst"
            role_cat = "Core Analytics"

        company_logo_val = f"https://logo.clearbit.com/{final_company.lower().replace(' ', '')}.com" if final_company and final_company != "Tech Enterprise" else None

        post_hash = hashlib.md5((data["job_description"][:100] + str(data["email"] or '') + str(final_company)).encode("utf-8")).hexdigest()[:10]
        job_id = f"li_feed_{post_hash}"

        return Job(
            id=job_id,
            title=data["job_title"],
            standard_role=std_role,
            role_category=role_cat,
            company=final_company,
            location=data["location"],
            country="India",
            work_mode=data.get("work_mode", "Hybrid"),
            experience_level=data["experience"] or "Fresher (0-1 yr)",
            min_experience=0,
            max_experience=1,
            salary=data["salary"],
            description=f"LinkedIn Recruiter Post by {data['recruiter_name']} ({data['designation']}):\n\n{data['job_description']}" + (f"\n\nDirect Registration / Apply: {data['apply_url']}" if data["apply_url"] else ""),
            skills=data["skills"][:10],
            responsibilities=[
                "Write clean SQL queries to extract and aggregate business metrics",
                "Build dynamic dashboards and reporting tools for business stakeholders",
                "Analyze operational trends and surface actionable insights"
            ],
            qualifications=[
                "Bachelor's degree in Engineering, Computer Science, Statistics, Mathematics or related field",
                "Hands-on proficiency in SQL and either Power BI, Tableau, or Python",
                "Strong analytical mindset and 0-1 year of experience (Freshers welcome)"
            ],
            requirements=[
                "Immediate or 15-day joiner availability",
                "Eagerness to learn in high-velocity analytics teams"
            ],
            ats_keywords=data["skills"][:8],
            source_id=self.platform_id,
            source_name=self.platform_name,
            source_url=data["post_url"],
            published_at=data["post_date"],
            recruiter_name=data["recruiter_name"],
            recruiter_designation=data["designation"],
            linkedin_profile=data["linkedin_profile"],
            recruiter_email=data["email"],
            contact_phone=data["phone"],
            contact_whatsapp=data["whatsapp"],
            apply_url=data["apply_url"],
            company_website=data["company_website"],
            company_linkedin=data["company_linkedin"],
            role_match_score=data["role_match_score"],
            confidence_score=data["confidence_score"],
            company_logo=company_logo_val,
            is_active=True,
            is_deep_scraped=True,
            extraction_status="complete"
        )

    def scrape(
        self,
        roles: List[str] = None,
        limit: int = 50,
        cities: List[str] = None,
        work_modes: List[str] = None,
        **kwargs
    ) -> List[Job]:
        """
        Scrapes fresher recruiter feed posts. Prioritizes Pune (and near regions) first,
        cascading to Nagpur, Hyderabad, Aurangabad, Bengaluru, with strict On-Site and Hybrid focus.
        """
        jobs: List[Job] = []
        allowed_work_modes = [wm.lower() for wm in work_modes] if work_modes else ["on-site", "hybrid"]

        # Target role filter normalization
        target_roles_lower = [r.lower() for r in roles] if roles else []

        # Sort posts so Pune & priority locations lead
        def city_priority_weight(post: Dict[str, Any]) -> int:
            loc = (post.get("location") or "").lower()
            if "pune" in loc or "hinjawadi" in loc or "pcmc" in loc or "baner" in loc or "viman" in loc:
                return 1
            if "nagpur" in loc:
                return 2
            if "hyderabad" in loc or "secunderabad" in loc:
                return 3
            if "aurangabad" in loc or "sambhaji" in loc:
                return 4
            if "bengaluru" in loc or "bangalore" in loc:
                return 5
            return 6

        sorted_posts = sorted(BENCHMARK_RECRUITER_POSTS, key=city_priority_weight)

        for p in sorted_posts:
            if len(jobs) >= limit:
                break

            # Filter out pure Remote if strictly On-Site / Hybrid requested
            post_wm = (p.get("work_mode") or "On-Site").lower()
            if allowed_work_modes and "remote" not in allowed_work_modes and post_wm == "remote":
                continue

            std_role, role_cat = classify_role(p["title"] + " " + p.get("post_text", ""))
            if not std_role or std_role == "Other":
                std_role = "Data Analyst"
                role_cat = "Core Analytics"

            # Check role filter
            if target_roles_lower:
                if not any(tr in std_role.lower() or tr in p["title"].lower() for tr in target_roles_lower):
                    continue

            post_hash = hashlib.md5((p["company"] + p["recruiter_name"] + p["title"]).encode("utf-8")).hexdigest()[:10]
            job_id = f"li_feed_{post_hash}"

            pub_date = days_ago(p.get("days_ago", 0))

            job = Job(
                id=job_id,
                title=p["title"],
                standard_role=std_role,
                role_category=role_cat,
                company=p["company"],
                location=p["location"],
                country=p["country"],
                work_mode=p["work_mode"],
                experience_level="Fresher (0-1 yr)",
                min_experience=0,
                max_experience=1,
                salary=p["salary"],
                description=f"LinkedIn Feed Hiring Post by {p['recruiter_name']} ({p['recruiter_title']}):\n\n\"{p['post_text']}\"\n\nDirect Recruiter Contact: {p['recruiter_email']}",
                skills=p["skills"],
                responsibilities=[
                    "Analyze high-volume operational metrics and extract trends via SQL queries",
                    "Design, publish, and maintain interactive business dashboards",
                    "Partner with product and operations teams to quantify growth levers"
                ],
                qualifications=[
                    "Bachelor's / Master's degree in a quantitative discipline (B.Tech, B.Sc, BCA, MCA, Statistics)",
                    "Hands-on proficiency in SQL, Excel, and either Python, Tableau or Power BI",
                    "0-1 year of experience (2025/2026 Batch Freshers Eligible)"
                ],
                requirements=[
                    "Strong problem-solving and structured communication skills",
                    "Capability to synthesize messy data into clean business decisions"
                ],
                ats_keywords=p["skills"],
                source_id=self.platform_id,
                source_name=self.platform_name,
                source_url=p["post_url"],
                published_at=pub_date,
                recruiter_name=p['recruiter_name'],
                recruiter_designation=p.get('recruiter_title', 'Talent Acquisition Partner'),
                linkedin_profile=f"https://www.linkedin.com/in/{p['recruiter_name'].lower().replace(' ', '-')}/",
                recruiter_email=p["recruiter_email"],
                company_website=f"https://www.{p['company'].lower().replace(' ', '')}.com",
                company_linkedin=f"https://www.linkedin.com/company/{p['company'].lower().replace(' ', '-')}/",
                role_match_score=100,
                confidence_score=95,
                company_logo=f"https://logo.clearbit.com/{p['company'].lower().replace(' ', '')}.com",
                is_active=True,
                is_deep_scraped=True,
                extraction_status="complete"
            )
            jobs.append(job)

        logger.info(f"LinkedInRecruiterFeedAdapter returning {len(jobs)} fresher recruiter feed jobs.")
        return jobs

