# GitHub Actions setup

Runs a Lincoln Square IMAX 70mm scan **every 10 minutes** for free. Alerts via Discord when **4+ seats** appear in rows H–M.

The bot runs on GitHub Actions, but **scheduling uses [cron-job.org](https://cron-job.org)** — GitHub's built-in cron often skips runs.

## Step 1: Create a Discord webhook

1. Open Discord → your server (or create a private server for alerts)
2. **Server Settings → Integrations → Webhooks → New Webhook**
3. Name it `Odyssey Bot`, pick a channel, click **Copy Webhook URL**
4. Keep this URL secret — anyone with it can post to your channel

## Step 2: Push this repo to GitHub

Repo: **https://github.com/Mrahim92/Odyssey**

If you're starting fresh:

```powershell
git init
git add .
git commit -m "Add Odyssey Lincoln Square IMAX 70mm ticket monitor"
gh repo create Odyssey --public --source=. --push
```

**Use a public repo** for unlimited free Actions minutes.

## Step 3: Add the Discord secret

1. GitHub repo → **Settings → Secrets and variables → Actions**
2. **New repository secret**
3. Name: `DISCORD_WEBHOOK`
4. Value: paste your Discord webhook URL
5. **Add secret**

## Step 4: Enable Actions and test manually

1. Repo → **Actions** tab → enable Actions if prompted
2. Left sidebar → **Scan Lincoln Square**
3. Click **Run workflow → Run workflow**

Watch the run complete (~2 min). Logs should show:

```
Odyssey 70mm monitor started — 1 theaters, 2026-08-21 through 2026-09-30 ...
Scan complete: ...
```

## Step 5: Set up cron-job.org (reliable every-10-min schedule)

### 5a. Create a GitHub token

1. GitHub → **Settings → Developer settings → Personal access tokens**
2. **Fine-grained tokens → Generate new token**
3. Name: `Odyssey cron trigger`
4. Repository access: **Only select repositories** → `Odyssey`
5. Permissions → **Repository permissions → Actions: Read and write**
6. Generate and **copy the token** (you won't see it again)

> Classic token alternative: scope `repo` also works.

**Do not commit this token or add it to the repo.** It lives only in cron-job.org.

### 5b. Create the cron job

1. Sign up at [cron-job.org](https://cron-job.org) (free)
2. **Cronjobs → Create cronjob**
3. Fill in:

| Field | Value |
|-------|-------|
| **Title** | Odyssey scan |
| **URL** | `https://api.github.com/repos/Mrahim92/Odyssey/actions/workflows/scan.yml/dispatches` |
| **Schedule** | Every 10 minutes |
| **Request method** | `POST` |

4. Open **Advanced** (or headers/body section):

**Headers:**

| Header | Value |
|--------|-------|
| `Accept` | `application/vnd.github+json` |
| `Authorization` | `Bearer YOUR_GITHUB_TOKEN` |
| `X-GitHub-Api-Version` | `2022-11-28` |
| `Content-Type` | `application/json` |

**Request body:**

```json
{"ref":"main"}
```

5. Save and **enable** the cron job
6. Use **Run now** once — within ~30 seconds a new run should appear under GitHub **Actions**

### 5c. Verify it's working

- GitHub → **Actions** → new runs every ~10 min with trigger **workflow_dispatch**
- cron-job.org → **History** → should show HTTP **204** (success)

## Step 6: Wait for tickets

When 4+ IMAX 70mm seats appear in rows H–M at Lincoln Square, you'll get a Discord message with the showtime and AMC link.

The bot remembers showtimes it already alerted on (via Actions cache) so you won't get spammed for the same slot.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| cron-job.org returns 401 | Token expired or wrong `Authorization` header format (`Bearer TOKEN`) |
| cron-job.org returns 404 | Check repo name and workflow filename in the URL |
| No run appears after cron | Confirm cron job is enabled; click **Run now** to test |
| `DISCORD_WEBHOOK` error | Add the secret in Step 3 |
| Scan times out | Re-run manually; AMC may have been slow |
| No showtimes found | Normal if everything is sold out |
| Two runs at once | Only use cron-job.org — don't re-add GitHub `schedule` cron |

## What runs

File: `.github/workflows/scan.yml`

- **cron-job.org** every 10 minutes + manual trigger
- Scans AMC Lincoln Square, Aug 21 – Sep 30, **IMAX 70mm** only
- Requires **4+ seats in rows H, J, K, L, M** before alerting
- Pings Discord; no desktop notifications (cloud has no GUI)
