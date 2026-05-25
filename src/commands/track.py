import logging
from aiogram import Router, types, F
from aiogram.filters import Command, CommandObject
from src.scraper.amazon import AmazonScraper
from src.services.product_service import ProductService
from src.services.tracking_service import TrackingService
from src.services.logging_service import LoggingService

router = Router()
logger = logging.getLogger(__name__)
scraper = AmazonScraper()

@router.message(Command("track"))
async def cmd_track(message: types.Message, command: CommandObject):
    if not command.args:
        await message.answer("Please provide the Amazon URL and your target price.\nFormat: <code>/track <url> <target_price></code>")
        return

    args = command.args.split()
    if len(args) < 2:
        await message.answer("Usage: <code>/track <url> <target_price></code>")
        return

    url = args[0]
    try:
        target_price = float(args[1])
    except ValueError:
        await message.answer("Invalid target price. Please provide a number.")
        return

    asin = scraper.extract_asin(url)
    if not asin:
        await message.answer("Could not extract ASIN from the URL. Please provide a valid Amazon India product link.")
        return

    # Check cache
    product = await ProductService.get_product_by_platform_id("amazon", asin)
    
    if product and await ProductService.is_cache_valid(product['last_checked']):
        logger.info(f"Using cached data for {asin}")
    else:
        status_msg = await message.answer("🔍 Scraping product details, please wait...")
        product_data = await scraper.scrape_product(url)
        await status_msg.delete()
        
        if not product_data:
            await message.answer("❌ Failed to fetch product details. Please check the URL and try again later.")
            return
        
        product_id = await ProductService.save_product(product_data)
        product = await ProductService.get_product_by_platform_id("amazon", asin)

    await TrackingService.track_product(message.from_user.id, product['id'], target_price)
    
    await LoggingService.log_to_channel(
        f"🔔 <b>New Track Request</b>\n"
        f"User: <code>{message.from_user.id}</code>\n"
        f"ASIN: <code>{asin}</code>\n"
        f"Target: ₹{target_price:,}"
    )

    response = (
        f"✅ <b>Tracking Started!</b>\n\n"
        f"📦 <b>{product['title']}</b>\n"
        f"💰 Current Price: ₹{product['current_price']:,}\n"
        f"🎯 Your Target: ₹{target_price:,}\n\n"
        f"📉 Lowest Seen: ₹{product['lowest_price']:,}\n"
        f"📈 Highest Seen: ₹{product['highest_price']:,}"
    )
    await message.answer(response)

@router.message(Command("mytracks"))
async def cmd_mytracks(message: types.Message):
    tracks = await TrackingService.get_user_tracks(message.from_user.id)
    if not tracks:
        await message.answer("You are not tracking any products yet.")
        return

    text = "📋 <b>Your Tracked Products:</b>\n\n"
    for t in tracks:
        text += (
            f"• <a href='{t['url']}'>{t['title'][:50]}...</a>\n"
            f"  Current: ₹{t['current_price']:,} | Target: ₹{t['target_price']:,}\n"
            f"  ASIN: <code>{t['product_id']}</code>\n\n"
        )
    await message.answer(text, disable_web_page_preview=True)

@router.message(Command("untrack"))
async def cmd_untrack(message: types.Message, command: CommandObject):
    if not command.args:
        await message.answer("Please provide the ASIN of the product to untrack.\nFormat: <code>/untrack <asin></code>")
        return

    asin = command.args.strip().upper()
    await TrackingService.untrack_product(message.from_user.id, asin)
    await message.answer(f"✅ Stopped tracking product with ASIN: <code>{asin}</code>")
