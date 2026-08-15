from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Theater:
    id: str
    name: str
    city: str
    state: str
    chain: str
    url: str


@dataclass
class Showtime:
    theater: Theater
    date: str  # YYYY-MM-DD
    time: str  # e.g. "7:30 PM" or ISO-ish local string
    format_label: str
    purchase_url: str
    available_seats: int | None = None
    booked: bool = False
    book_message: str = ""
    discovered_at: datetime = field(default_factory=datetime.now)

    @property
    def key(self) -> str:
        return f"{self.theater.id}|{self.date}|{self.time}|{self.format_label}"

    def summary(self) -> str:
        seats = (
            f"{self.available_seats} seats"
            if self.available_seats is not None
            else "seats unknown"
        )
        status = "BOOKED — pay in browser" if self.booked else seats
        lines = [
            f"{self.theater.name} ({self.theater.city}, {self.theater.state})",
            f"  {self.date} {self.time} — {self.format_label} — {status}",
            f"  {self.purchase_url}",
        ]
        if self.book_message:
            lines.append(f"  {self.book_message}")
        return "\n".join(lines)
