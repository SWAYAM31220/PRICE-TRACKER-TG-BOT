"""
Amazon scraper: URL resolution, ASIN extraction, price scraping,
and price history via PriceHistory.app / DB fallback.
"""

import re
import logging
import random
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]


def _random_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-IN,en-GB;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }


# ── URL Resolver ──────────────────────────────────────────

async def resolve_url(url: str) -> str:
    async with httpx.AsyncClient(follow_redirects=True, timeout=15, headers=_random_headers()) as client:
        resp = await client.head(url)
        final = str(resp.url)
        if not is_amazon_url(final):
            resp = await client.get(url)
            final = str(resp.url)
    return final


def is_amazon_url(url: str) -> bool:
    return bool(re.search(r"amazon\.(in|com|co\.uk|de|fr|es|it|ca|com\.au)", url))


# ── ASIN Extractor ────────────────────────────────────────

ASIN_PATTERNS = [
    r"/dp/([A-Z0-9]{10})",
    r"/gp/product/([A-Z0-9]{10})",
    r"/product/([A-Z0-9]{10})",
    r"asin=([A-Z0-9]{10})",
    r"/([A-Z0-9]{10})(?:[/?]|$)",
]


def extract_asin(url: str) -> str | None:
    for pattern in ASIN_PATTERNS:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


# ── Amazon Price Scraper ──────────────────────────────────

async def scrape_amazon(url: str) -> dict:
    asin = extract_asin(url)
    if not asin:
        raise ValueError(f"Could not extract ASIN from URL: {url}")

    canonical = f"https://www.amazon.in/dp/{asin}"

    async with httpx.AsyncClient(follow_redirects=True, timeout=20, headers=_random_headers()) as client:
        resp = await client.get(canonical)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")

    # Product name
    name = None
    for sel in ["#productTitle", "#title", "h1.a-size-large"]:
        tag = soup.select_one(sel)
        if tag:
            name = tag.get_text(strip=True)
            break
    name = name or "Unknown Product"

    # Product price
    price = None
    price_selectors = [
        "span.a-price.aok-align-center span.a-offscreen",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
        "#priceblock_saleprice",
        "span#price_inside_buybox",
        ".a-price .a-offscreen",
        "#corePrice_feature_div span.a-offscreen",
        "#apex_offerDisplay_desktop span.a-offscreen",
        "#buyNewSection span.a-offscreen",
        "span.priceToPay span.a-offscreen",
    ]
    for sel in price_selectors:
        tag = soup.select_one(sel)
        if tag:
            raw = tag.get_text(strip=True)
            price = _parse_price(raw)
            if price:
                break

    if not price:
        raise ValueError(f"Could not find price for ASIN {asin}.")

    # Product image
    image_url = None
    img_selectors = [
        "#landingImage",
        "#imgBlkFront",
        "#main-image",
        "img#ebooksImgBlkFront",
        ".a-dynamic-image",
    ]
    for sel in img_selectors:
        tag = soup.select_one(sel)
        if tag:
            image_url = tag.get("data-old-hires") or tag.get("data-src") or tag.get("src")
            if image_url and image_url.startswith("http"):
                break

    return {"name": name, "price": price, "asin": asin, "url": canonical, "image_url": image_url}


def _parse_price(text: str) -> float | None:
    cleaned = re.sub(r"[^\d.,]", "", text).replace(",", "")
    try:
        val = float(cleaned)
        return val if val > 0 else None
    except ValueError:
        return None


def _extract_from_meta(desc: str, pattern: str) -> float | None:
    m = re.search(pattern, desc)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


# ── Historical Price Data ─────────────────────────────────

async def scrape_camel(asin: str) -> dict:
    """
    1. PriceHistory.app — POST /api/search (reverse engineered)
    2. DB price_history fallback
    """

    # ── 1. PriceHistory.app ───────────────────────────────
    try:
        amazon_url = f"https://www.amazon.in/dp/{asin}"

        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            # Get slug via undocumented API
            resp = await client.post(
                "https://pricehistory.app/api/search",
                json={"url": amazon_url},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            resp.raise_for_status()
            data = resp.json()

            if not data.get("status"):
                raise Exception(f"Product not found on PriceHistory.app")

            slug = data["code"]
            logger.info(f"PriceHistory.app slug for {asin}: {slug}")

            # Fetch product page
            product_url = f"https://pricehistory.app/p/{slug}"
            resp = await client.get(product_url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()

        # Parse meta description for prices
        soup = BeautifulSoup(resp.text, "html.parser")
        meta = soup.find("meta", {"name": "description"})

        if not meta:
            raise Exception("Meta description not found")

        desc = meta.get("content", "")
        logger.info(f"PriceHistory.app meta: {desc[:120]}")

        lowest  = _extract_from_meta(desc, r"Lowest Price:\s*₹([\d,]+)")
        highest = _extract_from_meta(desc, r"Highest Price:\s*₹([\d,]+)")
        average = _extract_from_meta(desc, r"Average Price:\s*₹([\d,]+)")

        if lowest or highest or average:
            trend = "stable"
            if lowest and highest and highest > lowest:
                mid = (lowest + highest) / 2
                if lowest < mid * 0.95:
                    trend = "falling"
                elif highest > mid * 1.05:
                    trend = "rising"
            logger.info(f"PriceHistory.app OK for {asin}: low={lowest} high={highest} avg={average}")
            return {"lowest": lowest, "highest": highest, "average": average, "trend": trend}
        else:
            raise Exception("No prices found in meta description")

    except Exception as e:
        logger.warning(f"PriceHistory.app failed for {asin}: {e}")

    # ── 2. DB price_history fallback ──────────────────────
    try:
        import database as db
        history = db.get_price_history(asin)
        if len(history) >= 2:
            prices = [h["price"] for h in history]
            lowest  = min(prices)
            highest = max(prices)
            average = round(sum(prices) / len(prices), 2)
            trend   = "falling" if prices[-1] < prices[-2] else ("rising" if prices[-1] > prices[-2] else "stable")
            logger.info(f"DB history for {asin}: {len(prices)} records")
            return {"lowest": lowest, "highest": highest, "average": average, "trend": trend}
    except Exception as e:
        logger.warning(f"DB history fallback failed: {e}")

    return {"lowest": None, "highest": None, "average": None, "trend": "unknown"}


# ── Full Product Data ─────────────────────────────────────

async def get_full_product_data(url: str) -> dict:
    if any(d in url for d in ["amzn.in", "amzn.to", "a.co"]):
        url = await resolve_url(url)
    amazon_data = await scrape_amazon(url)
    camel_data = await scrape_camel(amazon_data["asin"])
    return {**amazon_data, **camel_data}