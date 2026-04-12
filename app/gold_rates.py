"""Fetch and cache live gold/silver rates in INR with Indian taxes applied.

Spot prices from Gold-API.com + India Import Duty (5%) + GST (3%)
as per Union Budget 2026.
"""

import time
import logging
import httpx

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 30 * 60
TROY_OZ_TO_GRAM = 31.1035

IMPORT_DUTY_PCT = 5.0   # Budget 2026: BCD on gold/silver
GST_PCT = 3.0            # GST on precious metals

_DUTY_MULT = (1 + IMPORT_DUTY_PCT / 100) * (1 + GST_PCT / 100)

_cache: dict = {
    "data": None,
    "fetched_at": 0.0,
}

GOLD_URL = "https://api.gold-api.com/price/XAU/INR"
SILVER_URL = "https://api.gold-api.com/price/XAG/INR"


async def _fetch_price(url: str) -> float | None:
    """Fetch a single metal price from Gold-API.com."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                return float(data.get("price", 0))
            logger.error("Gold-API returned %s: %s", resp.status_code, resp.text)
    except Exception:
        logger.error("Gold-API call failed for %s", url, exc_info=True)
    return None


def _apply_india_taxes(spot_per_gram: float) -> float:
    """Apply import duty + GST to get India retail price (before making charges)."""
    return spot_per_gram * _DUTY_MULT


def _build_rates(gold_per_oz: float, silver_per_oz: float) -> dict:
    """Convert per-troy-ounce spot prices to India retail per-gram and per-10g."""
    gold_spot = gold_per_oz / TROY_OZ_TO_GRAM
    silver_spot = silver_per_oz / TROY_OZ_TO_GRAM

    gold_india = _apply_india_taxes(gold_spot)
    silver_india = _apply_india_taxes(silver_spot)

    return {
        "gold_24k_per_gram": round(gold_india, 2),
        "gold_24k_per_10gram": round(gold_india * 10, 2),
        "gold_22k_per_gram": round(gold_india * 22 / 24, 2),
        "gold_22k_per_10gram": round(gold_india * 22 / 24 * 10, 2),
        "gold_18k_per_gram": round(gold_india * 18 / 24, 2),
        "gold_18k_per_10gram": round(gold_india * 18 / 24 * 10, 2),
        "silver_per_gram": round(silver_india, 2),
        "silver_per_kg": round(silver_india * 1000, 2),
        "import_duty_pct": IMPORT_DUTY_PCT,
        "gst_pct": GST_PCT,
        "source": "Gold-API.com + भारतीय शुल्क",
        "note": "इंपोर्ट ड्यूटी (5%) + GST (3%) शामिल। मेकिंग चार्ज अलग।",
    }


def _fallback_rates() -> dict:
    return {
        "gold_24k_per_gram": 0,
        "gold_24k_per_10gram": 0,
        "gold_22k_per_gram": 0,
        "gold_22k_per_10gram": 0,
        "gold_18k_per_gram": 0,
        "gold_18k_per_10gram": 0,
        "silver_per_gram": 0,
        "silver_per_kg": 0,
        "import_duty_pct": IMPORT_DUTY_PCT,
        "gst_pct": GST_PCT,
        "source": "unavailable",
        "note": "लाइव भाव अभी उपलब्ध नहीं हैं। कृपया दुकान पर कॉल करें।",
    }


async def get_rates() -> dict:
    """Return cached or freshly-fetched rates."""
    now = time.time()
    if _cache["data"] and (now - _cache["fetched_at"]) < CACHE_TTL_SECONDS:
        return _cache["data"]

    gold_price = await _fetch_price(GOLD_URL)
    silver_price = await _fetch_price(SILVER_URL)

    if gold_price and silver_price:
        parsed = _build_rates(gold_price, silver_price)
        _cache["data"] = parsed
        _cache["fetched_at"] = now
        return parsed

    if _cache["data"]:
        return _cache["data"]

    return _fallback_rates()


def format_rates_message(rates: dict) -> str:
    """Format rates into a beautiful Hindi message."""
    if rates["source"] == "unavailable":
        return (
            "🪙 *आज के भाव*\n\n"
            "⚠️ लाइव भाव अभी उपलब्ध नहीं हैं।\n"
            "कृपया दुकान पर संपर्क करें: शारदा ज्वेलर्स, बेमेतरा\n"
        )

    return (
        "🪙 *आज के सोने-चाँदी के भाव (भारत)*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "✨ *सोना (Gold)*\n"
        f"  24K (999):  ₹{rates['gold_24k_per_gram']:,.0f}/ग्राम  |  ₹{rates['gold_24k_per_10gram']:,.0f}/10 ग्राम\n"
        f"  22K (916):  ₹{rates['gold_22k_per_gram']:,.0f}/ग्राम  |  ₹{rates['gold_22k_per_10gram']:,.0f}/10 ग्राम\n"
        f"  18K (750):  ₹{rates['gold_18k_per_gram']:,.0f}/ग्राम  |  ₹{rates['gold_18k_per_10gram']:,.0f}/10 ग्राम\n\n"
        "🤍 *चाँदी (Silver)*\n"
        f"  999:  ₹{rates['silver_per_gram']:,.0f}/ग्राम  |  ₹{rates['silver_per_kg']:,.0f}/किलो\n\n"
        f"📋 *शुल्क विवरण:*\n"
        f"  इंपोर्ट ड्यूटी: {rates['import_duty_pct']:.0f}% | GST: {rates['gst_pct']:.0f}%\n"
        f"  मेकिंग चार्ज अलग से लगेगा\n\n"
        f"📊 स्रोत: {rates['source']}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💎 शारदा ज्वेलर्स, बेमेतरा — सन् 1971 से"
    )
