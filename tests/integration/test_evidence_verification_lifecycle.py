"""
End-to-End Cryptographic Evidence Verification Test Suite.
Tests:
  - Test A: Unmodified evidence file matches recorded SHA-256 digest -> VERIFIED
  - Test B: Tampered bytes in physical evidence file detected -> COMPROMISED
  - Test C: Deleted/missing physical evidence file detected -> MISSING
"""
import hashlib
import os
import uuid
import pytest
from pathlib import Path
from httpx import ASGITransport, AsyncClient

from backend.main import create_app
from backend.database import get_session_factory, init_db
from backend.database.schema import Evidence, Incident
from backend.config import get_settings


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


@pytest.mark.asyncio
async def test_cryptographic_evidence_verification_lifecycle():
    app = create_app()
    transport = ASGITransport(app=app)
    settings = get_settings()
    snap_dir = Path(settings.STORAGE_DIR) / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)

    test_token = uuid.uuid4().hex[:8]
    evidence_id = f"ev_test_{test_token}"
    incident_id = f"INC_TEST_{test_token}"
    test_file = snap_dir / f"test_crop_{test_token}.jpg"

    # Create dummy image bytes
    original_bytes = b"JPEG_FORENSIC_RAW_BYTES_PERCEPTA_TEST_DATA_" + test_token.encode("utf-8")
    test_file.write_bytes(original_bytes)
    original_hash = hashlib.sha256(original_bytes).hexdigest()

    factory = get_session_factory()
    async with factory() as session:
        inc = Incident(
            incident_id=incident_id,
            incident_type="SECURITY_BREACH",
            primary_camera_id="CAM-01",
            status="OPEN",
            severity="CRITICAL",
            peak_threat=85.0,
            current_threat=85.0,
            reason="Forensic cryptographic verification test incident",
        )
        session.add(inc)

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        ev = Evidence(
            evidence_id=evidence_id,
            incident_id=incident_id,
            camera_id="CAM-01",
            evidence_type="target_crop",
            target_crop_path=str(test_file),
            sha256_hash=original_hash,
            confidence=0.95,
            quality=1.0,
            timestamp=now,
            reason="Perimeter breach target crop",
        )
        session.add(ev)
        await session.commit()

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # ── Test A: Untampered evidence -> VERIFIED ──
        res_a = await client.get(f"/api/evidence/verify-record/{evidence_id}")
        assert res_a.status_code == 200
        data_a = res_a.json()
        assert data_a["verification_status"] == "VERIFIED"
        assert data_a["computed_hash"] == original_hash
        assert data_a["file_exists"] is True
        assert data_a["file_bytes_checked"] == len(original_bytes)

        # ── Test B: Tampered bytes -> COMPROMISED ──
        tampered_bytes = original_bytes + b"_TAMPERED_BYTE_PAYLOAD"
        test_file.write_bytes(tampered_bytes)
        tampered_hash = hashlib.sha256(tampered_bytes).hexdigest()

        res_b = await client.get(f"/api/evidence/verify-record/{evidence_id}")
        assert res_b.status_code == 200
        data_b = res_b.json()
        assert data_b["verification_status"] == "COMPROMISED"
        assert data_b["computed_hash"] == tampered_hash
        assert data_b["stored_hash"] == original_hash
        assert data_b["computed_hash"] != data_b["stored_hash"]

        # ── Test C: Deleted physical evidence file -> MISSING ──
        if test_file.exists():
            test_file.unlink()

        res_c = await client.get(f"/api/evidence/verify-record/{evidence_id}")
        assert res_c.status_code == 200
        data_c = res_c.json()
        assert data_c["verification_status"] == "MISSING"
        assert data_c["file_exists"] is False

    # Cleanup DB test rows
    async with factory() as session:
        db_ev = await session.get(Evidence, evidence_id)
        if db_ev:
            await session.delete(db_ev)
        db_inc = await session.get(Incident, incident_id)
        if db_inc:
            await session.delete(db_inc)
        await session.commit()
