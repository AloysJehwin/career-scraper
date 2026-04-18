"""Base scraper with shared Playwright setup, normalization, and S3 upload."""

import json
import os
import sys
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright, Browser, BrowserContext

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class BaseScraper(ABC):
    company: str  # e.g. "google"
    company_display: str  # e.g. "Google"

    def __init__(self, location: str, query: str = ""):
        self.location = location
        self.query = query

    def _launch_browser(self, playwright):
        """Launch headless Chromium with anti-detection settings."""
        browser = playwright.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        return browser

    def _new_context(self, browser: Browser) -> BrowserContext:
        """Create a browser context with stealth settings."""
        ctx = browser.new_context(
            user_agent=USER_AGENT,
            locale="en-US",
            viewport={"width": 1280, "height": 900},
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        return ctx

    @abstractmethod
    def fetch_all_jobs(self) -> list[dict]:
        """Fetch and return normalized job dicts from the company's career site."""
        ...

    def run(self) -> dict:
        """Orchestrate: fetch jobs and return the output envelope."""
        jobs = self.fetch_all_jobs()
        return {
            "fetchedAt": datetime.now(timezone.utc).isoformat(),
            "location": self.location,
            "query": self.query,
            "total": len(jobs),
            "jobs": jobs,
        }

    def save_and_upload(self, output: dict):
        """Save locally and optionally upload to S3."""
        local_path = f"/tmp/{self.company}-latest.json"
        with open(local_path, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"[{self.company_display}] Fetched {output['total']} jobs -> {local_path}")

        s3_bucket = os.environ.get("JOBS_S3_BUCKET", "")
        if s3_bucket:
            import boto3
            s3 = boto3.client("s3")
            s3_key = f"jobs/{self.company}-latest.json"
            s3.put_object(
                Bucket=s3_bucket,
                Key=s3_key,
                Body=json.dumps(output, ensure_ascii=False),
                ContentType="application/json",
            )
            print(f"[{self.company_display}] Uploaded to s3://{s3_bucket}/{s3_key}")
        else:
            print(f"[{self.company_display}] No S3 bucket configured, skipping upload")
