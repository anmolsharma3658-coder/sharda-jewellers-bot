"""Language detection and bilingual message templates.

Detects Hindi / English / Hinglish from message text using Unicode
script analysis. No external libraries needed.
"""

import re

_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_LATIN_ALPHA = re.compile(r"[a-zA-Z]")

_HINGLISH_MARKERS = frozenset({
    "kya", "hai", "hain", "nahi", "nhi", "mujhe", "muje", "kaise",
    "kab", "kaha", "kitne", "kitna", "kitni", "acha", "accha",
    "theek", "thik", "chahiye", "chahie", "bhai", "bhaiya",
    "ji", "haan", "naa", "bolo", "batao", "dikha", "dikhao",
    "bhejo", "wala", "wali", "karo", "karna", "karke", "dedo",
    "dena", "lena", "lelo", "aur", "lekin", "toh", "abhi",
    "yahan", "wahan", "sab", "kuch", "bohot", "bahut", "bohut",
    "suno", "dekho", "chalo", "aao", "jao", "ruko", "pehle",
    "baad", "paisa", "rupay", "sona", "chandi", "heera",
    "gehna", "gahna", "shaadi", "dulhan", "mangalsutr",
    "bhav", "aaj", "dikhao", "batao", "malik", "dunga", "doge",
    "milta", "milega", "lena", "khareedna", "order", "bhejna",
})

# Roman-script English cues (avoid classifying clear English as hinglish)
_ENGLISH_MARKERS = frozenset({
    "the", "and", "for", "you", "your", "what", "how", "when", "where", "why",
    "please", "thank", "thanks", "hello", "hey", "good", "morning", "evening",
    "today", "latest", "gold", "silver", "rate", "rates", "price", "prices",
    "show", "send", "want", "need", "can", "could", "would", "should", "tell",
    "give", "about", "from", "with", "this", "that", "have", "has", "any",
    "some", "more", "here", "there", "buy", "purchase", "order", "contact",
    "call", "number", "photo", "photos", "picture", "collection", "jewellery",
    "jewelry", "store", "shop",     "certainly", "are", "these", "those",
})


def _tokenize(text: str) -> set[str]:
    raw = re.sub(r"[^\w\s]", " ", text.lower())
    return {w for w in raw.split() if len(w) > 1}


def detect_language(text: str) -> str:
    """Detect language from message text.

    Returns "hi" (Hindi), "en" (English), or "hinglish".
    """
    stripped = text.strip()
    if not stripped:
        return "hi"

    devanagari_count = len(_DEVANAGARI.findall(text))
    latin_count = len(_LATIN_ALPHA.findall(text))
    total = devanagari_count + latin_count

    if total == 0:
        return "hi"

    if devanagari_count / total > 0.25:
        return "hi"

    words = _tokenize(text)
    if not words:
        return "hi"

    hinglish_hits = words & _HINGLISH_MARKERS
    english_hits = words & _ENGLISH_MARKERS

    # Clear English (e.g. "gold and silver rates today please")
    if english_hits and len(english_hits) >= len(hinglish_hits) + 1:
        return "en"
    if english_hits and len(english_hits) >= 2 and not hinglish_hits:
        return "en"

    if hinglish_hits:
        return "hinglish"

    return "en"


def t(lang: str, hi: str, en: str) -> str:
    """Pick the right string based on detected language."""
    if lang == "en":
        return en
    return hi


# ─── Pre-built bilingual messages ──────────────────────────

def welcome_msg(name: str, lang: str) -> str:
    if lang == "en":
        return (
            f"✨ {'Welcome, ' + name + '!' if name else 'Welcome!'}\n\n"
            "So glad you messaged *Sharda Jewellers* — Bemetara's family jeweller since *1971*.\n"
            "We're here to help with rates, designs, custom orders, or just a friendly chat about jewellery 💎\n\n"
            "Tap a button below or type what you need — we're listening!"
        )
    if lang == "hinglish":
        return (
            f"✨ {'Hi ' + name + '!' if name else 'Hi!'} Sharda Jewellers mein aapka swagat hai 🙏\n\n"
            "Bemetara ke family jeweller — *1971 se* yahin hain. Gold, silver, diamond, custom design — "
            "jo bhi dil mein ho, poochh lo! 💎\n\n"
            "Neeche button dabao ya seedha likho — hum taiyaar hain!"
        )
    return (
        f"✨ {'नमस्ते ' + name + ' जी!' if name else 'नमस्ते!'}\n\n"
        "शारदा ज्वेलर्स में आपका दिल से स्वागत है 🙏\n"
        "बेमेतरा के परिवारिक ज्वेलर — *सन् 1971* से आपके साथ। सोना, चाँदी, हीरा, कस्टम डिज़ाइन — "
        "जो चाहें, पूछिए! 💎\n\n"
        "नीचे बटन चुनें या सीधे लिखें — हम सुन रहे हैं!"
    )


def photo_greeting(name: str, lang: str) -> str:
    if lang == "en":
        return (
            f"📸 {'Lovely to hear from you, ' + name + '!' if name else 'Great choice!'}\n"
            "Here are some glimpses from our collection — the real magic is even better in store ✨"
        )
    if lang == "hinglish":
        return (
            f"📸 {'Ji ' + name + '!' if name else 'Ji!'} Collection ki jhalak bhej rahe hain — "
            "asli nazara to dukaan par aur bhi khoobsurat hai ✨"
        )
    return (
        f"📸 {'जी ' + name + ' जी!' if name else 'बहुत खूब!'}\n"
        "कलेक्शन की एक झलक — असली नज़ारा तो दुकान पर और भी खूबसूरत है ✨"
    )


def no_photos_msg(lang: str) -> str:
    if lang == "en":
        return (
            "Photos aren't loading just now — technology being a little shy 😅\n"
            "Do visit us in Bemetara; nothing beats seeing the pieces in person!"
        )
    if lang == "hinglish":
        return (
            "Abhi photos load nahi ho paayi — thodi technical museebat 😅\n"
            "Bemetara dukaan par aa jao, live dekhna alag hi baat hai!"
        )
    return (
        "अभी फोटो लोड नहीं हो पाई — थोड़ी तकनीकी मुसीबत 😅\n"
        "बेमेतरा दुकान पर आइए, सामने देखने का मज़ा ही अलग है!"
    )


def owner_connected_msg(lang: str) -> str:
    if lang == "en":
        return (
            "✅ *You're now chatting with the store team* — your messages go straight to them.\n"
            "Take your time. When they're done, our assistant will be right here again 💬"
        )
    if lang == "hinglish":
        return (
            "✅ *Ab aap seedhe store team se baat kar rahe ho* — message unhi tak jayega.\n"
            "Aaram se baat karo. Baad mein humara assistant phir yahin milega 💬"
        )
    return (
        "✅ *अब आप सीधे दुकान की टीम से जुड़ गए हैं* — आपका संदेश उन तक जाएगा।\n"
        "आराम से बात कीजिए। बाद में हमारा सहायक फिर यहीं मिलेगा 💬"
    )


def ai_visual_caption(lang: str) -> str:
    """Caption on WhatsApp for AI-generated inspiration image."""
    if lang == "en":
        return (
            "✨ AI inspiration only — not our real stock. Final design & gold work happen at "
            "Sharda Jewellers, Bemetara. Google Imagen / SynthID watermark may apply."
        )
    if lang == "hinglish":
        return (
            "✨ Ye AI inspiration hai — asli piece dukaan par banega. Final design Sharda Jewellers "
            "Bemetara par. (Imagen / SynthID watermark ho sakta hai.)"
        )
    return (
        "✨ यह AI से बनी *प्रेरणा* है — असली गहना दुकान पर तय होगा। "
        "फाइनल डिज़ाइन शारदा ज्वेलर्स, बेमेतरा। (Imagen / SynthID वॉटरमार्क हो सकता है।)"
    )


def ai_visual_queued_msg(lang: str) -> str:
    """Right after user triggers AI image — set expectation (takes a short while)."""
    if lang == "en":
        return "✨ Working on an AI inspiration image for you — please wait a few seconds…"
    if lang == "hinglish":
        return "✨ AI inspiration image bana rahe hain — thoda wait karo, kuch seconds…"
    return "✨ AI प्रेरणा चित्र तैयार कर रहे हैं — कृपया कुछ सेकंड प्रतीक्षा करें…"


def ai_visual_disabled_msg(lang: str) -> str:
    if lang == "en":
        return (
            "AI image previews are switched off on this server. "
            "You can send a reference photo or visit Sharda Jewellers in Bemetara."
        )
    if lang == "hinglish":
        return (
            "AI image preview abhi server par band hai. Reference photo bhejo ya Bemetara dukaan par aao."
        )
    return (
        "AI चित्र सुविधा इस सर्वर पर बंद है। रेफरेंस फोटो भेजें या बेमेतरा दुकान पर आएँ।"
    )


def ai_visual_failed_msg(lang: str) -> str:
    if lang == "en":
        return (
            "Sorry — I couldn't generate that preview just now (limits or safety filter). "
            "Try a simpler jewellery description, send a reference photo, or visit us in Bemetara."
        )
    if lang == "hinglish":
        return (
            "Sorry — abhi AI preview nahi ban paya (limit ya filter). Thoda simple description try karo, "
            "ya reference photo bhejo, ya Bemetara dukaan par aao."
        )
    return (
        "क्षमा करें — अभी AI प्रीव्यू नहीं बन पाया (सीमा या सुरक्षा फ़िल्टर)। "
        "थोड़ा सरल विवरण लिखें, रेफरेंस फोटो भेजें, या बेमेतरा दुकान पर आएँ।"
    )


def custom_inspiration_ack(lang: str) -> str:
    """After customer sends a design reference / inspiration photo."""
    if lang == "en":
        return (
            "📷 *We received your reference photo.*\n"
            "Our team will review it and get back to you on WhatsApp. "
            "If you have more details (metal, budget, occasion), send them as a message too ✨"
        )
    if lang == "hinglish":
        return (
            "📷 *Aapka reference photo mil gaya.*\n"
            "Team dekh kar WhatsApp par jawab degi. Agar metal, budget, occasion jaise detail ho to "
            "message mein likh bhej dena ✨"
        )
    return (
        "📷 *आपका रेफरेंस फोटो मिल गया।*\n"
        "हमारी टीम इसे देखकर WhatsApp पर जवाब देगी। धातु, बजट, मौका जैसी जानकारी हो तो संदेश में लिख भेजिए ✨"
    )


def session_ended_msg(lang: str) -> str:
    if lang == "en":
        return (
            "🙏 *That was the live chat with our team.*\n"
            "You're back with me — ask for *rates*, *photos*, *collections*, or type *menu* anytime. Happy to help! ✨"
        )
    if lang == "hinglish":
        return (
            "🙏 *Live chat yahi par khatam — team se baat ho gayi.*\n"
            "Ab main phir se yahin hoon — *rate*, *photo*, *collection* ya *menu* likho, khushi se madad karunga! ✨"
        )
    return (
        "🙏 *लाइव चैट यहीं समाप्त — टीम से बात हो गई।*\n"
        "अब मैं फिर यहीं हूँ — *भाव*, *फोटो*, *कलेक्शन* या *menu* लिखिए, खुशी से मदद करूँगा! ✨"
    )
