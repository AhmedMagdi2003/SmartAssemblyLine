from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from sqlalchemy import desc, func

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db.models import BoxEvent
from src.db.repositories import get_shift_summary, serialize_box_event
from src.db.session import SessionLocal, get_database_url


def build_parser():
    parser = argparse.ArgumentParser(
        description="Fetch Smart Assembly Line records from PostgreSQL.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    events_parser = subparsers.add_parser("events", help="Fetch box event records.")
    events_parser.add_argument("--limit", type=int, default=20, help="Number of records to fetch.")
    events_parser.add_argument("--shift", help="Filter by shift name, for example Morning_Shift.")
    events_parser.add_argument("--shift-date", dest="shift_date", help="Filter by shift date in YYYY-MM-DD.")
    events_parser.add_argument("--uuid", help="Fetch a specific event UUID.")
    events_parser.add_argument("--latest", action="store_true", help="Fetch only the latest matching record.")
    events_parser.add_argument("--json", action="store_true", help="Print JSON output.")

    shifts_parser = subparsers.add_parser("shifts", help="Fetch per-shift summary rows.")
    shifts_parser.add_argument("--limit", type=int, default=10, help="Number of shift windows to fetch.")
    shifts_parser.add_argument("--json", action="store_true", help="Print JSON output.")

    count_parser = subparsers.add_parser("count", help="Count stored box events.")
    count_parser.add_argument("--shift", help="Filter by shift name.")
    count_parser.add_argument("--shift-date", dest="shift_date", help="Filter by shift date in YYYY-MM-DD.")

    return parser


def apply_filters(query, args):
    if getattr(args, "shift", None):
        query = query.filter(BoxEvent.shift == args.shift)

    shift_date = getattr(args, "shift_date", None)
    if shift_date:
        normalized_date = shift_date.replace("-", "")
        if getattr(args, "shift", None):
            query = query.filter(BoxEvent.uuid.like(f"BOX-{normalized_date}-{args.shift}-%"))
        else:
            query = query.filter(BoxEvent.uuid.like(f"BOX-{normalized_date}-%"))

    if getattr(args, "uuid", None):
        query = query.filter(BoxEvent.uuid == args.uuid)

    return query


def format_table(rows, columns):
    if not rows:
        return "No records found."

    widths = {
        column: max(len(column), *(len(str(row.get(column, ""))) for row in rows))
        for column in columns
    }
    header = " | ".join(column.ljust(widths[column]) for column in columns)
    divider = "-+-".join("-" * widths[column] for column in columns)
    body = [
        " | ".join(str(row.get(column, "")).ljust(widths[column]) for column in columns)
        for row in rows
    ]
    return "\n".join([header, divider, *body])


def fetch_events(args):
    session = SessionLocal()
    try:
        query = session.query(BoxEvent)
        query = apply_filters(query, args)
        query = query.order_by(desc(BoxEvent.timestamp_iso), desc(BoxEvent.id))

        if args.latest:
            row = query.first()
            records = [serialize_box_event(row)] if row else []
        else:
            records = [serialize_box_event(row) for row in query.limit(max(1, args.limit)).all()]

        if args.json:
            print(json.dumps(records, indent=2))
            return

        columns = [
            "id",
            "uuid",
            "shift",
            "shift_date",
            "shift_count",
            "transit_time_sec",
            "orientation_deg",
            "timestamp_iso",
        ]
        print(format_table(records, columns))
    finally:
        session.close()


def fetch_shift_summaries(args):
    summaries = get_shift_summary(limit=max(1, args.limit))
    if args.json:
        print(json.dumps(summaries, indent=2))
        return

    columns = ["shift", "shift_date", "volume", "average_transit_time_sec"]
    print(format_table(summaries, columns))


def fetch_count(args):
    session = SessionLocal()
    try:
        query = session.query(func.count(BoxEvent.id))
        query = apply_filters(query, args)
        total = query.scalar() or 0
        print(f"Matching records: {int(total)}")
    finally:
        session.close()


def main():
    parser = build_parser()
    args = parser.parse_args()

    print(f"Database: {get_database_url()}")
    print(f"Command: {args.command}")

    if args.command == "events":
        fetch_events(args)
    elif args.command == "shifts":
        fetch_shift_summaries(args)
    elif args.command == "count":
        fetch_count(args)
    else:
        parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
