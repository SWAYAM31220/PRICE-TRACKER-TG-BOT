import logging
from typing import Optional
from src.config.settings import settings

logger = logging.getLogger(__name__)

class LoggingService:
    @staticmethod
    async def log_to_channel(message: str):
        if not settings.LOG_CHANNEL_ID:
            return
        
        from src.bot.init import bot
        try:
            await bot.send_message(
                chat_id=settings.LOG_CHANNEL_ID,
                text=message,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Failed to send log to channel: {e}")

    @staticmethod
    async def log_new_user(user_id: int, username: Optional[str] = None):
        msg = f"🆕 <b>New User Started</b>\nUser ID: <code>{user_id}</code>"
        if username:
            msg += f"\nUsername: @{username}"
        await LoggingService.log_to_channel(msg)

    @staticmethod
    async def log_db_op(operation: str, details: str):
        msg = f"💾 <b>Database Operation</b>\nOp: {operation}\nDetails: {details}"
        await LoggingService.log_to_channel(msg)

    @staticmethod
    async def log_price_hit(product_title: str, current_price: float, target_price: float, user_count: int):
        msg = (
            f"🎯 <b>Price Hit!</b>\n"
            f"Product: {product_title}\n"
            f"Price: ₹{current_price:,} (Target: ₹{target_price:,})\n"
            f"Users Notified: {user_count}"
        )
        await LoggingService.log_to_channel(msg)

    @staticmethod
    async def log_error(error_type: str, error_msg: str):
        msg = f"❌ <b>Error Occurred</b>\nType: {error_type}\nMsg: <code>{error_msg}</code>"
        await LoggingService.log_to_channel(msg)
