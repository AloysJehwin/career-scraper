"""Microsoft Careers scraper — extracted from the original scrape-jobs.py."""

from datetime import datetime, timezone
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

from .base import BaseScraper

SEARCH_BASE = "https://apply.careers.microsoft.com/careers"
JOB_BASE = "https://apply.careers.microsoft.com"


class MicrosoftScraper(BaseScraper):
    company = "microsoft"
    company_display = "Microsoft"

    def _fetch_page(self, page_num: int, page_size: int = 10):
        """Fetch a single page of results via API interception or DOM fallback."""
        start = (page_num - 1) * page_size
        params = {
            "start": start,
            "location": self.location,
            "sort_by": "distance",
            "filter_distance": 160,
            "filter_include_remote": 1,
        }
        if self.query:
            params["query"] = self.query
        search_url = SEARCH_BASE + "?" + urlencode(params)
        api_json = {}

        with sync_playwright() as p:
            browser = self._launch_browser(p)
            ctx = self._new_context(browser)
            pg = ctx.new_page()

            def on_response(resp):
                nonlocal api_json
                if "/api/pcsx/search" in resp.url and resp.status == 200:
                    try:
                        api_json = resp.json()
                    except Exception:
                        pass

            pg.on("response", on_response)
            pg.goto(search_url, wait_until="domcontentloaded", timeout=45000)

            try:
                pg.wait_for_selector('a[href*="/careers/job/"]', timeout=20000)
            except Exception:
                pass
            pg.wait_for_timeout(3000)

            if api_json and api_json.get("data"):
                positions = api_json["data"].get("positions", [])[:page_size]
                total = api_json["data"].get("count", len(positions))
                browser.close()
                return self._parse_api(positions), total

            raw = pg.evaluate(r"""
                () => {
                    const results = [];
                    const links = document.querySelectorAll('a[href*="/careers/job/"]');
                    const seen = new Set();
                    for (const a of links) {
                        const href = a.getAttribute('href') || '';
                        const idMatch = href.match(/\/job\/(\d+)/);
                        if (!idMatch) continue;
                        const jobId = idMatch[1];
                        if (seen.has(jobId)) continue;
                        seen.add(jobId);
                        const text = a.innerText.trim();
                        const lines = text.split('\n').map(s => s.trim()).filter(Boolean);
                        results.push({jobId, href, lines});
                    }
                    return results;
                }
            """)
            total_text = pg.evaluate(r"""
                () => {
                    const el = document.body.innerText.match(/(\d+)\s+jobs?\b/i);
                    return el ? parseInt(el[1]) : 0;
                }
            """)
            browser.close()
        return self._parse_scraped(raw[:page_size]), total_text

    def _parse_api(self, positions: list[dict]) -> list[dict]:
        results = []
        for pos in positions:
            ts = pos.get("postedTs")
            posted = (
                datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                if ts
                else "N/A"
            )
            locations = pos.get("locations", [])
            location_str = "; ".join(locations) if locations else "N/A"
            work_map = {"onsite": "On-site", "remote": "Remote", "hybrid": "Hybrid"}
            work_site = work_map.get(pos.get("workLocationOption", ""), "N/A")

            results.append(
                {
                    "jobId": pos.get("displayJobId", str(pos.get("id", ""))),
                    "title": pos.get("name", "N/A"),
                    "location": location_str,
                    "workSite": work_site,
                    "discipline": pos.get("department", "N/A"),
                    "datePosted": posted,
                    "applyUrl": f"{JOB_BASE}{pos.get('positionUrl', '')}",
                    "company": "Microsoft",
                }
            )
        return results

    def _parse_scraped(self, raw_jobs: list[dict]) -> list[dict]:
        results = []
        for item in raw_jobs:
            lines = item.get("lines", [])
            job_id = item.get("jobId", "")
            href = item.get("href", "")
            url = href if href.startswith("http") else JOB_BASE + href
            results.append(
                {
                    "jobId": job_id,
                    "title": lines[0] if lines else "N/A",
                    "location": lines[1] if len(lines) > 1 else "N/A",
                    "workSite": "N/A",
                    "discipline": "N/A",
                    "datePosted": lines[2] if len(lines) > 2 else "N/A",
                    "applyUrl": url,
                    "company": "Microsoft",
                }
            )
        return results

    def fetch_all_jobs(self) -> list[dict]:
        all_jobs = []
        page = 1
        while True:
            print(f"  [{self.company_display}] Page {page}...")
            jobs, total = self._fetch_page(page, 10)
            if not jobs:
                break
            all_jobs.extend(jobs)
            if len(all_jobs) >= total or len(jobs) < 10:
                break
            page += 1
        return all_jobs
