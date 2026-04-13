"""create box events table

Revision ID: 20260412_0001
Revises: 
Create Date: 2026-04-12 23:55:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260412_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "box_events",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("uuid", sa.String(length=128), nullable=False),
        sa.Column("yolo_session_id", sa.Integer(), nullable=False),
        sa.Column("timestamp_iso", sa.String(length=64), nullable=False),
        sa.Column("shift", sa.String(length=64), nullable=False),
        sa.Column("shift_count", sa.Integer(), nullable=False),
        sa.Column("transit_time_sec", sa.Float(), nullable=False),
        sa.Column("orientation_deg", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_box_events_id", "box_events", ["id"], unique=False)
    op.create_index("ix_box_events_shift", "box_events", ["shift"], unique=False)
    op.create_index("ix_box_events_timestamp_iso", "box_events", ["timestamp_iso"], unique=False)
    op.create_index("ix_box_events_uuid", "box_events", ["uuid"], unique=True)
    op.create_index("ix_box_events_yolo_session_id", "box_events", ["yolo_session_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_box_events_yolo_session_id", table_name="box_events")
    op.drop_index("ix_box_events_uuid", table_name="box_events")
    op.drop_index("ix_box_events_timestamp_iso", table_name="box_events")
    op.drop_index("ix_box_events_shift", table_name="box_events")
    op.drop_index("ix_box_events_id", table_name="box_events")
    op.drop_table("box_events")
