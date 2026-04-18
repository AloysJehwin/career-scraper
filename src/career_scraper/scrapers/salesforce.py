"""Salesforce Careers scraper — uses Playwright for client-rendered SPA."""

from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

from .base import BaseScraper


class SalesforceScraper(BaseScraper):
    company = "salesforce"
    company_display = "Salesforce"

    SEARCH_BASE = "https://careers.salesforce.com/en/jobs/"

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

                params = {"country": "India", "page": str(page)}
                if self.query:
                    params["keywords"] = self.query
                url = self.SEARCH_BASE + "?" + urlencode(params)

                pg.goto(url, wait_until="domcontentloaded", timeout=45000)
                pg.wait_for_timeout(6000)

                # Extract job cards from DOM
                # Structure: div.card.card-job > div.card-body
                #   child 0: discipline text (e.g. "Development & Strategy")
                #   child 1: h3.card-title > a[href="/en/jobs/jr.../..."]  (title)
                #   child 2: "Save" button
                #   child 3: location text (e.g. "India - Bangalore")
                page_data = pg.evaluate(r"""
                    () => {
                        const results = [];
                        const seen = new Set();

                        const cards = document.querySelectorAll('.card-job, [class*="card-job"]');
                        for (const card of cards) {
                            const link = card.querySelector('a[href*="/en/jobs/jr"]');
                            if (!link) continue;

                            const match = link.href.match(/\/en\/jobs\/(jr\d+)/i);
                            if (!match) continue;
                            const jobId = match[1];
                            if (seen.has(jobId)) continue;
                            seen.add(jobId);

                            const href = link.getAttribute('href') || '';
                            const title = link.innerText.trim() || 'N/A';

                            // Get all text parts from the card body
                            const body = card.querySelector('.card-body') || card;
                            const textParts = Array.from(body.children)
                                .map(el => el.innerText.trim())
                                .filter(t => t && t !== 'Save');

                            // Discipline is the first text before the title
                            let discipline = 'N/A';
                            let location = 'N/A';

                            for (const part of textParts) {
                                if (part === title) continue;
                                if (part.startsWith('India') || part.includes(' - ')) {
                                    location = part;
                                } else if (discipline === 'N/A' && part.length > 2) {
                                    discipline = part;
                                }
                            }

                            results.push({jobId, title, location, discipline, href});
                        }

                        // Fallback: if no .card-job found, try link-based extraction
                        if (results.length === 0) {
                            const links = Array.from(document.querySelectorAll('a'));
                            for (const a of links) {
                                const match = a.href.match(/\/en\/jobs\/(jr\d+)/i);
                                if (!match) continue;
                                const jobId = match[1];
                                if (seen.has(jobId)) continue;
                                seen.add(jobId);
                                results.push({
                                    jobId,
                                    title: a.innerText.trim() || 'N/A',
                                    location: 'N/A',
                                    discipline: 'N/A',
                                    href: a.getAttribute('href') || ''
                                });
                            }
                        }

                        const countMatch = document.body.innerText.match(
                            /Displaying\s+\d+\s+to\s+\d+\s+of\s+([\d,]+)/
                        );
                        const total = countMatch
                            ? parseInt(countMatch[1].replace(',', ''))
                            : 0;

                        return {jobs: results, total};
                    }
                """)

                pg.close()

                page_jobs = page_data.get("jobs", [])
                total = page_data.get("total", 0)

                if not page_jobs:
                    break

                new_count = 0
                for job in page_jobs:
                    jid = job.get("jobId", "")
                    if not jid or jid in seen_ids:
                        continue
                    seen_ids.add(jid)
                    new_count += 1

                    href = job.get("href", "")
                    apply_url = (
                        f"https://careers.salesforce.com{href}"
                        if href.startswith("/")
                        else f"https://careers.salesforce.com/en/jobs/{jid}/"
                    )

                    all_jobs.append({
                        "jobId": jid,
                        "title": job.get("title", "N/A"),
                        "location": job.get("location", "N/A"),
                        "workSite": "N/A",
                        "discipline": job.get("discipline", "N/A"),
                        "datePosted": "N/A",
                        "applyUrl": apply_url,
                        "company": "Salesforce",
                    })

                if new_count == 0 or (total and len(all_jobs) >= total):
                    break

                page += 1

            browser.close()

        print(f"  [{self.company_display}] Found {len(all_jobs)} jobs")
        return all_jobs
