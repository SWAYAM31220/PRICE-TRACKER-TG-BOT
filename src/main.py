import asyncio
import logging
import sys
import os
from aiohttp import web
from src.bot.init import dp, bot, setup_handlers
from src.database.init_db import init_db
from src.database.connection import DatabaseManager
from src.scheduler.manager import setup_scheduler
from src.scraper.amazon import AmazonScraper
from src.services.logging_service import LoggingService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def handle_ping(request):
    return web.Response(text="pong")

async def handle_root(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/ping", handle_ping)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port_env = os.environ.get("PORT", "10000")
    try:
        port = int(port_env)
    except ValueError:
        logger.warning(f"Invalid PORT environment variable '{port_env}'. Defaulting to 10000.")
        port = 10000
    
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Web server started on port {port}")

async def on_startup():
    logger.info("Starting up...")
    
    # 1. Start web server IMMEDIATELY for Render health checks
    # This must happen first so Render detects the port is open
    await start_web_server()
    
    # 2. Initialize Database
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        # We continue so the web server stays up and we can see logs
    
    # 3. Setup Bot Handlers
    setup_handlers()
    
    # 4. Start Scheduler
    try:
        scheduler = setup_scheduler()
        scheduler.start()
        logger.info("Scheduler started.")
    except Exception as e:
        logger.error(f"Scheduler failed to start: {e}")

async def on_shutdown():
    logger.info("Shutting down...")
    await DatabaseManager.close()
    await AmazonScraper.close()
    await bot.session.close()

async def main():
    try:
        await on_startup()
        
        # Verify bot token before polling
        bot_info = await bot.get_me()
        logger.info(f"Bot authorized: @{bot_info.username}")
        
        logger.info("Bot is polling...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Critical error: {e}")
        await LoggingService.log_error("CRITICAL_SYSTEM_ERROR", str(e))
    finally:
        await on_shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped!")
