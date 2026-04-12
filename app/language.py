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
            f"🙏 {'Welcome ' + name + '!' if name else 'Welcome!'}\n\n"
            "Welcome to Sharda Jewellers, Bemetara.\n"
            "Your family jeweller since 1971.\n\n"
            "Choose below or ask anything:"
        )
    return (
        f"🙏 {'नमस्ते ' + name + ' जी!' if name else 'नमस्ते!'}\n\n"
        "शारदा ज्वेलर्स, बेमेतरा में आपका स्वागत है।\n"
        "सन् 1971 से आपके परिवार के ज्वेलर।\n\n"
        "नीचे से चुनें या कुछ भी पूछें:"
    )


def photo_greeting(name: str, lang: str) -> str:
    if lang == "en":
        return f"📸 {'Hi ' + name + '!' if name else 'Hi!'} Sending some photos of our jewellery:"
    return f"📸 {'जी ' + name + ' जी!' if name else 'जी!'} हमारे कुछ गहनों की तस्वीरें भेज रहे हैं:"


def no_photos_msg(lang: str) -> str:
    if lang == "en":
        return "Sorry, photos are not available right now. Please visit our store to see our collection."
    return "क्षमा करें, अभी फोटो उपलब्ध नहीं हैं। कृपया दुकान पर आकर हमारा कलेक्शन देखें।"


def owner_connected_msg(lang: str) -> str:
    if lang == "en":
        return "✅ The owner has joined! You can now chat directly."
    return "✅ मालिक जी जुड़ गए हैं! अब आप सीधे बात कर सकते हैं।"


def session_ended_msg(lang: str) -> str:
    if lang == "en":
        return (
            "🙏 The owner has ended the conversation.\n"
            "You can now chat with the bot. Ask anything or type \"menu\"!"
        )
    return (
        "🙏 मालिक जी ने बातचीत समाप्त की।\n"
        "अब आप बॉट से बात कर सकते हैं। कुछ भी पूछें या \"menu\" लिखें!"
    )
