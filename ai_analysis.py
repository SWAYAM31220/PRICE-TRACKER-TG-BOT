import logging
from openai import AsyncOpenAI
from config import OPENAI_API_KEY, CHATANYWHERE_BASE_URL, AI_MODEL

logger = logging.getLogger(__name__)

_client = None


def get_client():
    global _client

    if _client is None:
        _client = AsyncOpenAI(
            api_key=OPENAI_API_KEY,
            base_url=CHATANYWHERE_BASE_URL,
        )

    return _client


def fmt(v):
    if v is None:
        return "N/A"
    return f"₹{v:,.0f}"


def calculate_score(
    current_price: float,
    lowest_ever: float | None,
    average_price: float | None,
):
    if average_price is None:
        return 5, "NEUTRAL"

    # Near historical low
    if lowest_ever and current_price <= lowest_ever * 1.05:
        return 9, "BUY"

    # Much cheaper than average
    if current_price <= average_price * 0.90:
        return 8, "BUY"

    # Slightly cheaper than average
    if current_price <= average_price * 0.97:
        return 7, "BUY"

    # Around average
    if current_price <= average_price * 1.03:
        return 5, "NEUTRAL"

    # Above average
    if current_price <= average_price * 1.10:
        return 4, "WAIT"

    # Way above average
    return 2, "WAIT"


def fallback_verdict(
    decision: str,
    current_price: float,
    average_price: float | None,
):
    if decision == "BUY":
        return "Current price looks attractive compared to historical pricing."

    if decision == "WAIT":
        if average_price:
            diff = current_price - average_price
            return (
                f"Current price is ₹{diff:,.0f} above the historical average. "
                f"Waiting for a discount may be worthwhile."
            )
        return "Current price appears expensive compared to historical pricing."

    return "Price is close to historical average levels."


async def get_buy_recommendation(
    product_name: str,
    current_price: float,
    lowest_ever: float | None,
    highest_ever: float | None,
    average_price: float | None,
    trend: str = "unknown",
):
    score, decision = calculate_score(
        current_price,
        lowest_ever,
        average_price,
    )

    try:
        client = get_client()

        prompt = f"""
You are an Amazon India shopping expert.

Product: {product_name}

Current Price: {fmt(current_price)}
Lowest Ever Price: {fmt(lowest_ever)}
Highest Ever Price: {fmt(highest_ever)}
Average Price: {fmt(average_price)}
Trend: {trend}

Decision already made:
{decision}

Score:
{score}/10

Write ONE short sentence explaining the decision.
Maximum 20 words.
No emojis.
No score.
"""

        response = await client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0.2,
            max_tokens=50,
        )

        verdict = response.choices[0].message.content.strip()

        logger.info(
            f"AI Analysis => score={score}, decision={decision}, verdict={verdict}"
        )

        return {
            "score": score,
            "verdict": verdict,
        }

    except Exception as e:
        logger.error(f"AI analysis failed: {e}")

        return {
            "score": score,
            "verdict": fallback_verdict(
                decision,
                current_price,
                average_price,
            ),
        }