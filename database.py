from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def upsert_product(asin: str, name: str, url: str, current_price: float, image_url: str = None) -> dict:
    db = get_client()
    data = {
        "asin": asin,
        "name": name,
        "url": url,
        "current_price": current_price,
        "last_checked": datetime.now(timezone.utc).isoformat(),
    }
    if image_url:
        data["image_url"] = image_url
    result = db.table("products").upsert(data, on_conflict="asin").execute()
    return result.data[0] if result.data else data


def get_all_products() -> list[dict]:
    db = get_client()
    result = db.table("products").select("*").execute()
    return result.data or []


def get_product_by_asin(asin: str) -> dict | None:
    db = get_client()
    result = db.table("products").select("*").eq("asin", asin).limit(1).execute()
    return result.data[0] if result.data else None


def update_product_price(asin: str, price: float):
    db = get_client()
    db.table("products").update({
        "current_price": price,
        "last_checked": datetime.now(timezone.utc).isoformat(),
    }).eq("asin", asin).execute()


def record_price(asin: str, price: float):
    db = get_client()
    db.table("price_history").insert({
        "asin": asin,
        "price": price,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


def get_price_history(asin: str) -> list[dict]:
    db = get_client()
    result = (
        db.table("price_history")
        .select("price, recorded_at")
        .eq("asin", asin)
        .order("recorded_at", desc=False)
        .execute()
    )
    return result.data or []


def create_alert(user_id: int, asin: str, target_price: float) -> dict:
    db = get_client()
    db.table("alerts").delete().eq("user_id", user_id).eq("asin", asin).eq("triggered", False).execute()
    data = {
        "user_id": user_id,
        "asin": asin,
        "target_price": target_price,
        "triggered": False,
    }
    result = db.table("alerts").insert(data).execute()
    return result.data[0] if result.data else data


def get_user_alerts(user_id: int) -> list[dict]:
    db = get_client()
    result = (
        db.table("alerts")
        .select("*, products(name, current_price)")
        .eq("user_id", user_id)
        .eq("triggered", False)
        .execute()
    )
    return result.data or []


def get_active_alerts_for_asin(asin: str) -> list[dict]:
    db = get_client()
    result = (
        db.table("alerts")
        .select("*")
        .eq("asin", asin)
        .eq("triggered", False)
        .execute()
    )
    return result.data or []


def mark_alert_triggered(alert_id: int):
    db = get_client()
    db.table("alerts").update({"triggered": True}).eq("id", alert_id).execute()


def get_stats() -> dict:
    db = get_client()
    products_count = len(db.table("products").select("id").execute().data or [])
    alerts_count = len(db.table("alerts").select("id").eq("triggered", False).execute().data or [])
    users_raw = db.table("alerts").select("user_id").execute().data or []
    unique_users = len({r["user_id"] for r in users_raw})
    return {"products": products_count, "alerts": alerts_count, "users": unique_users}