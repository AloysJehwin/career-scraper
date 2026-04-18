"""Apple Jobs scraper — uses jobs.apple.com with Playwright DOM extraction."""

import json
import re
import time
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

from .base import BaseScraper


class AppleScraper(BaseScraper):
    company = "apple"
    company_display = "Apple"

    SEARCH_BASE = "https://jobs.apple.com/en-us/search"

    def fetch_all_jobs(self) -> list[dict]:
        all_jobs = []
        seen_ids = set()
        page = 1

        with sync_playwright() as p:
            browser = self._launch_browser(p)
            ctx = self._new_context(browser)

            while True:
                print(f"  [{self.company_display}] Page {page}...")
                pg = ctx.new_page()

                # Collect any API responses with job data
                api_results = []

                def on_response(resp):
                    try:
                        if resp.status == 200:
                            ct = resp.headers.get("content-type", "")
                            if "json" in ct:
                                data = resp.json()
                                if isinstance(data, dict):
                                    if "searchResults" in data:
                                        api_results.extend(data["searchResults"])
                                    elif "requisitions" in data:
                                        api_results.extend(data["requisitions"])
                    except Exception:
                        pass

                pg.on("response", on_response)

                # Apple uses india-IND for India location
                params = {"location": "india-IND", "page": str(page)}
                if self.query:
                    params["search"] = self.query
                url = self.SEARCH_BASE + "?" + urlencode(params)

                pg.goto(url, wait_until="networkidle", timeout=45000)
                pg.wait_for_timeout(3000)

                # Extract jobs from hydrated page data or DOM
                page_jobs = pg.evaluate(r"""
                    () => {
                        const results = [];
                        const seen = new Set();

                        // Method 1: Try hydration data
                        try {
                            const hydration = window.__staticRouterHydrationData;
                            if (hydration?.loaderData) {
                                // Search through all loader data values
                                for (const [key, value] of Object.entries(hydration.loaderData)) {
                                    if (value && typeof value === 'object') {
                                        const sr = value.searchResults || value.results || [];
                                        const items = Array.isArray(sr) ? sr : [];
                                        for (const item of items) {
                                            const id = String(item.positionId || item.id || item.requisitionId || '');
                                            if (id && !seen.has(id)) {
                                                seen.add(id);
                                                results.push({
                                                    positionId: id,
                                                    postingTitle: item.postingTitle || item.title || 'N/A',
                                                    locations: item.locations || [],
                                                    team: item.team || {},
                                                    homeOffice: item.homeOffice,
                                                    postingDate: item.postingDate || item.postDateInGMT || ''
                                                });
                                            }
                                        }
                                    }
                                }
                            }
                        } catch {}

                        // Method 2: DOM parsing if no hydration data
                        if (results.length === 0) {
                            const links = document.querySelectorAll('a[href*="/details/"]');
                            for (const a of links) {
                                const href = a.getAttribute('href') || '';
                                const idMatch = href.match(/\/details\/([^\/\?]+)/);
                                if (!idMatch) continue;
                                const jobId = idMatch[1];
                                if (seen.has(jobId)) continue;
                                seen.add(jobId);

                                // Get the closest parent that's a list item or card
                                const card = a.closest('li, [class*="card"], [class*="result"], tr, [role="listitem"]') || a.parentElement;
                                const textParts = (card || a).innerText.split('\n').map(s => s.trim()).filter(Boolean);

                                // Extract team from URL param
                                const teamMatch = href.match(/team=([^&]+)/);
                                const team = teamMatch ? decodeURIComponent(teamMatch[1]) : 'N/A';

                                results.push({
                                    positionId: jobId,
                                    postingTitle: textParts[0] || 'N/A',
                                    locations: [],
                                    team: {teamName: team},
                                    homeOffice: null,
                                    postingDate: ''
                                });
                            }
                        }

                        return results;
                    }
                """)

                # Also get total count
                total_records = pg.evaluate(r"""
                    () => {
                        try {
                            const hydration = window.__staticRouterHydrationData;
                            if (hydration?.loaderData) {
                                for (const value of Object.values(hydration.loaderData)) {
                                    if (value && typeof value === 'object' && 'totalRecords' in value) {
                                        return value.totalRecords;
                                    }
                                }
                            }
                        } catch {}
                        // Try DOM
                        const text = document.body.innerText;
                        const match = text.match(/(\d+)\s+Result/i);
                        return match ? parseInt(match[1]) : 0;
                    }
                """)

                pg.close()

                # Merge API and page results
                items = api_results if api_results else page_jobs
                if not items:
                    break

                new_count = 0
                for item in items:
                    job = self._normalize(item)
                    if job and job["jobId"] not in seen_ids:
                        seen_ids.add(job["jobId"])
                        all_jobs.append(job)
                        new_count += 1

                total = total_records or len(all_jobs)

                # Apple typically shows 20 per page
                if new_count == 0 or len(all_jobs) >= total:
                    break

                page += 1
                time.sleep(2)

            browser.close()

        print(f"  [{self.company_display}] Found {len(all_jobs)} jobs")
        return all_jobs

    def _normalize(self, item: dict) -> dict | None:
        """Normalize an Apple job object to standard schema."""
        job_id = str(item.get("positionId", item.get("id", "")))
        if not job_id:
            return None

        title = item.get("postingTitle", item.get("title", "N/A"))

        # Locations can be array of objects or strings
        locations_raw = item.get("locations", [])
        if locations_raw:
            if isinstance(locations_raw[0], dict):
                loc_parts = [loc.get("name", "") for loc in locations_raw if loc.get("name")]
            else:
                loc_parts = [str(l) for l in locations_raw]
            location = "; ".join(loc_parts) if loc_parts else "N/A"
        else:
            location = "N/A"

        # Team / discipline
        team = item.get("team", {})
        discipline = "N/A"
        if isinstance(team, dict):
            discipline = team.get("teamName", "N/A")
        elif isinstance(team, str):
            discipline = team

        # Work type
        work_site = "N/A"
        home_office = item.get("homeOffice")
        if home_office is True:
            work_site = "Remote"
        elif home_office is False:
            work_site = "On-site"

        # Date
        date_posted = item.get("postingDate", item.get("postDateInGMT", "N/A")) or "N/A"
        if date_posted and date_posted != "N/A":
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%B %d, %Y", "%Y-%m-%d"):
                try:
                    from datetime import datetime
                    dt = datetime.strptime(date_posted.split(".")[0].split("+")[0], fmt)
                    date_posted = dt.strftime("%Y-%m-%d")
                    break
                except ValueError:
                    continue

        return {
            "jobId": job_id,
            "title": title,
            "location": location,
            "workSite": work_site,
            "discipline": discipline,
            "datePosted": date_posted,
            "applyUrl": f"https://jobs.apple.com/en-us/details/{job_id}",
            "company": "Apple",
        }
