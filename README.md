# Odyssey Ticket Bot — AMC Lincoln Square IMAX 70mm

Monitors **AMC Lincoln Square 13 & IMAX** in NYC for *The Odyssey* in native **IMAX 70mm** and alerts you (or opens the purchase page) when seats appear.

> Lincoln Square is the largest IMAX screen in the US and one of only ~25 US theaters that can run true 15/70 IMAX film. Showtimes sell out fast; the bot re-scans every 2 minutes for newly dropped dates and open seats.

## Quick start

```powershell
cd C:\Users\mrahi\Odyssey
$env:PYTHONPATH = "src"

# 1. Install
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium

# 2. Single test scan
python -m odyssey_bot once

# 3. Run forever (or use scripts\run_monitor.ps1)
python -m odyssey_bot run
```

`config.yaml` is already set for Lincoln Square only. Edit it for seat count, Discord alerts, etc.

## Configuration

| Setting | What it does |
|---------|--------------|
| `booking.min_seats` | Only alert when at least N seats appear available |
| `monitor.poll_interval_seconds` | How often to scan Lincoln Square (default 2 min) |
| `notifications.discord_webhook` | Ping your phone via Discord |
| `booking.auto_open` | Open AMC purchase URL in browser when found |
| `booking.auto_book` | Try to select seats (requires AMC login — see below) |

### Lincoln Square only

Theater is locked to `amc-lincoln-square` in `config.yaml`:

```yaml
booking:
  theater_ids:
    - amc-lincoln-square
  min_seats: 4
```

## Run 24/7

**Your PC must be on** for local monitoring. If the computer is off or asleep, the bot stops.

| Where it runs | PC can be off? | Cost |
|---------------|----------------|------|
| This PC | No | Free |
| **Oracle Cloud Always Free** | **Yes** | **Free** |
| **GitHub Actions** (every 5 min) | **Yes** | **Free** |
| Paid VPS (DigitalOcean, etc.) | Yes | ~$4–6/mo |

See **[DEPLOY.md](DEPLOY.md)** for step-by-step setup. **Cursor Cloud Agents are not for this** — they're AI coding agents, not general app hosting.

For cloud, set up a **Discord webhook** so alerts reach your phone.

### Local: Windows Task Scheduler

```powershell
# scripts/run_monitor.ps1
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument `
  "-NoProfile -WindowStyle Hidden -File `"C:\Users\mrahi\Odyssey\scripts\run_monitor.ps1`""
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "Odyssey70mmBot" -Action $action -Trigger $trigger
```

Or keep a terminal open:

```powershell
.\.venv\Scripts\Activate.ps1
python -m odyssey_bot run
```

## Optional: auto seat selection

1. Save a logged-in session:
   ```powershell
   python -m odyssey_bot login amc
   ```
2. In `config.yaml`:
   ```yaml
   booking:
     auto_book: true
     stop_before_payment: true   # recommended
   ```

The bot selects seats and stops at checkout so you can confirm payment.

## Commands

| Command | Description |
|---------|-------------|
| `python -m odyssey_bot run` | Continuous monitoring |
| `python -m odyssey_bot once` | One scan, print results |
| `python -m odyssey_bot login amc` | Save AMC login session |
| `python -m odyssey_bot clear-state` | Re-alert on showtimes you've already seen |

## How it works

1. Loads AMC Lincoln Square showtimes for the next N days
2. Uses Playwright (headless Chromium) to read the AMC showtimes page
3. Filters for **The Odyssey** + **IMAX 70mm** (not Dolby Cinema or digital IMAX)
4. Optionally checks seat maps for availability
5. Alerts via console, desktop toast, Discord, and/or opens the purchase URL

## Limitations

- Theater websites change often; if a chain breaks, file an issue or set `monitor.headless: false` to debug.
- Full auto-purchase without human confirmation is intentionally disabled by default.
- Museum/specialty venues (TCL Chinese, Esquire, etc.) may need manual URL tweaks in `theaters.yaml`.
