from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str
    LOG_CHANNEL_ID: Optional[str] = None
    DATABASE_URL: str
    SCRAPE_INTERVAL_HOURS: int = 6
    CACHE_EXPIRY_HOURS: int = 6
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
