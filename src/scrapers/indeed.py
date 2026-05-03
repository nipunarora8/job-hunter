import feedparser
from scrapers import make_slug
from db import insert_job, job_exists
from config import SEARCH_KEYWORDS

def scrape() -> int:
    new = 0
    seen_slugs = set()
    for keyword in SEARCH_KEYWORDS:
        url = f"https://de.indeed.com/rss?q={keyword.replace(' ', '+')}&l=Deutschland&sort=date&limit=50"
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                slug = make_slug("indeed", entry.get("link", entry.get("title", "")))
                if slug in seen_slugs or job_exists(slug):
                    continue
                seen_slugs.add(slug)
                insert_job({
                    "slug": slug,
                    "title": entry.get("title", ""),
                    "company": entry.get("source", {}).get("title", ""),
                    "location": "",
                    "remote": 0,
                    "url": entry.get("link", ""),
                    "source": "indeed",
                    "posted": entry.get("published", "")[:10],
                    "salary": "",
                    "description": entry.get("summary", ""),
                })
                new += 1
        except Exception as e:
            print(f"  indeed error [{keyword}]: {e}")
    return new

if __name__ == "__main__":
    from db import init_db
    init_db()
    n = scrape()
    print(f"Indeed: {n} new jobs")
