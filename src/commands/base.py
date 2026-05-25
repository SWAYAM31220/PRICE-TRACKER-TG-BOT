from aiogram import Router, types
from aiogram.filters import CommandStart
from src.services.logging_service import LoggingService

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    await LoggingService.log_new_user(message.from_user.id, message.from_user.username)
    welcome_text = (
        "👋 <b>Welcome to the Price Tracker Bot!</b>\n\n"
        "I can help you track prices on Amazon India and notify you when they drop.\n\n"
        "<b>Commands:</b>\n"
        "/track &lt;url&gt; &lt;target_price&gt; - Start tracking a product\n"
        "/mytracks - List your tracked products\n"
        "/untrack &lt;asin&gt; - Stop tracking a product\n\n"
        "Example:\n"
        "<code>/track https://www.amazon.in/dp/B0CHX1W1XY 50000</code>"
    )
    await message.answer(welcome_text)
