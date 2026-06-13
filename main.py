"""
Main entry point.
- FastAPI app for /health endpoint (required by Render)
- Telegram bot via polling
- APScheduler for price checks
"""

import asyncio
import logging
import threading
import uvicorn
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from telegram.ext import Application

from config import TELEGRAM_BOT_TOKEN, PORT
import scheduler as sched_module
from handlers import register_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── FastAPI Health App ────────────────────────────────────

web_app = FastAPI(title="Amazon Price Tracker Bot", docs_url=None, redoc_url=None)


@web_app.get("/health")
async def health():
    return PlainTextResponse("OK")


@web_app.get("/")
async def root():
    return PlainTextResponse("Amazon Price Tracker Bot is running.")


# ── Run health server in background thread ────────────────

def run_health_server():
    uvicorn.run(web_app, host="0.0.0.0", port=PORT, log_level="warning")


# ── Main ──────────────────────────────────────────────────

async def main():
    logger.info("🚀 Starting Amazon Price Tracker Bot...")

    # Build Telegram application
    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    # Register handlers
    register_handlers(app)

    # Give scheduler access to the bot
    sched_module.set_bot(app)

    # Start health server in background
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    logger.info(f"Health server running on port {PORT}")

    # Start scheduler
    sched_module.start_scheduler()

    # Start bot polling
    logger.info("Starting Telegram bot polling...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    logger.info("✅ Bot is live! Press Ctrl+C to stop.")

    # Keep running until interrupted
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        scheduler = sched_module.get_scheduler()
        if scheduler:
            scheduler.shutdown(wait=False)
        logger.info("Bot shut down cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
