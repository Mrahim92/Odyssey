# Project Log

**Last updated:** 2026-08-08

## What this project is

A Python bot that continuously monitors **AMC Lincoln Square 13 & IMAX** (NYC) for *The Odyssey* in native **IMAX 70mm** and alerts when seats become available. Optional auto seat-selection via saved AMC login.

## Key locations

| Item | Path |
|------|------|
| Repo | `C:\Users\mrahi\Odyssey` |
| Config | `config.yaml` (Lincoln Square only) |
| Theater list | `theaters.yaml` (full US 70mm list; filtered by config) |
| Entry point | `python -m odyssey_bot run` (set `PYTHONPATH=src` or use venv script) |
| AMC showtimes | `https://www.amctheatres.com/movie-theatres/new-york-city/amc-lincoln-square-13/showtimes` |

## Architecture

- **Playwright** (headless Chromium) loads AMC showtimes per date
- Filters page for "Odyssey" + "IMAX 70mm" (excludes Dolby Cinema / digital IMAX)
- Optional seat-map check; alerts via console, desktop toast, Discord webhook
- `state.json` dedupes already-alerted showtimes
- Optional `booker.py` selects seats with saved AMC session (`browser_state/amc.json`)

## Decisions made

- **Lincoln Square only** — user only wants NYC AMC Lincoln Square.
- **Minimum 4 seats** — alert only when 4+ contiguous seats appear available.
- **Cloud deploy via Docker** — for 24/7 when user's PC is off (see DEPLOY.md).

## Current state

- Bot scaffolded: config, scraper, monitor, notifier, optional booker.
- `config.yaml` locked to `amc-lincoln-square`.
- Dependencies install via `.venv`; Playwright Chromium installed.
- Not yet verified end-to-end against live AMC pages in this session.

## Roadmap

1. Set up Discord webhook for phone alerts.
2. Deploy free 24/7 hosting: Oracle Always Free (best) or GitHub Actions (easiest).
3. Run `python -m odyssey_bot once` locally to verify scraping works.

## Gotchas

- Lincoln Square runs Odyssey in **two** premium auditoriums — IMAX 70mm (480 seats) and Dolby Cinema. Bot filters on "IMAX 70mm" text only.
- AMC pages are JS-heavy; if scraping breaks, set `monitor.headless: false` to debug.
- 70mm showtimes often sell out within minutes; use `poll_interval_fast_seconds: 20` when hunting.
- Run with `$env:PYTHONPATH = "src"` from project root, or use `scripts/run_monitor.ps1`.

## Session notes (2026-08-08)

Built initial bot from empty repo. User narrowed scope to AMC Lincoln Square NYC only. Set `min_seats: 4`. Added Docker + DEPLOY.md for cloud 24/7 monitoring when PC is off. Discord webhook recommended for phone alerts from cloud.
