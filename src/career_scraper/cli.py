#!/usr/bin/env python3
"""
Job scraper that fetches career listings from multiple companies and uploads to S3.

Usage:
    scrape-jobs --company microsoft
    scrape-jobs --company all
"""

import argparse
import os
import sys
import traceback

from career_scraper.scrapers import SCRAPERS


def main():
    parser = argparse.ArgumentParser(description="Scrape job listings from career sites")
    parser.add_argument(
        "--company",
        required=True,
        choices=[*SCRAPERS.keys(), "all"],
        help="Company to scrape, or 'all' for every registered scraper",
    )
    args = parser.parse_args()

    location = os.environ.get("JOB_LOCATION", "Bangalore, Karnataka, India")
    query = os.environ.get("JOB_QUERY", "")

    companies = list(SCRAPERS.keys()) if args.company == "all" else [args.company]

    results = {}
    for company_id in companies:
        scraper_cls = SCRAPERS[company_id]
        scraper = scraper_cls(location=location, query=query)
        print(f"\n{'='*60}")
        print(f"Scraping {scraper.company_display} jobs...")
        print(f"{'='*60}")

        try:
            output = scraper.run()

            if output["total"] == 0:
                print(f"WARNING: {scraper.company_display} returned 0 jobs — skipping S3 upload")
                results[company_id] = {"status": "empty", "count": 0}
                continue

            scraper.save_and_upload(output)
            results[company_id] = {"status": "success", "count": output["total"]}
        except Exception as e:
            traceback.print_exc()
            print(f"ERROR scraping {scraper.company_display}: {e}", file=sys.stderr)
            results[company_id] = {"status": "error", "error": str(e)}

    print(f"\n{'='*60}")
    print("Summary:")
    print(f"{'='*60}")
    any_success = False
    for cid, result in results.items():
        status = result["status"]
        if status == "success":
            print(f"  {cid}: {result['count']} jobs")
            any_success = True
        elif status == "empty":
            print(f"  {cid}: 0 jobs (skipped upload)")
        else:
            print(f"  {cid}: FAILED - {result.get('error', 'unknown')}")

    if not any_success and companies:
        sys.exit(1)


if __name__ == "__main__":
    main()
