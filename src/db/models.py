from sqlalchemy import Column, DateTime, Float, Integer, String, func

from .base import Base


class BoxEvent(Base):
    __tablename__ = "box_events"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(128), unique=True, nullable=False, index=True)
    yolo_session_id = Column(Integer, nullable=False, index=True)
    timestamp_iso = Column(String(64), nullable=False, index=True)
    shift = Column(String(64), nullable=False, index=True)
    shift_count = Column(Integer, nullable=False)
    transit_time_sec = Column(Float, nullable=False)
    orientation_deg = Column(Float, nullable=False)
    status = Column(String(32), nullable=False, default="COMPLETED")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
