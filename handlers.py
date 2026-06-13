"""
Telegram bot command handlers.
"""

import logging
from datetime import datetime, timezone, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

import database as db
from scraper import get_full_product_data, extract_asin, resolve_url, is_amazon_url, scrape_amazon, scrape_camel
from ai_analysis import get_buy_recommendation
from config import ADMIN_ID, LOG_CHANNEL_ID
import scheduler as sched_module

logger = logging.getLogger(__name__)

CACHE_MINUTES = 30


async def _log_to_channel(context: ContextTypes.DEFAULT_TYPE, text: str):
    """Send a log message to the configured log channel, if set."""
    if not LOG_CHANNEL_ID:
        return
    try:
        await context.bot.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.warning(f"Failed to send log to channel: {e}")


# ── Helpers ───────────────────────────────────────────────

def fmt_price(v) -> str:
    return f"₹{v:,.0f}" if v else "N/A"


def score_emoji(score: int) -> str:
    if score >= 8:
        return "🟢"
    elif score >= 5:
        return "🟡"
    else:
        return "🔴"


async def _resolve_and_validate(url: str) -> tuple[str, str]:
    if any(d in url for d in ["amzn.in", "amzn.to", "a.co"]):
        url = await resolve_url(url)
    if not is_amazon_url(url):
        raise ValueError("That doesn't look like an Amazon URL. Please provide a valid Amazon link.")
    asin = extract_asin(url)
    if not asin:
        raise ValueError("Could not extract product ID (ASIN) from that URL.")
    return url, asin


def _is_fresh(last_checked_iso: str, minutes: int = CACHE_MINUTES) -> bool:
    try:
        last = datetime.fromisoformat(last_checked_iso.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) - last < timedelta(minutes=minutes)
    except Exception:
        return False


# ── /start ────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🛒 *Amazon Price Tracker Bot*\n\n"
        "Track products, get AI buy recommendations, and set price alerts.\n\n"
        "*Commands:*\n"
        "📊 `/track <amazon_url>` — Analyze price & get AI recommendation\n"
        "🔔 `/setalert <amazon_url> <target_price>` — Set price drop alert\n"
        "📋 `/myalerts` — View your active alerts\n\n"
        "*Supported URLs:*\n"
        "`amazon.in` · `amzn.in` · `amzn.to` · `a.co`\n\n"
        "_Prices are checked every 6 hours. You'll be notified when your target is hit._"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ── /track ────────────────────────────────────────────────

async def cmd_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: `/track <amazon_url>`\n\nExample:\n`/track https://amzn.in/d/abc123`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    url = context.args[0].strip()
    user = update.effective_user
    await _log_to_channel(
        context,
        f"🔍 *New /track*\n"
        f"👤 {user.full_name} (`{user.id}`) @{user.username or 'N/A'}\n"
        f"🔗 {url}"
    )

    msg = await update.message.reply_text("🔍 Fetching product data...")

    try:
        url, asin = await _resolve_and_validate(url)
    except ValueError as e:
        await msg.edit_text(f"❌ {e}")
        return

    # ── Check DB cache ────────────────────────────────────
    cached = db.get_product_by_asin(asin)
    use_cache = False
    current_price = None
    name = None
    image_url = None

    if cached and cached.get("last_checked") and _is_fresh(cached["last_checked"]):
        use_cache = True
        current_price = cached["current_price"]
        name = cached["name"]
        url = cached["url"]
        image_url = cached.get("image_url")
        logger.info(f"Using cached data for {asin}")
    else:
        # Fresh scrape from Amazon
        try:
            await msg.edit_text("📡 Scraping Amazon...")
            amazon_data = await scrape_amazon(url)
            current_price = amazon_data["price"]
            name = amazon_data["name"]
            url = amazon_data["url"]
            image_url = amazon_data.get("image_url")

            db.upsert_product(asin, name, url, current_price, image_url)
            db.record_price(asin, current_price)
            logger.info(f"Fresh scrape for {asin}: ₹{current_price}")

        except Exception as e:
            logger.error(f"Amazon scraping failed: {e}")
            await msg.edit_text(
                "❌ Could not fetch product data. Amazon may be temporarily blocking.\n"
                "Please try again in a few minutes."
            )
            return

    # ── Price history ─────────────────────────────────────
    await msg.edit_text("📊 Fetching price history...")

    lowest = highest = average = trend = None

    # Try DB history first
    db_history = db.get_price_history(asin)
    if len(db_history) >= 2:
        prices = [h["price"] for h in db_history]
        lowest  = min(prices)
        highest = max(prices)
        average = round(sum(prices) / len(prices), 2)
        trend   = "falling" if prices[-1] < prices[-2] else ("rising" if prices[-1] > prices[-2] else "stable")
        logger.info(f"DB history for {asin}: {len(prices)} points")
    else:
        # Not enough DB history — use PriceHistory.app
        camel = await scrape_camel(asin)
        lowest  = camel.get("lowest")
        highest = camel.get("highest")
        average = camel.get("average")
        trend   = camel.get("trend", "unknown")

    # ── AI analysis ───────────────────────────────────────
    await msg.edit_text("🤖 Generating AI recommendation...")
    try:
        ai = await get_buy_recommendation(
            product_name=name,
            current_price=current_price,
            lowest_ever=lowest,
            highest_ever=highest,
            average_price=average,
            trend=trend or "unknown",
        )
    except Exception as e:
        logger.error(f"AI failed: {e}")
        ai = {"score": 5, "verdict": "AI analysis unavailable at the moment."}

    score = ai["score"]
    trend_emoji = {"rising": "📈", "falling": "📉", "stable": "➡️"}.get(trend or "", "📊")
    cache_note = " _(cached)_" if use_cache else ""

    reply = (
        f"📦 *{name}*\n\n"
        f"💰 Current Price: *{fmt_price(current_price)}*{cache_note}\n"
        f"📉 Lowest Ever: {fmt_price(lowest)}\n"
        f"📈 Highest Ever: {fmt_price(highest)}\n"
        f"📊 Average Price: {fmt_price(average)}\n"
        f"{trend_emoji} Trend: {(trend or 'unknown').capitalize()}\n\n"
        f"{score_emoji(score)} *Buy Score: {score}/10*\n"
        f"💬 {ai['verdict']}\n\n"
        f"_To set alert:_\n`/setalert https://www.amazon.in/dp/{asin} <target_price>`"
    )

    if image_url:
        try:
            caption = reply if len(reply) <= 1024 else reply[:1020] + "..."
            await update.message.reply_photo(
                photo=image_url,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
            )
            await msg.delete()
        except Exception as e:
            logger.warning(f"Could not send product image: {e}")
            await msg.edit_text(reply, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
    else:
        await msg.edit_text(reply, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)


# ── /setalert ─────────────────────────────────────────────

async def cmd_setalert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Usage: `/setalert <amazon_url> <target_price>`\n\n"
            "Example:\n`/setalert https://amazon.in/dp/B0XXXXXX 49999`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    url = context.args[0].strip()
    try:
        target_price = float(context.args[1].replace(",", "").replace("₹", ""))
    except ValueError:
        await update.message.reply_text("❌ Invalid price. Use a number like `49999`.", parse_mode=ParseMode.MARKDOWN)
        return

    if target_price <= 0:
        await update.message.reply_text("❌ Target price must be greater than 0.")
        return

    user = update.effective_user
    await _log_to_channel(
        context,
        f"🔔 *New /setalert*\n"
        f"👤 {user.full_name} (`{user.id}`) @{user.username or 'N/A'}\n"
        f"🔗 {url}\n"
        f"🎯 Target: ₹{target_price:,.0f}"
    )

    msg = await update.message.reply_text("🔍 Validating product...")

    try:
        url, asin = await _resolve_and_validate(url)
    except ValueError as e:
        await msg.edit_text(f"❌ {e}")
        return

    product = db.get_product_by_asin(asin)
    if not product:
        try:
            await msg.edit_text("📡 Fetching product info...")
            amazon_data = await scrape_amazon(url)
            db.upsert_product(amazon_data["asin"], amazon_data["name"], amazon_data["url"], amazon_data["price"], amazon_data.get("image_url"))
            db.record_price(amazon_data["asin"], amazon_data["price"])
            product = db.get_product_by_asin(asin)
        except Exception as e:
            logger.error(f"Product fetch for alert failed: {e}")
            await msg.edit_text("❌ Could not fetch product info. Please try again.")
            return

    product_name = product["name"] if product else "Unknown Product"
    current_price = product["current_price"] if product else 0

    user_id = update.effective_user.id
    try:
        db.create_alert(user_id, asin, target_price)
    except Exception as e:
        logger.error(f"Alert creation failed: {e}")
        await msg.edit_text("❌ Could not create alert. Please try again.")
        return

    status_line = ""
    if current_price and current_price <= target_price:
        status_line = "\n⚠️ _Current price is already at or below your target!_"

    reply = (
        f"✅ *Alert Created!*\n\n"
        f"📦 {product_name}\n"
        f"🎯 Target Price: *{fmt_price(target_price)}*\n"
        f"💰 Current Price: {fmt_price(current_price)}\n\n"
        f"🔔 You'll be notified when the price drops to your target."
        f"{status_line}"
    )
    await msg.edit_text(reply, parse_mode=ParseMode.MARKDOWN)


# ── /myalerts ─────────────────────────────────────────────

async def cmd_myalerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        alerts = db.get_user_alerts(user_id)
    except Exception as e:
        logger.error(f"Fetch alerts failed: {e}")
        await update.message.reply_text("❌ Could not fetch your alerts. Please try again.")
        return

    if not alerts:
        await update.message.reply_text(
            "📭 You have no active alerts.\n\nUse `/setalert <url> <price>` to create one.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    lines = ["🔔 *Your Active Alerts*\n"]
    for i, alert in enumerate(alerts, 1):
        product_info = alert.get("products") or {}
        name = product_info.get("name", f"ASIN: {alert['asin']}")
        current = product_info.get("current_price")
        line = f"{i}. *{name}*\n   🎯 Target: {fmt_price(alert['target_price'])}"
        if current:
            line += f"  |  💰 Now: {fmt_price(current)}"
        lines.append(line)

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ── Admin: /stats ─────────────────────────────────────────

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only.")
        return
    try:
        stats = db.get_stats()
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
        return
    text = (
        "📊 *Bot Statistics*\n\n"
        f"📦 Total Products Tracked: {stats['products']}\n"
        f"🔔 Active Alerts: {stats['alerts']}\n"
        f"👥 Unique Users: {stats['users']}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ── Admin: /forcecheck ────────────────────────────────────

async def cmd_forcecheck(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only.")
        return
    msg = await update.message.reply_text("⚡ Running forced price check...")
    try:
        await sched_module.run_price_check()
        await msg.edit_text("✅ Forced price check completed.")
    except Exception as e:
        await msg.edit_text(f"❌ Error: {e}")


# ── Admin: /health ────────────────────────────────────────

async def cmd_health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Admin only.")
        return
    scheduler = sched_module.get_scheduler()
    sched_status = "✅ Running" if scheduler and scheduler.running else "❌ Stopped"
    text = (
        "🤖 *Bot Health*\n\n"
        f"🟢 Status: Online\n"
        f"⏰ Scheduler: {sched_status}\n"
        f"🗄️ Database: Connected"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ── Register handlers ─────────────────────────────────────

def register_handlers(app: Application):
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("track", cmd_track))
    app.add_handler(CommandHandler("setalert", cmd_setalert))
    app.add_handler(CommandHandler("myalerts", cmd_myalerts))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("forcecheck", cmd_forcecheck))
    app.add_handler(CommandHandler("health", cmd_health))
    logger.info("All command handlers registered.")