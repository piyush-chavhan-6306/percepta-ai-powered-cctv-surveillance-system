"""
Multi-frame temporal aggregation for ANPR and face evidence.

A single bad frame must not determine the final plate result. For each tracked
vehicle this collector gathers plate observations over the track's life, scores
them, and exposes a best-consensus reading:

  1. Every OCR observation (text, confidence, sharpness) is stored with its
     frame number and is never overwritten.
  2. Readings are grouped by normalized text; groups are scored by
     (max confidence, occurrence count, mean confidence).
  3. The winning group is the consensus; its best single observation supplies
     the stored text and confidence.
  4. If the winner is below the acceptance threshold or seen only once with a
     weak confidence, the plate is reported as UNCERTAIN instead of guessed.

Memory is bounded: only the most recent MAX_OBSERVATIONS per track are kept.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from backend.detection.evidence_detectors import INDIAN_PLATE_PATTERN


# Character confusion pairs common in PP-OCRv3 on Indian plates
_CONFUSABLES = {
    "3": "E", "E": "3",
    "5": "S", "S": "5",
    "0": "O", "O": "0",
    "1": "I", "I": "1",
}


def normalize_plate_text(text: str) -> str:
    """Normalize OCR text for grouping: uppercase, strip spaces."""
    return text.upper().strip().replace(" ", "")


def plate_texts_similar(a: str, b: str) -> bool:
    """Check if two plate texts are confusable (differ only in known OCR swaps)."""
    if a == b:
        return True
    if len(a) != len(b):
        return False
    diffs = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            if _CONFUSABLES.get(ca) == cb or _CONFUSABLES.get(cb) == ca:
                diffs += 1
            else:
                return False
    return diffs > 0 and diffs <= 2


ACCEPT_CONFIDENCE = 0.55      # single-observation acceptance floor
CONSENSUS_CONFIDENCE = 0.45   # floor when >= MIN_CONSENSUS_HITS agree
MIN_CONSENSUS_HITS = 2
MAX_OBSERVATIONS = 12         # per track, bounded memory
SHARPNESS_NORM = 300.0        # Laplacian-variance scale for scoring


@dataclass
class PlateObservation:
    text: str
    confidence: float
    sharpness: float
    frame_number: int
    timestamp: datetime
    evidence_uri: str = ""
    vehicle_box: List[float] = field(default_factory=list)
    plate_box: List[float] = field(default_factory=list)


@dataclass
class AggregatedPlate:
    text: str
    confidence: float
    hits: int
    uncertain: bool
    reason: str
    best: PlateObservation


class PlateEvidenceCollector:
    """Per-track temporal plate-evidence store with bounded memory."""

    def __init__(self, max_tracks: int = 512) -> None:
        self._tracks: "OrderedDict[str, List[PlateObservation]]" = OrderedDict()
        self._max_tracks = max_tracks

    def add_observation(
        self,
        track_key: str,
        text: str,
        confidence: float,
        frame_number: int,
        timestamp: datetime,
        sharpness: float = 0.0,
        evidence_uri: str = "",
        vehicle_box: Optional[List[float]] = None,
        plate_box: Optional[List[float]] = None,
    ) -> None:
        if not text or confidence <= 0.0:
            return
        obs = PlateObservation(
            text=text.upper(),
            confidence=float(confidence),
            sharpness=float(sharpness),
            frame_number=int(frame_number),
            timestamp=timestamp,
            evidence_uri=evidence_uri,
            vehicle_box=list(vehicle_box or []),
            plate_box=list(plate_box or []),
        )
        lst = self._tracks.get(track_key)
        if lst is None:
            if len(self._tracks) >= self._max_tracks:
                self._tracks.popitem(last=False)  # evict oldest track
            self._tracks[track_key] = lst = []
        lst.append(obs)
        if len(lst) > MAX_OBSERVATIONS:
            del lst[: len(lst) - MAX_OBSERVATIONS]

    def get_best(self, track_key: str) -> Optional[AggregatedPlate]:
        """
        Return the consensus reading for a track, or None if nothing recorded.

        Scoring: group observations by text; score = max_conf + 0.1*hits
        (bounded by MAX_OBSERVATIONS), tie-broken by mean confidence. The best
        observation of the winning group is returned. Uncertainty is explicit:
        a lone weak reading or a below-threshold consensus is flagged, never
        silently promoted.
        """
        obs_list = self._tracks.get(track_key)
        if not obs_list:
            return None

        groups: Dict[str, List[PlateObservation]] = {}
        for o in obs_list:
            # Find existing group that matches via confusable chars
            matched = False
            for gkey in groups:
                if plate_texts_similar(gkey, o.text):
                    groups[gkey].append(o)
                    matched = True
                    break
            if not matched:
                groups.setdefault(o.text, []).append(o)

        def score(items: List[PlateObservation]) -> tuple:
            max_c = max(i.confidence for i in items)
            mean_c = sum(i.confidence for i in items) / len(items)
            return (max_c + 0.1 * min(len(items), MAX_OBSERVATIONS), mean_c)

        best_text = max(groups, key=lambda t: score(groups[t]))
        group = groups[best_text]
        # Best evidence frame: highest composite of confidence and sharpness.
        best = max(
            group,
            key=lambda o: o.confidence + 0.2 * min(o.sharpness / SHARPNESS_NORM, 1.0),
        )
        max_conf = max(i.confidence for i in group)
        hits = len(group)

        if max_conf >= ACCEPT_CONFIDENCE and (hits >= MIN_CONSENSUS_HITS or max_conf >= ACCEPT_CONFIDENCE + 0.15):
            return AggregatedPlate(
                text=best.text, confidence=round(max_conf, 4), hits=hits,
                uncertain=False, reason=f"consensus over {hits} reading(s)",
                best=best,
            )
        if max_conf >= CONSENSUS_CONFIDENCE and hits >= MIN_CONSENSUS_HITS:
            return AggregatedPlate(
                text=best.text, confidence=round(max_conf, 4), hits=hits,
                uncertain=False, reason=f"multi-frame agreement ({hits}x)",
                best=best,
            )
        return AggregatedPlate(
            text=best.text, confidence=round(max_conf, 4), hits=hits,
            uncertain=True, reason="low confidence — marked uncertain, not guessed",
            best=best,
        )

    def is_valid_format(self, text: str) -> bool:
        return bool(INDIAN_PLATE_PATTERN.match((text or "").replace(" ", "")))

    def forget(self, track_key: str) -> None:
        self._tracks.pop(track_key, None)


# Process-wide collector. Keyed by f"{camera_id}:{track_id}".
global_plate_collector = PlateEvidenceCollector()


def get_plate_collector() -> PlateEvidenceCollector:
    return global_plate_collector
