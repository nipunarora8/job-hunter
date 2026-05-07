"""
Re-fetches descriptions for jobs that were scraped with empty descriptions.
Run on popos: uv run python src/backfill_descriptions.py --source linkedin
"""
import asyncio
import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from playwright.async_api import async_playwright
from db import get_empty_description_jobs, update_description, init_db

CONCURRENCY = 3


async def _fetch(ctx, url: str, source: str) -> str:
    if source == "linkedin":
        from scrapers.linkedin import _fetch_job_detail
        return await _fetch_job_detail(ctx, url)
    if source == "bundesagentur":
        from scrapers.bundesagentur import _fetch_description
        # Extract refnr from URL
        import re
        m = re.search(r"/jobdetail/(.+)$", url)
        if m:
            return _fetch_description(m.group(1))
    return ""


async def backfill_async(source: str):
    jobs = get_empty_description_jobs(source=source)
    print(f"Found {len(jobs)} {source} jobs with empty descriptions")
    if not jobs:
        return

    filled = 0

    # bundesagentur uses plain HTTP — no Playwright needed
    if source == "bundesagentur":
        from concurrent.futures import ThreadPoolExecutor
        from scrapers.bundesagentur import _fetch_description
        import re

        def process_ba(job):
            m = re.search(r"/jobdetail/(.+)$", job["url"])
            if not m:
                return False
            desc = _fetch_description(m.group(1))
            if desc:
                update_description(job["slug"], desc)
                print(f"  ✓ {job['slug'][:8]} — {len(desc)} chars")
                return True
            print(f"  ✗ {job['slug'][:8]} — still empty")
            return False

        with ThreadPoolExecutor(max_workers=6) as ex:
            results = list(ex.map(process_ba, jobs))
        filled = sum(results)
    else:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="en-GB",
                viewport={"width": 1280, "height": 800},
            )
            await ctx.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}", lambda r: r.abort())

            sem = asyncio.Semaphore(CONCURRENCY)

            async def process(job):
                nonlocal filled
                async with sem:
                    desc = await _fetch(ctx, job["url"], job["source"])
                    if desc:
                        update_description(job["slug"], desc)
                        filled += 1
                        print(f"  ✓ {job['slug'][:8]} — {len(desc)} chars")
                    else:
                        print(f"  ✗ {job['slug'][:8]} — still empty")

            await asyncio.gather(*[process(j) for j in jobs])
            await browser.close()

    print(f"\nDone: {filled}/{len(jobs)} descriptions filled")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="linkedin", help="Source to backfill (default: linkedin)")
    args = parser.parse_args()
    init_db()
    asyncio.run(backfill_async(args.source))
