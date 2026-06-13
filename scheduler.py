"""
Scheduler: runs every 6 hours to check prices and trigger alerts.
"""

import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import database as db
from scraper import scrape_amazon
from config import PRICE_CHECK_INTERVAL_HOURS, LOG_CHANNEL_ID

logger = logging.getLogger(__name__)

_bot_app = None  # set by main.py
_scheduler: AsyncIOScheduler | None = None


def set_bot(app):
    global _bot_app
    _bot_app = app


async def run_price_check():
    """Fetch all products, update prices, fire alerts."""
    logger.info("⏰ Running scheduled price check...")
    products = db.get_all_products()

    if not products:
        logger.info("No products to check.")
        return

    checked = 0
    alerted = 0

    for product in products:
        asin = product["asin"]
        url = product["url"]

        try:
            data = await scrape_amazon(url)
            new_price = data["price"]

            # Update DB
            db.update_product_price(asin, new_price)
            db.record_price(asin, new_price)
            checked += 1

            # Check alerts
            alerts = db.get_active_alerts_for_asin(asin)
            for alert in alerts:
                if new_price <= alert["target_price"]:
                    await _notify_user(
                        user_id=alert["user_id"],
                        product_name=product["name"],
                        current_price=new_price,
                        target_price=alert["target_price"],
                        url=url,
                    )
                    db.mark_alert_triggered(alert["id"])
                    alerted += 1

        except Exception as e:
            logger.error(f"Failed to check {asin}: {e}")

        # Small delay to avoid hammering Amazon
        await asyncio.sleep(2)

    logger.info(f"✅ Price check done. Checked: {checked}, Alerts sent: {alerted}")


async def _notify_user(user_id: int, product_name: str, current_price: float, target_price: float, url: str):
    if not _bot_app:
        logger.warning("Bot app not set — cannot send notification.")
        return

    message = (
        f"🔔 *Price Alert Triggered!*\n\n"
        f"📦 *{product_name}*\n"
        f"🎯 Your Target: ₹{target_price:,.0f}\n"
        f"💰 Current Price: ₹{current_price:,.0f}\n\n"
        f"🛒 [Buy Now]({url})"
    )

    try:
        await _bot_app.bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        logger.info(f"Alert sent to user {user_id} for {product_name}")

        if LOG_CHANNEL_ID:
            try:
                await _bot_app.bot.send_message(
                    chat_id=LOG_CHANNEL_ID,
                    text=(
                        f"🔔 *Alert Triggered*\n"
                        f"👤 User: `{user_id}`\n"
                        f"📦 {product_name}\n"
                        f"🎯 Target: ₹{target_price:,.0f} | 💰 Now: ₹{current_price:,.0f}"
                    ),
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.warning(f"Failed to log alert trigger: {e}")
    except Exception as e:
        logger.error(f"Failed to notify user {user_id}: {e}")


def start_scheduler():
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
    _scheduler.add_job(
        run_price_check,
        trigger=IntervalTrigger(hours=PRICE_CHECK_INTERVAL_HOURS),
        id="price_check",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    logger.info(f"Scheduler started — price checks every {PRICE_CHECK_INTERVAL_HOURS}h")
    return _scheduler


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler