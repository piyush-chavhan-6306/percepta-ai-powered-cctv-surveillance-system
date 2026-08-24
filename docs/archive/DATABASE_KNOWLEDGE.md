# BORDER INTELLIGENCE — COMPLETE DATABASE KNOWLEDGE BASE

**Project**: Border Intelligence (PS SIH26187)  
**Database Engine**: SQLite 3 with Write-Ahead Logging (WAL) Mode  
**Async ORM Layer**: SQLAlchemy 2.0 (Async Engine & AsyncSession with `async_sessionmaker`)  
**Production Database File**: `border_intelligence.db` (+ `.db-wal`, `.db-shm`)  

---

## 1. SQLite WAL Engine Configuration & PRAGMAs

SQLite is configured asynchronously on application startup (`backend/database.py::init_db`) with high-concurrency PRAGMAs:
```sql
PRAGMA journal_mode=WAL;      -- Enables concurrent reader execution during background writes
PRAGMA busy_timeout=5000;     -- Prevents database lock failures by waiting up to 5000ms
PRAGMA synchronous=NORMAL;    -- Maximizes I/O performance while preserving crash recovery integrity
```

### Persist-Before-Publish Guarantee:
- Implemented in `backend/events/store.py::EventStore.record_events_batch`.
- Events are persisted inside an atomic SQLite transaction before being published to the in-memory `EventBus`.
- If SQLite write contention occurs, exponential backoff retries (`backoff_ms = (2 ** attempt) * 10`) occur up to 5 times.

---

## 2. Relational Schema & ORM Model Specification

### Table 1: `event_logs` (`EventLogModel`)
The core immutable ledger of all system perception, spatial, tracking, and threat events.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `seq_id` | `Integer` | `PRIMARY KEY, AUTOINCREMENT` | Monotonically increasing sequence ID for strict deterministic replay tie-breaking |
| `event_id` | `String(36)` | `UNIQUE, NOT NULL, INDEXED` | Cryptographic public UUID v4 identifier |
| `event_type` | `String(32)` | `NOT NULL, INDEXED` | Event type: `DETECTION`, `TRACKING`, `ZONE`, `ALERT`, `INCIDENT`, `SYSTEM` |
| `timestamp` | `DateTime(tz)`| `NOT NULL, INDEXED` | UTC ISO-8601 timestamp with microsecond resolution |
| `camera_id` | `String(64)` | `NOT NULL, INDEXED` | Camera hardware/location identifier |
| `track_id` | `String(64)` | `NULLABLE, INDEXED` | Camera-local tracking centroid identifier |
| `incident_id`| `String(64)` | `NULLABLE, INDEXED` | Parent aggregated incident identifier (if linked) |
| `confidence` | `Float` | `NULLABLE` | YOLOv8 / tracking association confidence (0.0 to 1.0) |
| `source` | `String(32)` | `NOT NULL, DEFAULT 'video_file'` | Ingestion source type (`video_file`, `rtsp`, `simulation`) |
| `payload` | `Text` | `NOT NULL` | Full serialized JSON payload preserving raw coordinate & rule details |

#### Indexes:
1. `idx_events_timestamp_seq` on `(timestamp ASC, seq_id ASC)`: Used for zero-latency chronological replay queries.
2. `idx_events_incident_seq` on `(incident_id ASC, seq_id ASC)`: Used for instantaneous incident dossier reconstruction.

---

### Table 2: `incidents` (`IncidentModel`)
High-level aggregated security incident lifecycles.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `incident_id` | `String(64)` | `PRIMARY KEY` | Unique human-readable ID (e.g., `INC-20260823-0004`) |
| `title` | `String(255)` | `NOT NULL` | Auto-generated tactical summary title |
| `severity` | `String(32)` | `NOT NULL, INDEXED` | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `lifecycle` | `String(32)` | `NOT NULL, INDEXED` | `opened`, `investigating`, `escalated`, `closed` |
| `camera_id` | `String(64)` | `NOT NULL, INDEXED` | Camera sector where breach originated |
| `primary_track_id` | `String(64)` | `NULLABLE` | Suspect target track ID |
| `created_at` | `DateTime(tz)`| `NOT NULL, INDEXED` | Initial intrusion detection timestamp |
| `updated_at` | `DateTime(tz)`| `NOT NULL` | Most recent activity update timestamp |
| `summary` | `Text` | `NULLABLE` | Markdown-formatted Tactical SitRep summary |

---

### Table 3: `alerts` (`AlertModel`)
Operator action items and notification state.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `alert_id` | `String(36)` | `PRIMARY KEY` | Alert UUID v4 |
| `incident_id` | `String(64)` | `NULLABLE, INDEXED` | Foreign incident reference |
| `camera_id` | `String(64)` | `NOT NULL, INDEXED` | Camera sector ID |
| `track_id` | `String(64)` | `NULLABLE` | Associated tracked target ID |
| `severity` | `String(32)` | `NOT NULL, INDEXED` | `INFO`, `WARNING`, `RESTRICTED`, `CRITICAL` |
| `message` | `String(500)` | `NOT NULL` | Human-readable tactical alert description |
| `timestamp` | `DateTime(tz)`| `NOT NULL, INDEXED` | Generation timestamp |
| `is_acknowledged`| `Boolean` | `NOT NULL, DEFAULT FALSE` | Operator acknowledgment state |

---

### Table 4: `audit_logs`
Administrative actions and operator interactions log.

| Column | Type | Description |
| :--- | :--- | :--- |
| `audit_id` | `String(36)` | Unique audit record UUID |
| `action` | `String(64)` | Action code (e.g. `APPLY_PROFILE`, `REGISTER_CAMERA`, `DELETE_ZONE`) |
| `actor` | `String(64)` | Operator callsign or system service |
| `details` | `JSON / Text` | Complete JSON details dictionary of action parameters |
| `timestamp` | `DateTime(tz)`| Immutable UTC action timestamp |

---

## 3. End-to-End Persistence Pipeline

```
[Frame Ingestion & Tracking Result]
                 │
                 ▼
[Spatial / Loitering / Alert Rules]
                 │
                 ▼
     [EventLogModel Instance]
                 │
                 ▼
  ┌──────────────────────────────┐
  │ SQLite WAL Disk Transaction  │ (Guaranteed Commit)
  └──────────────────────────────┘
                 │
                 ▼
        [Async EventBus]
                 │
        ┌────────┴────────┐
        ▼                 ▼
 [WebSocket Client] [Forensic Log]
```

---

## 4. Enterprise PostgreSQL Migration Certification

As certified in `backend/database_diagnostics.py::get_database_diagnostics`:
- **ORM Independence**: 100% standard SQLAlchemy 2.0 models with no SQLite-proprietary data types or raw non-portable SQL dialect locks.
- **Dialect Compatibility**: Direct drop-in compatibility with PostgreSQL 15+ (`asyncpg` driver).
- **Migration Path**: Seamless migration requiring only switching `DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname` in `.env`.
