import sqlite3
import config

def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
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
    with get_conn() as conn:
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

def delete_job(slug: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM jobs WHERE slug=?", (slug,))
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

def get_jobs(status=None, min_score=None, source=None, days=None, category=None, exclude_senior=False) -> list:
    # german_required: show jobs where it's 0 (not required) or NULL (unclear) — only hide explicit 1
    query = "SELECT * FROM jobs WHERE analyzed=1 AND (german_required IS NULL OR german_required != 1)"
    params = []
    if status:
        query += " AND status=?"
        params.append(status)
    if min_score:
        query += " AND relevance_score>=?"
        params.append(min_score)
    if source:
        query += " AND source=?"
        params.append(source)
    if days:
        # Use created_at (always set) as primary; fall back to posted where available
        query += " AND created_at >= datetime('now', ?)"
        params.append(f"-{days} days")
    if category and category in CATEGORY_KEYWORDS:
        kws = CATEGORY_KEYWORDS[category]
        conditions = " OR ".join(["lower(title) LIKE ?"] * len(kws))
        query += f" AND ({conditions})"
        params.extend([f"%{kw}%" for kw in kws])
    if exclude_senior:
        for kw in SENIOR_KEYWORDS:
            query += " AND lower(title) NOT LIKE ?"
            params.append(f"%{kw}%")
    query += " ORDER BY relevance_score DESC, created_at DESC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

def update_status(slug: str, status: str):
    with get_conn() as conn:
        conn.execute("UPDATE jobs SET status=?, seen=1 WHERE slug=?", (status, slug))
        conn.commit()

if __name__ == "__main__":
    init_db()
    print("DB initialized OK")
