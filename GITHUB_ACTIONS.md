# GitHub Actions setup

Runs a Lincoln Square IMAX 70mm scan **every 10 minutes** for free. Alerts via Discord when **4+ seats** appear in rows H–M.

## Step 1: Create a Discord webhook

1. Open Discord → your server (or create a private server for alerts)
2. **Server Settings → Integrations → Webhooks → New Webhook**
3. Name it `Odyssey Bot`, pick a channel, click **Copy Webhook URL**
4. Keep this URL secret — anyone with it can post to your channel

## Step 2: Push this repo to GitHub

From PowerShell in `C:\Users\mrahi\Odyssey`:

```powershell
git init
git add .
git commit -m "Add Odyssey Lincoln Square IMAX 70mm ticket monitor"
gh repo create Odyssey --public --source=. --push
```

If you don't have the GitHub CLI:

1. Create a new **public** repo at [github.com/new](https://github.com/new) (name it `Odyssey`, don't add README)
2. Then:

```powershell
git init
git add .
git commit -m "Add Odyssey Lincoln Square IMAX 70mm ticket monitor"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/Odyssey.git
git push -u origin main
```

**Use a public repo** for unlimited free Actions minutes. Private repos only get 2,000 min/month.

## Step 3: Add the Discord secret

1. GitHub repo → **Settings → Secrets and variables → Actions**
2. **New repository secret**
3. Name: `DISCORD_WEBHOOK`
4. Value: paste your Discord webhook URL
5. **Add secret**

## Step 4: Enable Actions and test

1. Repo → **Actions** tab
2. If prompted, click **I understand, enable Actions**
3. Left sidebar → **Scan Lincoln Square**
4. Click **Run workflow → Run workflow**

Watch the run complete (~2–4 min first time while Playwright installs). Check logs for:

```
Odyssey 70mm monitor started — 1 theaters, ...
Scan complete: ...
```

## Step 5: Wait for tickets

When 4+ IMAX 70mm seats appear at Lincoln Square, you'll get a Discord message with the showtime and AMC link.

The bot remembers showtimes it already alerted on (via Actions cache) so you won't get spammed for the same slot.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Workflow doesn't run on schedule | Schedules only work on the default branch (`main`). First run can take up to 10 min to start. |
| `DISCORD_WEBHOOK` error | Add the secret in Step 3 |
| Scan times out | Re-run manually; AMC may have been slow |
| No showtimes found | Normal if everything is sold out — keep it running |
| Want to re-alert on same showtime | Actions → Run workflow after deleting cache, or push a commit |

## What runs

File: `.github/workflows/scan.yml`

- Every 10 minutes + manual trigger
- Scans AMC Lincoln Square for The Odyssey **IMAX 70mm** only
- Requires **4+ seats** before alerting
- Pings Discord; no desktop notifications (cloud has no GUI)
