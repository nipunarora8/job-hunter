from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logging.basicConfig(level=logging.INFO)

def run_scrapers():
    from scrapers.arbeitnow import scrape as s1
    from scrapers.bundesagentur import scrape as s2
    from scrapers.indeed import scrape as s3
    from scrapers.linkedin import scrape as s4
    from scrapers.stepstone import scrape as s5

    scrapers = [
        ("Arbeitnow", s1),
        ("Bundesagentur", s2),
        ("Indeed", s3),
        ("LinkedIn", s4),
        ("StepStone", s5),
    ]

    print("Starting all scrapers in parallel...")
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fn): name for name, fn in scrapers}
        for future in as_completed(futures):
            name = futures[future]
            try:
                n = future.result()
                print(f"{name}: {n} new jobs scraped")
            except Exception as e:
                print(f"{name} FAILED: {e}")
    print("All scrapers done.")

def run_all():
    run_scrapers()
    print("run_all complete.")

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
