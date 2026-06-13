# 🛒 Amazon Price Tracker Bot

A Telegram bot that tracks Amazon India product prices, provides AI-powered buy recommendations, and sends price-drop alerts.

---

## Features

- `/track <url>` — Scrape live price + CamelCamelCamel history → AI Buy Score (1–10)
- `/setalert <url> <price>` — Set a target price; get notified when it drops
- `/myalerts` — View all active alerts
- Background scheduler checks prices every 6 hours
- Admin commands: `/stats`, `/forcecheck`, `/health`
- Deployed on Render Free with a `/health` endpoint to keep the service alive

---

## Setup

### 1. Prerequisites

- Python 3.11+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- A [Supabase](https://supabase.com) project (free tier works)
- A [ChatAnywhere](https://api.chatanywhere.tech) API key (GPT-3.5 Turbo)

---

### 2. Database Setup

In your Supabase project, go to **SQL Editor** and run the contents of `schema.sql`.

> ⚠️ Use your **service role key** (not the anon key) as `SUPABASE_KEY` so the bot has full DB access.

---

### 3. Local Development

```bash
# Clone and install
git clone <your-repo>
cd amazon-price-bot
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your actual credentials

# Run
python main.py
```

---

### 4. Deploy to Render

1. Push the project to GitHub.
2. Go to [render.com](https://render.com) → **New Web Service** → connect your repo.
3. Render auto-detects `render.yaml` — just set the environment variables.

**Required Environment Variables:**

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Supabase **service role** key |
| `OPENAI_API_KEY` | ChatAnywhere API key |
| `ADMIN_ID` | Your Telegram user ID (get from @userinfobot) |
| `PORT` | `8080` (set automatically by render.yaml) |

> **Render Free Tier Note:** The free tier spins down after inactivity. Use a free uptime monitor (e.g. [UptimeRobot](https://uptimerobot.com)) to ping `https://your-app.onrender.com/health` every 5 minutes.

---

## Architecture

```
main.py
├── FastAPI (/health endpoint)          — keeps Render service alive
├── Telegram Bot (polling)              — handles commands
├── APScheduler (every 6h)             — price checks + alert firing
│
handlers.py    — /start /track /setalert /myalerts + admin cmds
scraper.py     — URL resolution, ASIN extraction, Amazon + CamelCamelCamel
ai_analysis.py — ChatAnywhere GPT-3.5 buy recommendation
database.py    — Supabase CRUD (products, price_history, alerts)
scheduler.py   — background price check job
config.py      — environment config
schema.sql     — Supabase table definitions
```

---

## Supported Amazon URL Formats

- `https://amazon.in/dp/B0XXXXXX`
- `https://www.amazon.in/product-name/dp/B0XXXXXX`
- `https://amzn.in/d/XXXXXXX` (shortened — resolved via redirect)
- `https://amzn.to/XXXXXXX` (shortened — resolved via redirect)
- `https://a.co/d/XXXXXXX` (shortened — resolved via redirect)

---

## Bot Commands

### User Commands

| Command | Description |
|---|---|
| `/start` | Welcome message and usage |
| `/track <url>` | Analyze product price with AI recommendation |
| `/setalert <url> <price>` | Set a price drop alert |
| `/myalerts` | View active alerts |

### Admin Commands

| Command | Description |
|---|---|
| `/stats` | Total products, alerts, and users |
| `/forcecheck` | Immediately run the price check job |
| `/health` | Bot and scheduler status |

---

## Notes on Scraping

Amazon actively blocks scrapers. If you see "Could not fetch product data":

1. **Try again in a few minutes** — Amazon rate-limits by IP
2. The bot rotates User-Agent strings to reduce blocking
3. CamelCamelCamel data is used for historical context; it may occasionally be unavailable
4. On Render Free, the shared IP pool may be more likely to get rate-limited — this is a known limitation of free hosting

---

## License

MIT
