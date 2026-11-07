"""Nepal Standard Time and Bikram Sambat (BS), Nepal's official calendar."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Nepal has observed a fixed UTC+05:45 offset with no daylight saving since 1986.
NEPAL_TZ = timezone(timedelta(hours=5, minutes=45), "NPT")


def nepal_now(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(NEPAL_TZ)


def bikram_sambat_label(moment: datetime) -> str | None:
    """'21 Kartik 2083 BS (२०८३ कार्तिक २१, शनिबार)' for a Nepal-local datetime.

    BS month lengths vary year to year and follow published tables, so this
    relies on nepali-datetime's table; None when the library or range is unavailable.
    """
    try:
        import nepali_datetime

        bs = nepali_datetime.date.from_datetime_date(moment.date())
    except Exception:
        return None
    return (
        f"{bs.day} {bs.strftime('%B')} {bs.year} BS "
        f"({bs.strftime('%K')} {bs.strftime('%N')} {bs.strftime('%D')}, {bs.strftime('%G')})"
    )
