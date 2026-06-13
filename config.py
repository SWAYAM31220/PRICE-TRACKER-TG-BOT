import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
LOG_CHANNEL_ID = os.environ.get("LOG_CHANNEL_ID", "")
PORT = int(os.environ.get("PORT", "8080"))

CHATANYWHERE_BASE_URL = "https://api.chatanywhere.tech/v1"
AI_MODEL = "gpt-3.5-turbo"

PRICE_CHECK_INTERVAL_HOURS = 6

AMAZON_DOMAINS = [
    "amazon.in",
    "www.amazon.in",
    "amzn.in",
    "amzn.to",
    "a.co",
]

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "TE": "Trailers",
}