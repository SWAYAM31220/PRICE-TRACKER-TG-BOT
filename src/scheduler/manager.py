import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.services.product_service import ProductService
from src.services.tracking_service import TrackingService
from src.scraper.amazon import AmazonScraper
from src.bot.init import bot
from src.config.settings import settings
from src.services.logging_service import LoggingService

from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

async def update_prices_task():
    logger.info("Starting background price update task...")
    products = await ProductService.get_products_needing_update()
    
    if not products:
        logger.info("No products need updating at this time.")
        return

    scraper = AmazonScraper()
    for product in products:
        try:
            logger.info(f"Updating product: {product['title']} ({product['product_id']})")
            product_data = await scraper.scrape_product(product['url'])
            
            if not product_data:
                logger.warning(f"Failed to scrape {product['url']}")
                continue

            # Save updated product and history
            await ProductService.save_product(product_data)
            
            # Check for price drops and notify users
            current_price = product_data['price']
            user_ids = await TrackingService.get_users_to_notify(product['id'], current_price)
            
            if user_ids:
                await LoggingService.log_price_hit(
                    product_data['title'], 
                    current_price, 
                    # We don't have the target price here easily without extra query, 
                    # but we can log that a hit occurred for X users
                    0.0, # Placeholder or we could fetch the min target price
                    len(user_ids)
                )

            for user_id in user_ids:
                try:
                    alert_text = (
                        f"🔥 <b>Price Drop Alert!</b>\n\n"
                        f"{product_data['title']}\n\n"
                        f"💰 Current Price: ₹{current_price:,}\n"
                        f"📉 Lowest Seen: ₹{product_data['price']:,}\n\n"
                        f"<a href='{product['url']}'>View Product</a>"
                    )
                    await bot.send_message(user_id, alert_text)
                    logger.info(f"Notification sent to user {user_id} for product {product['id']}")
                except Exception as e:
                    logger.error(f"Failed to send notification to user {user_id}: {e}")
            
            # Small delay between products to avoid being blocked
            await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"Error updating product {product['id']}: {e}")
            await LoggingService.log_error("SCHEDULER_UPDATE_ERROR", str(e))

def setup_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        update_prices_task, 
        'interval', 
        hours=settings.SCRAPE_INTERVAL_HOURS,
        next_run_time=datetime.now() + timedelta(seconds=10)
    )
    return scheduler
