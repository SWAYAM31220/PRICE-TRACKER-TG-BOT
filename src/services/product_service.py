import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from src.database.connection import DatabaseManager
from src.config.settings import settings
from src.services.logging_service import LoggingService

logger = logging.getLogger(__name__)

class ProductService:
    @staticmethod
    async def get_product_by_platform_id(platform: str, product_id: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM products WHERE platform = $1 AND product_id = $2"
        row = await DatabaseManager.fetchrow(query, platform, product_id)
        return dict(row) if row else None

    @staticmethod
    async def save_product(data: Dict[str, Any]) -> int:
        # Upsert logic
        query = """
        INSERT INTO products (platform, product_id, url, title, image, current_price, lowest_price, highest_price, currency, last_checked)
        VALUES ($1, $2, $3, $4, $5, $6, $6, $6, $7, CURRENT_TIMESTAMP)
        ON CONFLICT (platform, product_id) DO UPDATE SET
            current_price = EXCLUDED.current_price,
            lowest_price = LEAST(products.lowest_price, EXCLUDED.current_price),
            highest_price = GREATEST(products.highest_price, EXCLUDED.current_price),
            last_checked = CURRENT_TIMESTAMP,
            title = EXCLUDED.title,
            image = EXCLUDED.image
        RETURNING id
        """
        product_id = await DatabaseManager.fetchval(
            query, 
            data['platform'], 
            data['product_id'], 
            data['url'], 
            data['title'], 
            data['image'], 
            data['price'], 
            data['currency']
        )
        
        await LoggingService.log_db_op(
            "UPSERT_PRODUCT", 
            f"ID: {product_id} | Title: {data['title'][:50]} | Price: {data['price']}"
        )
        
        # Add to price history
        await ProductService.add_price_history(product_id, data['price'])
        
        return product_id

    @staticmethod
    async def add_price_history(product_id: int, price: float):
        query = "INSERT INTO price_history (product_id, price) VALUES ($1, $2)"
        await DatabaseManager.execute(query, product_id, price)

    @staticmethod
    async def is_cache_valid(last_checked: datetime) -> bool:
        if not last_checked:
            return False
        expiry = datetime.now(last_checked.tzinfo) - timedelta(hours=settings.CACHE_EXPIRY_HOURS)
        return last_checked > expiry

    @staticmethod
    async def get_products_needing_update() -> List[Dict[str, Any]]:
        query = """
        SELECT * FROM products 
        WHERE last_checked < CURRENT_TIMESTAMP - INTERVAL '1 hour' * $1
        """
        rows = await DatabaseManager.fetch(query, settings.SCRAPE_INTERVAL_HOURS)
        return [dict(row) for row in rows]
