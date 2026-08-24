# BORDER INTELLIGENCE — COMPLETE TEST COVERAGE MATRIX

**Project**: Border Intelligence (PS SIH26187)  
**Total Verified Tests**: 🟢 **130 / 130 Automated Tests Passing (100% Green)**  
**Test Categories**: Unit Tests (36 modules), Integration Tests (1 module), Failure Tests (5 modules)  

---

## 1. Test Suite Verification Overview

```
Total Test Files: 42 Files
Total Test Cases: 130 Test Cases
Execution Time: ~16-19s
Pass Rate: 100% (130 Passed, 0 Failed, 0 Skipped)
```

---

## 2. Production Module to Test Case Mapping

### 1. Ingestion & Camera Management
| Production Module | Test File Path | Test Cases Verified | Verified Behavior |
| :--- | :--- | :--- | :--- |
| `backend/ingestion/frame_buffer.py` | `tests/unit/test_ingestion.py` | `test_frame_buffer_bounded_capacity_and_slicing` | Ring buffer FIFO eviction, capacity bounds |
| `backend/ingestion/video_adapter.py` | `tests/unit/test_ingestion.py` | `test_video_file_adapter` | OpenCV video decoding, FPS pacing |
| `backend/ingestion/simulation_adapter.py`| `tests/unit/test_ingestion.py` | `test_simulation_adapter` | Synthetic frame generation, coordinate accuracy |
| `backend/ingestion/rtsp_adapter.py` | `tests/unit/test_rtsp_adapter.py` | `test_sanitize_rtsp_url`, `test_rtsp_adapter_initialization_and_info`, `test_rtsp_adapter_empty_url_raises` | Password sanitization, connection handling |
| `backend/ingestion/camera_manager.py` | `tests/unit/test_camera_manager.py` | `test_camera_manager_registration_and_list`, `test_camera_manager_unknown_camera_handling`, `test_camera_manager_stop_all` | Camera registration, state transitions, teardown |
| `backend/ingestion/camera_manager.py` | `tests/unit/test_camera_reconnect.py`| `test_camera_reconnect_success_after_retry`, `test_camera_reconnect_fails_after_max_retries`, `test_camera_reconnect_unknown_camera` | Exponential backoff retry, max retry handling |
| `backend/ingestion/optical_diagnostics.py`| `tests/unit/test_optical_diagnostics.py`| `test_evaluate_optical_quality_nominal`, `test_evaluate_optical_quality_blurred_occluded`, `test_evaluate_optical_quality_blinding_glare`, `test_evaluate_optical_quality_blackout`, `test_camera_diagnostics_rest_api` | Laplacian focus, glare ratio, blackout detection |

### 2. Detection & Hardware Fallback
| Production Module | Test File Path | Test Cases Verified | Verified Behavior |
| :--- | :--- | :--- | :--- |
| `backend/detection/model_loader.py` | `tests/unit/test_detection.py` | `test_model_loader_path_and_caching` | Model cache resolution, path validation |
| `backend/detection/model_loader.py` | `tests/unit/test_hardware_detection.py`| `test_detect_hardware_device_cpu_explicit`, `test_detect_hardware_device_cuda_fallback_when_unavailable`, `test_detect_hardware_device_cuda_when_available`, `test_detect_hardware_device_handles_exception_safely` | Device selection, CUDA auto-detection, CPU fallback |
| `backend/detection/detector.py` | `tests/unit/test_detection.py` | `test_detector_zero_detection_on_blank_frame`, `test_detector_detects_real_surveillance_objects`, `test_detector_frame_integration_and_event_emission` | Zero detection on blank frame, real object detection |

### 3. Tracking & Motion Prediction
| Production Module | Test File Path | Test Cases Verified | Verified Behavior |
| :--- | :--- | :--- | :--- |
| `backend/tracking/tracker.py` | `tests/unit/test_tracking.py` | `test_tracker_initialization`, `test_single_object_tracking_and_center_calculation`, `test_multiple_object_tracking`, `test_track_id_persistence_across_consecutive_frames`, `test_tracker_reset`, `test_bounded_trajectory_history`, `test_movement_vector_calculation`, `test_cardinal_headings`, `test_track_termination_after_track_buffer_expiry` | Centroid calculation, persistent IDs, track buffer |
| `backend/tracking/movement.py` | `tests/unit/test_tracker_prediction.py`| `test_tracker_predict_step_advances_coordinates`, `test_pipeline_intermediate_prediction_emits_zero_fake_detections` | Kalman intermediate step, coordinate advance |
| `backend/tracking/pipeline.py` | `tests/unit/test_adaptive_stride.py` | `test_adaptive_stride_increases_under_heavy_load`, `test_adaptive_stride_decreases_when_performance_recovers`, `test_stride_cooldown_prevents_rapid_oscillation`, `test_bytetrack_state_preserved_during_skipped_frames`, `test_watchdog_metrics_reporting` | Dynamic stride scaling, state preservation |
| `backend/tracking/pipeline.py` | `tests/unit/test_pipeline_metrics.py`| `test_tracking_pipeline_metrics_and_telemetry`, `test_tracking_pipeline_frame_stride_skipping` | Metrics watchdog, skipped frame tracking |
| `backend/tracking/pipeline.py` | `tests/integration/test_tracking_pipeline.py`| `test_full_pipeline_yolo_to_bytetrack_to_eventstore_to_replay` | Full end-to-end integration across all subsystems |

### 4. Spatial Perimeter & Security Zones
| Production Module | Test File Path | Test Cases Verified | Verified Behavior |
| :--- | :--- | :--- | :--- |
| `backend/zones/security_zone.py` | `tests/unit/test_zones.py` | `test_polygon_security_zone_containment`, `test_virtual_boundary_line_crossing`, `test_zone_monitor_entry_dwelling_and_exit_transitions`, `test_zone_monitor_virtual_boundary_crossing_event` | Ray casting polygon containment, line segment crossing |
| `backend/zones/security_zone.py` | `tests/unit/test_loitering.py` | `test_short_presence_generates_zero_loitering_alerts`, `test_exceeding_loitering_threshold_triggers_alert_and_debounces`, `test_zone_exit_and_reentry_resets_dwell_timer` | Loitering threshold triggers, debounce timers |
| `backend/zones/templates.py` | `tests/unit/test_zone_templates.py` | `test_list_and_apply_tactical_templates`, `test_zone_templates_rest_api` | Tactical defense preset deployment |
| `backend/zones/heatmap.py` | `tests/unit/test_heatmap.py` | `test_spatial_heatmap_density_computation`, `test_spatial_heatmap_rest_api` | 16x16 spatial density matrix computation |
| `backend/api/zones.py` | `tests/unit/test_zones_api.py` | `test_zones_and_boundaries_crud_api`, `test_alert_acknowledgement_and_incidents_list_api` | Zones REST CRUD, tripwires, alert acknowledgment |

### 5. Persistence, EventBus & Forensics
| Production Module | Test File Path | Test Cases Verified | Verified Behavior |
| :--- | :--- | :--- | :--- |
| `backend/events/schema.py` | `tests/unit/test_events.py` | `test_all_event_schemas_serialize_deserialize` | Pydantic model serialization & validation |
| `backend/events/bus.py` | `tests/unit/test_events.py` | `test_event_bus_pub_sub_and_isolation` | Async subscriber queue isolation |
| `backend/events/store.py` | `tests/unit/test_events.py` | `test_persist_before_publish_contract`, `test_deterministic_replay_ordering_with_tie_breaker`, `test_fastapi_health_and_replay_endpoints` | Persist-before-publish contract, deterministic ordering |
| `backend/events/forensics.py` | `tests/unit/test_forensics.py` | `test_compute_event_hash_deterministic`, `test_forensics_rest_api_verify_and_audit` | SHA-256 token verification, chain of custody audit |
| `backend/events/snapshots.py` | `tests/unit/test_evidence_snapshots.py`| `test_save_and_list_incident_snapshots`, `test_evidence_snapshots_rest_api` | Snapshot disk writing, path resolution |
| `backend/events/audit_logger.py` | `tests/unit/test_audit_logger.py` | `test_audit_logger_workflow`, `test_audit_logs_rest_api` | Administrative system action auditing |
| `backend/api/export.py` | `tests/unit/test_event_export.py` | `test_event_export_json_and_csv_rest_api` | RFC 4180 CSV / JSON exporter |

### 6. Incidents, Threat & Intelligence
| Production Module | Test File Path | Test Cases Verified | Verified Behavior |
| :--- | :--- | :--- | :--- |
| `backend/incidents/dossier.py` | `tests/unit/test_incident_dossier.py`| `test_incident_dossier_compilation_and_rest_api` | SitRep dossier generation, motion vectors |
| `backend/incidents/annotations.py`| `tests/unit/test_incident_annotations.py`| `test_operator_annotations_workflow`, `test_operator_annotations_rest_api` | Duty officer notes & QRF disposition |
| `backend/intelligence/threat_engine.py`| `tests/unit/test_threat_engine.py` | `test_threat_engine_levels_and_scoring`, `test_threat_level_rest_api` | DEFCON 1-4 scoring matrix, contributing factors |
| `backend/intelligence/assistant.py`| `tests/unit/test_intelligence_assistant.py`| `test_track_entry_query_grounded`, `test_track_exit_query_grounded`, `test_track_dwell_duration_query_grounded`, `test_track_movement_direction_query_grounded`, `test_alert_explanation_query`, `test_boundary_crossing_query`, `test_highest_risk_evidence_query`, `test_missing_track_produces_no_hallucination`, `test_biometric_identity_query_refused`, `test_weapon_presence_query_refused`, `test_subjective_intent_query_refused`, `test_cross_camera_identity_query_refused`, `test_sql_injection_attempt_safely_rejected`, `test_fastapi_intelligence_endpoint` | 3-tier grounded answers, refusal guardrails, SQL injection protection |

### 7. Multi-Modal Sensors & System Health
| Production Module | Test File Path | Test Cases Verified | Verified Behavior |
| :--- | :--- | :--- | :--- |
| `backend/sensors/multi_modal.py` | `tests/unit/test_multi_modal_sensors.py`| `test_sensor_manager_initial_registry`, `test_sensor_ingest_and_status_rest_api` | Multi-modal registry, radar/seismic ingestion |
| `backend/database_diagnostics.py`| `tests/unit/test_database_diagnostics.py`| `test_database_diagnostics_direct`, `test_database_diagnostics_rest_api` | SQLite storage health, PostgreSQL readiness |
| `backend/config_profiles.py` | `tests/unit/test_config_profiles.py` | `test_operational_profiles_switching`, `test_operational_profiles_rest_api` | Environmental sensitivity profile switcher |
| `backend/api/system.py` | `tests/unit/test_coverage_analytics.py`| `test_coverage_report_rest_api` | Fleet coverage & readiness report |
| `backend/api/streaming.py` | `tests/unit/test_streaming.py` | `test_websocket_events_endpoint_and_broadcast`, `test_mjpeg_video_stream_endpoint`, `test_mjpeg_stream_nonexistent_camera_returns_404` | WebSocket broadcast, MJPEG streaming |
| `backend/api/streaming.py` | `tests/unit/test_websocket_hardening.py`| `test_websocket_max_clients_limit`, `test_websocket_slow_client_pruned_on_broadcast_timeout` | Client limits, slow client pruning |
| `backend/config.py` | `tests/unit/test_production_config.py`| `test_settings_cors_origins_and_version` | Production config validation |
| All Subsystems | `tests/unit/test_exhaustive_verification.py`| `test_route_enumeration_and_invalid_inputs`, `test_concurrency_and_stress_persistence`, `test_database_restart_and_persistence_recovery`, `test_credential_leakage_and_security_refusal`, `test_event_ordering_and_deterministic_sequence` | 50-worker concurrency stress, DB restart recovery, credential leakage refusal |

### 8. Failure & Fault-Tolerance Tests (`tests/failure/`)
| Failure Scenario | Test File Path | Verified Resilience Mechanism |
| :--- | :--- | :--- |
| **Corrupt Video Stream** | `tests/failure/test_corrupt_video.py` | Graceful frame skip, zero pipeline crash |
| **Detection Failure** | `tests/failure/test_detection_failure.py` | Fallback to intermediate Kalman prediction |
| **Multi-Camera Fault Isolation**| `tests/failure/test_multicamera_fault_isolation.py`| Crashing camera feed does not affect peer feeds |
| **Ingestion Pipeline Failures** | `tests/failure/test_phase1_failure.py` | Bounded buffer overflow protection |
| **Tracking Pipeline Failures** | `tests/failure/test_tracking_failure.py` | Re-association after transient track loss |
