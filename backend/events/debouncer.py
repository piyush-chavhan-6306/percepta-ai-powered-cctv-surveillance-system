"""
PERCEPTA Defense — Event Debouncer.

Prevents event flooding by enforcing minimum intervals between equivalent events.
General-purpose debounce for any event type, keyed by (event_type, camera_id, track_id, zone_id).
"""
import time
from typing import Dict, Optional, Tuple


class EventDebouncer:
    """
    General-purpose event debouncer.

    Tracks the last emit time per (event_type, camera_id, track_id, zone_id) key
    and suppresses duplicate events within the debounce window.
    """

    def __init__(self, default_window_s: float = 5.0) -> None:
        self._last_emit: Dict[str, float] = {}
        self._windows: Dict[str, float] = {}
        self.default_window_s = default_window_s

    def _make_key(
        self,
        event_type: str,
        camera_id: str,
        track_id: Optional[str] = None,
        zone_id: Optional[str] = None,
    ) -> str:
        return f"{event_type}:{camera_id}:{track_id or ''}:{zone_id or ''}"

    def should_emit(
        self,
        event_type: str,
        camera_id: str,
        track_id: Optional[str] = None,
        zone_id: Optional[str] = None,
        window_s: Optional[float] = None,
    ) -> bool:
        """
        Returns True if the event should be emitted (not debounced).
        Automatically records the emission time on True.
        """
        key = self._make_key(event_type, camera_id, track_id, zone_id)
        now = time.time()
        window = window_s if window_s is not None else self._windows.get(key, self.default_window_s)
        last = self._last_emit.get(key)
        if last is not None and (now - last) < window:
            return False
        self._last_emit[key] = now
        return True

    def set_window(self, event_type: str, camera_id: str, window_s: float,
                   track_id: Optional[str] = None, zone_id: Optional[str] = None) -> None:
        """Set a custom debounce window for a specific event key."""
        key = self._make_key(event_type, camera_id, track_id, zone_id)
        self._windows[key] = window_s

    def clear(self) -> None:
        """Reset all debounce state."""
        self._last_emit.clear()
        self._windows.clear()

    def cleanup_stale(self, max_age_s: float = 3600.0) -> int:
        """Remove entries older than max_age_s. Returns count removed."""
        now = time.time()
        stale = [k for k, t in self._last_emit.items() if (now - t) > max_age_s]
        for k in stale:
            del self._last_emit[k]
            self._windows.pop(k, None)
        return len(stale)


_global_debouncer: Optional[EventDebouncer] = None


def get_event_debouncer() -> EventDebouncer:
    global _global_debouncer
    if _global_debouncer is None:
        _global_debouncer = EventDebouncer()
    return _global_debouncer
