"""FastAPI application — WhatsApp webhook for Sharda Jewellers chatbot."""

import logging
from fastapi import FastAPI, Request, Query, Response
from fastapi.responses import HTMLResponse
from app.config import WHATSAPP_VERIFY_TOKEN
from app.whatsapp import extract_message, send_text, send_interactive_buttons, mark_read
from app.chatbot import generate_reply

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sharda Jewellers WhatsApp Bot",
    description="WhatsApp chatbot for Sharda Jewellers, Bemetara — since 1971",
    version="1.0.0",
)

MENU_BUTTONS = [
    {"id": "btn_rates", "title": "आज के भाव 🪙"},
    {"id": "btn_products", "title": "हमारे गहने 💎"},
    {"id": "btn_custom", "title": "कस्टम ऑर्डर ✨"},
]

_processed_messages: set[str] = set()
MAX_DEDUP_SIZE = 5000


@app.get("/", response_class=HTMLResponse)
async def home():
    return """<!DOCTYPE html>
<html lang="hi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>शारदा ज्वेलर्स — WhatsApp Bot</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
               color: #fff; min-height: 100vh; display: flex; align-items: center;
               justify-content: center; text-align: center; padding: 2rem; }
        .card { background: rgba(255,255,255,0.05); backdrop-filter: blur(10px);
                border: 1px solid rgba(255,215,0,0.2); border-radius: 24px;
                padding: 3rem 2.5rem; max-width: 520px; width: 100%; }
        .logo { font-size: 3rem; margin-bottom: 0.5rem; }
        h1 { font-size: 1.8rem; color: #ffd700; margin-bottom: 0.25rem; }
        .est { color: #aaa; font-size: 0.95rem; margin-bottom: 1.5rem; }
        .tagline { color: #ccc; font-size: 1rem; line-height: 1.6; margin-bottom: 2rem; }
        .status { display: inline-block; background: #22c55e; width: 10px; height: 10px;
                  border-radius: 50%; margin-right: 6px; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        .status-text { color: #22c55e; font-size: 0.9rem; }
        .divider { border: none; border-top: 1px solid rgba(255,215,0,0.15);
                   margin: 1.5rem 0; }
        .credits { color: #888; font-size: 0.8rem; }
        .credits a { color: #ffd700; text-decoration: none; }
        .credits a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">🪙</div>
        <h1>शारदा ज्वेलर्स</h1>
        <p class="est">बेमेतरा, छत्तीसगढ़ — सन् 1971 से</p>
        <p class="tagline">पीढ़ियाँ बदलती हैं, डिज़ाइन बदलते हैं —<br>
        लेकिन हमारी कारीगरी और हमारे मूल्य आज भी वही हैं।</p>
        <p><span class="status"></span><span class="status-text">WhatsApp Bot Active</span></p>
        <hr class="divider">
        <p class="credits">
            Gold &amp; silver rates powered by
            <a href="https://goldpricez.com" target="_blank" rel="noopener">GoldPriceZ.com</a>
        </p>
    </div>
</body>
</html>"""


@app.get("/health")
async def health():
    return {
        "status": "running",
        "bot": "Sharda Jewellers WhatsApp Bot",
        "since": 1971,
    }


@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Meta webhook verification (GET request)."""
    if hub_mode == "subscribe" and hub_token == WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verified successfully")
        return Response(content=hub_challenge, media_type="text/plain")
    logger.warning("Webhook verification failed: mode=%s", hub_mode)
    return Response(content="Forbidden", status_code=403)


@app.post("/webhook")
async def receive_message(request: Request):
    """Handle incoming WhatsApp messages."""
    payload = await request.json()
    msg = extract_message(payload)

    if not msg:
        return {"status": "no_message"}

    msg_id = msg["msg_id"]
    if msg_id in _processed_messages:
        return {"status": "duplicate"}
    _processed_messages.add(msg_id)
    if len(_processed_messages) > MAX_DEDUP_SIZE:
        _processed_messages.clear()

    phone = msg["from"]
    text = msg["text"].strip()
    name = msg["name"]

    logger.info("Message from %s (%s): %s", name or "unknown", phone, text[:100])

    await mark_read(msg_id)

    if text.lower() in ("menu", "मेनू", "help", "मदद"):
        welcome = (
            f"🙏 {'नमस्ते ' + name + ' जी!' if name else 'नमस्ते!'}\n\n"
            "शारदा ज्वेलर्स, बेमेतरा में आपका स्वागत है।\n"
            "सन् 1971 से आपके परिवार के ज्वेलर।\n\n"
            "नीचे से चुनें या कुछ भी पूछें:"
        )
        await send_interactive_buttons(phone, welcome, MENU_BUTTONS)
        return {"status": "menu_sent"}

    if text.lower() in ("btn_rates", "bhav", "भाव", "rate", "rates", "gold rate",
                         "sone ka bhav", "सोने का भाव", "chandi ka bhav",
                         "चाँदी का भाव", "aaj ka bhav", "आज के भाव"):
        reply = await generate_reply(phone, "आज के सोने चाँदी के भाव बताओ", name)
        await send_text(phone, reply)
        return {"status": "rates_sent"}

    if text.lower() in ("btn_products", "products", "गहने", "jewellery", "jewelry",
                         "collection", "हमारे गहने"):
        reply = await generate_reply(phone, "आपके यहाँ कौन-कौन से गहने मिलते हैं?", name)
        await send_text(phone, reply)
        return {"status": "products_sent"}

    if text.lower() in ("btn_custom", "custom", "कस्टम", "custom order",
                         "कस्टम ऑर्डर", "apna design"):
        reply = await generate_reply(phone, "कस्टम ऑर्डर कैसे करें?", name)
        await send_text(phone, reply)
        return {"status": "custom_sent"}

    reply = await generate_reply(phone, text, name)
    await send_text(phone, reply)
    return {"status": "replied"}
