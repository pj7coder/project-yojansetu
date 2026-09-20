from datetime import datetime, timedelta, timezone
import random
from typing import Optional

from app.core.config import settings

PRIORITY_DEFAULT_MINUTES = {
    "TIER_1": 60,       # 1 hour
    "TIER_2": 360,      # 6 hours
    "TIER_3": 1440,     # 24 hours
    "TIER_4": 10080,    # 7 days
}


class MonitoringScheduler:
    """Calculates adaptive check intervals, failure backoff, and scheduling jitter."""

    def __init__(
        self,
        min_interval_minutes: Optional[int] = None,
        max_interval_minutes: Optional[int] = None,
        unchanged_backoff_factor: Optional[float] = None,
        failure_backoff_factor: Optional[float] = None,
        jitter_seconds: Optional[int] = None,
    ):
        self.min_interval_minutes = (
            min_interval_minutes or settings.MONITOR_MIN_INTERVAL_MINUTES
        )
        self.max_interval_minutes = (
            max_interval_minutes or settings.MONITOR_MAX_INTERVAL_MINUTES
        )
        self.unchanged_backoff_factor = (
            unchanged_backoff_factor or settings.MONITOR_UNCHANGED_BACKOFF_FACTOR
        )
        self.failure_backoff_factor = (
            failure_backoff_factor or settings.MONITOR_FAILURE_BACKOFF_FACTOR
        )
        self.jitter_seconds = (
            jitter_seconds
            if jitter_seconds is not None
            else settings.MONITOR_JITTER_SECONDS
        )

    def get_base_interval(self, priority: str, custom_interval: Optional[int] = None) -> int:
        """Determine base interval in minutes from priority or custom override."""
        if custom_interval and custom_interval > 0:
            interval = custom_interval
        else:
            interval = PRIORITY_DEFAULT_MINUTES.get(priority.upper(), 1440)
        return max(self.min_interval_minutes, min(interval, self.max_interval_minutes))

    def calculate_next_check(
        self,
        priority: str,
        result_status: str,
        consecutive_failures: int = 0,
        consecutive_unchanged: int = 0,
        custom_interval: Optional[int] = None,
        retry_after_seconds: Optional[int] = None,
        from_time: Optional[datetime] = None,
    ) -> datetime:
        """Calculate next scheduled check timestamp with adaptive rules and jitter."""
        if from_time is None:
            from_time = datetime.now(timezone.utc)

        base_minutes = self.get_base_interval(priority, custom_interval)

        # 1. Handling rate limiting / 429
        if retry_after_seconds and retry_after_seconds > 0:
            delay_seconds = max(retry_after_seconds, self.min_interval_minutes * 60)
            return from_time + timedelta(seconds=delay_seconds)

        # 2. Handling failures
        if result_status in ("CHECK_FAILED", "TEMPORARILY_UNAVAILABLE", "TIMEOUT"):
            # Exponential backoff on failures: base failure 15m * factor ^ failures
            failure_power = min(consecutive_failures, 5)
            calc_minutes = max(15, self.min_interval_minutes) * (
                self.failure_backoff_factor ** max(0, failure_power - 1)
            )
            interval_minutes = max(self.min_interval_minutes, min(calc_minutes, self.max_interval_minutes))

        elif result_status in ("BLOCKED_BY_POLICY", "ACCESS_FORBIDDEN", "AUTH_REQUIRED"):
            # Policy blocked: check infrequently (e.g. 24h or max interval)
            interval_minutes = min(1440, self.max_interval_minutes)

        elif result_status == "CHANGED":
            # Change detected: reset to base interval
            interval_minutes = base_minutes

        elif result_status in ("UNCHANGED", "BASELINE_CREATED"):
            # Adaptive backoff for stable, unchanged sources
            if consecutive_unchanged >= 10:
                calc_minutes = base_minutes * (self.unchanged_backoff_factor ** 2)
            elif consecutive_unchanged >= 5:
                calc_minutes = base_minutes * self.unchanged_backoff_factor
            else:
                calc_minutes = base_minutes
            interval_minutes = max(self.min_interval_minutes, min(calc_minutes, self.max_interval_minutes))

        else:
            interval_minutes = base_minutes

        # 3. Add jitter
        interval_seconds = interval_minutes * 60
        if self.jitter_seconds > 0:
            # Jitter between -jitter_seconds and +jitter_seconds, capped at 10% of interval
            max_jitter = min(self.jitter_seconds, int(interval_seconds * 0.1))
            jitter_offset = random.randint(-max_jitter, max_jitter)
            interval_seconds = max(self.min_interval_minutes * 60, interval_seconds + jitter_offset)

        return from_time + timedelta(seconds=interval_seconds)
