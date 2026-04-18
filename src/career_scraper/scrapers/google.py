"""Google Careers scraper."""

import re
import time
from urllib.parse import urlencode, quote

from playwright.sync_api import sync_playwright

from .base import BaseScraper


class GoogleScraper(BaseScraper):
    company = "google"
    company_display = "Google"

    SEARCH_BASE = "https://www.google.com/about/careers/applications/jobs/results"

    def fetch_all_jobs(self) -> list[dict]:
        all_jobs = []
        seen_ids = set()

        with sync_playwright() as p:
            browser = self._launch_browser(p)
            ctx = self._new_context(browser)
            pg = ctx.new_page()

            # Collect API responses that contain job data
            api_jobs = []

            def on_response(resp):
                try:
                    if resp.status == 200:
                        ct = resp.headers.get("content-type", "")
                        if "json" in ct or "protobuf" in ct:
                            try:
                                data = resp.json()
                                self._extract_from_api(data, api_jobs)
                            except Exception:
                                pass
                except Exception:
                    pass

            pg.on("response", on_response)

            params = {"location": "Bangalore India"}
            if self.query:
                params["q"] = self.query
            url = self.SEARCH_BASE + "?" + urlencode(params)

            print(f"  [{self.company_display}] Loading {url}")
            pg.goto(url, wait_until="networkidle", timeout=45000)
            pg.wait_for_timeout(5000)

            # Google loads ~20 jobs at a time via infinite scroll
            # Scroll repeatedly to load all results
            prev_count = 0
            for _ in range(30):  # Max 30 scroll attempts (~600 jobs)
                current_count = pg.evaluate("""() => {
                    const allA = Array.from(document.querySelectorAll('a'));
                    return allA.filter(a => /\\/jobs\\/results\\/\\d+/.test(a.href)).length;
                }""")
                if current_count == prev_count:
                    break  # No new jobs loaded
                prev_count = current_count
                pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                pg.wait_for_timeout(2000)

            # Extract from DOM
            dom_jobs = pg.evaluate(r"""
                () => {
                    const results = [];
                    const seen = new Set();

                    // Google uses relative hrefs like "jobs/results/{id}-{slug}"
                    // so we must check .href property, not getAttribute('href')
                    const allLinks = Array.from(document.querySelectorAll('a'));
                    const jobLinks = allLinks.filter(a => /\/jobs\/results\/\d+/.test(a.href));

                    for (const a of jobLinks) {
                        const href = a.href;
                        const idMatch = href.match(/\/jobs\/results\/(\d+)/);
                        if (!idMatch) continue;
                        const jobId = idMatch[1];
                        if (seen.has(jobId)) continue;
                        seen.add(jobId);

                        // Walk up to find the card container
                        let card = a;
                        for (let i = 0; i < 3; i++) {
                            if (card.parentElement) {
                                const parent = card.parentElement;
                                if (parent.tagName === 'LI' || parent.tagName === 'SECTION') {
                                    card = parent;
                                    break;
                                }
                                card = parent;
                            }
                        }

                        const textParts = card.innerText.split('\n').map(s => s.trim()).filter(s => s.length > 0 && !['share', 'Learn more', 'corporate_fare', 'place', 'bar_chart'].includes(s));

                        let title = 'N/A';
                        let location = 'N/A';

                        for (const part of textParts) {
                            if (['Google', 'Mid', 'Early', 'Senior', 'Advanced'].includes(part)) continue;
                            if (title === 'N/A' && part.length > 5) {
                                title = part;
                            } else if (location === 'N/A' && (part.includes(',') || part.toLowerCase().includes('bangalore') || part.toLowerCase().includes('bengaluru') || part.toLowerCase().includes('india'))) {
                                location = part.replace(/^;\s*/, '').replace(/;\s*\+.*$/, '').trim();
                            }
                        }

                        // Clean URL
                        const cleanHref = href.split('?')[0];
                        results.push({jobId, title, location, category: 'N/A', href: cleanHref});
                    }
                    return results;
                }
            """)

            browser.close()

        # Merge API and DOM results
        for job in api_jobs:
            jid = str(job.get("jobId", ""))
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
                href = f"https://www.google.com{href}" if href.startswith("/") else f"https://www.google.com/about/careers/applications/jobs/results/{jid}"

            all_jobs.append({
                "jobId": jid,
                "title": job.get("title", "N/A"),
                "location": job.get("location", "N/A"),
                "workSite": "N/A",
                "discipline": job.get("category", "N/A"),
                "datePosted": "N/A",
                "applyUrl": href,
                "company": "Google",
            })

        print(f"  [{self.company_display}] Found {len(all_jobs)} jobs")
        return all_jobs

    def _extract_from_api(self, data, results: list):
        """Extract job objects from API response data."""
        if isinstance(data, dict):
            # Look for arrays that might contain job data
            for key, value in data.items():
                if isinstance(value, list) and len(value) > 0:
                    for item in value:
                        if isinstance(item, dict) and ("title" in item or "name" in item):
                            job_id = str(item.get("id", item.get("jobId", "")))
                            if job_id:
                                results.append({
                                    "jobId": job_id,
                                    "title": item.get("title", item.get("name", "N/A")),
                                    "location": item.get("location", "N/A"),
                                    "workSite": "N/A",
                                    "discipline": item.get("category", item.get("department", "N/A")),
                                    "datePosted": "N/A",
                                    "applyUrl": f"https://www.google.com/about/careers/applications/jobs/results/{job_id}",
                                    "company": "Google",
                                })
                elif isinstance(value, dict):
                    self._extract_from_api(value, results)
