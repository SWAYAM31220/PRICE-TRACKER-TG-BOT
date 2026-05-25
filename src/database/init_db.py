import os
import logging
from src.database.connection import DatabaseManager

logger = logging.getLogger(__name__)

async def init_db():
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r") as f:
        schema_sql = f.read()
    
    try:
        await DatabaseManager.execute(schema_sql)
        logger.info("Database schema initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database schema: {e}")
        raise
