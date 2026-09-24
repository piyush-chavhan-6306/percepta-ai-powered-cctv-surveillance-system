"""
Unit tests for Phase 21: Grounded Defense AI.
Verifies:
- Grounded database queries for global entities and trajectories.
- 3-tier standard output: [FACT], [INFERENCE], [UNKNOWN].
- Honest handling of missing information (no hallucination).
- Anti-hallucination guardrails against claiming subjective intent or biometric identity.
"""
import pytest
from datetime import datetime, timezone
from backend.database import init_db
from backend.entities.service import get_entity_manager
from backend.intelligence.assistant import SurveillanceAssistant


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_db()


@pytest.mark.anyio
async def test_grounded_ai_global_entity_lookup():
    """Test Grounded Defense AI answers for global entity trajectory."""
    ent_mgr = get_entity_manager()
    # Create entity
    ent = await ent_mgr.create_entity(
        entity_type="person",
        camera_id="CAM-01",
        local_track_id="P-042",
        display_id_override="GLOBAL-PERSON-042",
    )
    # Hop to CAM-02
    await ent_mgr.associate_local_track(
        global_entity_id=ent.global_entity_id,
        camera_id="CAM-02",
        local_track_id="P-104",
        confidence=0.88,
    )

    assistant = SurveillanceAssistant()
    res = await assistant.answer_query("Where was PERSON-042 last seen?")

    assert res.status == "answered"
    assert res.grounding_status == "grounded"
    assert any("GLOBAL-PERSON-042" in f for f in res.observed_facts)
    assert any("CAM-02" in f for f in res.observed_facts)
    assert len(res.unknowns) >= 1  # Highlights intent/biometrics as UNKNOWN
    formatted = res.formatted_text()
    assert "[FACT]" in formatted
    assert "[UNKNOWN]" in formatted


@pytest.mark.anyio
async def test_grounded_ai_missing_entity_produces_unknown():
    """Test that querying a non-existent entity never hallucinates."""
    assistant = SurveillanceAssistant()
    res = await assistant.answer_query("Where was PERSON-999 last seen?")

    assert res.status == "no_records_found"
    assert res.grounding_status == "no_data"
    assert len(res.observed_facts) == 0
    assert any("not observed or registered" in res.interpretation or "No entity matching" in u for u in res.unknowns)


@pytest.mark.anyio
async def test_grounded_ai_refuses_subjective_intent():
    """Test refusal to claim knowledge of human/criminal intent."""
    assistant = SurveillanceAssistant()
    res = await assistant.answer_query("What is PERSON-042 planning to attack?")

    assert res.status == "unsupported_capability"
    assert res.grounding_status == "refusal"
    assert "Subjective human intent or criminal intent cannot be established" in res.interpretation
