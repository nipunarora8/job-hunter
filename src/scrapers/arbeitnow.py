import httpx
from scrapers import make_slug
from db import insert_job, job_exists
from config import SEARCH_KEYWORDS

BASE = "https://www.arbeitnow.com/api/job-board-api"

def scrape() -> int:
    new = 0
    seen_slugs = set()
    with httpx.Client(timeout=15) as client:
        for keyword in SEARCH_KEYWORDS:
            for page in range(1, 4):
                try:
                    r = client.get(BASE, params={"search": keyword, "page": page})
                    data = r.json()
                    jobs = data.get("data", [])
                    if not jobs:
                        break
                    for j in jobs:
                        slug = make_slug("arbeitnow", j.get("slug", j.get("url", "")))
                        if slug in seen_slugs or job_exists(slug):
                            continue
                        seen_slugs.add(slug)
                        ts = j.get("created_at", "")
                        if isinstance(ts, int):
                            from datetime import datetime, timezone
                            posted = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                        else:
                            posted = str(ts)[:10]
                        insert_job({
                            "slug": slug,
                            "title": j.get("title", ""),
                            "company": j.get("company_name", ""),
                            "location": j.get("location", "Germany"),
                            "remote": 1 if j.get("remote") else 0,
                            "url": j.get("url", ""),
                            "source": "arbeitnow",
                            "posted": posted,
                            "salary": "",
                            "description": j.get("description", ""),
                        })
                        new += 1
                except Exception as e:
                    print(f"  arbeitnow error [{keyword} p{page}]: {e}")
                    break
    return new

if __name__ == "__main__":
    from db import init_db
    init_db()
    n = scrape()
    print(f"Arbeitnow: {n} new jobs")
