"""Rough jewellery cost estimate using live gold rates + making + sale GST + discount.

Metal ₹/g from gold_rates already includes import duty + GST on landed bullion (per app/gold_rates.py).
Making: configurable % of (gross weight × 24K ₹/g) — default 11%.
Additional sale GST: configurable % on (metal + making − discount) — default 3% (B2C estimate).
Final bill may differ; hallmarks, stones, and store policy apply.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.config import JEWELLERY_MAKING_PCT_ON_24K, JEWELLERY_SALE_GST_PCT
from app.gold_rates import get_rates

logger = logging.getLogger(__name__)

_QUOTE_TAG_INNER = re.compile(
    r"\[JEWELLERY_QUOTE\](.*?)\[/JEWELLERY_QUOTE\]",
    re.IGNORECASE | re.DOTALL,
)

# quote 12 22 | quote 12.5 22 5  (5% discount) | estimate 10 18
_QUOTE_CMD = re.compile(
    r"^\s*(?:quote|estimate|कोट|अनुमान)\s*[:\s]\s*"
    r"(\d+(?:\.\d+)?)\s*g?\s+(\d{1,2})\s*k?"
    r"(?:\s+(\d+(?:\.\d+)?)\s*%?)?\s*$",
    re.IGNORECASE,
)


@dataclass
class QuoteParams:
    weight_grams: float
    purity_karat: int
    discount_percent: float = 0.0


def parse_quote_command(text: str) -> QuoteParams | None:
    """Parse 'quote: 10 22' / 'estimate 12.5 22 5' style messages."""
    m = _QUOTE_CMD.match((text or "").strip())
    if not m:
        return None
    w = float(m.group(1))
    k = int(m.group(2))
    d = float(m.group(3)) if m.group(3) else 0.0
    if w <= 0 or w > 10_000 or k not in (24, 22, 18, 14) or d < 0 or d > 90:
        return None
    return QuoteParams(weight_grams=w, purity_karat=k, discount_percent=d)


def parse_quote_tag_inner(inner: str) -> QuoteParams | None:
    """Parse 'weight=12 karat=22 discount=5' from model tag body."""
    raw = (inner or "").strip()
    if not raw:
        return None
    parts = re.split(r"[\s,;]+", raw)
    kv: dict[str, str] = {}
    for p in parts:
        if "=" in p:
            a, b = p.split("=", 1)
            kv[a.strip().lower()] = b.strip().lower()
    try:
        w_str = kv.get("weight") or kv.get("w") or kv.get("grams")
        if not w_str:
            return None
        w = float(re.sub(r"[^\d.]", "", w_str))
        k_str = kv.get("karat") or kv.get("k") or kv.get("purity") or "22"
        k = int(re.sub(r"[^\d]", "", k_str))
        if k not in (24, 22, 18, 14):
            k = 22
        d = float(kv.get("discount") or kv.get("d") or "0")
        d = max(0.0, min(90.0, d))
        if w <= 0 or w > 10_000:
            return None
        return QuoteParams(weight_grams=w, purity_karat=k, discount_percent=d)
    except (TypeError, ValueError):
        return None


def strip_quote_tag(reply_text: str) -> tuple[str, str | None]:
    """Remove [JEWELLERY_QUOTE]...[/JEWELLERY_QUOTE]; return (cleaned, inner or None)."""
    m = _QUOTE_TAG_INNER.search(reply_text or "")
    if not m:
        return reply_text or "", None
    inner = m.group(1).strip()
    cleaned = (reply_text[: m.start()] + reply_text[m.end() :]).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned, inner


def gold_rate_per_gram_for_karat(rates: dict, karat: int) -> float:
    if karat == 24:
        return float(rates.get("gold_24k_per_gram") or 0)
    if karat == 22:
        return float(rates.get("gold_22k_per_gram") or 0)
    if karat == 18:
        return float(rates.get("gold_18k_per_gram") or 0)
    # 14K etc.
    base = float(rates.get("gold_24k_per_gram") or 0)
    return round(base * karat / 24, 2)


def compute_breakdown(
    rates: dict,
    p: QuoteParams,
    making_pct: float = JEWELLERY_MAKING_PCT_ON_24K,
    sale_gst_pct: float = JEWELLERY_SALE_GST_PCT,
) -> dict | None:
    if rates.get("source") == "unavailable":
        return None
    p24 = float(rates.get("gold_24k_per_gram") or 0)
    if p24 <= 0:
        return None
    p_metal = gold_rate_per_gram_for_karat(rates, p.purity_karat)
    gold_value = round(p.weight_grams * p_metal, 2)
    making = round((making_pct / 100.0) * p.weight_grams * p24, 2)
    subtotal = round(gold_value + making, 2)
    discount_amt = round(subtotal * (p.discount_percent / 100.0), 2)
    after_discount = round(subtotal - discount_amt, 2)
    if after_discount < 0:
        after_discount = 0.0
    sale_gst = round(after_discount * (sale_gst_pct / 100.0), 2)
    grand_total = round(after_discount + sale_gst, 2)
    return {
        "weight_g": p.weight_grams,
        "karat": p.purity_karat,
        "gold_per_gram": p_metal,
        "gold_value": gold_value,
        "making_pct": making_pct,
        "making_amount": making,
        "subtotal": subtotal,
        "discount_pct": p.discount_percent,
        "discount_amount": discount_amt,
        "after_discount": after_discount,
        "sale_gst_pct": sale_gst_pct,
        "sale_gst_amount": sale_gst,
        "grand_total": grand_total,
        "import_duty_pct": rates.get("import_duty_pct", 5),
        "metal_gst_note_pct": rates.get("gst_pct", 3),
    }


def format_quote_whatsapp(b: dict, lang: str) -> str:
    k = int(b["karat"])
    duty = b["import_duty_pct"]
    mnote = b["metal_gst_note_pct"]

    if lang == "en":
        disc_line = ""
        if b["discount_pct"] > 0:
            disc_line = (
                f"🎁 Discount ({b['discount_pct']:.1f}% on gold+making): −₹{b['discount_amount']:,.0f}\n"
                f"   After discount: ₹{b['after_discount']:,.0f}\n"
            )
        return (
            "🧮 *Estimated quote (today’s live rates)*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"⚖️ Weight: *{b['weight_g']:.2f} g*  |  Purity: *{k}K*\n"
            f"🪙 Gold value @ ₹{b['gold_per_gram']:,.0f}/g: ₹{b['gold_value']:,.0f}\n"
            f"   _(Metal rate includes ~{duty:.0f}% import duty + {mnote:.0f}% GST on landed bullion — per our rate feed.)_\n"
            f"🔧 Making ({b['making_pct']:.0f}% of 24K gold value): ₹{b['making_amount']:,.0f}\n"
            f"📊 Subtotal (gold + making): ₹{b['subtotal']:,.0f}\n"
            f"{disc_line}"
            f"🧾 Sale GST (~{b['sale_gst_pct']:.0f}% on above): ₹{b['sale_gst_amount']:,.0f}\n"
            f"💰 *Indicative total: ₹{b['grand_total']:,.0f}*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ *Indicative only* — stones, hallmark, wastage rules, and final discount are decided at the store. "
            "Visit or call Sharda Jewellers, Bemetara."
        )

    if lang == "hinglish":
        disc_line = ""
        if b["discount_pct"] > 0:
            disc_line = (
                f"🎁 Discount ({b['discount_pct']:.1f}% on gold+making): −₹{b['discount_amount']:,.0f}\n"
                f"   Discount ke baad: ₹{b['after_discount']:,.0f}\n"
            )
        return (
            "🧮 *Estimated quote (aaj ke live rates)*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"⚖️ Weight: *{b['weight_g']:.2f} g*  |  Purity: *{k}K*\n"
            f"🪙 Gold value @ ₹{b['gold_per_gram']:,.0f}/g: ₹{b['gold_value']:,.0f}\n"
            f"   _(Metal rate mein ~{duty:.0f}% import duty + {mnote:.0f}% GST shamil — hamare rate feed ke hisaab.)_\n"
            f"🔧 Making ({b['making_pct']:.0f}% of 24K gold value): ₹{b['making_amount']:,.0f}\n"
            f"📊 Subtotal (gold + making): ₹{b['subtotal']:,.0f}\n"
            f"{disc_line}"
            f"🧾 Sale GST (~{b['sale_gst_pct']:.0f}%): ₹{b['sale_gst_amount']:,.0f}\n"
            f"💰 *Indicative total: ₹{b['grand_total']:,.0f}*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ *Sirf estimate* — stone, hallmark, wastage, final discount dukaan par. "
            "Sharda Jewellers Bemetara — call / visit."
        )

    disc_line = ""
    if b["discount_pct"] > 0:
        disc_line = (
            f"🎁 छूट ({b['discount_pct']:.1f}% सोना+मेकिंग पर): −₹{b['discount_amount']:,.0f}\n"
            f"   छूट के बाद: ₹{b['after_discount']:,.0f}\n"
        )
    return (
        "🧮 *अनुमानित कोट (आज के लाइव भाव)*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"⚖️ वज़न: *{b['weight_g']:.2f} ग्राम*  |  शुद्धता: *{k}K*\n"
        f"🪙 सोने का मूल्य @ ₹{b['gold_per_gram']:,.0f}/ग्राम: ₹{b['gold_value']:,.0f}\n"
        f"   _(धातु दर में ~{duty:.0f}% इंपोर्ट ड्यूटी + {mnote:.0f}% GST शामिल — हमारे भाव स्रोत के अनुसार।)_\n"
        f"🔧 मेकिंग ({b['making_pct']:.0f}% 24K सोने के मूल्य पर): ₹{b['making_amount']:,.0f}\n"
        f"📊 उप-योग (सोना + मेकिंग): ₹{b['subtotal']:,.0f}\n"
        f"{disc_line}"
        f"🧾 बिक्री GST (~{b['sale_gst_pct']:.0f}%): ₹{b['sale_gst_amount']:,.0f}\n"
        f"💰 *संकेतक कुल: ₹{b['grand_total']:,.0f}*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ *केवल अनुमान* — रत्न, हॉलमार्क, बेस्टेज व अंतिम छूट दुकान पर तय। "
        "शारदा ज्वेलर्स, बेमेतरा — कॉल / विज़िट।"
    )


async def build_quote_for_params(lang: str, params: QuoteParams) -> str | None:
    rates = await get_rates()
    b = compute_breakdown(rates, params)
    if not b:
        if lang == "en":
            return "⚠️ Live gold rates are not available right now — please call Sharda Jewellers for a quote."
        if lang == "hinglish":
            return "⚠️ Abhi live gold rate nahi mil raha — quote ke liye Sharda Jewellers ko call karo."
        return "⚠️ अभी लाइव सोने का भाव उपलब्ध नहीं — कोट के लिए शारदा ज्वेलर्स पर कॉल करें।"
    return format_quote_whatsapp(b, lang)
