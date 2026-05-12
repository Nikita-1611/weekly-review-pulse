import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

def generate_run_id() -> str:
    """Generates a unique run ID for a pipeline execution."""
    return f"run_{uuid.uuid4().hex[:8]}"

class WindowHelper:
    """Helper for ISO-week math, IST-aware."""
    
    @staticmethod
    def get_current_iso_week() -> str:
        """Returns the current ISO week in 'YYYY-WNN' format based on IST timezone."""
        ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
        year, week, _ = ist_now.isocalendar()
        return f"{year}-W{week:02d}"

    @staticmethod
    def validate_iso_week(iso_week: str) -> bool:
        """Basic validation for ISO week format YYYY-WNN."""
        if len(iso_week) != 8 or not iso_week[:4].isdigit() or iso_week[4:6] != "-W" or not iso_week[6:].isdigit():
            return False
        return True

import time
import asyncio
from functools import wraps
import logging

def with_retries(max_retries=3, base_delay=2.0, exceptions=(Exception,)):
    """
    A decorator that retries a function upon failure.
    Uses exponential backoff: base_delay * (2 ** attempt).
    Supports both synchronous and asynchronous functions.
    """
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                logger = logging.getLogger("retry_logic")
                attempt = 0
                while attempt <= max_retries:
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as e:
                        attempt += 1
                        if attempt > max_retries:
                            logger.error(f"Async function {func.__name__} failed after {max_retries} retries. Error: {e}")
                            raise
                        delay = base_delay * (2 ** (attempt - 1))
                        logger.warning(f"Async function {func.__name__} failed: {e}. Retrying {attempt}/{max_retries} in {delay}s...")
                        await asyncio.sleep(delay)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                logger = logging.getLogger("retry_logic")
                attempt = 0
                while attempt <= max_retries:
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        attempt += 1
                        if attempt > max_retries:
                            logger.error(f"Function {func.__name__} failed after {max_retries} retries. Error: {e}")
                            raise
                        delay = base_delay * (2 ** (attempt - 1))
                        logger.warning(f"Function {func.__name__} failed: {e}. Retrying {attempt}/{max_retries} in {delay}s...")
                        time.sleep(delay)
            return sync_wrapper
    return decorator

