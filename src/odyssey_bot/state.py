from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class StateStore:
    """Tracks showtimes we've already alerted on."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._seen: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._seen = data.get("seen", {})
        except (json.JSONDecodeError, OSError):
            self._seen = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now().isoformat(),
            "seen": self._seen,
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def is_new(self, key: str) -> bool:
        return key not in self._seen

    def mark_seen(self, key: str) -> None:
        self._seen[key] = datetime.now().isoformat()

    def clear(self) -> None:
        self._seen = {}
        self.save()
