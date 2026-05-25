import logging
from typing import List, Dict, Any, Optional
from src.database.connection import DatabaseManager

logger = logging.getLogger(__name__)

class TrackingService:
    @staticmethod
    async def track_product(user_id: int, product_id: int, target_price: float):
        query = """
        INSERT INTO tracked_items (user_id, product_id, target_price)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, product_id) DO UPDATE SET
            target_price = EXCLUDED.target_price
        """
        await DatabaseManager.execute(query, user_id, product_id, target_price)

    @staticmethod
    async def untrack_product(user_id: int, product_asin: str):
        # We need to find the product ID first
        query = """
        DELETE FROM tracked_items 
        WHERE user_id = $1 AND product_id IN (
            SELECT id FROM products WHERE product_id = $2
        )
        """
        await DatabaseManager.execute(query, user_id, product_asin)

    @staticmethod
    async def get_user_tracks(user_id: int) -> List[Dict[str, Any]]:
        query = """
        SELECT p.title, p.current_price, p.product_id, t.target_price, p.url
        FROM tracked_items t
        JOIN products p ON t.product_id = p.id
        WHERE t.user_id = $1
        """
        rows = await DatabaseManager.fetch(query, user_id)
        return [dict(row) for row in rows]

    @staticmethod
    async def get_users_to_notify(product_id: int, current_price: float) -> List[int]:
        query = """
        SELECT user_id FROM tracked_items
        WHERE product_id = $1 AND target_price >= $2
        """
        rows = await DatabaseManager.fetch(query, product_id, current_price)
        return [row['user_id'] for row in rows]
