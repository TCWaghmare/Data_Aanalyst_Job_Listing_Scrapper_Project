# Fresher Data Analyst Job Scraper & Web Finder (0–1 Year Exp)

A targeted multi-platform job scraper and web discovery dashboard strictly oriented toward **Freshers having 0 to 1 year experience** across **72 Curated Indian and Global Remote platforms open to India** (from `india_and_global_remote_job_platforms.pdf`).

---

## 🎓 Key Fresher Features

1. **Strict 0–1 Year Experience Focus**:
   - Every job posting in the database is verified for **Freshers (0 Years / Campus Graduates)**, **Junior / Entry-Level (0–1 Year)**, or **Internship / Trainee** roles.
   - Any senior, lead, or 2+ year requirement is automatically filtered out.

2. **Recent Postings of Last 1 Month at the Top**:
   - Listings are strictly restricted to the **last 30 days** (current month).
   - Sorted in descending chronological order so the newest jobs posted today and this week appear at the very top.

3. **Date Posted Filter**:
   - **Past 30 Days (Past 1 Month - Default)**
   - **Past 14 Days (Last 2 Weeks)**
   - **Past 7 Days (Last 1 Week)**
   - **Past 3 Days**
   - **Past 24 Hours**

4. **Multi-Select Analytical Role Filter**:
   - Filter by **multiple roles at the same time** (e.g. *Data Analyst* + *Junior Data Analyst* + *Power BI Developer* + *Junior Data Scientist*).
   - Features quick-action buttons: *Select All Core (13)*, *Select All Related (12)*, *Select All (25)*, and *Clear*.
   - Selected roles appear as removable interactive chips.

---

## 🎯 Targeted Analytical Role Taxonomy (25 Roles)

### Core Analytics Roles (13 Roles)
1. **Data Analyst**
2. **Junior Data Analyst**
3. **Associate Data Analyst**
4. **Business Data Analyst**
5. **Business Analyst**
6. **Reporting Analyst**
7. **MIS Executive / MIS Analyst**
8. **BI Analyst**
9. **Business Intelligence Analyst**
10. **Power BI Developer**
11. **Tableau Developer**
12. **SQL Analyst**
13. **Data Visualization Analyst**

### Related Roles (12 Roles)
1. **Product Analyst**
2. **Operations Analyst**
3. **Marketing Analyst**
4. **Financial Analyst**
5. **Customer Insights Analyst**
6. **Risk Analyst**
7. **Analytics Consultant**
8. **Data Quality Analyst**
9. **Junior Data Engineer**
10. **Analytics Engineer**
11. **Decision Scientist**
12. **Junior Data Scientist**

---

## 🌐 72 Curated Platforms (from Directory PDF)

Exclusively loaded from `india_and_global_remote_job_platforms.pdf`:

### A. India-Only Job Listing Platforms (26 platforms)
- **General Job Portals**: Naukri, LinkedIn Jobs (India filter), Indeed India, Foundit, Shine, TimesJobs, Glassdoor India, Apna, WorkIndia, PlacementIndia, Careerjet India, QuikrJobs
- **Freshers, Graduates & Internships**: Freshersworld, Internshala, Naukri Campus, LetsIntern, HelloIntern, Apprenticeship India, National Career Service (NCS)
- **Tech & Startup Hiring**: Cutshort, Instahyre, Hirist, Wellfound (filter for India), iimjobs, HerKey, TeamLease

### B. Remote Jobs from India & Global Remote Jobs Open to India (26 platforms)
- **Remote Platforms with India Filters**: Remotive — India remote jobs, RemoteGig, Remotify, Himalayas, We Work Remotely, Remote OK, Remote.co, Jobicy, Working Nomads, JustRemote, NoDesk, Dynamite Jobs, FlexJobs, Jobgether, 4 Day Week, Wellfound (Remote), Turing, Crossover, Upwork, Freelancer, PeoplePerHour
- **Global Aggregators**: Adzuna (country-specific API), Jooble, Talent.com, Careerjet, Jora

### C. Direct Company Career Pages (20 platforms)
- **Global & Indian Tech Employers**: Google Careers, Microsoft Careers, Amazon Jobs, Meta Careers, IBM Careers, Oracle Careers, Salesforce Careers, Accenture India Careers, Infosys Careers, TCS Careers, Wipro Careers, HCLTech Careers, Cognizant Careers, Capgemini Careers, Deloitte Careers, Flipkart Careers, Swiggy Careers, Zomato Careers, Razorpay Jobs, PhonePe Careers

---

## 🚀 Running the Web Application

### Start the Server:
```powershell
python start.py
```
*(Or double-click `start.bat` in Windows File Explorer)*

Open your browser at: **`http://127.0.0.1:8000`**

---

## 💻 CLI Commands (`run_scraper.py`)

```powershell
# Scrape all active adapters for 0-1 yr fresher postings:
python run_scraper.py --all

# Multi-select specific roles:
python run_scraper.py --roles "Data Analyst" "Junior Data Analyst" "Power BI Developer"

# Filter by posting age (e.g. past 7 days) and export to CSV:
python run_scraper.py --date-posted 7d --export csv --output fresh_jobs_7d.csv

# View the 72 curated platforms:
python run_scraper.py --list-platforms

# View current fresher database stats:
python run_scraper.py --stats
```
