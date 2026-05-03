import os
import time
import threading
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import db

app = FastAPI()

def _analyzer_background_loop(poll_interval: int = 15):
    from analyzer import run_analysis
    print("Analyzer background loop started — polling every 15s...")
    while True:
        try:
            run_analysis(limit=50)
        except Exception as e:
            print(f"Analyzer loop error: {e}")
        time.sleep(poll_interval)

_analyzer_thread = threading.Thread(target=_analyzer_background_loop, daemon=True)
_analyzer_thread.start()


@app.get("/api/stats")
def stats():
    with db.get_conn() as conn:
        total    = conn.execute("SELECT COUNT(*) FROM jobs WHERE analyzed=1 AND (german_required IS NULL OR german_required!=1)").fetchone()[0]
        new      = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='new' AND analyzed=1 AND (german_required IS NULL OR german_required!=1)").fetchone()[0]
        applied  = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='applied'").fetchone()[0]
        saved    = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='saved'").fetchone()[0]
        pending  = conn.execute("SELECT COUNT(*) FROM jobs WHERE analyzed=0").fetchone()[0]
    return {"total": total, "new": new, "applied": applied, "saved": saved, "pending_analysis": pending}

class StatusUpdate(BaseModel):
    status: str

@app.patch("/api/jobs/{slug}/status")
def update_status(slug: str, body: StatusUpdate):
    db.update_status(slug, body.status)
    return {"ok": True}

@app.get("/api/jobs/pending")
def pending_jobs(page: int = 1, per_page: int = 30):
    with db.get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM jobs WHERE analyzed=0").fetchone()[0]
        offset = (page - 1) * per_page
        rows = conn.execute(
            "SELECT slug, title, company, source, created_at FROM jobs WHERE analyzed=0 ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (per_page, offset)
        ).fetchall()
    return {"total": total, "page": page, "per_page": per_page, "jobs": [dict(r) for r in rows]}

@app.get("/api/jobs")
def list_jobs_paginated(status: str = None, min_score: int = None, source: str = None,
                        days: int = None, category: str = None, exclude_senior: bool = False,
                        page: int = 1, per_page: int = 20):
    total, jobs = db.get_jobs(status=status, min_score=min_score, source=source,
                              days=days, category=category, exclude_senior=exclude_senior,
                              page=page, per_page=per_page)
    return {"total": total, "page": page, "per_page": per_page, "jobs": jobs}

@app.post("/api/run-scraper")
def run_scraper():
    def _run():
        from scheduler import run_scrapers
        run_scrapers()
    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "message": "Scraper started in background"}

app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "frontend"), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    db.init_db()
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
