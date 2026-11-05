"""
HINAA OS — Phase 13: Deterministic Cron & Timezone Scheduling Engine
Provides standard 5-field cron parsing, step/range/list evaluation, IANA timezone conversion
(Asia/Kathmandu, UTC, America/New_York, Europe/London), DST transition handling, and misfire coalescing.
"""

from __future__ import annotations

import datetime
import re
import time
import zoneinfo
from typing import List, Optional, Set, Tuple

from .contracts import MisfirePolicy, ScheduleType


WEEKDAY_MAP = {
    "MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6
}


class CronSyntaxError(ValueError):
    """Raised when cron expression is malformed."""
    pass


class ScheduleValidationError(ValueError):
    """Raised when schedule parameters violate safety bounds."""
    pass


def _parse_field(field_str: str, min_val: int, max_val: int, name: str) -> Set[int]:
    """Parse a single cron field into a set of matching integer values."""
    field_str = field_str.strip().upper()
    if not field_str:
        raise CronSyntaxError(f"Empty cron field for {name}")

    # Handle named weekdays
    if name == "day_of_week":
        for k, v in WEEKDAY_MAP.items():
            field_str = field_str.replace(k, str(v))

    values: Set[int] = set()

    for part in field_str.split(","):
        part = part.strip()
        if not part:
            continue

        if "/" in part:
            subparts = part.split("/")
            if len(subparts) != 2:
                raise CronSyntaxError(f"Invalid step syntax in {name}: '{part}'")
            base, step_str = subparts
            try:
                step = int(step_str)
                if step <= 0:
                    raise CronSyntaxError(f"Step must be > 0 in {name}: '{part}'")
            except ValueError:
                raise CronSyntaxError(f"Invalid integer step in {name}: '{part}'")

            if base == "*":
                start, end = min_val, max_val
            elif "-" in base:
                r_parts = base.split("-")
                if len(r_parts) != 2:
                    raise CronSyntaxError(f"Invalid range in {name}: '{part}'")
                start, end = int(r_parts[0]), int(r_parts[1])
            else:
                start = int(base)
                end = max_val

            if start < min_val or end > max_val or start > end:
                raise CronSyntaxError(f"Value range out of bounds [{min_val}-{max_val}] in {name}: '{part}'")

            for v in range(start, end + 1, step):
                values.add(v)

        elif "-" in part:
            r_parts = part.split("-")
            if len(r_parts) != 2:
                raise CronSyntaxError(f"Invalid range syntax in {name}: '{part}'")
            try:
                start, end = int(r_parts[0]), int(r_parts[1])
            except ValueError:
                raise CronSyntaxError(f"Invalid integer in range in {name}: '{part}'")
            if start < min_val or end > max_val or start > end:
                raise CronSyntaxError(f"Range out of bounds [{min_val}-{max_val}] in {name}: '{part}'")
            for v in range(start, end + 1):
                values.add(v)

        elif part == "*":
            for v in range(min_val, max_val + 1):
                values.add(v)

        else:
            try:
                val = int(part)
            except ValueError:
                raise CronSyntaxError(f"Invalid numeric value '{part}' in {name}")
            # If day_of_week is 7, map to 0 (Sunday)
            if name == "day_of_week" and val == 7:
                val = 0
            if val < min_val or val > max_val:
                raise CronSyntaxError(f"Value {val} out of bounds [{min_val}-{max_val}] in {name}")
            values.add(val)

    if not values:
        raise CronSyntaxError(f"No valid values resolved for {name}")

    return values


class CronSchedule:
    def __init__(self, expr: str):
        self.expr = expr.strip()
        parts = re.split(r"\s+", self.expr)
        if len(parts) != 5:
            raise CronSyntaxError(
                f"Cron expression must have exactly 5 fields (got {len(parts)}): '{self.expr}'"
            )

        self.minutes = _parse_field(parts[0], 0, 59, "minute")
        self.hours = _parse_field(parts[1], 0, 23, "hour")
        self.days_of_month = _parse_field(parts[2], 1, 31, "day_of_month")
        self.months = _parse_field(parts[3], 1, 12, "month")
        self.days_of_week = _parse_field(parts[4], 0, 6, "day_of_week")

    def matches(self, dt: datetime.datetime) -> bool:
        """Check if a localized datetime matches this cron expression."""
        if dt.minute not in self.minutes:
            return False
        if dt.hour not in self.hours:
            return False
        if dt.day not in self.days_of_month:
            return False
        if dt.month not in self.months:
            return False
        # In Python weekday() Monday is 0, Sunday is 6
        if dt.weekday() not in self.days_of_week:
            return False
        return True

    def get_next_fire_time(
        self,
        ref_utc_epoch: float,
        tz_name: str = "Asia/Kathmandu",
        max_search_days: int = 366,
    ) -> float:
        """
        Calculate the next future epoch UTC fire time matching the cron schedule.
        Takes timezone and DST into account.
        """
        try:
            tz = zoneinfo.ZoneInfo(tz_name)
        except Exception as e:
            raise ScheduleValidationError(f"Invalid IANA timezone: '{tz_name}' ({e})")

        # Convert ref epoch to localized datetime
        ref_dt = datetime.datetime.fromtimestamp(ref_utc_epoch, tz=datetime.timezone.utc).astimezone(tz)
        
        # Start searching from the next full minute
        cur = ref_dt.replace(second=0, microsecond=0) + datetime.timedelta(minutes=1)
        end_search = cur + datetime.timedelta(days=max_search_days)

        while cur < end_search:
            # Quick month skip
            if cur.month not in self.months:
                # advance to next month
                if cur.month == 12:
                    cur = cur.replace(year=cur.year + 1, month=1, day=1, hour=0, minute=0)
                else:
                    cur = cur.replace(month=cur.month + 1, day=1, hour=0, minute=0)
                continue

            # Day of month & day of week match
            day_matches = (cur.day in self.days_of_month) and (cur.weekday() in self.days_of_week)
            if not day_matches:
                cur = cur.replace(hour=0, minute=0) + datetime.timedelta(days=1)
                continue

            # Hour match
            if cur.hour not in self.hours:
                cur = cur.replace(minute=0) + datetime.timedelta(hours=1)
                continue

            # Minute match
            if cur.minute in self.minutes:
                # Target found. Convert back to UTC epoch.
                utc_dt = cur.astimezone(datetime.timezone.utc)
                return utc_dt.timestamp()

            cur += datetime.timedelta(minutes=1)

        raise ScheduleValidationError(f"No matching fire time within {max_search_days} days for '{self.expr}'")


def validate_schedule_params(
    schedule_type: ScheduleType,
    cron_expr: Optional[str] = None,
    interval_seconds: Optional[int] = None,
    timezone_name: str = "Asia/Kathmandu",
    min_interval_seconds: int = 10,
) -> None:
    """Validate schedule creation parameters according to safety bounds."""
    # 1. Validate timezone
    try:
        zoneinfo.ZoneInfo(timezone_name)
    except Exception as e:
        raise ScheduleValidationError(f"Invalid timezone '{timezone_name}': {e}")

    # 2. Validate schedule type constraints
    if schedule_type == ScheduleType.CRON:
        if not cron_expr or not cron_expr.strip():
            raise ScheduleValidationError("Cron expression required for CRON schedule type")
        # Validate syntax
        CronSchedule(cron_expr)

    elif schedule_type == ScheduleType.INTERVAL:
        if interval_seconds is None:
            raise ScheduleValidationError("interval_seconds required for INTERVAL schedule type")
        if interval_seconds < min_interval_seconds:
            raise ScheduleValidationError(
                f"Excessive frequency: interval_seconds must be >= {min_interval_seconds}s (got {interval_seconds}s)"
            )

    elif schedule_type == ScheduleType.ONE_SHOT:
        pass


def calculate_next_fire_time(
    schedule_type: ScheduleType,
    cron_expr: Optional[str],
    interval_seconds: Optional[int],
    timezone_name: str,
    ref_time_utc: Optional[float] = None,
) -> Optional[float]:
    """Calculate the next fire timestamp in UTC epoch seconds."""
    if ref_time_utc is None:
        ref_time_utc = time.time()

    if schedule_type == ScheduleType.INTERVAL:
        if not interval_seconds or interval_seconds <= 0:
            return None
        return ref_time_utc + interval_seconds

    elif schedule_type == ScheduleType.CRON:
        if not cron_expr:
            return None
        cron = CronSchedule(cron_expr)
        return cron.get_next_fire_time(ref_time_utc, tz_name=timezone_name)

    elif schedule_type == ScheduleType.ONE_SHOT:
        # Default one-shot runs immediately or at specified time
        return ref_time_utc

    return None


def resolve_misfire(
    scheduled_for_utc: float,
    now_utc: float,
    policy: MisfirePolicy,
    interval_seconds: Optional[int] = None,
) -> Tuple[bool, float]:
    """
    Resolve misfire behavior when backend recovers from downtime.
    Returns (should_run, run_timestamp).
    """
    if now_utc <= scheduled_for_utc:
        # Not a misfire
        return True, scheduled_for_utc

    if policy == MisfirePolicy.SKIP:
        return False, scheduled_for_utc

    if policy == MisfirePolicy.COALESCE:
        # Coalesce all missed executions into a single execution at now_utc
        return True, now_utc

    if policy == MisfirePolicy.RUN_LATEST:
        # Run only the single most recent execution
        return True, scheduled_for_utc

    return True, now_utc
