# Local Data Directory (`data/`)

This directory stores runtime application data, local databases, user-uploaded career documents, and dynamically generated files.

## Local Files & Directories

- **`jobs.db`**: SQLite database storing scraped job listings, tracking status, schedules, and custom settings. Automatically created and seeded with necessary schema on first launch.
- **`documents/`**: Holds user-uploaded career documents (master resumes in PDF/LaTeX/TXT, LinkedIn exports, project documentation). Kept local to protect personal contact and employment information.
- **`resumes/`**: Stores dynamically generated tailored resumes and cover letters across PDF, DOCX, TXT, and LaTeX formats.
- **`knowledge_base.json`**: Synthesized career profile and evidence index parsed from user documents.
- **`linkedin_feed_settings.json`**: Local user settings for LinkedIn post sync (keywords, auto-sync preferences). Note: Session cookies (`li_at`) are never stored in this file and must be set via the `LI_AT` environment variable.

## Security & Version Control Notice

All files in this directory (except `.gitkeep` and this `README.md`) are intentionally ignored by `.gitignore`. They are never committed to version control in order to prevent personal data, proprietary job listings, and secret credentials from being exposed.

## Production Persistence (PostgreSQL)

In production or cloud serverless environments (such as Vercel), setting `DATABASE_URL` automatically enables the PostgreSQL storage layer. All 12 tables, metadata, and binary file storage (`stored_files` table with `BYTEA`) are stored persistently in PostgreSQL without ephemeral `/tmp` disk loss. Existing data can be migrated idempotently using `scripts/migrate_sqlite_to_postgres.py`.
