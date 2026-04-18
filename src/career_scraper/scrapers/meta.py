"""Meta Careers scraper — handles React SPA with GraphQL/API interception."""

import json
import re
import time
import random
from urllib.parse import urlencode, quote

from playwright.sync_api import sync_playwright

from .base import BaseScraper


class MetaScraper(BaseScraper):
    company = "meta"
    company_display = "Meta"

    SEARCH_BASE = "https://www.metacareers.com/jobs"

    def fetch_all_jobs(self) -> list[dict]:
        all_jobs = []
        seen_ids = set()

        with sync_playwright() as p:
            browser = self._launch_browser(p)
            ctx = self._new_context(browser)
            pg = ctx.new_page()

            # Collect API responses
            api_jobs = []

            def on_response(resp):
                try:
                    url = resp.url
                    if resp.status == 200 and ("graphql" in url or "api" in url or "search" in url):
                        ct = resp.headers.get("content-type", "")
                        if "json" in ct:
                            data = resp.json()
                            self._extract_jobs_from_api(data, api_jobs)
                except Exception:
                    pass

            pg.on("response", on_response)

            url = f"{self.SEARCH_BASE}?offices[0]={quote('Bangalore, India')}"
            if self.query:
                url += f"&q={quote(self.query)}"

            print(f"  [{self.company_display}] Loading {url}")
            pg.goto(url, wait_until="domcontentloaded", timeout=45000)

            # Extra wait for React SPA to hydrate and make API calls
            pg.wait_for_timeout(8000)

            # Try scrolling to trigger lazy loading
            for scroll_attempt in range(5):
                pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                pg.wait_for_timeout(random.uniform(2000, 4000))

                # Check for "Show more" / "See more" buttons
                try:
                    more_btn = pg.query_selector(
                        'a:has-text("See more jobs"), button:has-text("Show more"), '
                        'a:has-text("Show more"), [role="button"]:has-text("more")'
                    )
                    if more_btn:
                        more_btn.click()
                        pg.wait_for_timeout(3000)
                except Exception:
                    pass

            # Parse DOM for job listings
            # Meta uses /profile/job_details/{id} as the link pattern
            dom_jobs = pg.evaluate(r"""
                () => {
                    const results = [];
                    const seen = new Set();

                    const links = document.querySelectorAll('a[href*="/profile/job_details/"]');
                    for (const a of links) {
                        const href = a.getAttribute('href') || '';
                        const idMatch = href.match(/\/profile\/job_details\/(\d+)/);
                        if (!idMatch) continue;
                        const jobId = idMatch[1];
                        if (seen.has(jobId)) continue;
                        seen.add(jobId);

                        // The <a> wraps the entire card; extract text from it
                        const textParts = a.innerText.split('\n').map(s => s.trim()).filter(Boolean);

                        // Title is in the first H3 or first meaningful text
                        const h3 = a.querySelector('h3');
                        const title = h3?.innerText?.trim() || textParts[0] || 'N/A';

                        // Skip navigation links
                        if (title.length < 3 || title === 'Jobs') continue;

                        let location = 'N/A';
                        let team = 'N/A';

                        // Parse the text parts: title, location, team info
                        // Typical format: "Title\nLocation\n⋅\nTeam\n⋅\nSubteam"
                        for (const part of textParts) {
                            if (part === title || part === '⋅') continue;
                            if (location === 'N/A' && (
                                part.toLowerCase().includes('bangalore') ||
                                part.toLowerCase().includes('india') ||
                                part.includes('+') && part.includes('location')
                            )) {
                                location = part;
                            } else if (team === 'N/A' && part !== location && part.length > 2 && part !== '⋅') {
                                team = part;
                            }
                        }

                        results.push({jobId, title, location, team, href});
                    }
                    return results;
                }
            """)

            browser.close()

        # Merge API and DOM results
        for job in api_jobs:
            jid = job.get("jobId", "")
            if jid and jid not in seen_ids:
                seen_ids.add(jid)
                all_jobs.append(job)

        for job in dom_jobs:
            jid = job.get("jobId", "")
            if not jid or jid in seen_ids:
                continue
            seen_ids.add(jid)

            href = job.get("href", "")
            if not href.startswith("http"):
                href = f"https://www.metacareers.com{href}" if href.startswith("/") else f"https://www.metacareers.com/profile/job_details/{jid}"

            all_jobs.append({
                "jobId": jid,
                "title": job.get("title", "N/A"),
                "location": job.get("location", "N/A"),
                "workSite": "N/A",
                "discipline": job.get("team", "N/A"),
                "datePosted": "N/A",
                "applyUrl": href,
                "company": "Meta",
            })

        print(f"  [{self.company_display}] Found {len(all_jobs)} jobs")
        return all_jobs

    def _extract_jobs_from_api(self, data, results: list):
        """Recursively extract job objects from API response JSON."""
        if isinstance(data, dict):
            # Check if this looks like a job object
            if "id" in data and ("title" in data or "name" in data):
                job = self._normalize_api_job(data)
                if job:
                    results.append(job)
                    return

            # Check for edges/nodes pattern (GraphQL)
            if "edges" in data:
                for edge in data["edges"]:
                    node = edge.get("node", edge)
                    self._extract_jobs_from_api(node, results)
                return

            if "data" in data:
                self._extract_jobs_from_api(data["data"], results)
                return

            if "results" in data:
                self._extract_jobs_from_api(data["results"], results)
                return

            if "jobs" in data:
                for job in data["jobs"]:
                    self._extract_jobs_from_api(job, results)
                return

            for v in data.values():
                if isinstance(v, (dict, list)):
                    self._extract_jobs_from_api(v, results)

        elif isinstance(data, list):
            for item in data:
                self._extract_jobs_from_api(item, results)

    def _normalize_api_job(self, item: dict) -> dict | None:
        """Normalize a Meta API job object to standard schema."""
        job_id = str(item.get("id", ""))
        if not job_id or not job_id.isdigit():
            return None

        title = item.get("title", item.get("name", "N/A"))
        if not title or len(title) < 3:
            return None

        # Location
        locations = item.get("locations", item.get("offices", []))
        if isinstance(locations, list) and locations:
            if isinstance(locations[0], dict):
                loc_parts = [l.get("name", l.get("city", "")) for l in locations]
            else:
                loc_parts = [str(l) for l in locations]
            location = "; ".join(filter(None, loc_parts)) or "N/A"
        elif isinstance(locations, str):
            location = locations
        else:
            location = "N/A"

        # Team / discipline
        team = item.get("team", item.get("departments", item.get("category", "N/A")))
        if isinstance(team, list):
            team = team[0] if team else "N/A"
        if isinstance(team, dict):
            team = team.get("name", "N/A")

        return {
            "jobId": job_id,
            "title": title,
            "location": location,
            "workSite": "N/A",
            "discipline": str(team) if team else "N/A",
            "datePosted": "N/A",
            "applyUrl": f"https://www.metacareers.com/profile/job_details/{job_id}",
            "company": "Meta",
        }
