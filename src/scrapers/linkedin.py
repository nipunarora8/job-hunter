import asyncio
from playwright.async_api import async_playwright, BrowserContext
from scrapers import make_slug
from db import insert_job, job_exists
from config import SEARCH_KEYWORDS

BASE = "https://www.linkedin.com/jobs/search/"
CONCURRENCY = 5  # parallel job page loads


async def _fetch_job_detail(ctx: BrowserContext, href: str) -> str:
    """Returns description text, empty string on failure."""
    clean_url = href.split("?")[0]
    for attempt in range(2):
        jpage = None
        try:
            jpage = await ctx.new_page()
            await jpage.goto(clean_url, wait_until="domcontentloaded", timeout=25000)
            # Wait for description to appear, up to 5s
            try:
                await jpage.wait_for_selector(
                    ".description__text, .show-more-less-html__markup",
                    timeout=5000
                )
            except Exception:
                pass
            desc_el = await jpage.query_selector(".description__text, .show-more-less-html__markup")
            description = (await desc_el.inner_text()).strip() if desc_el else ""
            await jpage.close()
            if description:
                return description
            # Empty — wait a bit and retry
            await asyncio.sleep(2)
        except Exception as e:
            print(f"  linkedin desc error (attempt {attempt+1}): {e}")
            try:
                await jpage.close()
            except Exception:
                pass
    return ""


async def scrape_async() -> int:
    new = 0
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            locale="en-GB",
            viewport={"width": 1280, "height": 800},
        )
        await ctx.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}", lambda r: r.abort())

        for keyword in SEARCH_KEYWORDS:
            try:
                page = await ctx.new_page()
                url = (
                    f"{BASE}?keywords={keyword.replace(' ', '%20')}"
                    f"&location=Germany&geoId=101282230"
                    f"&f_TPR=r604800&sortBy=DD"
                )
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2500)

                for _ in range(3):
                    await page.keyboard.press("End")
                    await page.wait_for_timeout(800)

                cards = await page.query_selector_all(".base-card")

                # Collect card metadata first
                card_data = []
                for card in cards:
                    try:
                        title_el   = await card.query_selector(".base-search-card__title")
                        company_el = await card.query_selector(".base-search-card__subtitle")
                        loc_el     = await card.query_selector(".job-search-card__location")
                        link_el    = await card.query_selector("a.base-card__full-link")
                        date_el    = await card.query_selector("time[datetime]")

                        title    = (await title_el.inner_text()).strip()   if title_el   else ""
                        company  = (await company_el.inner_text()).strip() if company_el else ""
                        location = (await loc_el.inner_text()).strip()     if loc_el     else "Germany"
                        href     = await link_el.get_attribute("href")     if link_el    else ""
                        posted   = (await date_el.get_attribute("datetime") or "")[:10] if date_el else ""

                        if not title or not href:
                            continue

                        slug = make_slug("linkedin", href)
                        if job_exists(slug):
                            continue

                        card_data.append({
                            "slug": slug, "title": title, "company": company,
                            "location": location, "href": href, "posted": posted,
                        })
                    except Exception as e:
                        print(f"  linkedin card error: {e}")

                await page.close()

                # Fetch descriptions in parallel batches
                sem = asyncio.Semaphore(CONCURRENCY)

                async def fetch_with_sem(job):
                    async with sem:
                        return await _fetch_job_detail(ctx, job["href"])

                descriptions = await asyncio.gather(*[fetch_with_sem(j) for j in card_data])

                for job, description in zip(card_data, descriptions):
                    insert_job({
                        "slug": job["slug"],
                        "title": job["title"],
                        "company": job["company"],
                        "location": job["location"],
                        "remote": 1 if "remote" in job["location"].lower() else 0,
                        "url": job["href"].split("?")[0],
                        "source": "linkedin",
                        "posted": job["posted"],
                        "salary": "",
                        "description": description,
                    })
                    new += 1

                await asyncio.sleep(2)
            except Exception as e:
                print(f"  linkedin error [{keyword}]: {e}")

        await browser.close()
    return new


def scrape() -> int:
    return asyncio.run(scrape_async())


if __name__ == "__main__":
    from db import init_db
    init_db()
    n = scrape()
    print(f"LinkedIn: {n} new jobs")
