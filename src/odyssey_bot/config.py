from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from .models import Theater


ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Config:
    movie_title_match: list[str]
    amc_movie_name: str
    amc_format_name: str
    alert_label: str
    format_match: list[str]
    days_ahead: int
    start_date: date | None
    end_date: date | None
    onsale_at: datetime | None
    poll_interval_seconds: int
    poll_interval_fast_seconds: int
    onsale_poll_interval_seconds: int
    concurrency: int
    headless: bool
    page_timeout_seconds: int
    seat_check_delay_seconds: float
    seat_cache_ttl_minutes: int
    min_seats: int
    preferred_rows: list[str]
    theater_ids: list[str]
    earliest_time: str
    latest_time: str
    auto_open: bool
    auto_book: bool
    stop_before_payment: bool
    notify_console: bool
    notify_desktop: bool
    discord_webhook: str
    notify_sound: bool
    browser_state_dir: Path
    theaters: list[Theater]

    @property
    def scan_dates(self) -> list[str]:
        today = date.today()
        first = self.start_date if self.start_date is not None else today
        first = max(first, today)

        if self.end_date is not None:
            if first > self.end_date:
                return []
            last = self.end_date
        else:
            last = today + timedelta(days=self.days_ahead)

        dates: list[str] = []
        current = first
        while current <= last:
            dates.append(current.isoformat())
            current += timedelta(days=1)
        return dates


def _load_yaml(path: Path) -> Any:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(str(value))


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(str(value))


def load_config(config_path: Path | None = None) -> Config:
    config_path = config_path or ROOT / "config.yaml"
    example_path = ROOT / "config.yaml.example"

    raw = _load_yaml(config_path)
    if raw is None:
        raw = _load_yaml(example_path)
    if raw is None:
        raise FileNotFoundError(
            f"No config found. Copy {example_path.name} to config.yaml"
        )

    theaters_raw = _load_yaml(ROOT / "theaters.yaml") or {"theaters": []}
    theaters = [
        Theater(
            id=item["id"],
            name=item["name"],
            city=item["city"],
            state=item["state"],
            chain=item["chain"],
            url=item["url"].rstrip("/"),
        )
        for item in theaters_raw.get("theaters", [])
    ]

    monitor = raw.get("monitor", {})
    booking = raw.get("booking", {})
    notifications = raw.get("notifications", {})
    browser = raw.get("browser", {})
    movie = raw.get("movie", {})
    amc_movie_name = str(movie.get("amc_movie_name", "")).strip()
    if not amc_movie_name:
        amc_movie_name = "The Odyssey"
    amc_format_name = str(movie.get("amc_format_name", "IMAX 70MM")).strip()
    alert_label = str(movie.get("alert_label", "")).strip() or amc_movie_name

    theater_filter = booking.get("theater_ids") or []
    if theater_filter:
        allowed = set(theater_filter)
        theaters = [t for t in theaters if t.id in allowed]

    return Config(
        movie_title_match=[s.lower() for s in movie.get("title_match", ["odyssey"])],
        amc_movie_name=amc_movie_name,
        amc_format_name=amc_format_name,
        alert_label=alert_label,
        format_match=[s.lower() for s in movie.get("format_match", ["imax 70mm"])],
        days_ahead=int(monitor.get("days_ahead", 21)),
        start_date=_parse_date(monitor.get("start_date")),
        end_date=_parse_date(monitor.get("end_date")),
        onsale_at=_parse_datetime(monitor.get("onsale_at")),
        poll_interval_seconds=int(monitor.get("poll_interval_seconds", 180)),
        poll_interval_fast_seconds=int(
            monitor.get("poll_interval_fast_seconds", 30)
        ),
        onsale_poll_interval_seconds=int(
            monitor.get("onsale_poll_interval_seconds", 20)
        ),
        concurrency=max(1, int(monitor.get("concurrency", 3))),
        headless=bool(monitor.get("headless", True)),
        page_timeout_seconds=int(monitor.get("page_timeout_seconds", 45)),
        seat_check_delay_seconds=float(monitor.get("seat_check_delay_seconds", 1.5)),
        seat_cache_ttl_minutes=int(monitor.get("seat_cache_ttl_minutes", 30)),
        min_seats=int(booking.get("min_seats", 2)),
        preferred_rows=[str(r).upper() for r in booking.get("preferred_rows", [])],
        theater_ids=list(theater_filter),
        earliest_time=str(booking.get("earliest_time", "")),
        latest_time=str(booking.get("latest_time", "")),
        auto_open=bool(booking.get("auto_open", True)),
        auto_book=bool(booking.get("auto_book", False)),
        stop_before_payment=bool(booking.get("stop_before_payment", True)),
        notify_console=bool(notifications.get("console", True)),
        notify_desktop=bool(notifications.get("desktop", True)),
        discord_webhook=str(notifications.get("discord_webhook", "")),
        notify_sound=bool(notifications.get("sound", True)),
        browser_state_dir=ROOT / browser.get("state_dir", "browser_state"),
        theaters=theaters,
    )
