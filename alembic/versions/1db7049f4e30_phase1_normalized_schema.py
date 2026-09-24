"""
Phase 1: Additive-only schema — create new normalized tables.

DO NOT modify existing alerts/incidents/event_logs tables.
Those will be migrated in Phase 3 with dual-write strategy.

Revision ID: 1db7049f4e30
Revises: 
Create Date: 2026-09-10 21:42:50.982760
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1db7049f4e30'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create new normalized tables. Existing tables are untouched."""

    # ── cameras (no FK deps) ──
    op.create_table(
        'cameras',
        sa.Column('camera_id', sa.String(64), primary_key=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('source_type', sa.String(32), nullable=False, server_default='video_file'),
        sa.Column('source_path', sa.String(512), nullable=False),
        sa.Column('status', sa.String(32), nullable=False, server_default='registered'),
        sa.Column('location_lat', sa.Float, nullable=True),
        sa.Column('location_lon', sa.Float, nullable=True),
        sa.Column('zone_metadata', sa.JSON, nullable=True),
        sa.Column('connected_cameras', sa.JSON, nullable=True),
        sa.Column('expected_direction', sa.String(32), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── zones (no FK deps) ──
    op.create_table(
        'zones',
        sa.Column('zone_id', sa.String(36), primary_key=True),
        sa.Column('zone_name', sa.String(128), nullable=False),
        sa.Column('zone_type', sa.String(32), nullable=False, server_default='MONITORED'),
        sa.Column('severity', sa.String(32), nullable=False, server_default='NORMAL'),
        sa.Column('polygon', sa.JSON, nullable=True),
        sa.Column('camera_ids', sa.JSON, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── global_entities (no FK deps) ──
    op.create_table(
        'global_entities',
        sa.Column('global_entity_id', sa.String(36), primary_key=True),
        sa.Column('display_id', sa.String(32), nullable=False, unique=True),
        sa.Column('entity_type', sa.String(32), nullable=False),
        sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('current_camera_id', sa.String(64), nullable=True),
        sa.Column('current_local_track_id', sa.String(64), nullable=True),
        sa.Column('status', sa.String(32), nullable=False, server_default='active'),
        sa.Column('metadata', sa.JSON, nullable=True),
    )
    op.create_index('ix_global_entities_entity_type', 'global_entities', ['entity_type'])

    # ── sessions (FK → cameras) ──
    op.create_table(
        'sessions',
        sa.Column('session_id', sa.String(36), primary_key=True),
        sa.Column('camera_id', sa.String(64), sa.ForeignKey('cameras.camera_id'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(32), nullable=False, server_default='active'),
        sa.Column('fps', sa.Float, nullable=True),
        sa.Column('resolution_w', sa.Integer, nullable=True),
        sa.Column('resolution_h', sa.Integer, nullable=True),
    )
    op.create_index('ix_sessions_camera_id', 'sessions', ['camera_id'])

    # ── local_tracks (FK → cameras, global_entities) ──
    op.create_table(
        'local_tracks',
        sa.Column('local_track_id', sa.String(64), primary_key=True),
        sa.Column('camera_id', sa.String(64), sa.ForeignKey('cameras.camera_id'), nullable=False),
        sa.Column('session_id', sa.String(36), nullable=False),
        sa.Column('global_entity_id', sa.String(36), sa.ForeignKey('global_entities.global_entity_id'), nullable=True),
        sa.Column('class_name', sa.String(32), nullable=False),
        sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False),
        sa.Column('frame_count', sa.Integer, nullable=False, server_default=sa.text('1')),
        sa.Column('trajectory', sa.JSON, nullable=True),
        sa.Column('velocity', sa.JSON, nullable=True),
        sa.Column('status', sa.String(32), nullable=False, server_default='active'),
        sa.Column('tracking_confidence', sa.Float, nullable=False, server_default=sa.text('0.0')),
        sa.Column('appearance_embedding', sa.LargeBinary, nullable=True),
    )
    op.create_index('ix_local_tracks_camera_id', 'local_tracks', ['camera_id'])
    op.create_index('ix_local_tracks_session_id', 'local_tracks', ['session_id'])
    op.create_index('ix_local_tracks_global_entity_id', 'local_tracks', ['global_entity_id'])

    # ── detections (FK → sessions) ──
    op.create_table(
        'detections',
        sa.Column('detection_id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('sessions.session_id'), nullable=False),
        sa.Column('camera_id', sa.String(64), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('frame_number', sa.Integer, nullable=False),
        sa.Column('class_name', sa.String(32), nullable=False),
        sa.Column('confidence', sa.Float, nullable=False),
        sa.Column('bbox_x1', sa.Float, nullable=False),
        sa.Column('bbox_y1', sa.Float, nullable=False),
        sa.Column('bbox_x2', sa.Float, nullable=False),
        sa.Column('bbox_y2', sa.Float, nullable=False),
        sa.Column('detector_source', sa.String(32), nullable=False, server_default='yolov8n'),
        sa.Column('local_track_id', sa.String(64), nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
    )
    op.create_index('ix_detections_session_id', 'detections', ['session_id'])
    op.create_index('ix_detections_camera_id', 'detections', ['camera_id'])
    op.create_index('ix_detections_timestamp', 'detections', ['timestamp'])
    op.create_index('ix_detections_class_name', 'detections', ['class_name'])
    op.create_index('ix_detections_local_track_id', 'detections', ['local_track_id'])
    op.create_index('idx_det_cam_time', 'detections', ['camera_id', 'timestamp'])
    op.create_index('idx_det_class', 'detections', ['class_name', 'camera_id'])

    # ── camera_transitions (FK → global_entities) ──
    op.create_table(
        'camera_transitions',
        sa.Column('transition_id', sa.String(36), primary_key=True),
        sa.Column('global_entity_id', sa.String(36), sa.ForeignKey('global_entities.global_entity_id'), nullable=False),
        sa.Column('from_camera_id', sa.String(64), nullable=False),
        sa.Column('from_local_track_id', sa.String(64), nullable=False),
        sa.Column('to_camera_id', sa.String(64), nullable=False),
        sa.Column('to_local_track_id', sa.String(64), nullable=False),
        sa.Column('association_confidence', sa.Float, nullable=False),
        sa.Column('transition_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('association_signals', sa.JSON, nullable=True),
    )
    op.create_index('ix_camera_transitions_global_entity_id', 'camera_transitions', ['global_entity_id'])

    # ── incidents (FK → global_entities, zones) ──
    # MUST be created before events (events has FK → incidents)
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

    # ── events (FK → global_entities, zones, incidents) ──
    # All FKs inline — SQLite requires FKs in CREATE TABLE, not ALTER TABLE
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

    # ── alerts (FK → incidents) ──
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

    # ── evidence (FK → incidents) ──
    op.create_table(
        'evidence',
        sa.Column('evidence_id', sa.String(36), primary_key=True),
        sa.Column('incident_id', sa.String(36), sa.ForeignKey('incidents.incident_id'), nullable=False),
        sa.Column('event_id', sa.String(36), nullable=True),
        sa.Column('global_entity_id', sa.String(36), nullable=True),
        sa.Column('local_track_id', sa.String(64), nullable=True),
        sa.Column('camera_id', sa.String(64), nullable=False),
        sa.Column('session_id', sa.String(36), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('evidence_type', sa.String(32), nullable=False),
        sa.Column('source_frame_number', sa.Integer, nullable=True),
        sa.Column('target_bbox', sa.JSON, nullable=True),
        sa.Column('target_crop_path', sa.String(512), nullable=True),
        sa.Column('full_scene_path', sa.String(512), nullable=True),
        sa.Column('confidence', sa.Float, nullable=True),
        sa.Column('quality', sa.Float, nullable=True),
        sa.Column('reason', sa.Text, nullable=True),
        sa.Column('sha256_hash', sa.String(64), nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
    )
    op.create_index('ix_evidence_incident_id', 'evidence', ['incident_id'])
    op.create_index('ix_evidence_global_entity_id', 'evidence', ['global_entity_id'])

    # ── threat_assessments (FK → incidents) ──
    op.create_table(
        'threat_assessments',
        sa.Column('assessment_id', sa.String(36), primary_key=True),
        sa.Column('incident_id', sa.String(36), sa.ForeignKey('incidents.incident_id'), nullable=False),
        sa.Column('score', sa.Float, nullable=False),
        sa.Column('severity', sa.String(32), nullable=False),
        sa.Column('factors', sa.JSON, nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('source_event_id', sa.String(36), nullable=True),
        sa.Column('explanation', sa.Text, nullable=True),
    )
    op.create_index('ix_threat_assessments_incident_id', 'threat_assessments', ['incident_id'])

    # ── face_observations (no FK deps) ──
    op.create_table(
        'face_observations',
        sa.Column('observation_id', sa.String(36), primary_key=True),
        sa.Column('camera_id', sa.String(64), nullable=False),
        sa.Column('local_track_id', sa.String(64), nullable=True),
        sa.Column('global_entity_id', sa.String(36), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('frame_number', sa.Integer, nullable=True),
        sa.Column('face_bbox', sa.JSON, nullable=True),
        sa.Column('face_crop_path', sa.String(512), nullable=True),
        sa.Column('confidence', sa.Float, nullable=False),
        sa.Column('quality_score', sa.Float, nullable=True),
        sa.Column('landmarks', sa.JSON, nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
    )
    op.create_index('ix_face_observations_camera_id', 'face_observations', ['camera_id'])
    op.create_index('ix_face_observations_local_track_id', 'face_observations', ['local_track_id'])
    op.create_index('ix_face_observations_global_entity_id', 'face_observations', ['global_entity_id'])

    # ── plate_observations (no FK deps) ──
    op.create_table(
        'plate_observations',
        sa.Column('observation_id', sa.String(36), primary_key=True),
        sa.Column('camera_id', sa.String(64), nullable=False),
        sa.Column('local_track_id', sa.String(64), nullable=True),
        sa.Column('global_entity_id', sa.String(36), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('frame_number', sa.Integer, nullable=True),
        sa.Column('plate_text', sa.String(32), nullable=True),
        sa.Column('plate_confidence', sa.Float, nullable=True),
        sa.Column('plate_uncertain', sa.Boolean, nullable=False, server_default=sa.text('1')),
        sa.Column('plate_bbox', sa.JSON, nullable=True),
        sa.Column('plate_crop_path', sa.String(512), nullable=True),
        sa.Column('vehicle_class', sa.String(32), nullable=True),
        sa.Column('consensus_hits', sa.Integer, nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
    )
    op.create_index('ix_plate_observations_camera_id', 'plate_observations', ['camera_id'])
    op.create_index('ix_plate_observations_local_track_id', 'plate_observations', ['local_track_id'])
    op.create_index('ix_plate_observations_global_entity_id', 'plate_observations', ['global_entity_id'])

    # ── weapon_observations (no FK deps) ──
    op.create_table(
        'weapon_observations',
        sa.Column('observation_id', sa.String(36), primary_key=True),
        sa.Column('camera_id', sa.String(64), nullable=False),
        sa.Column('local_track_id', sa.String(64), nullable=True),
        sa.Column('global_entity_id', sa.String(36), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('frame_number', sa.Integer, nullable=True),
        sa.Column('weapon_class', sa.String(32), nullable=True),
        sa.Column('confidence', sa.Float, nullable=False),
        sa.Column('weapon_bbox', sa.JSON, nullable=True),
        sa.Column('crop_path', sa.String(512), nullable=True),
        sa.Column('model_source', sa.String(32), nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
    )
    op.create_index('ix_weapon_observations_camera_id', 'weapon_observations', ['camera_id'])
    op.create_index('ix_weapon_observations_local_track_id', 'weapon_observations', ['local_track_id'])
    op.create_index('ix_weapon_observations_global_entity_id', 'weapon_observations', ['global_entity_id'])

    # ── ai_queries (no FK deps) ──
    op.create_table(
        'ai_queries',
        sa.Column('query_id', sa.String(36), primary_key=True),
        sa.Column('query_text', sa.Text, nullable=False),
        sa.Column('parsed_intent', sa.String(64), nullable=True),
        sa.Column('resolved_entity_ids', sa.JSON, nullable=True),
        sa.Column('response_text', sa.Text, nullable=True),
        sa.Column('response_tier', sa.String(32), nullable=True),
        sa.Column('facts', sa.JSON, nullable=True),
        sa.Column('inferences', sa.JSON, nullable=True),
        sa.Column('unknowns', sa.JSON, nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('processing_ms', sa.Float, nullable=True),
    )


def downgrade() -> None:
    """Drop new normalized tables in reverse FK order."""
    op.drop_table('ai_queries')
    op.drop_table('weapon_observations')
    op.drop_table('plate_observations')
    op.drop_table('face_observations')
    op.drop_table('threat_assessments')
    op.drop_table('evidence')
    op.drop_table('alerts')
    op.drop_table('events')
    op.drop_table('incidents')
    op.drop_table('camera_transitions')
    op.drop_table('detections')
    op.drop_table('local_tracks')
    op.drop_table('global_entities')
    op.drop_table('sessions')
    op.drop_table('zones')
    op.drop_table('cameras')
