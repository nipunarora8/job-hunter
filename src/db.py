import sqlite3
import config

def get_conn():
    conn = sqlite3.connect(config.DB_PATH, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    return conn

def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                slug TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                remote INTEGER DEFAULT 0,
                url TEXT,
                source TEXT,
                posted TEXT,
                salary TEXT,
                description TEXT,
                german_required INTEGER,
                relevance_score INTEGER,
                matched_skills TEXT,
                reasoning TEXT,
                analyzed INTEGER DEFAULT 0,
                status TEXT DEFAULT 'new',
                seen INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()

def job_exists(slug: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM jobs WHERE slug=?", (slug,)).fetchone()
        return row is not None

def insert_job(job: dict):
    title = job.get("title", "")
    company = job.get("company", "")
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT 1 FROM jobs WHERE slug=? OR (lower(title)=lower(?) AND lower(company)=lower(?))",
            (job["slug"], title, company)
        ).fetchone()
        if existing:
            return
        conn.execute("""
            INSERT OR IGNORE INTO jobs
            (slug, title, company, location, remote, url, source, posted, salary, description)
            VALUES (:slug, :title, :company, :location, :remote, :url, :source, :posted, :salary, :description)
        """, job)
        conn.commit()

def get_pending_analysis(limit=50) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE analyzed=0 ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

def save_analysis(slug: str, german_required, relevance_score: int, matched_skills: str, reasoning: str):
    with get_conn() as conn:
        conn.execute("""
            UPDATE jobs SET
                german_required=?, relevance_score=?, matched_skills=?,
                reasoning=?, analyzed=1
            WHERE slug=?
        """, (german_required, relevance_score, matched_skills, reasoning, slug))
        conn.commit()

def reject_job(slug: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE jobs SET analyzed=1, status='rejected' WHERE slug=?", (slug,)
        )
        conn.commit()

CATEGORY_KEYWORDS = {
    "ai": ["ai engineer", "machine learning", "ml engineer", "llm", "deep learning",
           "computer vision", "nlp", "data scientist", "foundation model", "agentic",
           "perception engineer", "vision engineer"],
    "robotics": ["robotics", "robot", "ros", "autonomous", "embedded", "firmware",
                 "mechatronics", "control systems", "navigation", "slam", "perception"],
    "software": ["software engineer", "backend", "frontend", "fullstack", "devops",
                 "platform engineer", "site reliability", "cloud engineer"],
}

SENIOR_KEYWORDS = ["senior", "lead", "principal", "head of", "director", "vp ", "staff ",
                   "architect", "manager", "chief", "sr.", "sr "]

def get_jobs(status=None, min_score=None, source=None, days=None, category=None,
             exclude_senior=False, search=None, page=1, per_page=20) -> tuple[int, list]:
    if status == 'rejected':
        base = "WHERE status='rejected'"
    elif status in ('saved', 'applied'):
        base = f"WHERE analyzed=1 AND status='{status}'"
    else:
        base = "WHERE analyzed=1 AND status='new' AND (german_required IS NULL OR german_required != 1)"
    params = []
    if min_score:
        base += " AND relevance_score>=?"
        params.append(min_score)
    if source:
        base += " AND source=?"
        params.append(source)
    if days:
        base += " AND COALESCE(NULLIF(posted,''), created_at) >= date('now', ?)"
        params.append(f"-{days} days")
    if category and category in CATEGORY_KEYWORDS:
        kws = CATEGORY_KEYWORDS[category]
        conditions = " OR ".join(["lower(title) LIKE ?"] * len(kws))
        base += f" AND ({conditions})"
        params.extend([f"%{kw}%" for kw in kws])
    if exclude_senior:
        for kw in SENIOR_KEYWORDS:
            base += " AND lower(title) NOT LIKE ?"
            params.append(f"%{kw}%")
    if search:
        term = f"%{search.lower()}%"
        base += " AND (lower(title) LIKE ? OR lower(company) LIKE ? OR lower(location) LIKE ?)"
        params.extend([term, term, term])

    with get_conn() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM jobs {base}", params).fetchone()[0]
        offset = (page - 1) * per_page
        rows = conn.execute(
            f"SELECT * FROM jobs {base} ORDER BY relevance_score DESC, created_at DESC LIMIT ? OFFSET ?",
            params + [per_page, offset]
        ).fetchall()
        return total, [dict(r) for r in rows]

def update_status(slug: str, status: str):
    with get_conn() as conn:
        conn.execute("UPDATE jobs SET status=?, seen=1 WHERE slug=?", (status, slug))
        conn.commit()

if __name__ == "__main__":
    init_db()
    print("DB initialized OK")
