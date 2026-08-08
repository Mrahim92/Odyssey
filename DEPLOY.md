# Deploy to the cloud (free & paid options)

Your PC must be **on** for local monitoring. When it's off, the bot needs to run somewhere else.

## Does Cursor have cloud hosting for this?

**No — not for this kind of bot.**

Cursor's cloud features are for **AI coding agents**, not running your own apps 24/7:

| Cursor feature | What it does | Good for ticket bot? |
|----------------|--------------|----------------------|
| **Cloud Agents** | AI that writes code, runs tests, opens PRs on a VM | No — task finishes and VM goes away |
| **Automations** | Scheduled AI tasks (e.g. "review PRs every morning") | No — runs AI prompts, not your Python script |
| **Cursor SDK cloud runtime** | Programmatic coding agents from scripts | No — same as Cloud Agents |

Cursor Cloud is like hiring a remote developer for a task, not renting a server to run a daemon. For this bot you want a **small always-on Linux VM** or **scheduled GitHub Actions**.

---

## Free options (ranked)

### 1. Oracle Cloud Always Free — best free 24/7 option

**Cost: $0 forever** (not a trial). Gives you an ARM VM with up to 4 CPUs and 24 GB RAM — plenty for Playwright.

1. Sign up at [cloud.oracle.com](https://www.oracle.com/cloud/free/)
2. Create a compute instance:
   - Shape: **VM.Standard.A1.Flex** (Ampere ARM, Always Free-eligible)
   - OS: **Ubuntu 24.04**
   - Add your SSH public key
3. SSH in and install Docker:
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker $USER
   # log out and back in
   ```
4. Copy the project from your PC:
   ```powershell
   scp -r C:\Users\mrahi\Odyssey ubuntu@YOUR_INSTANCE_IP:/opt/odyssey
   ```
5. Edit `config.yaml` on the server (Discord webhook, disable desktop/sound/auto_open)
6. Start:
   ```bash
   cd /opt/odyssey
   docker compose up -d --build
   docker compose logs -f
   ```

**Gotcha:** Oracle signup can be picky about credit cards (verification only, not charged). Account approval sometimes takes a day.

**Tip:** Add 2 GB swap on the free VM — Playwright + Chromium can be memory-hungry:
```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

### 2. GitHub Actions — free, but scans every 5 minutes

**Cost: $0** on public repos (unlimited minutes). Private repos get 2,000 min/month on the free plan.

This repo includes `.github/workflows/scan.yml` — it runs one scan every 5 minutes and pings Discord if 4+ seats appear.

**Setup:**

1. Push this project to a **GitHub repo** (public recommended for unlimited minutes)
2. Add a secret: repo → **Settings → Secrets → Actions → New secret**
   - Name: `DISCORD_WEBHOOK`
   - Value: your Discord webhook URL
3. Enable Actions: repo → **Actions** tab → enable workflows
4. Click **Scan Lincoln Square → Run workflow** to test

**Tradeoffs vs Oracle:**
- ✅ Zero cost, zero server maintenance
- ❌ Scans every **5 min** (not 2 min) — slightly slower to catch drops
- ❌ Each run cold-starts Chromium (~1–2 min per scan)

---

### 3. Keep your PC on — free but limited

- Task Scheduler + disable sleep while plugged in
- Stops when PC is off, lid closed (unless configured), or power lost

---

## Paid options (if free tiers don't work)

| Option | Cost | Runs when PC off? |
|--------|------|-------------------|
| Hetzner CX22 | ~€4/mo | Yes |
| DigitalOcean droplet | ~$6/mo | Yes |

Same Docker steps as Oracle after you have the VM.

---

## Discord webhook (required for any cloud option)

Desktop toasts and `auto_open` only work on your local PC. For cloud, use Discord:

1. Discord → your server → **Server Settings → Integrations → Webhooks → New Webhook**
2. Copy URL into:
   - **Oracle/server:** `config.yaml` → `notifications.discord_webhook`
   - **GitHub Actions:** repo secret `DISCORD_WEBHOOK`

Cloud config should look like:

```yaml
booking:
  min_seats: 4
  auto_open: false

notifications:
  desktop: false
  sound: false
  discord_webhook: "https://discord.com/api/webhooks/..."
```

---

## Security

Never commit your Discord webhook to a public repo. Use GitHub Secrets or keep `config.yaml` only on the server.
