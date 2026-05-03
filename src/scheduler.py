from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

logging.basicConfig(level=logging.INFO)

def run_all():
    from scrapers.arbeitnow import scrape as s1
    from scrapers.bundesagentur import scrape as s2
    from scrapers.indeed import scrape as s3
    from scrapers.linkedin import scrape as s4
    from scrapers.stepstone import scrape as s5
    from analyzer import run_analysis

    total = 0
    for name, fn in [("Arbeitnow", s1), ("Bundesagentur", s2), ("Indeed", s3), ("LinkedIn", s4), ("StepStone", s5)]:
        try:
            n = fn()
            print(f"{name}: {n} new jobs")
            total += n
        except Exception as e:
            print(f"{name} FAILED: {e}")

    print(f"Total new: {total}")
    run_analysis(limit=2000)

if __name__ == "__main__":
    from db import init_db
    init_db()
    print("Running initial scrape on startup...")
    run_all()

    scheduler = BlockingScheduler()
    scheduler.add_job(run_all, CronTrigger(hour=8, minute=0))
    print("Scheduler started — will run daily at 08:00")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("Scheduler stopped")
