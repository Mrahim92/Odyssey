# Project Log

**Last updated:** 2026-08-14

## What this project is

A Python bot that continuously monitors **AMC Lincoln Square 13 & IMAX** (NYC) for *The Odyssey* in native **IMAX 70mm** and alerts when **4+ regular seats** in **rows H, J, K, L, M** become available. Runs locally or via GitHub Actions + **cron-job.org** (every 10 min) for 24/7 coverage when the PC is off.

## Key locations

| Item | Path |
|------|------|
| Repo | `C:\Users\mrahi\Odyssey` → https://github.com/Mrahim92/Odyssey |
| Config | `config.yaml` (Lincoln Square only, `min_seats: 4`, `preferred_rows: [H,J,K,L,M]`, `start_date: 2026-08-21`, `end_date: 2026-09-30`) |
| Entry point | `python -m odyssey_bot run` (`PYTHONPATH=src`) |
| AMC scraper | `src/odyssey_bot/amc_scraper.py` |
| Seat counter | `src/odyssey_bot/amc_seats.py` |
| GitHub Actions | `.github/workflows/scan.yml` (triggered by cron-job.org every 10 min) |
| Setup docs | `GITHUB_ACTIONS.md`, `DEPLOY.md` |

## Architecture

1. Playwright loads AMC Lincoln Square showtimes (base URL, not date-in-path).
2. Date dropdown + filter for **The Odyssey** + **IMAX 70MM** section.
3. Extract showtime links; skip "Sold Out" buttons.
4. Count available checkbox seats in rows H–M via `amc_seats.py`.
5. Discord alert when `seats >= 4`; dedupe via `state.json`.
6. AMC page load retries 3× with 4s backoff; failures log **Scan incomplete** (not sold out).

## Current state

- cron-job.org + GitHub Actions every 10 min (working).
- AMC scrape failures now retried and logged explicitly (fix pushed 2026-08-14).

## Gotchas

- Cloudflare / GitHub IP blocks cause AMC page load failures — now retried and surfaced as warnings in Actions.
- **GitHub schedule cron unreliable** — use cron-job.org (`GITHUB_ACTIONS.md`).
- IMAX 70mm filter strict; wheelchair/companion seats excluded; auditorium skips row I.

## Session notes (2026-08-14, alert link fix)

**What:** Discord alert linked to `/showtimes/145499914` which 404s; `/seats` URL works.
**How:** `amc_urls.normalize_amc_purchase_url()` appends `/seats`; Discord alerts now use clickable URLs (not code blocks). Seat-page format check reads **Showtime Information** panel only (rejects plain `70mm`).
**Learned:** Showtime 145499914 was plain 70mm @ 2:00 AM — false positive, not IMAX 70mm.
