import httpx
from scrapers import make_slug
from db import insert_job, job_exists
from config import SEARCH_KEYWORDS

BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
HEADERS = {
    "X-API-Key": "jobboerse-jobsuche",
    "User-Agent": "Mozilla/5.0",
}

def scrape() -> int:
    new = 0
    seen_slugs = set()
    with httpx.Client(timeout=15, verify=False) as client:
        for keyword in SEARCH_KEYWORDS:
            for page in range(1, 4):
                try:
                    r = client.get(BASE, headers=HEADERS, params={
                        "was": keyword,
                        "wo": "Deutschland",
                        "umkreis": 0,
                        "angebotsart": 1,
                        "page": page,
                        "size": 25,
                    })
                    data = r.json()
                    jobs = data.get("stellenangebote", []) or []
                    if not jobs:
                        break
                    for j in jobs:
                        refnr = j.get("refnr", "")
                        slug = make_slug("ba", refnr)
                        if slug in seen_slugs or job_exists(slug):
                            continue
                        seen_slugs.add(slug)
                        ort = j.get("arbeitsort", {})
                        location = ort.get("ort", "Germany")
                        insert_job({
                            "slug": slug,
                            "title": j.get("titel", ""),
                            "company": j.get("arbeitgeber", ""),
                            "location": location,
                            "remote": 0,
                            "url": f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}",
                            "source": "bundesagentur",
                            "posted": j.get("aktuelleVeroeffentlichungsdatum", "")[:10],
                            "salary": "",
                            "description": j.get("titel", ""),
                        })
                        new += 1
                except Exception as e:
                    print(f"  bundesagentur error [{keyword} p{page}]: {e}")
                    break
    return new

if __name__ == "__main__":
    from db import init_db
    init_db()
    n = scrape()
    print(f"Bundesagentur: {n} new jobs")
