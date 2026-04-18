"""Amazon Jobs scraper — uses amazon.jobs JSON API."""

import time
from datetime import datetime
from urllib.parse import urlencode

from .base import BaseScraper


class AmazonScraper(BaseScraper):
    company = "amazon"
    company_display = "Amazon"

    # Amazon uses "Bengaluru" not "Bangalore"
    SEARCH_BASE = "https://www.amazon.jobs/en/search.json"

    def _location_params(self) -> dict:
        """Return location-specific query params for Bangalore."""
        return {
            "loc_query": "Bengaluru, Karnataka, India",
            "latitude": "12.97194",
            "longitude": "77.59369",
            "radius": "24km",
        }

    def _fetch_page_api(self, offset: int, limit: int = 25) -> tuple[list[dict], int]:
        """Fetch a page of results directly from the Amazon Jobs JSON API."""
        import json
        from urllib.request import Request, urlopen

        params = {
            "offset": offset,
            "result_limit": limit,
            "sort": "recent",
            **self._location_params(),
        }
        if self.query:
            params["base_query"] = self.query

        url = self.SEARCH_BASE + "?" + urlencode(params)
        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            "Accept": "application/json",
        })

        try:
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            print(f"  [{self.company_display}] API request failed: {e}")
            return [], 0

        jobs = []
        total = data.get("hits", 0)
        for item in data.get("jobs", []):
            jobs.append(self._normalize(item))

        return jobs, total

    def _normalize(self, item: dict) -> dict:
        """Normalize an Amazon job object to standard schema."""
        # Parse date: "April 15, 2026" -> "2026-04-15"
        posted_raw = item.get("posted_date", "N/A")
        date_posted = "N/A"
        if posted_raw and posted_raw != "N/A":
            try:
                dt = datetime.strptime(posted_raw, "%B %d, %Y")
                date_posted = dt.strftime("%Y-%m-%d")
            except ValueError:
                date_posted = posted_raw

        # Work site from locations array
        work_site = "N/A"
        locations = item.get("locations", [])
        if locations and isinstance(locations, list):
            first_loc = locations[0]
            if isinstance(first_loc, dict):
                loc_type = first_loc.get("type", "")
                work_map = {"ONSITE": "On-site", "REMOTE": "Remote", "HYBRID": "Hybrid"}
                work_site = work_map.get(loc_type.upper(), "N/A")

        job_id = item.get("id_icims", item.get("id", ""))
        job_path = item.get("job_path", "")
        apply_url = f"https://www.amazon.jobs{job_path}" if job_path else f"https://www.amazon.jobs/en/jobs/{job_id}"

        return {
            "jobId": str(job_id),
            "title": item.get("title", "N/A"),
            "location": item.get("normalized_location", item.get("location", "N/A")),
            "workSite": work_site,
            "discipline": item.get("job_category", "N/A"),
            "datePosted": date_posted,
            "applyUrl": apply_url,
            "company": "Amazon",
        }

    def fetch_all_jobs(self) -> list[dict]:
        all_jobs = []
        offset = 0
        limit = 25

        while True:
            print(f"  [{self.company_display}] Offset {offset}...")
            jobs, total = self._fetch_page_api(offset, limit)
            if not jobs:
                break
            all_jobs.extend(jobs)
            offset += limit
            if offset >= total:
                break
            time.sleep(2)  # Rate-limit protection

        print(f"  [{self.company_display}] Found {len(all_jobs)} jobs")
        return all_jobs
