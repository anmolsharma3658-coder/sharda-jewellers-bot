"""Fetch and cache live gold/silver rates in INR from GoldPricez API."""

import time
import logging
import httpx
from app.config import GOLD_API_KEY

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 30 * 60  # 30 minutes

_cache: dict = {
    "data": None,
    "fetched_at": 0.0,
}

GOLDPRICEZ_URL = "https://goldpricez.com/api/rates/currency/inr/measure/gram"


async def _fetch_from_api() -> dict | None:
    """Call GoldPricez API and return parsed rate data."""
    if not GOLD_API_KEY:
        logger.warning("GOLD_API_KEY not set, returning fallback rates")
        return None

    headers = {"Authorization": f"Bearer {GOLD_API_KEY}"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(GOLDPRICEZ_URL, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            logger.error("GoldPricez API returned %s: %s", resp.status_code, resp.text)
    except Exception:
        logger.error("GoldPricez API call failed", exc_info=True)
    return None


def _parse_rates(raw: dict) -> dict:
    """Extract gold and silver per-gram prices from API response."""
    try:
        gold_per_gram = float(raw.get("price_gram_24k", 0))
        silver_per_gram = float(raw.get("price_gram_silver", 0))

        return {
            "gold_24k_per_gram": round(gold_per_gram, 2),
            "gold_24k_per_10gram": round(gold_per_gram * 10, 2),
            "gold_22k_per_gram": round(gold_per_gram * 22 / 24, 2),
            "gold_22k_per_10gram": round(gold_per_gram * 22 / 24 * 10, 2),
            "gold_18k_per_gram": round(gold_per_gram * 18 / 24, 2),
            "gold_18k_per_10gram": round(gold_per_gram * 18 / 24 * 10, 2),
            "silver_per_gram": round(silver_per_gram, 2),
            "silver_per_kg": round(silver_per_gram * 1000, 2),
            "source": "GoldPricez (International)",
            "note": "ये अंतरराष्ट्रीय भाव हैं। स्थानीय भाव में मामूली फ़र्क हो सकता है।",
        }
    except (ValueError, TypeError):
        logger.error("Failed to parse rate data", exc_info=True)
        return _fallback_rates()


def _fallback_rates() -> dict:
    """Provide a helpful message when live rates are unavailable."""
    return {
        "gold_24k_per_gram": 0,
        "gold_24k_per_10gram": 0,
        "gold_22k_per_gram": 0,
        "gold_22k_per_10gram": 0,
        "gold_18k_per_gram": 0,
        "gold_18k_per_10gram": 0,
        "silver_per_gram": 0,
        "silver_per_kg": 0,
        "source": "unavailable",
        "note": "लाइव भाव अभी उपलब्ध नहीं हैं। कृपया दुकान पर कॉल करें।",
    }


async def get_rates() -> dict:
    """Return cached or freshly-fetched rates."""
    now = time.time()
    if _cache["data"] and (now - _cache["fetched_at"]) < CACHE_TTL_SECONDS:
        return _cache["data"]

    raw = await _fetch_from_api()
    if raw:
        parsed = _parse_rates(raw)
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
        "🪙 *आज के सोने-चाँदी के भाव (INR)*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "✨ *सोना (Gold)*\n"
        f"  24K (999):  ₹{rates['gold_24k_per_gram']:,.2f}/ग्राम  |  ₹{rates['gold_24k_per_10gram']:,.2f}/10 ग्राम\n"
        f"  22K (916):  ₹{rates['gold_22k_per_gram']:,.2f}/ग्राम  |  ₹{rates['gold_22k_per_10gram']:,.2f}/10 ग्राम\n"
        f"  18K (750):  ₹{rates['gold_18k_per_gram']:,.2f}/ग्राम  |  ₹{rates['gold_18k_per_10gram']:,.2f}/10 ग्राम\n\n"
        "🤍 *चाँदी (Silver)*\n"
        f"  999:  ₹{rates['silver_per_gram']:,.2f}/ग्राम  |  ₹{rates['silver_per_kg']:,.2f}/किलो\n\n"
        f"📊 स्रोत: {rates['source']}\n"
        f"📝 {rates['note']}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💎 शारदा ज्वेलर्स, बेमेतरा — सन् 1971 से"
    )
