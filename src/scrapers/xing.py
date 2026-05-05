import asyncio
import re
from datetime import date, timedelta
from playwright.async_api import async_playwright, BrowserContext
from scrapers import make_slug
from db import insert_job, job_exists
from config import SEARCH_KEYWORDS


def _parse_xing_date(text: str) -> str:
    """Convert Xing relative date strings to YYYY-MM-DD. Returns '' if unparseable."""
    text = text.strip().lower().split("\n")[0]
    today = date.today()
    if not text or text == "heute":
        return today.isoformat()
    if text == "gestern":
        return (today - timedelta(days=1)).isoformat()
    m = re.search(r"vor\s+(\d+)\s+stunde", text)
    if m:
        return today.isoformat()
    m = re.search(r"vor\s+(\d+)\s+tag", text)
    if m:
        return (today - timedelta(days=int(m.group(1)))).isoformat()
    m = re.search(r"vor\s+(\d+)\s+woche", text)
    if m:
        return (today - timedelta(weeks=int(m.group(1)))).isoformat()
    m = re.search(r"vor\s+(\d+)\s+monat", text)
    if m:
        return (today - timedelta(days=int(m.group(1)) * 30)).isoformat()
    return ""

BASE = "https://www.xing.com/jobs/search"


async def _fetch_description(ctx: BrowserContext, url: str) -> str:
    try:
        page = await ctx.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(1500)
        desc_el = await page.query_selector(
            "[data-testid='job-description-text'], "
            "[class*='JobDescription'], "
            "section[class*='description'], "
            "div[class*='Description']"
        )
        description = (await desc_el.inner_text()).strip() if desc_el else ""
        await page.close()
        return description
    except Exception:
        try:
            await page.close()
        except Exception:
            pass
        return ""


async def scrape_async() -> int:
    new = 0
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="de-DE",
            viewport={"width": 1280, "height": 800},
        )
        await ctx.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}", lambda r: r.abort())

        for keyword in SEARCH_KEYWORDS:
            try:
                page = await ctx.new_page()
                url = f"{BASE}?keywords={keyword.replace(' ', '%20')}&location=Deutschland&radius=100"
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)

                # Dismiss cookie banner if present
                try:
                    accept_btn = await page.query_selector("[data-testid='cookie-consent-accept-btn'], button[id*='accept']")
                    if accept_btn:
                        await accept_btn.click()
                        await page.wait_for_timeout(1000)
                except Exception:
                    pass

                # Scroll to load more results
                for _ in range(3):
                    await page.keyboard.press("End")
                    await page.wait_for_timeout(800)

                cards = await page.query_selector_all("article")

                card_data = []
                for card in cards:
                    try:
                        link_el    = await card.query_selector("a[href*='/jobs/']")
                        company_el = await card.query_selector("[class*='Company']")
                        loc_el     = await card.query_selector("[class*='location']")
                        date_el    = await card.query_selector("[class*='meta']")

                        if not link_el:
                            continue

                        href     = await link_el.get_attribute("href") or ""
                        title    = (await link_el.get_attribute("aria-label") or "").strip()
                        company  = (await company_el.inner_text()).strip() if company_el else ""
                        location = (await loc_el.inner_text()).strip()     if loc_el     else "Germany"
                        posted   = _parse_xing_date(await date_el.inner_text() if date_el else "")

                        if not title or not href:
                            continue

                        full_url = f"https://www.xing.com{href}" if href.startswith("/") else href
                        slug = make_slug("xing", full_url)

                        if job_exists(slug):
                            continue

                        card_data.append({
                            "slug": slug, "title": title, "company": company,
                            "location": location, "url": full_url, "posted": posted,
                        })
                    except Exception as e:
                        print(f"  xing card error: {e}")

                await page.close()

                # Fetch descriptions with limited concurrency
                sem = asyncio.Semaphore(3)

                async def fetch_with_sem(job):
                    async with sem:
                        return await _fetch_description(ctx, job["url"])

                descriptions = await asyncio.gather(*[fetch_with_sem(j) for j in card_data])

                for job, description in zip(card_data, descriptions):
                    insert_job({
                        "slug": job["slug"],
                        "title": job["title"],
                        "company": job["company"],
                        "location": job["location"],
                        "remote": 1 if "remote" in job["location"].lower() or "remote" in job["title"].lower() else 0,
                        "url": job["url"],
                        "source": "xing",
                        "posted": job["posted"],
                        "salary": "",
                        "description": description,
                    })
                    new += 1

                await asyncio.sleep(2)
            except Exception as e:
                print(f"  xing error [{keyword}]: {e}")

        await browser.close()
    return new


def scrape() -> int:
    return asyncio.run(scrape_async())


if __name__ == "__main__":
    from db import init_db
    init_db()
    n = scrape()
    print(f"Xing: {n} new jobs")
