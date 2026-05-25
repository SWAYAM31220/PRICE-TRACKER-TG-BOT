from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class BaseScraper(ABC):
    @abstractmethod
    async def scrape_product(self, url: str) -> Optional[Dict[str, Any]]:
        pass

    @staticmethod
    @abstractmethod
    def extract_asin(url: str) -> Optional[str]:
        pass
