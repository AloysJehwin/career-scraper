"""Visa Careers scraper — uses search.visa.com REST API."""

import json
from datetime import datetime
from urllib.request import Request, urlopen

from .base import BaseScraper


class VisaScraper(BaseScraper):
    company = "visa"
    company_display = "Visa"

    API_URL = "https://search.visa.com/CAREERS/careers/jobs?q="

    def fetch_all_jobs(self) -> list[dict]:
        body = json.dumps({
            "from": 0,
            "size": 1000,
            "city": ["Bangalore"],
        }).encode()

        req = Request(self.API_URL, data=body, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": "https://corporate.visa.com",
            "Referer": "https://corporate.visa.com/en/jobs/",
        })

        try:
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            print(f"  [{self.company_display}] API request failed: {e}")
            return []

        all_jobs = []
        for item in data.get("jobDetails", []):
            all_jobs.append(self._normalize(item))

        print(f"  [{self.company_display}] Found {len(all_jobs)} jobs")
        return all_jobs

    def _normalize(self, item: dict) -> dict:
        """Normalize a Visa job object to standard schema."""
        ref = item.get("refNumber", "")
        posting_id = item.get("postingId", "")
        job_id = ref or posting_id

        # Parse date: "2026-04-15T00:00:00.000Z" or similar
        date_posted = "N/A"
        created = item.get("createdOn", "")
        if created:
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                date_posted = dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                date_posted = created[:10] if len(created) >= 10 else "N/A"

        city = item.get("city", "")
        country = item.get("country", "")
        location = f"{city}, {country}".strip(", ") if city or country else "N/A"

        emp_type = item.get("typeOfEmployment", "N/A") or "N/A"
        department = item.get("department", "") or item.get("superDepartment", "") or "N/A"

        apply_url = item.get("applyUrl", "")
        if not apply_url:
            apply_url = f"https://corporate.visa.com/en/jobs/?refNumber={ref}" if ref else "https://corporate.visa.com/en/jobs/"

        return {
            "jobId": job_id,
            "title": (item.get("jobTitle", "N/A") or "N/A").strip(),
            "location": location,
            "workSite": "N/A",
            "discipline": department,
            "datePosted": date_posted,
            "applyUrl": apply_url,
            "company": "Visa",
        }
