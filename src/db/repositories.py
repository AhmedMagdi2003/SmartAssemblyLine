from sqlalchemy import desc, func
from sqlalchemy.exc import IntegrityError

from .models import BoxEvent
from .session import SessionLocal


REQUIRED_FIELDS = (
    "uuid",
    "yolo_session_id",
    "timestamp_iso",
    "shift",
    "shift_count",
    "transit_time_sec",
    "orientation_deg",
    "status",
)


def normalize_box_event_payload(payload):
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"Missing required payload fields: {', '.join(missing)}")

    return {
        "uuid": str(payload["uuid"]),
        "yolo_session_id": int(payload["yolo_session_id"]),
        "timestamp_iso": str(payload["timestamp_iso"]),
        "shift": str(payload["shift"]),
        "shift_count": int(payload["shift_count"]),
        "transit_time_sec": float(payload["transit_time_sec"]),
        "orientation_deg": float(payload["orientation_deg"]),
        "status": str(payload["status"]),
    }


def save_box_event(payload, session_factory=SessionLocal):
    """
    Persist a completed carton event.
    Returns True when a new record is inserted and False when the UUID already exists.
    """
    normalized = normalize_box_event_payload(payload)
    session = session_factory()
    try:
        session.add(BoxEvent(**normalized))
        session.commit()
        return True
    except IntegrityError:
        session.rollback()
        return False
    finally:
        session.close()


def serialize_box_event(event):
    return {
        "id": event.id,
        "uuid": event.uuid,
        "yolo_session_id": event.yolo_session_id,
        "timestamp_iso": event.timestamp_iso,
        "shift": event.shift,
        "shift_count": event.shift_count,
        "transit_time_sec": event.transit_time_sec,
        "orientation_deg": event.orientation_deg,
        "status": event.status,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def list_recent_box_events(limit=50, session_factory=SessionLocal):
    session = session_factory()
    try:
        rows = (
            session.query(BoxEvent)
            .order_by(desc(BoxEvent.timestamp_iso), desc(BoxEvent.id))
            .limit(limit)
            .all()
        )
        return [serialize_box_event(row) for row in rows]
    finally:
        session.close()


def get_latest_box_event(session_factory=SessionLocal):
    session = session_factory()
    try:
        row = (
            session.query(BoxEvent)
            .order_by(desc(BoxEvent.timestamp_iso), desc(BoxEvent.id))
            .first()
        )
        return serialize_box_event(row) if row else None
    finally:
        session.close()


def get_current_kpis(session_factory=SessionLocal):
    session = session_factory()
    try:
        latest = (
            session.query(BoxEvent)
            .order_by(desc(BoxEvent.timestamp_iso), desc(BoxEvent.id))
            .first()
        )
        if latest is None:
            return {
                "current_shift": None,
                "shift_volume": 0,
                "average_transit_time_sec": 0.0,
                "last_angle_deg": 0.0,
                "last_event_uuid": None,
            }

        aggregates = (
            session.query(
                func.count(BoxEvent.id),
                func.avg(BoxEvent.transit_time_sec),
            )
            .filter(BoxEvent.shift == latest.shift)
            .one()
        )
        shift_volume, average_transit_time_sec = aggregates

        return {
            "current_shift": latest.shift,
            "shift_volume": int(shift_volume or 0),
            "average_transit_time_sec": round(float(average_transit_time_sec or 0.0), 2),
            "last_angle_deg": float(latest.orientation_deg or 0.0),
            "last_event_uuid": latest.uuid,
        }
    finally:
        session.close()


def get_shift_summary(limit=10, session_factory=SessionLocal):
    session = session_factory()
    try:
        rows = (
            session.query(
                BoxEvent.shift.label("shift"),
                func.count(BoxEvent.id).label("volume"),
                func.avg(BoxEvent.transit_time_sec).label("average_transit_time_sec"),
            )
            .group_by(BoxEvent.shift)
            .order_by(desc(func.max(BoxEvent.timestamp_iso)))
            .limit(limit)
            .all()
        )
        return [
            {
                "shift": row.shift,
                "volume": int(row.volume or 0),
                "average_transit_time_sec": round(float(row.average_transit_time_sec or 0.0), 2),
            }
            for row in rows
        ]
    finally:
        session.close()


def get_chart_overview(limit=50, session_factory=SessionLocal):
    session = session_factory()
    try:
        rows = (
            session.query(BoxEvent)
            .order_by(desc(BoxEvent.timestamp_iso), desc(BoxEvent.id))
            .limit(limit)
            .all()
        )
        events = [serialize_box_event(row) for row in reversed(rows)]
        orientation = [
            {
                "timestamp_iso": event["timestamp_iso"],
                "orientation_deg": event["orientation_deg"],
                "color": "#ef4444" if abs(event["orientation_deg"]) > 15 else "#10b981",
            }
            for event in events
        ]
        transit = [event["transit_time_sec"] for event in events]
        volume = [
            {
                "timestamp_iso": event["timestamp_iso"],
                "shift_count": event["shift_count"],
            }
            for event in events
        ]
        return {
            "orientation": orientation,
            "transit": transit,
            "volume": volume,
        }
    finally:
        session.close()
