# Project Log

**Last updated:** 2026-08-08

## What this project is

A Python bot that continuously monitors **AMC Lincoln Square 13 & IMAX** (NYC) for *The Odyssey* in native **IMAX 70mm** and alerts when **4+ regular seats** become available. Runs locally or via GitHub Actions (every 5 min) for 24/7 coverage when the PC is off.

## Key locations

| Item | Path |
|------|------|
| Repo | `C:\Users\mrahi\Odyssey` → https://github.com/Mrahim92/Odyssey |
| Config | `config.yaml` (Lincoln Square only, `min_seats: 4`, `end_date: 2026-09-30`) |
| Entry point | `python -m odyssey_bot run` (`PYTHONPATH=src`) |
| AMC scraper | `src/odyssey_bot/amc_scraper.py` |
| Seat counter | `src/odyssey_bot/amc_seats.py` |
| Seat capture tool | `scripts/capture_seat_map.py` → saves to `scripts/captures/` |
| GitHub Actions | `.github/workflows/scan.yml` (cron every 5 min, 30 min timeout) |
| Setup docs | `GITHUB_ACTIONS.md`, `DEPLOY.md` |

## Architecture

1. Playwright loads AMC Lincoln Square showtimes (base URL, not date-in-path).
2. Date dropdown + filter for **The Odyssey** + **IMAX 70MM** section.
3. Extract showtime links from `section[aria-label*="Showtimes for The Odyssey"]`; skip buttons containing "Sold Out".
4. Open each candidate URL; count **gold SVG seat tiles** via `amc_seats.py` (excludes wheelchair/companion).
5. Alert via Discord webhook when `seats >= min_seats`; dedupe via `state.json`.
6. 1.5s delay between seat page loads to reduce Cloudflare rate limits.

## Decisions made

- **Lincoln Square only** — user only wants NYC AMC Lincoln Square.
- **Minimum 4 regular seats** — alert only when seat map confirms 4+ non-wheelchair available seats.
- **Gold SVG tile = available** — each seat is a stacked SVG; available tiles have `#dfc66b` background path, occupied use `#4d4337`. Wheelchair/companion tiles have extra white path overlays (accessibility icon) and are excluded.
- **GitHub Actions for 24/7** — user added `DISCORD_WEBHOOK` secret; no Docker required for basic monitoring.

## Current state

- Seat counter **validated** on live IMAX 70mm showtime `145674731` (Aug 23 2026 6pm): **2 regular available**, 3 wheelchair/companion excluded, 475 occupied.
- With `min_seats: 4`, that showtime correctly does **not** alert.
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
- Screen arc at top of map is gold SVG but has no chair gradient — counter excludes it (height < 1000px, no gradient).
- Wheelchair/companion seats show white icon paths inside the seat SVG — counter excludes any available tile with white fills or wheelchair aria-labels.

## Session notes (2026-08-08, seat calibration)

**What we did:** User provided live calibration URL (`/showtimes/145674731/seats`). Rewrote `amc_seats.py` to count AMC's per-seat SVG tiles by fill color instead of pointer-cursor UI elements. Excluded wheelchair/companion seats (white path overlays + aria-label patterns). Validated against saved capture: 2 regular / 3 WC / 475 occupied.

**How:** Each seat = large stacked `<svg>`. Available regular = `#dfc66b` background without `#4d4337` and without white overlay paths. Screen arc excluded when gold-only and height < 1000px.

**Calibration URL:** https://www.amctheatres.com/showtimes/145674731/seats — The Odyssey IMAX 70MM, Aug 23 2026 6pm.
