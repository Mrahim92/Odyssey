from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path


class StateStore:
    """Tracks alerted showtimes and cached seat-check results."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._seen: dict[str, str] = {}
        self._seat_cache: dict[str, dict[str, int | str]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._seen = data.get("seen", {})
            self._seat_cache = data.get("seat_cache", {})
        except (json.JSONDecodeError, OSError):
            self._seen = {}
            self._seat_cache = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now().isoformat(),
            "seen": self._seen,
            "seat_cache": self._seat_cache,
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def is_new(self, key: str) -> bool:
        return key not in self._seen

    def mark_seen(self, key: str) -> None:
        self._seen[key] = datetime.now().isoformat()

    def get_cached_seats(
        self, url: str, min_seats: int, ttl_minutes: int
    ) -> int | None:
        """Return cached count if recently checked and still below alert threshold."""
        entry = self._seat_cache.get(url)
        if not entry:
            return None
        try:
            checked_at = datetime.fromisoformat(str(entry["checked_at"]))
            seats = int(entry["seats"])
        except (KeyError, TypeError, ValueError):
            return None
        if datetime.now() - checked_at > timedelta(minutes=ttl_minutes):
            return None
        # Re-check showtimes that previously had enough seats — inventory changes fast.
        if seats >= min_seats:
            return None
        return seats

    def cache_seats(self, url: str, seats: int) -> None:
        self._seat_cache[url] = {
            "seats": seats,
            "checked_at": datetime.now().isoformat(),
        }

    def clear(self) -> None:
        self._seen = {}
        self._seat_cache = {}
        self.save()
