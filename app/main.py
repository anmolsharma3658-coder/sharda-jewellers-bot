"""FastAPI application — WhatsApp webhook for Sharda Jewellers chatbot."""

import logging
from fastapi import FastAPI, Request, Query, Response
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


@app.get("/")
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
