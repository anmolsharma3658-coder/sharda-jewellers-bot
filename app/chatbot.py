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
from app.livechat import owner_escalation_allowed

logger = logging.getLogger(__name__)

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL = "gemini-2.5-flash-lite"

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0

SYSTEM_PROMPT = """
तुम "शारदा ज्वेलर्स" के आधिकारिक WhatsApp सहायक हो — दोस्ताना, गर्मजोशी भरा, थोड़ा मनोरंजक,
लेकिन हमेशा सम्मानजनक और भरोसेमंद। जैसे दुकान में कोई प्यारा सा स्टाफ जो ग्राहक का दिल जीत ले।

PERSONALITY (use reply_language):
• Warm welcome energy — customer chose *you*; make them glad they did.
• Light, tasteful humour or playfulness is OK (one line max) — never mock the customer or jewellery.
• Occasional ✨💎🙏 style emoji is fine (1–2 per message) — not spam.
• Celebrate the store's 1971 legacy in natural moments, not every message.
• Sound human, not robotic — short sentences, natural flow, WhatsApp vibe.

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
• ग्राहक *फोटो* भेजकर डिज़ाइन / प्रेरणा दिखा सकते हैं — बॉट पुष्टि देता है और टीम को भेज देता है
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

2. लहजा: ऊपर PERSONALITY देखो — पारिवारिक + थोड़ा fun, कभी सूखा औपचारिक जवाब मत दो।
3. कभी भी किसी दूसरी दुकान का नाम मत लो और न ही comparison करो।
4. अगर कोई ऐसा सवाल आए जो ज्वेलरी से संबंधित न हो, तो विनम्रता से कहो कि तुम सिर्फ गहनों में मदद कर सकते हो।
5. कीमत का अनुमान देने से बचो — हमेशा कहो "आज के भाव के हिसाब से" और लाइव रेट बताओ, या दुकान पर आने को कहो।
6. जवाब WhatsApp-friendly रखो — ज़्यादातर 80–200 शब्द; ज़रूरत हो तो थोड़ा लंबा OK।
7. जब ग्राहक पहली बार मैसेज करे, तो उसे स्वागत करो और मुख्य विकल्प बताओ।
8. अगर ग्राहक का नाम मिले, तो उसे नाम से संबोधित करो।
9. emoji — PERSONALITY के हिसाब से; हर लाइन में नहीं, पर खुश माहौल बनाने के लिए ठीक है।
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

⚠️ पहले यह ज़रूर पढ़ो — [PHOTOS_REQUEST] गलत मत लगाना:
• ग्राहक अपनी *प्रेरणा / रेफरेंस / आइडिया / स्केच / "ऐसा चाहिए"* की बात करे, या *खुद फोटो भेजने* की बात करे
  (inspiration, reference, my design, idea, sending photo, photo bhej raha, screenshot, Pinterest, Instagram se)
  → **[PHOTOS_REQUEST] बिल्कुल नहीं** — यह दुकान की Google गैलरी नहीं खोलता।
  → बताओ: इसी WhatsApp चैट में *फोटो या दस्तावेज़ भेज दें* (कैप्शन लिख सकते हैं); टीम लॉग कर लेगी। टेक्स्ट से विवरण भी चलेगा।
• [PHOTOS_REQUEST] *सिर्फ़* जब वे साफ़ *आपकी दुकान / शोरूम / कलेक्शन की असली तस्वीरें* देखना चाहें
  (आपके पास क्या डिज़ाइन हैं, दुकान दिखाओ, collection photos, store gallery, नमूने दिखाओ हमारे)।

अगर ग्राहक इनमें से कुछ पूछे, तो तुम्हें FUNCTION_CALL prefix के साथ जवाब देना है:

• "भाव", "rate", "price", "सोने का भाव", "gold rate", "चाँदी का भाव", "silver rate", "aaj ka bhav"
  → जवाब की शुरुआत में EXACTLY यह लिखो: [RATES_REQUEST]
  → फिर एक छोटा सा वाक्य जैसे "जी बिल्कुल! आज के ताज़ा भाव ये रहे:"

• "menu", "help", "मेनू", "मदद", "hi", "hello", "नमस्ते", "hii", "hey"
  → जवाब की शुरुआत में EXACTLY यह लिखो: [MENU_REQUEST]
  → फिर स्वागत संदेश

• दुकान की कलेक्शन / शोरूम फोटो (ऊपर "अपनी प्रेरणा" वाला केस नहीं):
  "photo", "फोटो", "तस्वीर", "picture", "image", "दिखाओ", "collection dikhao",
  "गहने दिखाओ", "show me", "photos bhejo", "gallery", "designs dikhao",
  "कुछ दिखाओ", "नमूने दिखाओ", "sample" — *केवल जब संदर्भ साफ़ हो कि वे हमारे स्टोर के फोटो चाहते हैं*
  → जवाब की शुरुआत में EXACTLY यह लिखो: [PHOTOS_REQUEST]
  → फिर एक छोटा वाक्य जैसे "जी बिल्कुल! हमारे कुछ गहनों की तस्वीरें भेज रहे हैं:"

• AI से *नया* गहनों का चित्र (दुकान की असली फोटो नहीं) — जब ग्राहक साफ़ मांगे:
  - जैसे: generate / AI image / visualize / mockup / picture bana do / design kaise dikhega / sketch banao
  - और साथ में गहने का विवरण हो
  → पहले EXACTLY: [AI_IMAGE_REQUEST]
  → फिर EXACTLY: [AI_IMAGE_PROMPT] ... [/AI_IMAGE_PROMPT] — बीच में केवल English, सिर्फ़ गहना (product photo), 400 अक्षर से कम; कोई इंसान/चेहरा/हाथ नहीं
  → फिर reply_language में छोटा संदेश: ये *AI प्रेरणा* है, असली काम दुकान पर
• [AI_IMAGE_REQUEST] मत लिखो अगर वे सिर्फ़ दुकान की *असली* तस्वीरें चाहें — उस पर [PHOTOS_REQUEST]
• हर बार AI चित्र मत चालू करो — सिर्फ़ जब ग्राहक स्पष्ट रूप से चित्र बनवाना चाहे

• [CONNECT_OWNER] — बहुत दुर्लभ, सिर्फ़ जब ग्राहक साफ़ तौर पर यह चाहे:
  - मालिक / ओनर / owner / manager / इंसान से सीधे बात (जैसे "मालिक से बात करानी है", "owner se baat", "speak to the owner", "human agent")
  - खरीद के बाद गंभीर शिकायत — गलत माल, refund, धोखा, पुलिस/कोर्ट जैसी बात + ऑर्डर/गहना/बिल का ज़िक्र
  → तभी जवाब की शुरुआत में EXACTLY: [CONNECT_OWNER]
  → फिर एक छोटा वाक्य: मालिक जी से लाइव चैट जोड़ रहे हैं, अगला मैसेज उन तक जाएगा।

• [CONNECT_OWNER] कभी मत लिखो अगर ग्राहक सिर्फ़ ये पूछ रहा हो:
  - भाव, फोटो, कलेक्शन, कस्टम ऑर्डर, डिज़ाइन, पता, टाइमिंग
  - खरीद में दिलचस्पी, "मुझे नेकलेस चाहिए", "order karna hai", बुक करना, विज़िट करना
  - कीमत, डिस्काउंट, "kitne ka", मोल-भाव — इनका जवाब तुम दो: आज के भाव + दुकान पर फाइनल रेट + फोन नंबर
  - कोई सामान्य सवाल जिसका जवाब तुम दे सको — पहले तुम ही जवाब दो

बाकी सभी सवालों का जवाब अपनी बुद्धिमानी से दो, ऊपर दी गई जानकारी के आधार पर।

═══════════════════════════════════════
CRITICAL OUTPUT RULES
═══════════════════════════════════════
- User messages are ONLY what the customer typed. There is NO [CONTEXT] line in their text.
- NEVER output [CONTEXT], "भाषा=", "reply_language", "Customer name:", message counts, dates, tags, or ANY internal/session metadata.
- Your reply must be ONLY the customer-facing WhatsApp text (plus optional [RATES_REQUEST], [AI_IMAGE_REQUEST], [AI_IMAGE_PROMPT]… tags where rules say so — server strips tags).
- Follow reply_language from the internal block at the bottom of these instructions — never mention it to the user.
"""

# If model outputs [CONNECT_OWNER] but the user's text does not qualify, we replace the reply (see generate_reply).
_HANDOFF_BLOCKED = {
    "en": (
        "I'm here to help with rates, photos, collections, and custom orders in this chat.\n\n"
        "📞 Sharda Jewellers, Bemetara: +91 94255 61850, +91 70003 44110\n\n"
        "We only open a *live chat to the owner* when you clearly ask to *speak to the owner* "
        "or you have a serious issue *after a purchase*. What would you like to know?"
    ),
    "hinglish": (
        "Main yahin se rates, photos, collection aur custom order mein help kar sakta hoon.\n\n"
        "📞 Sharda Jewellers, Bemetara: +91 94255 61850, +91 70003 44110\n\n"
        "Owner se live chat tabhi khulta hai jab aap clearly likho *malik/owner se baat* "
        "ya serious complaint ho *piece khareedne ke baad*. Ab batao kya chahiye?"
    ),
    "hi": (
        "मैं यहीं से भाव, फोटो, कलेक्शन और कस्टम ऑर्डर में मदद कर सकता हूँ।\n\n"
        "📞 शारदा ज्वेलर्स, बेमेतरा: +91 94255 61850, +91 70003 44110\n\n"
        "मालिक जी से *लाइव चैट* सिर्फ़ तभी खुलती है जब आप साफ़ लिखें *मालिक से बात* "
        "या *खरीद के बाद* गंभीर शिकायत हो। अभी क्या जानना चाहेंगे?"
    ),
}

_conversations: dict[str, list[types.Content]] = {}

MAX_HISTORY = 20

# Strip accidental echoes of internal metadata (safety net)
_CONTEXT_LEAK = re.compile(r"\[CONTEXT\s*:\s*.*?\]\s*", re.DOTALL | re.IGNORECASE)
_META_LINE = re.compile(
    r"^\s*(भाषा|reply_language|language)\s*[=:]\s*\S+.*$",
    re.IGNORECASE | re.MULTILINE,
)
_AI_IMAGE_PROMPT_BLOCK = re.compile(
    r"\[AI_IMAGE_PROMPT\]\s*(.*?)\s*\[/AI_IMAGE_PROMPT\]",
    re.DOTALL | re.IGNORECASE,
)


def is_customer_inspiration_reference_message(text: str) -> bool:
    """True when the customer is sharing / offering THEIR reference or idea — not asking for our store gallery."""
    raw = (text or "").strip()
    if not raw:
        return False
    t = raw.lower()

    if "inspiration" in t or "inspire" in t:
        return True
    if "प्रेरणा" in raw or "प्रेरण" in raw:
        return True
    if re.search(r"\breference\b", t) and re.search(
        r"\b(design|jewelry|jewellery|necklace|ring|bangle|earring|photo|pic|image|piece|"
        r"jhumka|mangalsutra|choker|set|gold|silver|custom|order)\b",
        t,
    ):
        return True
    if re.search(r"\b(my|our|own|apna|apni|mera|meri|humara)\s+(design|idea|photo|picture|image|sketch)\b", t):
        return True
    if re.search(r"\b(custom|कस्टम)\s+(order|piece|design)\b", t) and re.search(
        r"\b(photo|image|picture|pic|फोटो|reference|like|similar|sketch)\b", t
    ):
        return True
    if re.search(
        r"\b(i\s*'?m sending|i am sending|i\s*'?ve sent|i sent|here('?s| is)|"
        r"bhej\s*(raha|rahi|rha|rhi|diya|di|rahe|unga|ungi|dunga|dungi)|maine\s*bhej|mene\s*bhej|"
        r"upload(ed|ing)?|sending you|aapko bhej|aapke liye bhej)\b",
        t,
    ) and re.search(r"\b(photo|image|picture|pic|फोटो|screenshot)\b", t):
        return True
    if re.search(r"\b(share|shared)\b", t) and re.search(r"\b(my|mera|meri|apna|apni|our)\b", t) and re.search(
        r"\b(photo|image|picture|pic|फोटो)\b", t
    ):
        return True
    if re.search(
        r"\b(like this|something like|similar to|aise|is tarah|jaisa|jesaa|"
        r"इस तरह|ऐसा ही|same as)\b",
        t,
    ):
        return True
    if re.search(r"\b(pinterest|instagram|screenshot|screen shot|idea hai|have an idea)\b", t):
        return True
    return False


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


async def generate_reply(phone: str, user_text: str, user_name: str = "") -> tuple[str, bool, bool, bool, str | None]:
    """Generate a chatbot reply for the given user message.

    Returns (reply_text, wants_photos, wants_owner, wants_ai_image, ai_imagen_prompt_en).
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
        return reply_text, False, False, False, None

    ai_imagen_prompt_en: str | None = None
    m_ai = _AI_IMAGE_PROMPT_BLOCK.search(reply_text)
    if m_ai:
        ai_imagen_prompt_en = (m_ai.group(1) or "").strip()
        reply_text = reply_text[: m_ai.start()] + reply_text[m_ai.end() :]
        reply_text = re.sub(r"\n{3,}", "\n\n", reply_text).strip()

    _wants_ai_image = "[AI_IMAGE_REQUEST]" in reply_text
    if _wants_ai_image:
        reply_text = reply_text.replace("[AI_IMAGE_REQUEST]", "").strip()

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
    if _wants_ai_image:
        _has_photos = False
    if is_customer_inspiration_reference_message(user_text):
        if _has_photos:
            logger.info("Suppressed store [PHOTOS_REQUEST] — inspiration/reference customer message")
        _has_photos = False
        reply_text = reply_text.replace("[PHOTOS_REQUEST]", "").strip()

    raw_wants_owner = "[CONNECT_OWNER]" in reply_text
    if raw_wants_owner:
        reply_text = reply_text.replace("[CONNECT_OWNER]", "").strip()

    allowed_owner = owner_escalation_allowed(user_text)
    _wants_owner = raw_wants_owner and allowed_owner
    if raw_wants_owner and not allowed_owner:
        logger.info("Owner handoff blocked (not explicit): %s", user_text[:120])
        reply_text = _HANDOFF_BLOCKED.get(lang, _HANDOFF_BLOCKED["hi"])

    reply_text = _sanitize_reply(reply_text)

    history.append(types.Content(role="model", parts=[types.Part(text=reply_text)]))
    _trim_history(phone)

    return reply_text, _has_photos, _wants_owner, _wants_ai_image, ai_imagen_prompt_en


def is_menu_request(reply: str) -> bool:
    """Check if the original Gemini response contained a menu request tag."""
    return "[MENU_REQUEST]" in reply


def clear_conversation(phone: str) -> None:
    """Reset conversation history for a user."""
    _conversations.pop(phone, None)
