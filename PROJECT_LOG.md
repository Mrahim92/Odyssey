# Project Log

**Last updated:** 2026-08-08

## What this project is

A Python bot that continuously monitors **AMC Lincoln Square 13 & IMAX** (NYC) for *The Odyssey* in native **IMAX 70mm** and alerts when **4+ regular seats** in **rows H, J, K, L, M** become available. Runs locally or via GitHub Actions (every 30 min) for 24/7 coverage when the PC is off.

## Key locations

| Item | Path |
|------|------|
| Repo | `C:\Users\mrahi\Odyssey` → https://github.com/Mrahim92/Odyssey |
| Config | `config.yaml` (Lincoln Square only, `min_seats: 4`, `preferred_rows: [H,J,K,L,M]`, `end_date: 2026-09-30`) |
| Entry point | `python -m odyssey_bot run` (`PYTHONPATH=src`) |
| AMC scraper | `src/odyssey_bot/amc_scraper.py` |
| Seat counter | `src/odyssey_bot/amc_seats.py` |
| Seat capture tool | `scripts/capture_seat_map.py` → saves to `scripts/captures/` |
| GitHub Actions | `.github/workflows/scan.yml` (cron every 30 min, 30 min timeout) |
| Setup docs | `GITHUB_ACTIONS.md`, `DEPLOY.md` |

## Architecture

1. Playwright loads AMC Lincoln Square showtimes (base URL, not date-in-path).
2. Date dropdown + filter for **The Odyssey** + **IMAX 70MM** section.
3. Extract showtime links from `section[aria-label*="Showtimes for The Odyssey"]`; skip buttons containing "Sold Out".
4. Open each candidate URL; count **available checkbox seats** via `amc_seats.py` (excludes wheelchair/companion; optional row filter).
5. Alert via Discord webhook when `seats >= min_seats` in `preferred_rows`; dedupe via `state.json`.
6. 1.5s delay between seat page loads to reduce Cloudflare rate limits.

## Decisions made

- **Lincoln Square only** — user only wants NYC AMC Lincoln Square.
- **Minimum 4 regular seats in back rows** — `preferred_rows: [H, J, K, L, M]` (last 5 rows; no row I in this auditorium). Empty list = any row.
- **Checkbox seat map** — each seat has `input name="H42"` and aria-label; available = enabled, not Occupied, not wheelchair. Row parsed from name prefix.
- **GitHub Actions for 24/7** — user added `DISCORD_WEBHOOK` secret; no Docker required for basic monitoring.

## Current state

- Seat counter uses checkbox `name`/`aria-label` per seat; row filter **H, J, K, L, M** configured in `config.yaml`.
- Validated on showtime `145674731`: 2 available in row A (front), **0 in back rows** — no alert (correct).
- Showtime scraping verified locally (Odyssey section, sold-out skip, date dropdown).

## Roadmap

1. Confirm GitHub Actions run succeeds with calibrated seat counter.
2. Optional: `alert_mode: notify` fallback — ping on any non-sold-out link without waiting for seat count.
3. Optimize scan scope if rate limits persist (only seat-check dates with non-sold-out links).

## Gotchas

- Lincoln Square has **IMAX 70mm** (480 seats) and **Dolby Cinema** — bot filters on "IMAX 70mm" text only.
- AMC `/showtimes/YYYY-MM-DD` URLs hang on "Loading"; use base `/showtimes` + date dropdown.
- Cloudflare Error 1015 if too many seat page loads in quick succession.
- AMC dropdown may not list dates past ~Sep 25 yet even though config scans through Sep 30.
- Wheelchair/companion excluded via aria-label patterns (`Wheelchair Space`, `Wheelchair Companion`, etc.).
- Row letters parsed from seat name (e.g. `H42` = row H). This auditorium skips row I.

## Session notes (2026-08-08, seat calibration)

**What we did:** Calibrated seat counter on live URL; user confirmed 2 gold seats. Added `preferred_rows: [H,J,K,L,M]` — bot only counts available seats in back 5 rows.

**How:** Switched primary counting to checkbox inputs (`input name="H42"`). Row filter applied before counting; wheelchair/companion still excluded.

**Calibration URL:** https://www.amctheatres.com/showtimes/145674731/seats — 2 seats in row A, 0 in H–M.
