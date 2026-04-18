"""SAP Jobs scraper — uses jobs.sap.com server-rendered HTML."""

import re
import time
from html import unescape
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .base import BaseScraper


class SAPScraper(BaseScraper):
    company = "sap"
    company_display = "SAP"

    SEARCH_BASE = "https://jobs.sap.com/search/"

    def _fetch_page(self, offset: int) -> tuple[list[dict], int]:
        """Fetch a page of results from SAP Jobs HTML."""
        params = {
            "q": self.query or "",
            "locale": "en_US",
            "sortColumn": "referencedate",
            "sortDirection": "desc",
            "location": "Bangalore, IN",
            "startrow": str(offset),
        }
        url = self.SEARCH_BASE + "?" + urlencode(params)
        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html",
        })

        try:
            with urlopen(req, timeout=30) as resp:
                html = resp.read().decode()
        except Exception as e:
            print(f"  [{self.company_display}] HTTP request failed: {e}")
            return [], 0

        # Parse total count from "Results X to Y of Z" pattern
        total = 0
        total_match = re.search(r'Results\s+\d+\s+to\s+\d+\s+of\s+([\d,]+)', html)
        if total_match:
            total = int(total_match.group(1).replace(",", ""))

        # Extract job entries: each has a jobTitle-link anchor and a jobLocation span
        # Links appear in pairs (title + hover), so use a set to dedup by job ID
        jobs = []
        seen = set()

        # Pattern: <a class="...jobTitle-link..." href="/job/slug/ID/">Title</a>
        title_pattern = re.compile(
            r'<a[^>]*class="[^"]*jobTitle-link[^"]*"[^>]*href="(/job/[^"]+/(\d+)/)"[^>]*>([^<]+)</a>'
        )
        # Location spans follow title links in the HTML
        location_pattern = re.compile(
            r'<span[^>]*class="[^"]*jobLocation[^"]*"[^>]*>([^<]+)</span>'
        )

        titles = title_pattern.findall(html)
        locations = location_pattern.findall(html)

        # Titles appear in pairs (once for display, once for hover); locations also doubled
        for i, (href, job_id, title) in enumerate(titles):
            if job_id in seen:
                continue
            seen.add(job_id)

            # Find corresponding location (same index in the paired list)
            loc = "N/A"
            if i < len(locations):
                loc = unescape(locations[i]).strip()

            jobs.append({
                "jobId": job_id,
                "title": unescape(title).strip(),
                "location": loc,
                "href": href,
            })

        return jobs, total

    def _normalize(self, item: dict) -> dict:
        """Normalize a SAP job to standard schema."""
        href = item.get("href", "")
        job_id = item.get("jobId", "")
        apply_url = f"https://jobs.sap.com{href}" if href else f"https://jobs.sap.com/job/-/{job_id}/"

        return {
            "jobId": job_id,
            "title": item.get("title", "N/A"),
            "location": item.get("location", "N/A"),
            "workSite": "N/A",
            "discipline": "N/A",
            "datePosted": "N/A",
            "applyUrl": apply_url,
            "company": "SAP",
        }

    def fetch_all_jobs(self) -> list[dict]:
        all_jobs = []
        offset = 0

        while True:
            print(f"  [{self.company_display}] Offset {offset}...")
            page_jobs, total = self._fetch_page(offset)
            if not page_jobs:
                break
            all_jobs.extend(self._normalize(j) for j in page_jobs)
            offset += 25
            if offset >= total:
                break
            time.sleep(2)

        print(f"  [{self.company_display}] Found {len(all_jobs)} jobs")
        return all_jobs
