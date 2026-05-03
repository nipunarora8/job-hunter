import asyncio
from playwright.async_api import async_playwright
from scrapers import make_slug
from db import insert_job, job_exists
from config import SEARCH_KEYWORDS

BASE = "https://www.stepstone.de/jobs/"

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
                        await page.close()
                        break

                    for card in cards:
                        try:
                            title_el   = await card.query_selector("[data-at='job-item-title']")
                            company_el = await card.query_selector("[data-at='job-item-company-name']")
                            loc_el     = await card.query_selector("[data-at='job-item-location']")
                            link_el    = await card.query_selector("a[data-at='job-item-title']")

                            title   = (await title_el.inner_text()).strip()   if title_el   else ""
                            company = (await company_el.inner_text()).strip() if company_el else ""
                            location= (await loc_el.inner_text()).strip()     if loc_el     else "Germany"
                            href    = await link_el.get_attribute("href")     if link_el    else ""

                            if not title or not href:
                                continue

                            full_url = f"https://www.stepstone.de{href}" if href.startswith("/") else href
                            slug = make_slug("stepstone", href)
                            if job_exists(slug):
                                continue

                            # Fetch description
                            description = ""
                            try:
                                jpage = await ctx.new_page()
                                await jpage.goto(full_url, wait_until="domcontentloaded", timeout=20000)
                                await jpage.wait_for_timeout(1200)
                                desc_el = await jpage.query_selector("[data-at='section-text-description-content']")
                                if desc_el:
                                    description = (await desc_el.inner_text()).strip()
                                await jpage.close()
                            except:
                                pass

                            insert_job({
                                "slug": slug,
                                "title": title,
                                "company": company,
                                "location": location,
                                "remote": 1 if "remote" in location.lower() or "remote" in title.lower() else 0,
                                "url": full_url,
                                "source": "stepstone",
                                "posted": "",
                                "salary": "",
                                "description": description,
                            })
                            new += 1
                        except Exception as e:
                            print(f"  stepstone card error: {e}")

                    await page.close()
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
