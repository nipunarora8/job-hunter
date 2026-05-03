from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
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

def analyzer_loop(stop_event: threading.Event, poll_interval: int = 10):
    from analyzer import run_analysis
    print("Analyzer loop started — polling every {poll_interval}s for pending jobs...")
    while not stop_event.is_set():
        run_analysis(limit=50)
        stop_event.wait(poll_interval)
    # Final drain after scrapers finish
    run_analysis(limit=2000)
    print("Analyzer loop done.")

def run_all():
    stop_event = threading.Event()

    # Start analyzer polling in background
    analyzer_thread = threading.Thread(target=analyzer_loop, args=(stop_event,), daemon=True)
    analyzer_thread.start()

    # Run all scrapers in parallel (blocking until all done)
    run_scrapers()

    # Signal analyzer to stop after one final pass
    stop_event.set()
    analyzer_thread.join(timeout=120)
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
