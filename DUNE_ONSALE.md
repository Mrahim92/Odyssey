# Dune: Part Three — Aug 18 on-sale playbook

**On-sale:** Tuesday, August 18, 2026 at **12:00 PM Eastern**  
**Target:** AMC Lincoln Square 13, **IMAX 70mm**, 4+ seats in rows H–M  
**Release:** December 18, 2026 (opening weekend already sold out at Lincoln Square)

## Reality check

- Opening-weekend IMAX 70mm at Lincoln Square is **already sold out** from the April drop.
- Aug 18 is a **second batch** — likely additional dates/showtimes. Competition will be fierce.
- **GitHub Actions (every 10 min) is too slow** for a noon drop. Use your **PC locally** for the main attack; cloud is backup only.

## Best plan (recommended)

### Before Aug 18

1. Copy the Dune config:
   ```powershell
   cd C:\Users\mrahi\Odyssey
   copy config.dune.yaml.example config.dune.yaml
   ```
2. Edit `config.dune.yaml` — paste your Discord webhook.
3. Install Playwright if needed:
   ```powershell
   pip install -r requirements.txt
   python -m playwright install chromium
   ```
4. **Verify AMC dropdown labels** (Aug 17 or earlier): open [Lincoln Square showtimes](https://www.amctheatres.com/movie-theatres/new-york-city/amc-lincoln-square-13/showtimes), check the movie dropdown says exactly `Dune: Part Three` and format says `IMAX 70MM`. Update `amc_movie_name` / `amc_format_name` in config if different.
5. Clear old alert state so Dune isn't deduped against Odyssey:
   ```powershell
   $env:PYTHONPATH="src"
   python -m odyssey_bot clear-state
   ```

### Aug 18 — drop day

1. **11:50 AM ET** — start the local monitor (leave PC awake, plugged in):
   ```powershell
   cd C:\Users\mrahi\Odyssey
   $env:PYTHONPATH="src"
   python -m odyssey_bot run --config config.dune.yaml
   ```
   The bot waits until **12:00 PM ET** (`onsale_at`), then polls every **20 seconds**.

2. **When Discord pings** — tap the `/seats` link immediately and checkout manually. You have seconds, not minutes.

3. **Optional backup** — set cron-job.org to **every 1–2 minutes** on Aug 18 only, with GitHub workflow config temporarily switched to Dune (see below).

### After you buy (or if sold out)

Stop the local monitor (`Ctrl+C`). Switch cron-job.org back to 10 min and restore Odyssey config in GitHub if you still want Odyssey monitoring.

## Cloud backup (optional)

Edit `.github/workflows/scan.yml` inline config on Aug 18 morning:

```yaml
movie:
  title_match: [dune]
  amc_movie_name: "Dune: Part Three"
  amc_format_name: "IMAX 70MM"
  alert_label: "Dune Part Three IMAX 70mm"
monitor:
  start_date: "2026-12-18"
  end_date: "2026-12-28"
  poll_interval_seconds: 60
  seat_cache_ttl_minutes: 5
```

Set cron-job.org to **every 2 minutes** for Aug 18, then revert.

## What the bot won't do (yet)

- **Auto-checkout** — `auto_book` doesn't reliably select AMC checkbox seats in rows H–M. Manual checkout from the Discord link is the plan.
- **Beat humans at scalpers** — you'll still need to be fast when the alert fires.

## Config reference

| Setting | Dune value | Why |
|---------|------------|-----|
| `amc_movie_name` | `Dune: Part Three` | Exact AMC dropdown label |
| `onsale_at` | `2026-08-18T12:00:00-04:00` | Fast polling starts at noon ET |
| `onsale_poll_interval_seconds` | `20` | Scan every 20s after on-sale |
| `start_date` / `end_date` | Dec 18–28 | December release window |
| `preferred_rows` | H, J, K, L, M | Back rows (same as Odyssey) |
| `min_seats` | `4` | Alert only when 4+ available |
