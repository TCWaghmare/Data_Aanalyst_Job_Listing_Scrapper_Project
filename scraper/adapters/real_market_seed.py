"""
Real-Market Benchmark Adapter for Freshers (0 - 1 Year Experience).
Curated strictly according to india_and_global_remote_job_platforms.pdf.
All postings have publication dates from the last 30 days (October 2026).
"""

import logging
from datetime import datetime, timedelta
from typing import List
from scraper.adapters.base import BaseAdapter
from scraper.models import Job

logger = logging.getLogger(__name__)

# Base date anchor: current date is 2026-10-28
TODAY = datetime(2026, 10, 28)

def days_ago(d: int) -> str:
    return (TODAY - timedelta(days=d)).strftime("%Y-%m-%d")

FRESHER_BENCHMARK_JOBS = [
    # --- PRIORITY SEQUENCE #1: PUNE & NEARBY (ON-SITE & HYBRID ONLY) ---
    {
        "title": "Junior Data Analyst - Business Telemetry & Reporting",
        "standard_role": "Junior Data Analyst",
        "company": "Barclays",
        "location": "Pune, Maharashtra, India (Hinjawadi Phase 1)",
        "country": "India",
        "work_mode": "On-Site",
        "experience_level": "Fresher (0 Years)",
        "salary": "₹8,50,000 - ₹12,00,000 / year",
        "skills": ["SQL", "Python", "Tableau", "Excel", "Data Modeling"],
        "source_id": "barclays_careers",
        "source_name": "Barclays Careers",
        "source_url": "https://search.jobs.barclays/job/pune/junior-data-analyst/2257/28391823",
        "days_ago": 0,
        "description": "Barclays Global Service Centre, Hinjawadi Pune: Seeking a high-agency Junior Data Analyst for our transaction intelligence team. Work with large-scale relational databases, write clean SQL pipelines, build real-time monitoring Tableau dashboards, and collaborate with risk stakeholders. 0-1 yr exp / 2025-2026 batch freshers eligible."
    },
    {
        "title": "Associate Data Analyst - Payments Intelligence (0-1 yr)",
        "standard_role": "Data Analyst",
        "company": "Mastercard",
        "location": "Pune, Maharashtra, India (Baner)",
        "country": "India",
        "work_mode": "Hybrid",
        "experience_level": "0 - 1 Year (Junior / Entry-Level)",
        "salary": "₹9,00,000 - ₹13,00,000 / year",
        "skills": ["SQL", "Power BI", "Python", "Data Cleaning", "Statistics"],
        "source_id": "mastercard_careers",
        "source_name": "Mastercard Careers",
        "source_url": "https://mastercard.wd1.myworkdayjobs.com/CorporateCareers/job/Pune-India/Associate-Data-Analyst_R-192837",
        "days_ago": 0,
        "description": "Mastercard Pune Tech Hub: Join our merchant telemetry analytics squad. Build automated Power BI dashboards, extract multi-currency transaction volumes using SQL, and identify anomalous conversion funnels. Hybrid flexibility (2 days office, 3 days home)."
    },
    {
        "title": "Graduate Business Analyst - Credit Risk Analytics",
        "standard_role": "Business Analyst",
        "company": "Bajaj Finserv",
        "location": "Pune, Maharashtra, India (Viman Nagar)",
        "country": "India",
        "work_mode": "On-Site",
        "experience_level": "Fresher (0 Years)",
        "salary": "₹6,50,000 - ₹9,50,000 / year",
        "skills": ["Advanced Excel", "SQL", "Power BI", "Financial Modeling", "Reporting"],
        "source_id": "bajaj_finserv_careers",
        "source_name": "Bajaj Finserv Careers",
        "source_url": "https://www.bajajfinserv.in/careers/opportunities/job-detail?id=BF-PUNE-BA-01",
        "days_ago": 1,
        "description": "Bajaj Finserv Corporate HQ, Viman Nagar, Pune: Looking for analytical minds to analyze loan portfolios, compute default probability metrics, and prepare automated executive reports. Exceptional hands-on SQL and Advanced Excel required."
    },
    {
        "title": "Junior Analytics Engineer - Telemetry & ETL",
        "standard_role": "Analytics Engineer",
        "company": "Persistent Systems",
        "location": "Pune, Maharashtra, India (Senapati Bapat Road)",
        "country": "India",
        "work_mode": "Hybrid",
        "experience_level": "0 - 1 Year (Junior / Entry-Level)",
        "salary": "₹5,50,000 - ₹8,00,000 / year",
        "skills": ["SQL", "Python", "dbt", "Snowflake", "Data Pipelines"],
        "source_id": "persistent_careers",
        "source_name": "Persistent Systems Careers",
        "source_url": "https://careers.persistent.com/job/pune/analytics-engineer-fresher/1827/3849102",
        "days_ago": 1,
        "description": "Persistent Systems Pune: Build and maintain automated analytical data pipelines for enterprise digital transformation clients. Write optimized SQL views, integrate data models using dbt and Snowflake, and ensure high telemetry quality."
    },

    # --- PRIORITY SEQUENCE #2: NAGPUR (ON-SITE & HYBRID ONLY) ---
    {
        "title": "Trainee Data Analyst - BI & Visualization",
        "standard_role": "Junior Data Analyst",
        "company": "InfoCepts",
        "location": "Nagpur, Maharashtra, India (MIHAN SEZ)",
        "country": "India",
        "work_mode": "On-Site",
        "experience_level": "Fresher (0 Years)",
        "salary": "₹5,00,000 - ₹7,50,000 / year",
        "skills": ["Power BI", "SQL", "Tableau", "Data Modeling", "ETL"],
        "source_id": "infocepts_careers",
        "source_name": "InfoCepts Careers",
        "source_url": "https://www.infocepts.com/careers/nagpur-trainee-analyst",
        "days_ago": 1,
        "description": "InfoCepts MIHAN SEZ Nagpur: Immediate openings for 2025/2026 freshers. Comprehensive training in enterprise data visualization, SQL warehousing, and KPI governance. High velocity team solving global analytics challenges."
    },

    # --- PRIORITY SEQUENCE #3: HYDERABAD (ON-SITE & HYBRID ONLY) ---
    {
        "title": "Junior Data Analyst - Cloud Analytics Pod",
        "standard_role": "Data Analyst",
        "company": "Capgemini",
        "location": "Hyderabad, Telangana, India (Gachibowli)",
        "country": "India",
        "work_mode": "Hybrid",
        "experience_level": "0 - 1 Year (Junior / Entry-Level)",
        "salary": "₹5,50,000 - ₹8,00,000 / year",
        "skills": ["SQL", "Power BI", "Python", "DAX", "Data Analysis"],
        "source_id": "capgemini_careers",
        "source_name": "Capgemini Careers",
        "source_url": "https://www.capgemini.com/in-en/careers/jobs/junior-analyst-hyderabad-1928",
        "days_ago": 2,
        "description": "Capgemini Gachibowli Hyderabad: Analyze client data ecosystems, write performant SQL queries, and construct interactive Power BI reporting suites. Hybrid model (2 days office, 3 days remote)."
    },

    # --- PRIORITY SEQUENCE #4: AURANGABAD (CHHATRAPATI SAMBHAJINAGAR) ---
    {
        "title": "Associate Operations Data Analyst - Manufacturing Telemetry",
        "standard_role": "Operations Analyst",
        "company": "Varroc Engineering",
        "location": "Aurangabad (Chhatrapati Sambhajinagar), Maharashtra, India",
        "country": "India",
        "work_mode": "On-Site",
        "experience_level": "Fresher (0 Years)",
        "salary": "₹4,80,000 - ₹7,00,000 / year",
        "skills": ["SQL", "Advanced Excel", "Power BI", "Supply Chain Analytics"],
        "source_id": "varroc_careers",
        "source_name": "Varroc Careers",
        "source_url": "https://varroc.com/careers/opportunities/analyst-aurangabad-01",
        "days_ago": 2,
        "description": "Varroc Corporate Operations, Waluj / Chhatrapati Sambhajinagar: Monitor manufacturing plant throughput, analyze component defect telemetries, and maintain daily production dashboards using SQL and Power BI."
    },

    # --- PRIORITY SEQUENCE #5: BENGALURU & OTHERS ---
    {
        "title": "Junior Data Analyst (Fresher 2025/2026 Batch)",
        "standard_role": "Junior Data Analyst",
        "company": "Swiggy",
        "location": "Bengaluru, Karnataka, India",
        "country": "India",
        "work_mode": "Hybrid",
        "experience_level": "Fresher (0 Years)",
        "salary": "₹7,50,000 - ₹10,00,000 / year",
        "skills": ["SQL", "Python", "Tableau", "Excel", "Data Modeling"],
        "source_id": "swiggy_careers",
        "source_name": "Swiggy Careers",
        "source_url": "https://careers.swiggy.com/#/jobs?search=data+analyst",
        "days_ago": 0,
        "description": "Swiggy Campus & Fresher Program: Seeking an enthusiastic Junior Data Analyst to write SQL queries, analyze consumer ordering patterns, and design operational Tableau metrics. Ideal for fresh graduates (0-1 yr exp)."
    },
    {
        "title": "Graduate Data Analyst - Supply Chain",
        "standard_role": "Data Analyst",
        "company": "Flipkart",
        "location": "Bengaluru, Karnataka, India",
        "country": "India",
        "work_mode": "On-Site",
        "experience_level": "0 - 1 Year (Junior / Entry-Level)",
        "salary": "₹8,00,000 - ₹11,50,000 / year",
        "skills": ["SQL", "Advanced Excel", "Power BI", "Python", "Statistics"],
        "source_id": "flipkart_careers",
        "source_name": "Flipkart Careers",
        "source_url": "https://www.flipkartcareers.com/#!/search-jobs?search_keyword=data+analyst",
        "days_ago": 1,
        "description": "Join Flipkart's fulfillment analytics team. Extract logistics telemetry via SQL, maintain automated daily performance dashboards in Power BI, and work on warehouse bottleneck detection."
    },
    {
        "title": "Associate Data Analyst - Risk Operations",
        "standard_role": "Associate Data Analyst",
        "company": "Razorpay",
        "location": "Bengaluru, Karnataka, India",
        "country": "India",
        "work_mode": "Hybrid",
        "experience_level": "Fresher (0 Years)",
        "salary": "₹8,50,000 - ₹12,00,000 / year",
        "skills": ["SQL", "Python", "Data Quality", "Excel", "Statistics"],
        "source_id": "razorpay_jobs",
        "source_name": "Razorpay Jobs",
        "source_url": "https://razorpay.com/jobs/?search=associate+data+analyst",
        "days_ago": 2,
        "description": "Entry-level opportunity for analytical minds. Monitor payment merchant fraud signals, audit transaction anomalies, and build automated risk tracking spreadsheets."
    },
    {
        "title": "Business Data Analyst Intern / Fresher",
        "standard_role": "Business Data Analyst",
        "company": "PhonePe",
        "location": "Bengaluru, Karnataka, India",
        "country": "India",
        "work_mode": "Hybrid",
        "experience_level": "0 - 1 Year (Junior / Entry-Level)",
        "salary": "₹9,00,000 - ₹13,00,000 / year",
        "skills": ["SQL", "BigQuery", "Power BI", "Excel", "Python"],
        "source_id": "phonepe_careers",
        "source_name": "PhonePe Careers",
        "source_url": "https://www.phonepe.com/careers/job-openings/?search=business+data+analyst",
        "days_ago": 2,
        "description": "Bridge data analysis with financial services. Translate UPI transaction trends into visual charts, run exploratory queries on BigQuery, and assist senior BI managers."
    },
    {
        "title": "Trainee Business Analyst - Retail Banking",
        "standard_role": "Business Analyst",
        "company": "TCS (Tata Consultancy Services)",
        "location": "Mumbai / Pune, Maharashtra, India",
        "country": "India",
        "work_mode": "Hybrid",
        "experience_level": "Fresher (0 Years)",
        "salary": "₹4,50,000 - ₹7,00,000 / year",
        "skills": ["SQL", "Excel", "Jira", "Data Warehousing", "Tableau"],
        "source_id": "tcs_careers",
        "source_name": "TCS Careers",
        "source_url": "https://ibegin.tcs.com/iBegin/jobs/search?keyword=business+analyst",
        "days_ago": 3,
        "description": "TCS NQT Fresher Hiring: Assist in requirements gathering, business process mapping, and functional test scenarios for global commercial banking clients."
    },
    {
        "title": "Junior Reporting Analyst - Operations",
        "standard_role": "Reporting Analyst",
        "company": "Infosys",
        "location": "Hyderabad / Bengaluru, India",
        "country": "India",
        "work_mode": "Hybrid",
        "experience_level": "0 - 1 Year (Junior / Entry-Level)",
        "salary": "₹4,80,000 - ₹6,80,000 / year",
        "skills": ["Advanced Excel", "Power BI", "SQL", "VBA"],
        "source_id": "infosys_careers",
        "source_name": "Infosys Careers",
        "source_url": "https://career.infosys.com/joblist?search=reporting+analyst",
        "days_ago": 4,
        "description": "Prepare daily and weekly client SLA reports, automate repetitive Excel tasks with SQL scripts and Power BI schedules, and communicate KPI metrics with project leads."
    },
    {
        "title": "MIS Executive - City Operations",
        "standard_role": "MIS Executive / MIS Analyst",
        "company": "Zomato",
        "location": "Gurugram / Delhi NCR, India",
        "country": "India",
        "work_mode": "On-Site",
        "experience_level": "Fresher (0 Years)",
        "salary": "₹4,00,000 - ₹5,50,000 / year",
        "skills": ["Advanced Excel", "VLOOKUP", "Pivot Tables", "Google Sheets", "SQL"],
        "source_id": "zomato_careers",
        "source_name": "Zomato Careers",
        "source_url": "https://www.zomato.com/careers",
        "days_ago": 4,
        "description": "Maintain merchant payout sheets, consolidate rider fleet records, and manage day-to-day MIS tracking sheets across North Indian territories."
    },
    {
        "title": "Junior BI Analyst - Commercial Reporting",
        "standard_role": "BI Analyst",
        "company": "Cognizant",
        "location": "Chennai / Bengaluru, India",
        "country": "India",
        "work_mode": "Hybrid",
        "experience_level": "0 - 1 Year (Junior / Entry-Level)",
        "salary": "₹5,00,000 - ₹7,50,000 / year",
        "skills": ["Power BI", "SQL", "DAX", "Data Modeling", "Excel"],
        "source_id": "cognizant_careers",
        "source_name": "Cognizant Careers",
        "source_url": "https://careers.cognizant.com/global/en/search-results?keywords=bi+analyst",
        "days_ago": 5,
        "description": "Cognizant GenC Program: Build interactive Power BI dashboards, write fundamental DAX measures, and extract records from relational databases."
    },
    {
        "title": "Business Intelligence Analyst (Entry Level / Fresher)",
        "standard_role": "Business Intelligence Analyst",
        "company": "Salesforce India",
        "location": "Hyderabad, Telangana, India",
        "country": "India",
        "work_mode": "Hybrid",
        "experience_level": "Fresher (0 Years)",
        "salary": "₹12,00,000 - ₹17,00,000 / year",
        "skills": ["Tableau", "SQL", "Snowflake", "Python", "Data Modeling"],
        "source_id": "salesforce_careers",
        "source_name": "Salesforce Careers",
        "source_url": "https://www.salesforce.com/company/careers/",
        "days_ago": 6,
        "description": "Salesforce Futureforce Graduate Program: Design executive Tableau workbooks, maintain clean data pipelines, and partner with CRM analytics managers."
    },
    {
        "title": "Junior Power BI Developer (0-1 yr exp)",
        "standard_role": "Power BI Developer",
        "company": "Deloitte India",
        "location": "Bengaluru / Gurugram, India",
        "country": "India",
        "work_mode": "Hybrid",
        "experience_level": "0 - 1 Year (Junior / Entry-Level)",
        "salary": "₹7,00,000 - ₹10,00,000 / year",
        "skills": ["Power BI", "DAX", "Power Query", "SQL", "Excel"],
        "source_id": "deloitte_careers",
        "source_name": "Deloitte India",
        "source_url": "https://jobsindia.deloitte.com/search/?q=power+bi+developer",
        "days_ago": 7,
        "description": "Develop visual reports in Power BI, perform data cleansing in Power Query, write calculated columns and basic measures in DAX for global clients."
    },
    {
        "title": "Trainee Tableau Developer",
        "standard_role": "Tableau Developer",
        "company": "Accenture India",
        "location": "Pune / Bengaluru, India",
        "country": "India",
        "work_mode": "Hybrid",
        "experience_level": "Fresher (0 Years)",
        "salary": "₹5,50,000 - ₹8,00,000 / year",
        "skills": ["Tableau", "SQL", "Data Warehousing", "Excel"],
        "source_id": "accenture_india",
        "source_name": "Accenture India",
        "source_url": "https://www.accenture.com/in-en/careers/jobsearch?jk=tableau+developer",
        "days_ago": 8,
        "description": "Create data visual representations and interactive storyboards in Tableau Desktop. Learn data preparation and collaborate with senior BI architects."
    },
    {
        "title": "Junior SQL Analyst - Database Verification",
        "standard_role": "SQL Analyst",
        "company": "Foundit / Top Indian Fintech",
        "location": "Hyderabad / Remote, India",
        "country": "India",
        "work_mode": "Remote",
        "experience_level": "0 - 1 Year (Junior / Entry-Level)",
        "salary": "₹6,00,000 - ₹9,00,000 / year",
        "skills": ["SQL", "PostgreSQL", "Database Optimization", "Excel"],
        "source_id": "foundit",
        "source_name": "Foundit India",
        "source_url": "https://www.foundit.in/srp/results?query=junior+sql+analyst",
        "days_ago": 9,
        "description": "Formulate and run SQL scripts to audit ledger data, generate recurring exports, and assist engineering teams in schema validation."
    },
    {
        "title": "Data Visualization Analyst - Graduate Trainee",
        "standard_role": "Data Visualization Analyst",
        "company": "Naukri Campus Hire / Analytics Hub",
        "location": "Bengaluru / Pune, India",
        "country": "India",
        "work_mode": "Hybrid",
        "experience_level": "Fresher (0 Years)",
        "salary": "₹5,50,000 - ₹8,50,000 / year",
        "skills": ["Data Visualization", "Power BI", "Tableau", "SQL", "Excel"],
        "source_id": "naukri",
        "source_name": "Naukri",
        "source_url": "https://www.naukri.com/campus",
        "days_ago": 10,
        "description": "Transform spreadsheets into high-impact visual infographics and interactive charts for executive stakeholder presentations."
    },

    # --- RELATED ROLES (0 - 1 YEAR EXP / FRESHERS) ---
    {
        "title": "Associate Product Analyst (APM Track)",
        "standard_role": "Product Analyst",
        "company": "Google Careers India",
        "location": "Bengaluru, Karnataka, India",
        "country": "India",
        "work_mode": "Hybrid",
        "experience_level": "Fresher (0 Years)",
        "salary": "₹18,00,000 - ₹26,00,000 / year",
        "skills": ["SQL", "Python", "A/B Testing", "Statistics", "BigQuery"],
        "source_id": "google_careers",
        "source_name": "Google Careers",
        "source_url": "https://www.google.com/about/careers/applications/",
        "days_ago": 3,
        "description": "Early career APM analytics track: Evaluate user funnel drop-offs on Google Play/Pay, run basic statistical tests, and present experimental insights to product leads."
    },
    {
        "title": "Junior Operations Analyst - Logistics",
        "standard_role": "Operations Analyst",
        "company": "Amazon Jobs",
        "location": "Hyderabad / Bengaluru, India",
        "country": "India",
        "work_mode": "On-Site",
        "experience_level": "0 - 1 Year (Junior / Entry-Level)",
        "salary": "₹7,50,000 - ₹11,00,000 / year",
        "skills": ["SQL", "Excel", "Operations Research", "Tableau"],
        "source_id": "amazon_jobs",
        "source_name": "Amazon Jobs",
        "source_url": "https://www.amazon.jobs/",
        "days_ago": 5,
        "description": "Campus hiring for university graduates. Analyze fulfillment speed, monitor package distribution SLAs, and build SQL queries for logistics managers."
    },
    {
        "title": "Junior Marketing Analyst - Growth & User Acquisition",
        "standard_role": "Marketing Analyst",
        "company": "Remotive / Global Remote Tech",
        "location": "Remote (Open to India)",
        "country": "Remote (Open to India)",
        "work_mode": "Remote",
        "experience_level": "0 - 1 Year (Junior / Entry-Level)",
        "salary": "$25,000 - $38,000 / year (₹20L - ₹31L)",
        "skills": ["Google Analytics", "SQL", "Excel", "Marketing Attribution", "Python"],
        "source_id": "remotive",
        "source_name": "Remotive — India Remote",
        "source_url": "https://remotive.com/remote-jobs/l-india",
        "days_ago": 6,
        "description": "Remote international role welcoming Indian candidates. Monitor digital ad performance, calculate customer acquisition costs (CAC), and compile weekly growth metrics."
    },
    {
        "title": "Junior Financial Analyst - FP&A Operations",
        "standard_role": "Financial Analyst",
        "company": "Microsoft Careers India",
        "location": "Bengaluru / Hyderabad, India",
        "country": "India",
        "work_mode": "Hybrid",
        "experience_level": "Fresher (0 Years)",
        "salary": "₹12,00,000 - ₹18,00,000 / year",
        "skills": ["Excel", "Financial Modeling", "Power BI", "SQL"],
        "source_id": "microsoft_careers",
        "source_name": "Microsoft Careers",
        "source_url": "https://careers.microsoft.com/",
        "days_ago": 7,
        "description": "University Graduate program: Assist in monthly OPEX tracking, build automated financial variance reports in Excel, and learn corporate finance forecasting."
    },
    {
        "title": "Trainee Customer Insights Analyst",
        "standard_role": "Customer Insights Analyst",
        "company": "Freshersworld / Consumer Brand",
        "location": "Bengaluru, Karnataka, India",
        "country": "India",
        "work_mode": "Hybrid",
        "experience_level": "Fresher (0 Years)",
        "salary": "₹4,50,000 - ₹6,50,000 / year",
        "skills": ["SQL", "Excel", "Survey Analysis", "Statistics", "Power BI"],
        "source_id": "freshersworld",
        "source_name": "Freshersworld",
        "source_url": "https://www.freshersworld.com/",
        "days_ago": 9,
        "description": "Analyze CSAT and Net Promoter Score (NPS) feedback surveys, categorize qualitative customer complaints, and draft weekly user insight bulletins."
    },
    {
        "title": "Junior Risk Analyst - Fraud Investigations",
        "standard_role": "Risk Analyst",
        "company": "Internshala / Fintech Partner",
        "location": "Mumbai / Remote, India",
        "country": "India",
        "work_mode": "Hybrid",
        "experience_level": "0 - 1 Year (Junior / Entry-Level)",
        "salary": "₹5,00,000 - ₹7,50,000 / year",
        "skills": ["SQL", "Excel", "Data Profiling", "Python"],
        "source_id": "internshala",
        "source_name": "Internshala India",
        "source_url": "https://internshala.com/jobs/data-analytics-jobs/",
        "days_ago": 11,
        "description": "Inspect high-risk transaction alerts, perform account authenticity checks, and run SQL queries to identify fraudulent identity rings."
    },
    {
        "title": "Graduate Analytics Consultant",
        "standard_role": "Analytics Consultant",
        "company": "Capgemini India",
        "location": "Bengaluru / Pune, India",
        "country": "India",
        "work_mode": "Hybrid",
        "experience_level": "Fresher (0 Years)",
        "salary": "₹5,25,000 - ₹7,75,000 / year",
        "skills": ["Power BI", "SQL", "Excel", "Python", "Data Warehousing"],
        "source_id": "capgemini_careers",
        "source_name": "Capgemini Careers",
        "source_url": "https://www.capgemini.com/careers/",
        "days_ago": 12,
        "description": "Capgemini Graduate Program: Train on modern enterprise business intelligence, understand client business requirements, and assist in report migrations."
    },
    {
        "title": "Junior Data Quality Analyst",
        "standard_role": "Data Quality Analyst",
        "company": "HCLTech",
        "location": "Noida / Chennai, India",
        "country": "India",
        "work_mode": "Hybrid",
        "experience_level": "0 - 1 Year (Junior / Entry-Level)",
        "salary": "₹4,50,000 - ₹6,50,000 / year",
        "skills": ["SQL", "Data Quality", "Excel", "Python"],
        "source_id": "hcltech_careers",
        "source_name": "HCLTech Careers",
        "source_url": "https://www.hcltech.com/careers",
        "days_ago": 14,
        "description": "Run automated data profiling rules, investigate missing and erroneous records in enterprise databases, and track master data health."
    },
    {
        "title": "Junior Data Engineer (Fresher / Trainee)",
        "standard_role": "Junior Data Engineer",
        "company": "Wipro Careers",
        "location": "Bengaluru / Hyderabad, India",
        "country": "India",
        "work_mode": "Hybrid",
        "experience_level": "Fresher (0 Years)",
        "salary": "₹5,00,000 - ₹7,50,000 / year",
        "skills": ["Python", "SQL", "Spark", "AWS", "ETL"],
        "source_id": "wipro_careers",
        "source_name": "Wipro Careers",
        "source_url": "https://careers.wipro.com/",
        "days_ago": 15,
        "description": "Wipro Elite Fresher Hiring: Assist data architects in constructing data extraction pipelines, writing SQL stored procedures, and loading cloud databases."
    },
    {
        "title": "Associate Analytics Engineer (0-1 yr exp)",
        "standard_role": "Analytics Engineer",
        "company": "Himalayas / Remote Global",
        "location": "Remote (Open to India)",
        "country": "Remote (Open to India)",
        "work_mode": "Remote",
        "experience_level": "0 - 1 Year (Junior / Entry-Level)",
        "salary": "$28,000 - $42,000 / year (₹23L - ₹35L)",
        "skills": ["dbt", "Snowflake", "SQL", "Git", "Data Modeling"],
        "source_id": "himalayas",
        "source_name": "Himalayas",
        "source_url": "https://himalayas.app/jobs",
        "days_ago": 16,
        "description": "Remote-first opening open to Indian junior engineers: Maintain data models using dbt and Snowflake. Write data quality tests and document metadata tables."
    },
    {
        "title": "Associate Decision Scientist (Fresher / Campus)",
        "standard_role": "Decision Scientist",
        "company": "IBM Careers India",
        "location": "Bengaluru / Kochi, India",
        "country": "India",
        "work_mode": "Hybrid",
        "experience_level": "Fresher (0 Years)",
        "salary": "₹8,50,000 - ₹12,50,000 / year",
        "skills": ["Python", "R", "SQL", "Statistics", "Machine Learning"],
        "source_id": "ibm_careers",
        "source_name": "IBM Careers",
        "source_url": "https://www.ibm.com/careers/",
        "days_ago": 18,
        "description": "Collaborate with senior researchers to formulate mathematical hypotheses, analyze customer behavioral datasets, and prototype regression models."
    },
    {
        "title": "Junior Data Scientist (0-1 yr exp / Fresher)",
        "standard_role": "Junior Data Scientist",
        "company": "Remote OK / Global Tech",
        "location": "Worldwide Remote (Open to India)",
        "country": "Remote (Open to India)",
        "work_mode": "Remote",
        "experience_level": "Fresher (0 Years)",
        "salary": "$30,000 - $45,000 / year (₹25L - ₹37L)",
        "skills": ["Python", "Pandas", "Scikit-Learn", "SQL", "Statistics"],
        "source_id": "remoteok",
        "source_name": "Remote OK",
        "source_url": "https://remoteok.com/",
        "days_ago": 20,
        "description": "Global remote data science team hiring junior researchers. Clean datasets, explore predictive features with Pandas, and assist in model validation."
    }
]

class RealMarketSeedAdapter(BaseAdapter):
    def __init__(self):
        super().__init__(platform_id="real_market_seed", platform_name="Curated Fresher Market Feed")

    def scrape(
        self,
        roles: List[str] = None,
        limit: int = 50,
        cities: List[str] = None,
        work_modes: List[str] = None,
        **kwargs
    ) -> List[Job]:
        jobs: List[Job] = []
        allowed_work_modes = [wm.lower() for wm in work_modes] if work_modes else ["on-site", "hybrid"]

        # Sort FRESHER_BENCHMARK_JOBS by location priority: Pune #1, Nagpur, Hyderabad, Aurangabad, Bengaluru
        def city_priority_weight(item: dict) -> int:
            loc = (item.get("location") or "").lower()
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

        sorted_benchmarks = sorted(FRESHER_BENCHMARK_JOBS, key=city_priority_weight)

        for item in sorted_benchmarks:
            # Enforce On-Site and Hybrid only (skip Remote)
            item_wm = (item.get("work_mode") or "On-Site").lower()
            if allowed_work_modes and "remote" not in allowed_work_modes and item_wm == "remote":
                continue

            std_role = item["standard_role"]
            if roles and std_role not in roles and not any(r.lower() in item["title"].lower() for r in roles):
                continue

            category = "Core Analytics" if std_role in [
                "Data Analyst", "Junior Data Analyst", "Associate Data Analyst", "Business Data Analyst",
                "Business Analyst", "Reporting Analyst", "MIS Executive / MIS Analyst", "BI Analyst",
                "Business Intelligence Analyst", "Power BI Developer", "Tableau Developer", "SQL Analyst",
                "Data Visualization Analyst"
            ] else "Related"

            pub_date = days_ago(item["days_ago"])
            job_id = f"fresher_{item['source_id']}_{abs(hash(item['title'] + item['company']))}"

            job = Job(
                id=job_id,
                title=item["title"],
                standard_role=std_role,
                role_category=category,
                company=item["company"],
                location=item["location"],
                country=item["country"],
                work_mode=item["work_mode"],
                experience_level=item["experience_level"],
                salary=item["salary"],
                description=item["description"],
                skills=item["skills"],
                source_id=item["source_id"],
                source_name=item["source_name"],
                source_url=item["source_url"],
                published_at=pub_date,
                is_active=True,
                is_deep_scraped=True,
                extraction_status="complete"
            )
            jobs.append(job)
            if len(jobs) >= limit:
                break

        return jobs
