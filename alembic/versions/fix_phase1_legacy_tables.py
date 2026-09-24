"""
Phase 1 fix: Drop and recreate legacy alerts/incidents/events with correct schema.

The original codebase had IncidentModel and AlertModel that were removed from
the code but their physical tables remain with legacy columns. The new normalized
Alert and Incident ORM models expect different columns. This migration:

1. Drops legacy alerts/incidents/events (all 0 rows, no code references)
2. Recreates them with correct normalized columns and FKs
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'fix_phase1_legacy_tables'
down_revision: Union[str, Sequence[str], None] = '1db7049f4e30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove legacy tables with wrong columns and recreate with correct schema."""

    # Drop in FK-dependency order: events first (references incidents, zones, global_entities)
    op.execute("DROP TABLE IF EXISTS [events]")
    op.execute("DROP TABLE IF EXISTS [alerts]")
    op.execute("DROP TABLE IF EXISTS [incidents]")

    # Recreate incidents (no FK dependencies except global_entities and zones)
    op.create_table(
        'incidents',
        sa.Column('incident_id', sa.String(36), primary_key=True),
        sa.Column('incident_type', sa.String(64), nullable=False),
        sa.Column('status', sa.String(32), nullable=False, server_default='DETECTED'),
        sa.Column('severity', sa.String(32), nullable=False, server_default='NORMAL'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('entry_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=True),
        sa.Column('exit_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Float, nullable=True),
        sa.Column('peak_threat', sa.Float, nullable=False, server_default=sa.text('0.0')),
        sa.Column('current_threat', sa.Float, nullable=False, server_default=sa.text('0.0')),
        sa.Column('primary_entity_id', sa.String(36), sa.ForeignKey('global_entities.global_entity_id'), nullable=True),
        sa.Column('primary_camera_id', sa.String(64), nullable=True),
        sa.Column('zone_id', sa.String(36), sa.ForeignKey('zones.zone_id'), nullable=True),
        sa.Column('reason', sa.Text, nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
    )
    op.create_index('ix_incidents_incident_type', 'incidents', ['incident_type'])
    op.create_index('ix_incidents_status', 'incidents', ['status'])
    op.create_index('ix_incidents_primary_entity_id', 'incidents', ['primary_entity_id'])

    # Recreate events with inline FK to incidents (SQLite requires FKs in CREATE TABLE)
    op.create_table(
        'events',
        sa.Column('event_id', sa.String(36), primary_key=True),
        sa.Column('event_type', sa.String(64), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('camera_id', sa.String(64), nullable=False),
        sa.Column('session_id', sa.String(36), nullable=True),
        sa.Column('local_track_id', sa.String(64), nullable=True),
        sa.Column('global_entity_id', sa.String(36), sa.ForeignKey('global_entities.global_entity_id'), nullable=True),
        sa.Column('zone_id', sa.String(36), sa.ForeignKey('zones.zone_id'), nullable=True),
        sa.Column('incident_id', sa.String(36), sa.ForeignKey('incidents.incident_id'), nullable=True),
        sa.Column('entity_type', sa.String(32), nullable=True),
        sa.Column('confidence', sa.Float, nullable=True),
        sa.Column('source', sa.String(32), nullable=False, server_default='pipeline'),
        sa.Column('metadata', sa.JSON, nullable=True),
        sa.Column('evidence_id', sa.String(36), nullable=True),
    )
    op.create_index('ix_events_event_type', 'events', ['event_type'])
    op.create_index('ix_events_timestamp', 'events', ['timestamp'])
    op.create_index('ix_events_camera_id', 'events', ['camera_id'])
    op.create_index('ix_events_local_track_id', 'events', ['local_track_id'])
    op.create_index('ix_events_global_entity_id', 'events', ['global_entity_id'])
    op.create_index('ix_events_zone_id', 'events', ['zone_id'])
    op.create_index('ix_events_incident_id', 'events', ['incident_id'])
    op.create_index('idx_event_cam_time', 'events', ['camera_id', 'timestamp'])
    op.create_index('idx_event_type_time', 'events', ['event_type', 'timestamp'])
    op.create_index('idx_event_incident', 'events', ['incident_id', 'timestamp'])

    # Recreate alerts with inline FK to incidents
    op.create_table(
        'alerts',
        sa.Column('alert_id', sa.String(36), primary_key=True),
        sa.Column('incident_id', sa.String(36), sa.ForeignKey('incidents.incident_id'), nullable=False),
        sa.Column('operator_severity', sa.String(32), nullable=False, server_default='INFORMATIONAL'),
        sa.Column('operator_status', sa.String(32), nullable=False, server_default='ACTIVE'),
        sa.Column('message', sa.Text, nullable=True),
        sa.Column('is_acknowledged', sa.Boolean, nullable=False, server_default=sa.text('0')),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_by', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_alerts_incident_id', 'alerts', ['incident_id'])


def downgrade() -> None:
    """Restore legacy tables."""
    op.drop_table('alerts')
    op.drop_table('events')
    op.drop_table('incidents')

    # Recreate legacy incidents
    op.create_table(
        'incidents',
        sa.Column('incident_id', sa.String(64), primary_key=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('severity', sa.String(32), nullable=False, server_default='LOW', index=True),
        sa.Column('lifecycle', sa.String(32), nullable=False, server_default='opened', index=True),
        sa.Column('camera_id', sa.String(64), nullable=False, index=True),
        sa.Column('primary_track_id', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('summary', sa.Text, nullable=True),
    )

    # Recreate legacy alerts
    op.create_table(
        'alerts',
        sa.Column('alert_id', sa.String(36), primary_key=True),
        sa.Column('incident_id', sa.String(64), nullable=True, index=True),
        sa.Column('camera_id', sa.String(64), nullable=False, index=True),
        sa.Column('track_id', sa.String(64), nullable=True),
        sa.Column('severity', sa.String(32), nullable=False, index=True),
        sa.Column('message', sa.String(500), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('is_acknowledged', sa.Boolean, nullable=False, server_default=sa.text('0')),
    )

    # Recreate legacy events
    op.create_table(
        'events',
        sa.Column('event_id', sa.String(36), primary_key=True),
        sa.Column('event_type', sa.String(32), nullable=False, index=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('camera_id', sa.String(64), nullable=False, index=True),
        sa.Column('session_id', sa.String(36), nullable=True),
        sa.Column('local_track_id', sa.String(64), nullable=True),
        sa.Column('global_entity_id', sa.String(36), nullable=True),
        sa.Column('zone_id', sa.String(36), nullable=True),
        sa.Column('incident_id', sa.String(36), nullable=True),
        sa.Column('entity_type', sa.String(32), nullable=True),
        sa.Column('confidence', sa.Float, nullable=True),
        sa.Column('source', sa.String(32), nullable=False, server_default='pipeline'),
        sa.Column('metadata', sa.JSON, nullable=True),
        sa.Column('evidence_id', sa.String(36), nullable=True),
    )
