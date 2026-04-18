"""Oracle Careers scraper — uses Oracle HCM REST API."""

import json
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

from .base import BaseScraper


class OracleScraper(BaseScraper):
    company = "oracle"
    company_display = "Oracle"

    API_BASE = "https://eeho.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    SITE_NUMBER = "CX_45001"
    # Bengaluru, Karnataka, India facet ID
    LOCATION_FACET_ID = "300001842985425"

    def _fetch_page_api(self, offset: int, limit: int = 25) -> tuple[list[dict], int]:
        """Fetch a page of results from the Oracle HCM REST API."""
        facets = "LOCATIONS;WORK_LOCATIONS;WORKPLACE_TYPES;TITLES;CATEGORIES;ORGANIZATIONS;POSTING_DATES;FLEX_FIELDS"
        finder = (
            f"findReqs;"
            f"siteNumber={self.SITE_NUMBER},"
            f"facetsList={facets},"
            f"limit={limit},"
            f"offset={offset},"
            f"sortBy=POSTING_DATES_DESC,"
            f"lastSelectedFacet=LOCATIONS,"
            f"selectedLocationsFacet={self.LOCATION_FACET_ID}"
        )
        if self.query:
            finder += f",keyword={quote(self.query)}"

        url = (
            f"{self.API_BASE}?onlyData=true"
            f"&expand=requisitionList.secondaryLocations,flexFieldsFacet.values"
            f"&finder={quote(finder)}"
        )

        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            "Accept": "application/json",
        })

        try:
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            print(f"  [{self.company_display}] API request failed: {e}")
            return [], 0

        items = data.get("items", [])
        if not items:
            return [], 0

        item = items[0]
        total = item.get("TotalJobsCount", 0)
        reqs = item.get("requisitionList", [])

        jobs = [self._normalize(r) for r in reqs]
        return jobs, total

    def _normalize(self, item: dict) -> dict:
        """Normalize an Oracle HCM job object to standard schema."""
        job_id = str(item.get("Id", ""))
        title = item.get("Title", "N/A")
        location = item.get("PrimaryLocation", "N/A")

        # PostedDate is already YYYY-MM-DD
        date_posted = item.get("PostedDate", "N/A") or "N/A"

        # WorkplaceTypeCode: ORA_ON_SITE, ORA_REMOTE, ORA_HYBRID
        wt = item.get("WorkplaceTypeCode", "") or ""
        work_map = {"ORA_ON_SITE": "On-site", "ORA_REMOTE": "Remote", "ORA_HYBRID": "Hybrid"}
        work_site = work_map.get(wt, "N/A")

        # Category from JobFamily or JobFunction
        discipline = item.get("JobFamily", item.get("JobFunction", "N/A")) or "N/A"

        return {
            "jobId": job_id,
            "title": title,
            "location": location,
            "workSite": work_site,
            "discipline": discipline,
            "datePosted": date_posted,
            "applyUrl": f"https://careers.oracle.com/jobs/#en/sites/jobsearch/job/{job_id}",
            "company": "Oracle",
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
            time.sleep(2)

        print(f"  [{self.company_display}] Found {len(all_jobs)} jobs")
        return all_jobs
