import re
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed
from scrapers import make_slug
from db import insert_job, job_exists
from config import SEARCH_KEYWORDS

BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
DETAIL_BASE = "https://www.arbeitsagentur.de/jobsuche/jobdetail"
HEADERS = {
    "X-API-Key": "jobboerse-jobsuche",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
}

_BA_COPYTEXT = re.compile(r'class="ba-copytext[^"]*"[^>]*>(.*?)</(?:div|section)', re.DOTALL)


def _fetch_description(refnr: str) -> str:
    try:
        with httpx.Client(timeout=15, verify=False, headers=HEADERS) as client:
            r = client.get(f"{DETAIL_BASE}/{refnr}")
            match = _BA_COPYTEXT.search(r.text)
            if match:
                return re.sub(r"<[^>]+>", " ", match.group(1)).strip()
    except Exception:
        pass
    return ""


def scrape() -> int:
    new = 0
    seen_slugs = set()
    pending = []  # collect new jobs before fetching descriptions

    with httpx.Client(timeout=15, verify=False, headers=HEADERS) as client:
        for keyword in SEARCH_KEYWORDS:
            for page in range(1, 4):
                try:
                    r = client.get(BASE, params={
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
                        pending.append({
                            "slug": slug,
                            "refnr": refnr,
                            "title": j.get("titel", ""),
                            "company": j.get("arbeitgeber", ""),
                            "location": ort.get("ort", "Germany"),
                            "posted": j.get("aktuelleVeroeffentlichungsdatum", "")[:10],
                        })
                except Exception as e:
                    print(f"  bundesagentur error [{keyword} p{page}]: {e}")
                    break

    # Fetch descriptions in parallel
    def _fetch_and_insert(job: dict) -> int:
        description = _fetch_description(job["refnr"])
        insert_job({
            "slug": job["slug"],
            "title": job["title"],
            "company": job["company"],
            "location": job["location"],
            "remote": 0,
            "url": f"{DETAIL_BASE}/{job['refnr']}",
            "source": "bundesagentur",
            "posted": job["posted"],
            "salary": "",
            "description": description,
        })
        return 1

    if pending:
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(_fetch_and_insert, job) for job in pending]
            for future in as_completed(futures):
                try:
                    new += future.result()
                except Exception as e:
                    print(f"  bundesagentur insert error: {e}")

    return new


if __name__ == "__main__":
    from db import init_db
    init_db()
    n = scrape()
    print(f"Bundesagentur: {n} new jobs")
