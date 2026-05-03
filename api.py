from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import db

app = FastAPI()

@app.get("/api/jobs")
def list_jobs(status: str = None, min_score: int = None, source: str = None,
              days: int = None, category: str = None, exclude_senior: bool = False):
    return db.get_jobs(status=status, min_score=min_score, source=source,
                       days=days, category=category, exclude_senior=exclude_senior)

@app.get("/api/stats")
def stats():
    with db.get_conn() as conn:
        total    = conn.execute("SELECT COUNT(*) FROM jobs WHERE analyzed=1 AND german_required!=1").fetchone()[0]
        new      = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='new' AND analyzed=1 AND german_required!=1").fetchone()[0]
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

@app.post("/api/run-analysis")
def run_analysis_endpoint():
    import threading
    def _run():
        from analyzer import run_analysis
        run_analysis(limit=100)
    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "message": "Analysis started in background"}

@app.post("/api/run-scraper")
def run_scraper():
    import threading
    def _run():
        from scrapers.arbeitnow import scrape as s1
        from scrapers.bundesagentur import scrape as s2
        from scrapers.indeed import scrape as s3
        from scrapers.linkedin import scrape as s4
        from scrapers.stepstone import scrape as s5
        from analyzer import run_analysis
        n = s1() + s2() + s3() + s4() + s5()
        print(f"Scraped {n} new jobs total")
        run_analysis()
    threading.Thread(target=_run, daemon=True).start()
    return {"ok": True, "message": "Scraper started in background"}

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    db.init_db()
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
