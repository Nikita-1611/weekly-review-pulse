import time
import schedule
import subprocess
import os
import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

# Add root to sys.path to import run_pulse
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(ROOT_DIR))

# ─── Cron Schedule ───────────────────────────────────────────────────────
# Default: Every Monday at 8:00 AM IST
# Cron equivalent: 0 8 * * 1 TZ=Asia/Kolkata python /path/to/run_pulse.py --product all

SCHEDULE_DAY = "monday"
SCHEDULE_TIME_IST = "08:00"


def job(product: str = "all"):
    """Triggers a scheduled Pulse pipeline run."""
    ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
    print(f"\n[{ist_now.strftime('%Y-%m-%d %H:%M:%S IST')}] ⏰ Triggering scheduled Pulse run for '{product}'...")
    try:
        result = subprocess.run(
            [sys.executable, "run_pulse.py", "--product", product],
            check=True,
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.stderr:
            print(f"STDERR: {result.stderr}")
        print(f"[{ist_now.strftime('%H:%M:%S')}] ✅ Scheduled run completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"[{ist_now.strftime('%H:%M:%S')}] ❌ Scheduled run failed (exit code {e.returncode})")
        if e.stdout:
            print(f"STDOUT: {e.stdout}")
        if e.stderr:
            print(f"STDERR: {e.stderr}")
    except Exception as e:
        print(f"[{ist_now.strftime('%H:%M:%S')}] ❌ Error in scheduled job: {e}")


def start_weekly_scheduler(product: str = "all", run_immediately: bool = False):
    """
    Starts the weekly scheduler.
    
    Runs every Monday at 8:00 AM IST (configurable via SCHEDULE_TIME_IST).
    The scheduler uses the `schedule` library for simplicity. For production
    environments, consider using system cron or a cloud-based scheduler.
    
    Usage:
        python cron_config.py                     # Start weekly scheduler
        python cron_config.py --run-now           # Run immediately then schedule
        python cron_config.py --product groww     # Schedule for a specific product
    """
    print("=" * 60)
    print("  Weekly Product Review Pulse — Scheduler")
    print("=" * 60)
    print(f"  Schedule : Every {SCHEDULE_DAY.capitalize()} at {SCHEDULE_TIME_IST} IST")
    print(f"  Product  : {product}")
    print(f"  Root Dir : {ROOT_DIR}")
    print("=" * 60)

    if run_immediately:
        print("\n▶ Running immediately (--run-now flag detected)...")
        job(product)

    # Schedule weekly run on Monday at 8:00 AM IST
    getattr(schedule.every(), SCHEDULE_DAY).at(SCHEDULE_TIME_IST).do(job, product=product)

    print(f"\n⏳ Scheduler is running. Waiting for {SCHEDULE_DAY.capitalize()} {SCHEDULE_TIME_IST} IST...")
    print("   Press Ctrl+C to stop.\n")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        print("\n\n🛑 Scheduler stopped by user.")


def generate_cron_command(product: str = "all") -> str:
    """
    Generates the system crontab command for users who prefer OS-level scheduling.
    
    Returns:
        str: The crontab entry string.
    """
    python_path = sys.executable
    script_path = ROOT_DIR / "run_pulse.py"
    log_path = ROOT_DIR / "logs" / "cron.log"
    
    # Cron: minute hour day_of_month month day_of_week command
    # Monday = 1, 8:00 AM IST (UTC+5:30 = 2:30 AM UTC)
    cron_line = f"30 2 * * 1 cd {ROOT_DIR} && {python_path} {script_path} --product {product} >> {log_path} 2>&1"
    
    return cron_line


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pulse Weekly Scheduler")
    parser.add_argument("--product", type=str, default="all", help="Product ID or 'all' (default: all)")
    parser.add_argument("--run-now", action="store_true", help="Run immediately before starting the schedule")
    parser.add_argument("--show-cron", action="store_true", help="Print the system crontab entry and exit")

    args = parser.parse_args()

    if args.show_cron:
        print("\n📋 Add this line to your system crontab (crontab -e):\n")
        print(f"  {generate_cron_command(args.product)}")
        print("\n  This runs every Monday at 8:00 AM IST (2:30 AM UTC).\n")
    else:
        start_weekly_scheduler(product=args.product, run_immediately=args.run_now)
