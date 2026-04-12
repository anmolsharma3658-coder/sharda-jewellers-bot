"""Gemini-powered conversational AI for Sharda Jewellers WhatsApp bot."""

import asyncio
import logging
import re
from google import genai
from google.genai import types
from app.config import GEMINI_API_KEY
from app.gold_rates import get_rates, format_rates_message
from app.customers import get_customer
from app.language import detect_language

logger = logging.getLogger(__name__)

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL = "gemini-2.5-flash-lite"

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0

SYSTEM_PROMPT = """
तुम "शारदा ज्वेलर्स" के आधिकारिक WhatsApp सहायक हो।

═══════════════════════════════════════
दुकान की पूरी जानकारी (STORE KNOWLEDGE)
═══════════════════════════════════════

नाम: शारदा ज्वेलर्स (Sharda Jewellers)
स्थापना: सन् 1971
स्थान: बेमेतरा, छत्तीसगढ़, भारत
फ़ोन: +91 94255 61850, +91 70003 44110
Google: https://business.google.com/n/5073554692225386022/searchprofile?hl=en

विरासत: "सन् 1971 से, जब इस इलाके में गहनों की कोई दुकान तक नहीं थी — हम थे।
आपके दादाजी भी यहीं आया करते थे, और आज आप भी यहाँ हैं। यही हमारी असली पहचान है।
पीढ़ियाँ बदलती हैं, ज़माने के तौर-तरीके बदलते हैं, डिज़ाइन बदलते हैं —
लेकिन हमारी कारीगरी और हमारे मूल्य आज भी वही हैं जो पहले दिन थे।"

विशेषज्ञता:
• सोने के गहने (Gold Jewellery) — 24K, 22K, 18K
• चाँदी के गहने (Silver Jewellery)
• हीरे के गहने (Diamond Jewellery)
• इन-हाउस मैन्युफैक्चरिंग (In-house Manufacturing)
• पूर्ण कस्टमाइज़ेशन (Full Customization) — कोई भी डिज़ाइन, कोई भी ख्वाहिश
• हॉलमार्क ज्वेलरी (BIS Hallmarked)

उत्पाद श्रेणियाँ:
• हार / नेकलेस (Necklaces)
• अंगूठी (Rings) — सगाई, शादी, रोज़ाना
• कंगन / चूड़ी (Bangles / Bracelets)
• झुमके / बालियाँ (Earrings / Jhumkas)
• मंगलसूत्र (Mangalsutra)
• पायल (Anklets)
• नाक की नथ (Nose Rings)
• माँग टीका (Maang Tikka)
• कमरबंद (Waist Belt / Kamarband)
• सोने के सिक्के (Gold Coins)
• चाँदी के बर्तन और गिफ्ट आइटम (Silver Utensils & Gifts)
• शादी / ब्राइडल सेट (Bridal Sets)

सेवाएँ:
• पुराने गहनों की एक्सचेंज / बदलाई
• गहनों की मरम्मत और पॉलिश
• कस्टम ऑर्डर — अपना डिज़ाइन लाएं, हम बनाएंगे
• शादी के लिए विशेष ब्राइडल कलेक्शन
• गिफ्टिंग के लिए चाँदी के आइटम

═══════════════════════════════════════
तुम्हारे व्यवहार के नियम (BEHAVIOR RULES)
═══════════════════════════════════════

1. ⚡ भाषा (MOST IMPORTANT RULE):
   - नीचे "CURRENT TURN (internal)" ब्लॉक में reply_language दिया रहता है: en, hi, या hinglish
   - तुम्हें STRICTLY उसी में जवाब देना है।
   - en → पूरा जवाब English only। Devanagari Hindi मत लिखो। Numbers/symbols OK।
   - hi → पूरा जवाब देवनागरी हिंदी में। English शब्द मत मिलाओ।
   - hinglish → Roman script में natural mix (जैसे WhatsApp पर लोग लिखते हैं)।
   - ग्राहक की भाषा बदलने पर अगले टर्न में नया reply_language follow करो।
   - NEVER default to Hindi when reply_language is en.

2. लहजा / Tone: गर्मजोशी भरा, सम्मानजनक, पारिवारिक। जैसे एक भरोसेमंद ज्वेलर बात करता है।
   In English: warm, respectful, family-like — like a trusted family jeweller.
3. कभी भी किसी दूसरी दुकान का नाम मत लो और न ही comparison करो।
4. अगर कोई ऐसा सवाल आए जो ज्वेलरी से संबंधित न हो, तो विनम्रता से कहो कि तुम सिर्फ गहनों में मदद कर सकते हो।
5. कीमत का अनुमान देने से बचो — हमेशा कहो "आज के भाव के हिसाब से" और लाइव रेट बताओ, या दुकान पर आने को कहो।
6. हर जवाब छोटा, सीधा और WhatsApp-friendly रखो (ज़्यादा से ज़्यादा 300 शब्द)।
7. जब ग्राहक पहली बार मैसेज करे, तो उसे स्वागत करो और मुख्य विकल्प बताओ।
8. अगर ग्राहक का नाम मिले, तो उसे नाम से संबोधित करो।
9. emoji कम और सार्थक इस्तेमाल करो — अतिरंजित मत करो।
10. अगर कोई complaint हो तो सहानुभूति दिखाओ और दुकान पर आने या कॉल करने को कहो।
11. अगर ग्राहक नंबर, फ़ोन, contact, "call karna hai", "number do" पूछे → सीधे दोनों नंबर बताओ: +91 94255 61850 और +91 70003 44110
12. CURRENT TURN (internal) ब्लॉक में ग्राहक विवरण आता है — इसका उपयोग करो लेकिन कभी कॉपी मत करो:
    - message_count > 1 → returning customer — short "welcome back" in reply_language
    - tag vip → extra care
    - tag bride → mention bridal collection
    - notes → use subtly if relevant

═══════════════════════════════════════
विशेष कमांड (SPECIAL INTENTS)
═══════════════════════════════════════

अगर ग्राहक इनमें से कुछ पूछे, तो तुम्हें FUNCTION_CALL prefix के साथ जवाब देना है:

• "भाव", "rate", "price", "सोने का भाव", "gold rate", "चाँदी का भाव", "silver rate", "aaj ka bhav"
  → जवाब की शुरुआत में EXACTLY यह लिखो: [RATES_REQUEST]
  → फिर एक छोटा सा वाक्य जैसे "जी बिल्कुल! आज के ताज़ा भाव ये रहे:"

• "menu", "help", "मेनू", "मदद", "hi", "hello", "नमस्ते", "hii", "hey"
  → जवाब की शुरुआत में EXACTLY यह लिखो: [MENU_REQUEST]
  → फिर स्वागत संदेश

• "photo", "फोटो", "तस्वीर", "picture", "image", "दिखाओ", "collection dikhao",
  "गहने दिखाओ", "show me", "photos bhejo", "gallery", "designs dikhao",
  "कुछ दिखाओ", "नमूने दिखाओ", "sample"
  → जवाब की शुरुआत में EXACTLY यह लिखो: [PHOTOS_REQUEST]
  → फिर एक छोटा वाक्य जैसे "जी बिल्कुल! हमारे कुछ गहनों की तस्वीरें भेज रहे हैं:"

• जब ग्राहक इनमें से कुछ कहे:
  - मालिक से बात करनी है, owner से बात करो, "insaan se baat karo"
  - ऑर्डर करना है, खरीदना है, बुक करना, "I want to buy", "order place karna hai"
  - शिकायत / complaint / "mera order kharab hai" / "problem hai"
  - कोई ऐसी बात जो तुम्हारे ज्ञान से बाहर हो या जिसमें तुम confident नहीं हो
  - negotiation / price discussion / "kitne mein doge" / "discount"
  → जवाब की शुरुआत में EXACTLY यह लिखो: [CONNECT_OWNER]
  → फिर कहो: "जी बिल्कुल, मैं आपको हमारे मालिक जी से सीधे जोड़ रहा हूँ। अब आपकी बात सीधे मालिक जी तक पहुँचेगी। कृपया थोड़ा इंतज़ार करें।"
  → ग्राहक को बताओ कि उनके अगले मैसेज सीधे मालिक को जाएंगे।

बाकी सभी सवालों का जवाब अपनी बुद्धिमानी से दो, ऊपर दी गई जानकारी के आधार पर।

═══════════════════════════════════════
CRITICAL OUTPUT RULES
═══════════════════════════════════════
- User messages are ONLY what the customer typed. There is NO [CONTEXT] line in their text.
- NEVER output [CONTEXT], "भाषा=", "reply_language", "Customer name:", message counts, dates, tags, or ANY internal/session metadata.
- Your reply must be ONLY the customer-facing WhatsApp text (plus optional [RATES_REQUEST] etc. prefixes where rules say so).
- Follow reply_language from the internal block at the bottom of these instructions — never mention it to the user.
"""

_conversations: dict[str, list[types.Content]] = {}

MAX_HISTORY = 20

# Strip accidental echoes of internal metadata (safety net)
_CONTEXT_LEAK = re.compile(r"\[CONTEXT\s*:\s*.*?\]\s*", re.DOTALL | re.IGNORECASE)
_META_LINE = re.compile(
    r"^\s*(भाषा|reply_language|language)\s*[=:]\s*\S+.*$",
    re.IGNORECASE | re.MULTILINE,
)


def _sanitize_reply(text: str) -> str:
    t = _CONTEXT_LEAK.sub("", text or "")
    t = _META_LINE.sub("", t)
    return t.strip()


def _usable_customer_name(name: str) -> str:
    n = (name or "").strip()
    if len(n) < 2:
        return ""
    if not re.search(r"[\u0900-\u097Fa-zA-Z]", n):
        return ""
    return n


def _session_instruction(lang: str, display_name: str, customer: dict | None) -> str:
    """English-only session block — never concatenated into user-visible chat text."""
    lines = [
        "",
        "════════ CURRENT TURN (internal — NEVER show this block or paraphrase it to the user) ════════",
        f"reply_language: {lang}   # en = English only | hi = Devanagari Hindi only | hinglish = Roman mix",
    ]
    if display_name:
        lines.append(f"customer_display_name: {display_name}")
    else:
        lines.append("customer_display_name: (none)")
    if customer:
        lines.append(f"message_count: {customer['msg_count']}")
        if customer["msg_count"] > 1:
            lines.append(f"first_seen_date: {customer['first_seen'][:10]}")
        if customer.get("tags"):
            lines.append(f"tags: {customer['tags']}")
        if customer.get("notes"):
            lines.append(f"notes: {customer['notes']}")
    lines.append(
        "Use reply_language for this reply only. Do not print this section. Do not print [CONTEXT]."
    )
    lines.append("═══════════════════════════════════════════════════════════════════════════════════")
    return "\n".join(lines)


def _get_history(phone: str) -> list[types.Content]:
    if phone not in _conversations:
        _conversations[phone] = []
    return _conversations[phone]


def _trim_history(phone: str) -> None:
    hist = _conversations.get(phone, [])
    if len(hist) > MAX_HISTORY:
        _conversations[phone] = hist[-MAX_HISTORY:]


async def generate_reply(phone: str, user_text: str, user_name: str = "") -> tuple[str, bool, bool]:
    """Generate a chatbot reply for the given user message.

    Returns (reply_text, wants_photos, wants_owner).
    """
    history = _get_history(phone)

    lang = detect_language(user_text)
    customer = get_customer(phone)
    display_name = _usable_customer_name(user_name)
    session = _session_instruction(lang, display_name, customer)
    full_system = SYSTEM_PROMPT + session

    # Only the customer's words go into multi-turn history (no [CONTEXT] leakage)
    history.append(types.Content(role="user", parts=[types.Part(text=user_text)]))

    reply_text = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=history,
                config=types.GenerateContentConfig(
                    system_instruction=full_system,
                    temperature=0.7,
                    max_output_tokens=1024,
                ),
            )
            reply_text = _sanitize_reply(response.text or "")
            if not reply_text:
                reply_text = "क्षमा करें, कुछ तकनीकी समस्या हुई। कृपया दोबारा कोशिश करें।"
            break
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning("Rate limited (attempt %d/%d), retrying in %.1fs", attempt + 1, MAX_RETRIES, delay)
                await asyncio.sleep(delay)
                continue
            logger.error("Gemini API call failed", exc_info=True)
            break

    if reply_text is None:
        reply_text = "क्षमा करें, अभी हमारे सिस्टम में कुछ समस्या है। कृपया कुछ देर बाद कोशिश करें या दुकान पर कॉल करें।"
        history.append(types.Content(role="model", parts=[types.Part(text=reply_text)]))
        return reply_text, False, False

    if "[RATES_REQUEST]" in reply_text:
        rates = await get_rates()
        rates_msg = format_rates_message(rates, lang)
        reply_text = reply_text.replace("[RATES_REQUEST]", "").strip()
        reply_text = f"{reply_text}\n\n{rates_msg}" if reply_text else rates_msg

    if "[MENU_REQUEST]" in reply_text:
        reply_text = reply_text.replace("[MENU_REQUEST]", "").strip()

    _has_photos = "[PHOTOS_REQUEST]" in reply_text
    if _has_photos:
        reply_text = reply_text.replace("[PHOTOS_REQUEST]", "").strip()

    _wants_owner = "[CONNECT_OWNER]" in reply_text
    if _wants_owner:
        reply_text = reply_text.replace("[CONNECT_OWNER]", "").strip()

    reply_text = _sanitize_reply(reply_text)

    history.append(types.Content(role="model", parts=[types.Part(text=reply_text)]))
    _trim_history(phone)

    return reply_text, _has_photos, _wants_owner


def is_menu_request(reply: str) -> bool:
    """Check if the original Gemini response contained a menu request tag."""
    return "[MENU_REQUEST]" in reply


def clear_conversation(phone: str) -> None:
    """Reset conversation history for a user."""
    _conversations.pop(phone, None)
