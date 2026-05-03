import asyncio
from playwright.async_api import async_playwright, BrowserContext, Page
from scrapers import make_slug
from db import insert_job, job_exists
from config import SEARCH_KEYWORDS

BASE = "https://www.stepstone.de/jobs/"
CONCURRENCY = 5


async def _fetch_description(ctx: BrowserContext, inline_url: str, referer: str) -> str:
    try:
        jpage = await ctx.new_page()
        await jpage.set_extra_http_headers({"Referer": referer})
        await jpage.goto(inline_url, wait_until="domcontentloaded", timeout=20000)
        await jpage.wait_for_timeout(1000)
        desc_el = await jpage.query_selector("[data-at='section-text-description-content']")
        description = (await desc_el.inner_text()).strip() if desc_el else ""
        await jpage.close()
        return description
    except Exception:
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
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="en-GB",
            viewport={"width": 1280, "height": 800},
        )
        await ctx.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}", lambda r: r.abort())

        for keyword in SEARCH_KEYWORDS:
            for page_num in range(1, 4):
                try:
                    page = await ctx.new_page()
                    params = f"?q={keyword.replace(' ', '+')}&where=Deutschland"
                    if page_num > 1:
                        params += f"&page={page_num}"
                    await page.goto(BASE + params, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(2000)

                    cards = await page.query_selector_all("article[data-testid='job-item']")
                    if not cards:
                        cards = await page.query_selector_all("[data-genesis-element='BASE_JOB_CARD']")
                    if not cards:
                        cards = await page.query_selector_all("article.sc-jTzLTM, article[class*='JobCard']")
                    if not cards:
                        print(f"  stepstone: no cards found for '{keyword}' p{page_num}")
                        await page.close()
                        break

                    referer = page.url
                    card_data = []

                    for card in cards:
                        try:
                            title_el   = await card.query_selector("[data-at='job-item-title'], h2 a, h3 a, [data-genesis-element='JOB_TITLE']")
                            company_el = await card.query_selector("[data-at='job-item-company-name'], [data-genesis-element='COMPANY_NAME'], [class*='company']")
                            loc_el     = await card.query_selector("[data-at='job-item-location'], [data-genesis-element='LOCATION'], [class*='location']")
                            link_el    = await card.query_selector("a[data-at='job-item-title'], a[href*='/stellenangebote/'], a[href*='/job/']")
                            date_el    = await card.query_selector("time[datetime]")

                            title       = (await title_el.inner_text()).strip()   if title_el   else ""
                            company     = (await company_el.inner_text()).strip() if company_el else ""
                            location    = (await loc_el.inner_text()).strip()     if loc_el     else "Germany"
                            href        = await link_el.get_attribute("href")     if link_el    else ""
                            card_posted = (await date_el.get_attribute("datetime") or "")[:10] if date_el else ""

                            if not title or not href:
                                continue

                            raw_url    = f"https://www.stepstone.de{href}" if href.startswith("/") else href
                            inline_url = raw_url if raw_url.endswith("-inline.html") else raw_url.replace(".html", "-inline.html")
                            full_url   = raw_url.replace("-inline.html", ".html")
                            slug       = make_slug("stepstone", full_url)

                            if job_exists(slug):
                                continue

                            card_data.append({
                                "slug": slug, "title": title, "company": company,
                                "location": location, "full_url": full_url,
                                "inline_url": inline_url, "posted": card_posted,
                            })
                        except Exception as e:
                            print(f"  stepstone card error: {e}")

                    await page.close()

                    # Fetch descriptions in parallel
                    sem = asyncio.Semaphore(CONCURRENCY)

                    async def fetch_with_sem(job):
                        async with sem:
                            return await _fetch_description(ctx, job["inline_url"], referer)

                    descriptions = await asyncio.gather(*[fetch_with_sem(j) for j in card_data])

                    for job, description in zip(card_data, descriptions):
                        insert_job({
                            "slug": job["slug"],
                            "title": job["title"],
                            "company": job["company"],
                            "location": job["location"],
                            "remote": 1 if "remote" in job["location"].lower() or "remote" in job["title"].lower() else 0,
                            "url": job["full_url"],
                            "source": "stepstone",
                            "posted": job["posted"],
                            "salary": "",
                            "description": description,
                        })
                        new += 1

                    await asyncio.sleep(1.5)
                except Exception as e:
                    print(f"  stepstone error [{keyword} p{page_num}]: {e}")
                    break

        await browser.close()
    return new


def scrape() -> int:
    return asyncio.run(scrape_async())


if __name__ == "__main__":
    from db import init_db
    init_db()
    n = scrape()
    print(f"StepStone: {n} new jobs")
