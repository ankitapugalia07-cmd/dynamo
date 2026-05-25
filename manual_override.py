"""Manual pause locks — weather automation must not override these until they expire."""

from datetime import datetime, timezone, timedelta

TIMED_PAUSE_DURATIONS = {
    "(1 hr)": timedelta(hours=1),
    "(3 hrs)": timedelta(hours=3),
}


def _changed_at(item) -> datetime | None:
    raw = item.get("last_changed_at")
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def is_manual_weather_lock(item, now: datetime | None = None) -> bool:
    """
    Return True if weather / rule automation must not change this line item.

    Locks apply to manual pauses (timed or until resume), bulk pause-all,
    and emergency pauses. Timed locks expire after 1 hr / 3 hrs from last_changed_at.
    """
    now = now or datetime.now(timezone.utc)
    reason = item.get("state_reason") or ""
    lower = reason.lower()

    if not any(k in lower for k in ("manual pause", "bulk pause", "emergency")):
        return False

    if "until resume" in lower or "bulk pause" in lower or "emergency" in lower:
        return True

    for label, duration in TIMED_PAUSE_DURATIONS.items():
        if label in reason:
            changed = _changed_at(item)
            if changed is None:
                return True
            return now < changed + duration

    if "manual pause" in lower:
        return True

    return False
