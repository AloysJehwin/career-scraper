# Career Scraper

Job listing scrapers for 9 major tech companies, filtered to Bangalore, India. Runs as a GitHub Actions cron job and exposes a REST API for consuming the data.

## Supported Companies

Microsoft, Google, Amazon, Apple, Meta, SAP, Oracle, Visa, Salesforce

## Quick Start

```bash
pip install -e .
playwright install chromium --with-deps
```

### Scrape jobs

```bash
# Single company
scrape-jobs --company microsoft

# All companies
scrape-jobs --company all
```

### Start the API server

```bash
career-api
# Runs on http://localhost:8000
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/companies` | List supported company IDs |
| GET | `/jobs` | All companies' jobs aggregated |
| GET | `/jobs/{company}` | Single company's jobs |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `JOB_LOCATION` | `Bangalore, Karnataka, India` | Location filter for scrapers |
| `JOB_QUERY` | _(empty)_ | Optional keyword filter |
| `JOBS_S3_BUCKET` | `dashboard-static-assets-708835965056` | S3 bucket for job data |
| `AWS_REGION` | `us-east-1` | AWS region |
| `PORT` | `8000` | API server port |
| `CACHE_TTL_SECONDS` | `300` | S3 cache TTL for API responses |

## Docker

```bash
docker build -t career-scraper .
docker run -p 8000:8000 \
  -e AWS_ACCESS_KEY_ID=... \
  -e AWS_SECRET_ACCESS_KEY=... \
  career-scraper
```

## Adding a New Scraper

1. Create `src/career_scraper/scrapers/{company}.py` extending `BaseScraper`
2. Implement `fetch_all_jobs() -> list[dict]`
3. Add to the registry in `src/career_scraper/scrapers/__init__.py`
4. Add to the matrix in `.github/workflows/scrape.yml`

Each job must conform to this schema:

```json
{
  "jobId": "string",
  "title": "string",
  "location": "string",
  "workSite": "string",
  "discipline": "string",
  "datePosted": "string",
  "applyUrl": "string",
  "company": "string"
}
```
