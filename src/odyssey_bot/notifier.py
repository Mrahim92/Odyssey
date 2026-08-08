from __future__ import annotations

import json
import sys
import webbrowser
from datetime import datetime

import requests

from .models import Showtime


def _console(message: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)


def _desktop(title: str, message: str) -> None:
    try:
        from plyer import notification

        notification.notify(title=title, message=message, timeout=20)
    except Exception as exc:  # noqa: BLE001 - best-effort notification
        _console(f"Desktop notification failed: {exc}")


def _discord(webhook: str, content: str) -> None:
    if not webhook:
        return
    try:
        response = requests.post(
            webhook,
            json={"content": content[:1900]},
            timeout=15,
        )
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        _console(f"Discord webhook failed: {exc}")


def _sound() -> None:
    if sys.platform == "win32":
        import winsound

        for _ in range(3):
            winsound.Beep(880, 250)
    else:
        print("\a", end="", flush=True)


class Notifier:
    def __init__(
        self,
        *,
        console: bool = True,
        desktop: bool = True,
        discord_webhook: str = "",
        sound: bool = True,
        auto_open: bool = True,
    ) -> None:
        self.console = console
        self.desktop = desktop
        self.discord_webhook = discord_webhook
        self.sound = sound
        self.auto_open = auto_open

    def alert(self, showtimes: list[Showtime]) -> None:
        if not showtimes:
            return

        header = f"Found {len(showtimes)} IMAX 70mm Odyssey showtime(s)!"
        body = "\n\n".join(st.summary() for st in showtimes)

        if self.console:
            _console(header)
            print(body, flush=True)

        if self.desktop:
            short = showtimes[0].summary().replace("\n", " | ")
            _desktop("Odyssey 70mm tickets!", short[:240])

        if self.discord_webhook:
            _discord(self.discord_webhook, f"**{header}**\n```\n{body}\n```")

        if self.sound:
            _sound()

        if self.auto_open and showtimes[0].purchase_url:
            webbrowser.open(showtimes[0].purchase_url)

    def status(self, message: str) -> None:
        if self.console:
            _console(message)

    def debug(self, payload: dict) -> None:
        if self.console:
            _console(json.dumps(payload, default=str))
