import asyncio
from playwright.async_api import async_playwright
from scrapers import make_slug
from db import insert_job, job_exists
from config import SEARCH_KEYWORDS

BASE = "https://www.linkedin.com/jobs/search/"

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
                for card in cards:
                    try:
                        title_el   = await card.query_selector(".base-search-card__title")
                        company_el = await card.query_selector(".base-search-card__subtitle")
                        loc_el     = await card.query_selector(".job-search-card__location")
                        link_el    = await card.query_selector("a.base-card__full-link")

                        title   = (await title_el.inner_text()).strip()   if title_el   else ""
                        company = (await company_el.inner_text()).strip() if company_el else ""
                        location= (await loc_el.inner_text()).strip()     if loc_el     else "Germany"
                        href    = await link_el.get_attribute("href")     if link_el    else ""

                        if not title:
                            continue

                        slug = make_slug("linkedin", href or title + company)
                        if job_exists(slug):
                            continue

                        description = ""
                        if href:
                            try:
                                jpage = await ctx.new_page()
                                await jpage.goto(href, wait_until="domcontentloaded", timeout=20000)
                                await jpage.wait_for_timeout(1500)
                                desc_el = await jpage.query_selector(".show-more-less-html__markup")
                                if desc_el:
                                    description = await desc_el.inner_text()
                                await jpage.close()
                            except:
                                pass

                        insert_job({
                            "slug": slug,
                            "title": title,
                            "company": company,
                            "location": location,
                            "remote": 1 if "remote" in location.lower() else 0,
                            "url": href.split("?")[0] if href else "",
                            "source": "linkedin",
                            "posted": "",
                            "salary": "",
                            "description": description,
                        })
                        new += 1
                    except Exception as e:
                        print(f"  linkedin card error: {e}")

                await page.close()
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
