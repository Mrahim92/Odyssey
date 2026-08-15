# Dune: Part Three — Aug 18 on-sale playbook

**On-sale:** Tuesday, August 18, 2026 at **12:00 PM Eastern**  
**Target:** AMC Lincoln Square, **IMAX 70mm**, 4 seats together in rows **H–M**  
**Mode:** **Auto-book** — bot selects seats and advances to checkout; you enter payment.

## Before Aug 18 (do this now)

### 1. Save your AMC login

The bot needs your logged-in session to hold seats in checkout:

```powershell
cd C:\Users\mrahi\Odyssey
$env:PYTHONPATH="src"
copy config.dune.yaml.example config.dune.yaml
# Edit config.dune.yaml — add Discord webhook

python -m odyssey_bot login amc --config config.dune.yaml
```

A browser opens → log in to AMC → press **Enter** in the terminal to save `browser_state/amc.json`.

### 2. Verify AMC dropdown names (Aug 17)

Open [Lincoln Square showtimes](https://www.amctheatres.com/movie-theatres/new-york-city/amc-lincoln-square-13/showtimes) and confirm:
- Movie dropdown: **`Dune: Part Three`**
- Format dropdown: **`IMAX 70MM`**

Update `config.dune.yaml` if labels differ.

### 3. Clear alert state

```powershell
python -m odyssey_bot clear-state
```

## Aug 18 — drop day

### 11:50 AM ET — start the bot on your PC

Leave the PC **awake, plugged in, on wired internet** if possible:

```powershell
cd C:\Users\mrahi\Odyssey
$env:PYTHONPATH="src"
python -m odyssey_bot run --config config.dune.yaml
```

### What happens at noon

1. Bot waits until **12:00 PM ET**
2. Scans AMC every **10 seconds**
3. When 4+ IMAX 70mm seats appear in rows H–M:
   - Clicks the best **4-seat block** in one row
   - Clicks **Continue** through Tickets / Food
   - Stops at the **payment page** with browser open
4. **You enter your card and pay** — the bot does not store payment info

### If booking succeeds

- Browser stays open at checkout
- Discord pings **"BOOKED — pay in browser NOW!"**
- Bot stops (won't keep scanning)

## What auto-book does NOT do

- **Does not enter payment** — you pay manually (safer; no card stored in code)
- **Does not guarantee tickets** — AMC + competition at noon is brutal; this maximizes speed but isn't a sure thing
- **Does not run well on GitHub Actions** for booking — use your **local PC** Aug 18

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `auto_book requires AMC login` | Run `login amc` step above |
| `Continue button stayed disabled` | Seats taken between scan and click — bot keeps trying |
| `Movie not in AMC dropdown yet` | Normal before noon; bot retries every 10s |
| Browser closes immediately | Set `stop_before_payment: true` in config |

## After Aug 18

Stop the bot (`Ctrl+C`). Switch cron-job.org back to Odyssey monitoring if desired.
