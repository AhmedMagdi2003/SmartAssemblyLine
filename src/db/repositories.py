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


def _apply_optional_limit(query, limit):
    if limit is None:
        return query
    return query.limit(limit)


def _extract_shift_prefix(uuid_value):
    parts = str(uuid_value or "").rsplit("-", 1)
    if len(parts) != 2:
        return None
    return f"{parts[0]}-"


def _extract_shift_date(uuid_value):
    parts = str(uuid_value or "").split("-")
    if len(parts) < 4:
        return None
    encoded_date = parts[1]
    if len(encoded_date) != 8 or not encoded_date.isdigit():
        return None
    return f"{encoded_date[:4]}-{encoded_date[4:6]}-{encoded_date[6:]}"


def _apply_shift_window_filter(query, shift=None, shift_date=None):
    if shift:
        query = query.filter(BoxEvent.shift == str(shift))

    if shift_date:
        normalized_date = str(shift_date).replace("-", "")
        if shift:
            prefix = f"BOX-{normalized_date}-{shift}-%"
            query = query.filter(BoxEvent.uuid.like(prefix))
        else:
            query = query.filter(BoxEvent.uuid.like(f"BOX-{normalized_date}-%"))

    return query


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
        "shift_date": _extract_shift_date(event.uuid),
        "shift_count": event.shift_count,
        "transit_time_sec": event.transit_time_sec,
        "orientation_deg": event.orientation_deg,
        "status": event.status,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def list_recent_box_events(limit=50, shift=None, shift_date=None, session_factory=SessionLocal):
    session = session_factory()
    try:
        query = (
            session.query(BoxEvent)
            .order_by(desc(BoxEvent.timestamp_iso), desc(BoxEvent.id))
        )
        query = _apply_shift_window_filter(query, shift=shift, shift_date=shift_date)
        rows = _apply_optional_limit(query, limit).all()
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
                "shift_date": None,
                "shift_volume": 0,
                "average_transit_time_sec": 0.0,
                "last_angle_deg": 0.0,
                "last_event_uuid": None,
            }

        shift_prefix = _extract_shift_prefix(latest.uuid)
        if shift_prefix is None:
            return {
                "current_shift": latest.shift,
                "shift_date": _extract_shift_date(latest.uuid),
                "shift_volume": int(latest.shift_count or 0),
                "average_transit_time_sec": round(float(latest.transit_time_sec or 0.0), 2),
                "last_angle_deg": float(latest.orientation_deg or 0.0),
                "last_event_uuid": latest.uuid,
            }
        aggregates = (
            session.query(
                func.count(BoxEvent.id),
                func.avg(BoxEvent.transit_time_sec),
            )
            .filter(BoxEvent.uuid.like(f"{shift_prefix}%"))
            .one()
        )
        shift_volume, average_transit_time_sec = aggregates

        return {
            "current_shift": latest.shift,
            "shift_date": _extract_shift_date(latest.uuid),
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
        events = (
            session.query(BoxEvent)
            .order_by(desc(BoxEvent.timestamp_iso), desc(BoxEvent.id))
            .all()
        )

        summaries = []
        seen_prefixes = set()
        for event in events:
            shift_prefix = _extract_shift_prefix(event.uuid)
            if shift_prefix in seen_prefixes or shift_prefix is None:
                continue

            seen_prefixes.add(shift_prefix)
            aggregates = (
                session.query(
                    func.count(BoxEvent.id),
                    func.avg(BoxEvent.transit_time_sec),
                )
                .filter(BoxEvent.uuid.like(f"{shift_prefix}%"))
                .one()
            )
            volume, average_transit_time_sec = aggregates
            summaries.append(
                {
                    "shift": event.shift,
                    "shift_date": _extract_shift_date(event.uuid),
                    "volume": int(volume or 0),
                    "average_transit_time_sec": round(float(average_transit_time_sec or 0.0), 2),
                }
            )
            if limit is not None and len(summaries) >= limit:
                break

        return summaries
    finally:
        session.close()


def get_chart_overview(limit=50, shift=None, shift_date=None, session_factory=SessionLocal):
    session = session_factory()
    try:
        query = (
            session.query(BoxEvent)
            .order_by(desc(BoxEvent.timestamp_iso), desc(BoxEvent.id))
        )
        query = _apply_shift_window_filter(query, shift=shift, shift_date=shift_date)
        rows = _apply_optional_limit(query, limit).all()
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


def get_shift_event_count(shift, shift_date, session_factory=SessionLocal):
    """
    Return the highest persisted shift_count for a shift window identified by
    the operational shift date used in the UUID prefix.
    """
    session = session_factory()
    try:
        prefix = f"BOX-{shift_date.strftime('%Y%m%d')}-{shift}-%"
        latest_count = (
            session.query(func.max(BoxEvent.shift_count))
            .filter(BoxEvent.shift == shift)
            .filter(BoxEvent.uuid.like(prefix))
            .scalar()
        )
        return int(latest_count or 0)
    finally:
        session.close()
