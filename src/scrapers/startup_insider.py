import json
import re
import time
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed
from scrapers import make_slug
from db import insert_job, job_exists
from config import SEARCH_KEYWORDS

BASE = "https://jobs.startup-insider.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
}
_JOB_PATH = re.compile(r'/companies/[^"\']+/jobs/[^"\'/]+')
_LD_JSON = re.compile(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL)
_STRIP_TAGS = re.compile(r'<[^>]+>')


def _extract_detail(client: httpx.Client, path: str) -> dict | None:
    try:
        r = client.get(f"{BASE}{path}")
        for block in _LD_JSON.findall(r.text):
            try:
                data = json.loads(block)
                if data.get("@type") == "JobPosting":
                    desc_html = data.get("description", "")
                    desc = re.sub(r'\s+', ' ', _STRIP_TAGS.sub(' ', desc_html)).strip()
                    loc = data.get("jobLocation", {})
                    if isinstance(loc, list):
                        loc = loc[0] if loc else {}
                    city = loc.get("address", {}).get("addressLocality", "") if isinstance(loc, dict) else ""
                    country = loc.get("address", {}).get("addressCountry", "") if isinstance(loc, dict) else ""
                    location = city or country or "Germany"
                    remote_str = str(data.get("jobLocationType", "")).lower()
                    return {
                        "title": data.get("title", ""),
                        "company": data.get("hiringOrganization", {}).get("name", "") if isinstance(data.get("hiringOrganization"), dict) else "",
                        "location": location,
                        "remote": 1 if "remote" in remote_str or "telecommute" in remote_str else 0,
                        "posted": (data.get("datePosted", "") or "")[:10],
                        "description": desc[:6000],
                        "url": f"{BASE}{path}",
                    }
            except (json.JSONDecodeError, AttributeError):
                continue
    except Exception:
        pass
    return None


def _keyword_matches(path: str, keyword: str) -> bool:
    kw_lower = keyword.lower()
    path_lower = path.lower().replace("-", " ")
    return any(w in path_lower for w in kw_lower.split())


def scrape() -> int:
    new = 0
    seen_paths: set[str] = set()
    pending: list[str] = []

    with httpx.Client(timeout=15, headers=HEADERS, follow_redirects=True) as client:
        for page in range(1, 6):
            try:
                r = client.get(f"{BASE}/jobs", params={"page": page})
                paths = list(dict.fromkeys(_JOB_PATH.findall(r.text)))
                if not paths:
                    break
                for path in paths:
                    if path in seen_paths:
                        continue
                    seen_paths.add(path)
                    slug = make_slug("startup_insider", path)
                    if job_exists(slug):
                        continue
                    # Filter to keyword-relevant jobs by slug text
                    if not any(_keyword_matches(path, kw) for kw in SEARCH_KEYWORDS):
                        continue
                    pending.append(path)
                time.sleep(0.5)
            except Exception as e:
                print(f"  startup_insider listing error [page {page}]: {e}")
                break

    def _fetch_and_insert(path: str) -> int:
        with httpx.Client(timeout=15, headers=HEADERS, follow_redirects=True) as client:
            detail = _extract_detail(client, path)
        if not detail:
            return 0
        slug = make_slug("startup_insider", path)
        insert_job({
            "slug": slug,
            "title": detail["title"],
            "company": detail["company"],
            "location": detail["location"],
            "remote": detail["remote"],
            "url": detail["url"],
            "source": "startup_insider",
            "posted": detail["posted"],
            "salary": "",
            "description": detail["description"],
        })
        return 1

    if pending:
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(_fetch_and_insert, path) for path in pending]
            for future in as_completed(futures):
                try:
                    new += future.result()
                except Exception as e:
                    print(f"  startup_insider insert error: {e}")

    return new


if __name__ == "__main__":
    from db import init_db
    init_db()
    n = scrape()
    print(f"Startup Insider: {n} new jobs")
