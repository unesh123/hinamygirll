"""Move HINAA's private data from local dev subjects onto a real sign-in subject.

The dev identity header used to be the only way to name an owner, so his
conversations, memories and projects accumulated under invented strings
("local-dev-user", "local-web-user", "unesh"). Clerk issues a stable subject
instead, and this script re-points the old rows at it.

Ownership hangs off users.auth_subject; every other table stores users.id, so
renaming that one column carries the whole history with it. Rows that were
keyed by the subject string itself (agent_runs) are normalised to the id.

Usage (apps/api, with the API stopped):
    python scripts/reassign_subject.py --to user_3Jh7... --from local-dev-user --from unesh
    ... --apply
Dry-run by default; it prints what it would touch and writes nothing.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# (table, column) pairs that store users.id, plus agent_runs which historically
# stored the raw subject string instead.
OWNER_COLUMNS: list[tuple[str, str]] = [
    ("conversations", "user_id"),
    ("explicit_memories", "user_id"),
    ("memory_consents", "user_id"),
    ("audit_events", "user_id"),
    ("local_projects", "user_id"),
    ("generation_sets", "user_id"),
    ("provider_usage", "user_id"),
    ("conversation_entities", "user_id"),
    ("episodic_memories", "user_id"),
    ("training_example_candidates", "user_id"),
    ("conversation_turn_states", "user_id"),
    ("conversation_episodes", "user_id"),
    ("user_continuity_states", "owner_id"),
    ("durable_tasks", "owner_id"),
    ("agent_runs", "user_id"),
]


def default_database_path() -> Path:
    return Path.home() / ".hinaa" / "hinaa.db"


def user_by_subject(conn: sqlite3.Connection, subject: str) -> tuple[str, str] | None:
    row = conn.execute(
        "SELECT id, auth_subject FROM users WHERE auth_subject = ?", (subject,)
    ).fetchone()
    return (row[0], row[1]) if row else None


def owned_counts(conn: sqlite3.Connection, keys: list[str]) -> dict[str, int]:
    """How many rows each owner id (or literal subject) holds, per table."""
    totals: dict[str, int] = {}
    for table, column in OWNER_COLUMNS:
        placeholders = ",".join("?" for _ in keys)
        found = conn.execute(
            f"SELECT {column}, COUNT(*) FROM {table} WHERE {column} IN ({placeholders}) GROUP BY {column}",
            keys,
        ).fetchall()
        totals[f"{table}.{column}"] = sum(count for _, count in found)
    return totals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=default_database_path())
    parser.add_argument("--to", required=True, help="subject that will own the data (a Clerk user id)")
    parser.add_argument(
        "--from",
        dest="sources",
        action="append",
        default=[],
        help="an old subject to absorb; repeat for each one",
    )
    parser.add_argument("--apply", action="store_true", help="write the changes instead of reporting them")
    args = parser.parse_args(argv)

    if not args.sources:
        parser.error("at least one --from subject is required")
    if args.to in args.sources:
        parser.error("--to must differ from every --from subject")
    if not args.database.exists():
        print(f"database not found: {args.database}", file=sys.stderr)
        return 2

    conn = sqlite3.connect(args.database)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        target = user_by_subject(conn, args.to)
        resolved = [(subject, user_by_subject(conn, subject)) for subject in args.sources]
        missing = [subject for subject, found in resolved if found is None]
        for subject in missing:
            print(f"  no users row for {subject}; searching for rows filed under that literal")

        plan_rows = [(subject, found) for subject, found in resolved if found]
        if not plan_rows:
            print("nothing to do: none of the --from subjects exist", file=sys.stderr)
            return 1

        keys = [value for _, (value, _) in plan_rows] + [subject for subject, _ in plan_rows]
        if target:
            keys.append(target[0])
        print(f"rows currently held by the subjects in scope:")
        for column, count in owned_counts(conn, sorted(set(keys))).items():
            if count:
                print(f"  {column}: {count}")

        # A target row created by an earlier sign-in has to be vacated before the
        # survivor can take its subject, otherwise the unique index rejects it.
        if target:
            target_id, _ = target
            blocking = {
                column: count
                for column, count in owned_counts(conn, [target_id]).items()
                if count
            }
            if blocking:
                print(
                    f"\nrefusing to merge: {args.to} already owns data ({blocking}).\n"
                    "Move those rows deliberately; this script will not overwrite them.",
                    file=sys.stderr,
                )
                return 1
            if args.apply:
                conn.execute("DELETE FROM users WHERE id = ?", (target_id,))

        survivor_subjects = {subject for subject, _ in plan_rows}
        primary_subject, (primary_id, _) = plan_rows[0]
        if args.apply:
            conn.execute(
                "UPDATE users SET auth_subject = ? WHERE id = ?", (args.to, primary_id)
            )
        print(f"\n{primary_subject} -> {args.to} (user id {primary_id} keeps every row)")

        for subject, (source_id, _) in plan_rows[1:]:
            for table, column in OWNER_COLUMNS:
                if args.apply:
                    conn.execute(
                        f"UPDATE {table} SET {column} = ? WHERE {column} = ?",
                        (primary_id, source_id),
                    )
                    # Rows written before identity resolution stored the subject
                    # text itself rather than the user id.
                    conn.execute(
                        f"UPDATE {table} SET {column} = ? WHERE {column} = ?",
                        (primary_id, subject),
                    )
            if args.apply:
                conn.execute("DELETE FROM users WHERE id = ?", (source_id,))
            print(f"  absorbed {subject} (user id {source_id}) into {primary_id}")

        # Literals that never had a users row still own rows: the local UI wrote
        # generation history under "local-user" before any identity existed.
        for subject in missing:
            reclaimed = 0
            for table, column in OWNER_COLUMNS:
                found = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {column} = ?", (subject,)
                ).fetchone()[0]
                if found and args.apply:
                    conn.execute(
                        f"UPDATE {table} SET {column} = ? WHERE {column} = ?",
                        (primary_id, subject),
                    )
                reclaimed += found
            if reclaimed:
                print(f"  reclaimed {reclaimed} rows filed under the bare literal '{subject}'")

        if args.apply:
            for table, column in OWNER_COLUMNS:
                conn.execute(
                    f"UPDATE {table} SET {column} = ? WHERE {column} = ?",
                    (primary_id, primary_subject),
                )
            conn.commit()
            remaining = conn.execute(
                "SELECT COUNT(*) FROM users WHERE auth_subject IN (%s)"
                % ",".join("?" for _ in survivor_subjects),
                tuple(survivor_subjects),
            ).fetchone()[0]
            print(f"\napplied. old subjects still present: {remaining}")
        else:
            print("\ndry run - nothing written. re-run with --apply")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
