"""The clock behind "Reminder set", tested on rows a real schedule_reminder wrote.

A stored row is not yet a reminder: until something advances it, the promise holds
only while his tab stays open. These cases pin what makes it true -- a due row
fires once and speaks in the thread, a future row waits, a cancelled row never
fires, and a row with no thread to speak in says so instead of passing as sent.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pytest

from hinaa_api.config import Settings
from hinaa_api.persistence.db import get_session_factory, reset_session_factory
from hinaa_api.persistence.memory_service import MemoryService
from hinaa_api.reminder_scheduler import fire_due, run_scheduler
from hinaa_api.tools.reminder import cancel_reminder, list_reminders, schedule_reminder


def _settings(database_url: str) -> Settings:
    return Settings(
        _env_file=None,
        HINAA_PROVIDER_MODE="mock",
        HINAA_DATABASE_URL=database_url,
        HINAA_AUTH_MODE="dev",
        HINAA_PERSISTENCE_ENABLED=True,
    )


@pytest.fixture
def clock_db(tmp_path):
    """A file database plus the module-global reset, so the rows this suite
    writes are the only ones its clock can see."""
    reset_session_factory()
    settings = _settings(f"sqlite+pysqlite:///{(tmp_path / 'clock.db').as_posix()}")
    get_session_factory(settings)
    yield settings
    reset_session_factory()


def _thread(settings: Settings, user_id: str, conversation_id: str) -> list[tuple[str, str]]:
    rows = MemoryService(get_session_factory(settings)).get_conversation_messages(
        user_id, conversation_id
    )
    return [(row["role"], row["content"]) for row in rows]


def _minutes_ago(minutes: int) -> str:
    return (datetime.now() - timedelta(minutes=minutes)).isoformat(timespec="minutes")


def _hours_ago(hours: int) -> str:
    return (datetime.now() - timedelta(hours=hours)).isoformat(timespec="minutes")


def _hour_from_now() -> str:
    return (datetime.now() + timedelta(hours=1)).isoformat(timespec="minutes")


def test_a_due_reminder_fires_once_and_the_thread_speaks_it(clock_db):
    row = schedule_reminder(
        user_id="clock-user",
        title="Call Sile",
        at=_minutes_ago(1),
        conversation_id="clock-thread",
        settings=clock_db,
    )

    fired = fire_due(settings=clock_db)

    assert [item["id"] for item in fired] == [row["id"]]
    assert fired[0]["delivered"] is True
    assert fired[0]["title"] == "Call Sile"
    assert list_reminders(user_id="clock-user", status="scheduled", settings=clock_db) == []
    assert [item["title"] for item in list_reminders(
        user_id="clock-user", status="fired", settings=clock_db
    )] == ["Call Sile"]
    # The line he should see when he next opens the thread -- and no fake bubble
    # of his own invented next to it.
    assert _thread(clock_db, "clock-user", "clock-thread") == [
        ("assistant", "Reminder: Call Sile.")
    ]

    assert fire_due(settings=clock_db) == []


def test_a_reminder_that_is_not_due_yet_waits(clock_db):
    schedule_reminder(
        user_id="clock-user",
        title="Stretch",
        at=_hour_from_now(),
        conversation_id="clock-later",
        settings=clock_db,
    )

    assert fire_due(settings=clock_db) == []
    assert [item["title"] for item in list_reminders(
        user_id="clock-user", status="scheduled", settings=clock_db
    )] == ["Stretch"]
    assert _thread(clock_db, "clock-user", "clock-later") == []


def test_a_cancelled_reminder_never_fires(clock_db):
    row = schedule_reminder(
        user_id="clock-user",
        title="Skip",
        at=_minutes_ago(1),
        conversation_id="clock-cancelled",
        settings=clock_db,
    )
    cancel_reminder(user_id="clock-user", reminder_id=row["id"], settings=clock_db)

    assert fire_due(settings=clock_db) == []
    assert list_reminders(user_id="clock-user", status="all", settings=clock_db)[0][
        "status"
    ] == "cancelled"
    assert _thread(clock_db, "clock-user", "clock-cancelled") == []


def test_a_reminder_with_no_thread_fires_and_reports_that_it_was_not_delivered(clock_db):
    row = schedule_reminder(
        user_id="clock-user", title="Loose end", at=_minutes_ago(1), settings=clock_db
    )

    fired = fire_due(settings=clock_db)

    assert [item["id"] for item in fired] == [row["id"]]
    assert fired[0]["status"] == "fired"
    assert fired[0]["delivered"] is False
    assert list_reminders(user_id="clock-user", status="fired", settings=clock_db)


def test_a_row_that_came_due_long_ago_is_missed_instead_of_announced_late(clock_db):
    stale = schedule_reminder(
        user_id="clock-user",
        title="Yesterday's appointment",
        at=_hours_ago(5),
        conversation_id="clock-stale",
        settings=clock_db,
    )
    fresh = schedule_reminder(
        user_id="clock-user",
        title="Call back now",
        at=_minutes_ago(1),
        conversation_id="clock-fresh",
        settings=clock_db,
    )

    outcomes = {item["id"]: item for item in fire_due(settings=clock_db)}

    assert outcomes[stale["id"]]["status"] == "missed"
    assert outcomes[stale["id"]]["delivered"] is False
    assert outcomes[fresh["id"]]["status"] == "fired"
    assert _thread(clock_db, "clock-user", "clock-stale") == []
    assert _thread(clock_db, "clock-user", "clock-fresh") == [
        ("assistant", "Reminder: Call back now.")
    ]
    assert [item["title"] for item in list_reminders(
        user_id="clock-user", status="missed", settings=clock_db
    )] == ["Yesterday's appointment"]


def test_a_long_identity_subject_still_creates_its_owner(clock_db):
    """A Clerk subject can outgrow the 36-char primary key, and minting a uuid
    for it is the only way the row gets an owner at all."""
    subject = "user_" + "x" * 60

    row = schedule_reminder(
        user_id=subject,
        title="Call the bank",
        at=_minutes_ago(1),
        conversation_id="clock-long-id",
        settings=clock_db,
    )
    assert row["title"] == "Call the bank"

    assert fire_due(settings=clock_db)[0]["delivered"] is True
    assert [item["title"] for item in list_reminders(
        user_id=subject, status="fired", settings=clock_db
    )] == ["Call the bank"]
    assert _thread(clock_db, subject, "clock-long-id") == [
        ("assistant", "Reminder: Call the bank.")
    ]


def test_the_loop_ticks_the_clock_and_stops_on_request(clock_db):
    schedule_reminder(
        user_id="loop-user",
        title="Water the plants",
        at=_minutes_ago(1),
        conversation_id="loop-thread",
        settings=clock_db,
    )

    async def drive() -> None:
        stop = asyncio.Event()
        task = asyncio.create_task(
            run_scheduler(settings=clock_db, stop=stop, tick_seconds=0.05)
        )
        for _ in range(60):
            await asyncio.sleep(0.05)
            if list_reminders(user_id="loop-user", status="fired", settings=clock_db):
                break
        stop.set()
        await asyncio.wait_for(task, timeout=5)

    asyncio.run(drive())

    assert _thread(clock_db, "loop-user", "loop-thread") == [
        ("assistant", "Reminder: Water the plants.")
    ]


def test_the_app_itself_starts_and_stops_the_clock(clock_db):
    """A clock nothing boots is a clock that never fires, so this asserts on the
    running app: the task exists while the lifespan is open, a due reminder
    fires without anyone calling it, and the task is gone once it closes."""
    from hinaa_api.main import create_app

    schedule_reminder(
        user_id="app-user",
        title="Check the oven",
        at=_minutes_ago(1),
        conversation_id="app-thread",
        settings=clock_db,
    )

    async def drive() -> tuple[bool, bool]:
        app = create_app(clock_db)
        async with app.router.lifespan_context(app):
            started = "hinaa-reminder-scheduler" in {
                task.get_name() for task in asyncio.all_tasks()
            }
            await asyncio.sleep(0.2)
        still = "hinaa-reminder-scheduler" in {
            task.get_name() for task in asyncio.all_tasks()
        }
        return started, still

    started, still_running = asyncio.run(drive())

    assert started is True
    assert still_running is False
    assert [item["title"] for item in list_reminders(
        user_id="app-user", status="fired", settings=clock_db
    )] == ["Check the oven"]
    assert _thread(clock_db, "app-user", "app-thread") == [
        ("assistant", "Reminder: Check the oven.")
    ]
