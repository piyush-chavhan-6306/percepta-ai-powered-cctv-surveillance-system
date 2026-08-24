# BORDER INTELLIGENCE — COMPLETE SECURITY KNOWLEDGE BASE

**Project**: Border Intelligence (PS SIH26187)  
**Security Posture**: Zero-Trust Defensive C2 Architecture  
**Verification Status**: 🟢 100% Verified against Automated Security & Injection Tests  

---

## 1. Security Boundaries & Safeguards Matrix

| Security Guardrail | Implementation Location | Mechanism & Architecture | Verifying Automated Test |
| :--- | :--- | :--- | :--- |
| **RTSP Credential Masking** | `backend/ingestion/rtsp_adapter.py::sanitize_rtsp_url` | Regex extraction of basic-auth credentials (`rtsp://user:pass@host` → `rtsp://***:***@host`). Passwords are never logged or returned over API. | `tests/unit/test_rtsp_adapter.py::test_sanitize_rtsp_url`, `tests/unit/test_exhaustive_verification.py` |
| **SQL Parameterization** | `backend/intelligence/assistant.py::ControlledQueryLayer` | Strictly uses SQLAlchemy parameterized ORM queries (`select(EventLogModel).where(...)`). Zero raw string interpolation. | `tests/unit/test_exhaustive_verification.py::test_credential_leakage_and_security_refusal` |
| **SQL Injection Rejection** | `backend/intelligence/assistant.py::_check_anti_hallucination_guardrails` | Regex keyword scanner detects `SELECT *`, `DROP TABLE`, `UNION SELECT`, `INSERT INTO` in NL queries and returns immediate refusal with `status="invalid_query"`. | `tests/unit/test_intelligence_assistant.py::test_sql_injection_attempt_safely_rejected` |
| **Biometric Refusal** | `backend/intelligence/assistant.py` | Detects facial recognition / person identity requests and refuses with explanation that CCTV centroids do not provide biometrics. | `tests/unit/test_intelligence_assistant.py::test_biometric_identity_query_refused` |
| **Weapon Claim Refusal** | `backend/intelligence/assistant.py` | Detects weapon/firearm queries and refuses, clarifying YOLOv8n is configured for general perimeter classes only. | `tests/unit/test_intelligence_assistant.py::test_weapon_presence_query_refused` |
| **Subjective Intent Refusal**| `backend/intelligence/assistant.py` | Refuses questions speculating on human mental intent or suspicious motives, restricting output to deterministic spatial rules. | `tests/unit/test_intelligence_assistant.py::test_subjective_intent_query_refused` |
| **Cross-Camera Identity Refusal**| `backend/intelligence/assistant.py` | Refuses cross-camera re-ID questions, explicitly enforcing the camera-local track identity boundary. | `tests/unit/test_intelligence_assistant.py::test_cross_camera_identity_query_refused` |
| **Persist-Before-Publish** | `backend/events/store.py` | Atomically commits event batch to SQLite WAL prior to dispatching across in-memory EventBus or WebSocket streams. | `tests/unit/test_events.py::test_persist_before_publish_contract` |
| **Cryptographic SHA-256 Token** | `backend/events/forensics.py` | Computes deterministic SHA-256 token across `(seq_id, event_id, timestamp, camera_id, event_type, payload)` for tamper detection. | `tests/unit/test_forensics.py::test_compute_event_hash_deterministic` |
| **WebSocket Client Limits**| `backend/api/streaming.py` | Enforces `MAX_WEBSOCKET_CLIENTS = 50` limit, refusing connections beyond threshold with HTTP 1008 policy violation. | `tests/unit/test_websocket_hardening.py::test_websocket_max_clients_limit` |
| **Slow Client Pruning** | `backend/events/bus.py` | 1.0s timeout per client queue. Stalled or unresponsive WebSocket consumers are disconnected without blocking the pipeline. | `tests/unit/test_websocket_hardening.py::test_websocket_slow_client_pruned_on_broadcast_timeout` |
| **Snapshot Path Traversal**| `backend/events/snapshots.py` | Validates snapshot filenames using `Path(filename).name` and resolves strictly within `storage/snapshots/` directory. | `tests/unit/test_evidence_snapshots.py::test_evidence_snapshots_rest_api` |

---

## 2. Explainable 3-Tier Grounded Output Model

To prevent operator confusion and eliminate LLM hallucinations during high-stakes border operations, the AI Assistant architecture enforces strict separation across 3 output tiers:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        3-TIER GROUNDED INTELLIGENCE RESPONSE                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [TIER 1: OBSERVED FACTS]                                                               │
│ Immutable facts retrieved directly from SQLite WAL disk records (e.g. centroid entered │
│ polygon at 10:15:02 UTC with 0.94 confidence).                                         │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [TIER 2: DETERMINISTIC RULE RESULTS]                                                   │
│ Exact rule results evaluated by deterministic code (e.g. loitering timer exceeded 1.5s,│
│ tripwire line crossed from North to South).                                            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [TIER 3: AI INTERPRETATION / SUMMARY]                                                  │
│ High-level plain text synthesis clearly labeled as derived summary, explicitly never  │
│ presented as raw ground truth.                                                         │
└────────────────────────────────────────────────────────────────────────────────────────┘
```
