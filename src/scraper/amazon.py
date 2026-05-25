import re
import logging
import asyncio
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from src.scraper.base import BaseScraper

logger = logging.getLogger(__name__)

class AmazonScraper(BaseScraper):
    _browser: Optional[Browser] = None
    _playwright = None

    @classmethod
    async def get_browser(cls) -> Browser:
        if cls._browser is None:
            cls._playwright = await async_playwright().start()
            cls._browser = await cls._playwright.chromium.launch(headless=True)
            logger.info("Playwright browser launched.")
        return cls._browser

    @classmethod
    async def close(cls):
        if cls._browser:
            await cls._browser.close()
            await cls._playwright.stop()
            cls._browser = None
            cls._playwright = None
            logger.info("Playwright browser closed.")

    @staticmethod
    def extract_asin(url: str) -> Optional[str]:
        # Support /dp/ASIN and /gp/product/ASIN
        patterns = [
            r'/dp/([A-Z0-9]{10})',
            r'/gp/product/([A-Z0-9]{10})',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    async def scrape_product(self, url: str) -> Optional[Dict[str, Any]]:
        browser = await AmazonScraper.get_browser()
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            # Add timeout and wait for network idle
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # Extract ASIN from URL if not already known
            asin = self.extract_asin(url)
            
            # Robust selectors for title
            title = await self._get_text(page, ["#productTitle", ".qa-title-text"])
            
            # Robust selectors for price
            # Amazon India often uses .a-price-whole
            price_str = await self._get_text(page, [
                ".a-price-whole", 
                "#priceblock_ourprice", 
                "#priceblock_dealprice",
                ".a-offscreen"
            ])
            
            # Clean price string
            price = self._parse_price(price_str)
            
            # Image selector
            image = await page.eval_on_selector("#landingImage", "el => el.src")
            
            if not title or price is None:
                logger.warning(f"Failed to extract essential data for {url}")
                return None

            return {
                "platform": "amazon",
                "product_id": asin,
                "url": url,
                "title": title.strip(),
                "price": price,
                "image": image,
                "currency": "INR"
            }

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None
        finally:
            await page.close()
            await context.close()

    async def _get_text(self, page: Page, selectors: list) -> Optional[str]:
        for selector in selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=5000)
                if element:
                    return await element.inner_text()
            except:
                continue
        return None

    def _parse_price(self, price_str: Optional[str]) -> Optional[float]:
        if not price_str:
            return None
        # Remove currency symbols, commas, and whitespace
        clean_price = re.sub(r'[^\d.]', '', price_str)
        try:
            return float(clean_price)
        except ValueError:
            return None
