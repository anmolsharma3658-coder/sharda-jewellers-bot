"""FastAPI application — WhatsApp webhook for Sharda Jewellers chatbot."""

import asyncio
import logging
from fastapi import FastAPI, Request, Query, Response, Header, UploadFile, File
from fastapi.responses import HTMLResponse, PlainTextResponse
from app.config import WHATSAPP_VERIFY_TOKEN, OWNER_PHONES, ADMIN_KEY
from app.whatsapp import (
    extract_message, send_text, send_image, send_template,
    send_interactive_buttons, mark_read,
)
from app.chatbot import generate_reply
from app.google_photos import get_store_photos
from app.livechat import (
    start_session, customer_in_session, owner_has_session,
    find_pending_session, link_owner, touch,
    end_session_for_owner, is_end_command,
)
from app.customers import (
    upsert_customer, get_customer, get_all_customers, get_customer_count,
    search_customers, update_tags, update_notes, delete_customer,
    export_csv, import_csv, get_broadcast_targets,
)
from app.language import (
    detect_language, welcome_msg, photo_greeting, no_photos_msg,
    owner_connected_msg, session_ended_msg,
)

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
    {"id": "btn_photos", "title": "फोटो देखें 📸"},
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


@app.get("/test")
async def test_chat(msg: str = Query("नमस्ते")):
    """Debug endpoint to test bot replies directly."""
    reply, wants_photos, wants_owner = await generate_reply("test_user", msg, "TestUser")
    return {"input": msg, "reply": reply, "wants_photos": wants_photos, "wants_owner": wants_owner}


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

    # ── Owner message during live session → relay to customer ──
    if phone in OWNER_PHONES and (owner_has_session(phone) or find_pending_session() or is_end_command(text)):
        return await _handle_owner_message(phone, text, name)

    # ── Customer in live chat → forward to owner ──
    if customer_in_session(phone):
        return await _handle_live_customer_message(phone, text, name)

    # ── Detect language and save customer ──
    lang = detect_language(text)
    upsert_customer(phone, name, language=lang)

    if text.lower() in ("menu", "मेनू", "help", "मदद"):
        await send_interactive_buttons(phone, welcome_msg(name, lang), MENU_BUTTONS)
        return {"status": "menu_sent"}

    if text.lower() in ("btn_rates", "bhav", "भाव", "rate", "rates", "gold rate",
                         "sone ka bhav", "सोने का भाव", "chandi ka bhav",
                         "चाँदी का भाव", "aaj ka bhav", "आज के भाव"):
        reply, _, _ = await generate_reply(phone, "आज के सोने चाँदी के भाव बताओ", name)
        await send_text(phone, reply)
        return {"status": "rates_sent"}

    if text.lower() in ("btn_photos", "photo", "photos", "फोटो", "तस्वीर",
                         "gallery", "दिखाओ", "pictures", "फोटो देखें"):
        return await _handle_photos(phone, name, lang)

    if text.lower() in ("btn_products", "products", "गहने", "jewellery", "jewelry",
                         "collection", "हमारे गहने"):
        reply, _, _ = await generate_reply(phone, "आपके यहाँ कौन-कौन से गहने मिलते हैं?", name)
        await send_text(phone, reply)
        return {"status": "products_sent"}

    if text.lower() in ("btn_custom", "custom", "कस्टम", "custom order",
                         "कस्टम ऑर्डर", "apna design"):
        reply, _, _ = await generate_reply(phone, "कस्टम ऑर्डर कैसे करें?", name)
        await send_text(phone, reply)
        return {"status": "custom_sent"}

    reply, wants_photos, wants_owner = await generate_reply(phone, text, name)
    await send_text(phone, reply)
    if wants_photos:
        await _send_photos(phone, lang=lang)
    if wants_owner:
        await _start_live_chat(phone, name, text, lang)
    return {"status": "replied"}


# ═══════════════════════════════════════════════════════════
# Live Chat Relay — owner ↔ customer through the bot
# ═══════════════════════════════════════════════════════════

async def _start_live_chat(customer_phone: str, customer_name: str, customer_msg: str, lang: str = "hi") -> None:
    """Create a live session and notify owners they can reply directly."""
    start_session(customer_phone, customer_name)

    from app.chatbot import _get_history
    history = _get_history(customer_phone)

    chat_lines = []
    for entry in history[-10:]:
        role = "ग्राहक" if entry.role == "user" else "Bot"
        txt = entry.parts[0].text if entry.parts else ""
        if len(txt) > 200:
            txt = txt[:200] + "..."
        chat_lines.append(f"  {role}: {txt}")
    chat_summary = "\n".join(chat_lines)

    lang_label = {"hi": "हिंदी", "en": "English", "hinglish": "Hinglish"}.get(lang, lang)

    owner_msg = (
        "🔔 *लाइव चैट — ग्राहक जुड़ना चाहता है*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 नाम: {customer_name or 'अज्ञात'}\n"
        f"📱 नंबर: wa.me/{customer_phone}\n"
        f"🌐 भाषा: {lang_label}\n"
        f"💬 संदेश: {customer_msg}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 *बातचीत:*\n{chat_summary}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👉 *सीधे यहाँ जवाब दें* — आपका मैसेज ग्राहक को पहुँच जाएगा।\n"
        "👉 चैट खत्म करने के लिए \"बंद\" लिखें।"
    )

    for op in OWNER_PHONES:
        await send_text(op, owner_msg)


async def _handle_owner_message(owner_phone: str, text: str, name: str) -> dict:
    """Route an owner's message: relay to customer or handle session commands."""

    # Check if owner wants to end the session
    if is_end_command(text):
        customer_phone = end_session_for_owner(owner_phone)
        if customer_phone:
            cust = get_customer(customer_phone)
            cust_lang = cust.get("language", "hi") if cust else "hi"
            await send_text(owner_phone, "✅ लाइव चैट समाप्त। ग्राहक अब बॉट से बात करेगा।")
            await send_text(customer_phone, session_ended_msg(cust_lang))
            return {"status": "session_ended"}
        await send_text(owner_phone, "कोई लाइव चैट चल नहीं रही।")
        return {"status": "no_session"}

    # Already linked to a customer → forward message
    linked_customer = owner_has_session(owner_phone)
    if linked_customer:
        touch(linked_customer)
        await send_text(linked_customer, f"💬 *शारदा ज्वेलर्स:*\n{text}")
        return {"status": "relayed_to_customer"}

    # Not linked yet — check if there's a pending customer waiting
    pending = find_pending_session()
    if pending:
        link_owner(owner_phone, pending)
        from app.livechat import get_session
        session = get_session(pending)
        cust_name = session["customer_name"] if session else ""
        cust = get_customer(pending)
        cust_lang = cust.get("language", "hi") if cust else "hi"

        await send_text(
            owner_phone,
            f"✅ आप {cust_name or pending} से जुड़ गए हैं। अब जो भी लिखेंगे, सीधे ग्राहक को जाएगा।\n"
            "चैट खत्म करने के लिए \"बंद\" लिखें।",
        )
        await send_text(pending, owner_connected_msg(cust_lang))
        # Forward this first message too
        await send_text(pending, f"💬 *शारदा ज्वेलर्स:*\n{text}")
        return {"status": "owner_linked_and_relayed"}

    # No pending session — just ignore or acknowledge
    return {"status": "owner_no_action"}


async def _handle_live_customer_message(customer_phone: str, text: str, name: str) -> dict:
    """Customer is in a live session — forward their message to the connected owner."""
    from app.livechat import get_session
    touch(customer_phone)
    session = get_session(customer_phone)

    if not session:
        return {"status": "session_expired"}

    owner_phone = session.get("owner_phone")
    cust_label = name or customer_phone

    if owner_phone:
        await send_text(owner_phone, f"👤 *{cust_label}:*\n{text}")
        return {"status": "relayed_to_owner"}

    # No owner connected yet — forward to all owners
    for op in OWNER_PHONES:
        await send_text(op, f"👤 *{cust_label} (जवाब का इंतज़ार):*\n{text}")
    return {"status": "forwarded_to_all_owners"}


async def _send_photos(phone: str, count: int = 5, lang: str = "hi") -> None:
    """Fetch and send store photos to the customer."""
    photos = await get_store_photos(count)
    if not photos:
        await send_text(phone, no_photos_msg(lang))
        return
    for i, url in enumerate(photos):
        caption = "Sharda Jewellers, Bemetara" if lang == "en" else "शारदा ज्वेलर्स, बेमेतरा"
        await send_image(phone, url, caption if i == 0 else "")


async def _handle_photos(phone: str, name: str, lang: str = "hi") -> dict:
    """Handle a direct photo request (from button or keyword)."""
    await send_text(phone, photo_greeting(name, lang))
    await _send_photos(phone, lang=lang)
    return {"status": "photos_sent"}


def _check_admin(key: str | None) -> bool:
    return key == ADMIN_KEY


# ═══════════════════════════════════════════════════════════
# Admin API — Customer Directory
# ═══════════════════════════════════════════════════════════

@app.get("/admin/customers")
async def list_customers(
    q: str = Query("", description="Search by name or phone"),
    x_admin_key: str | None = Header(None),
):
    """List all customers or search by name/phone."""
    if not _check_admin(x_admin_key):
        return Response(content="Unauthorized", status_code=401)
    if q:
        return {"customers": search_customers(q), "query": q}
    return {"customers": get_all_customers(), "total": get_customer_count()}


@app.get("/admin/customers/export")
async def export_customers(x_admin_key: str | None = Header(None)):
    """Download entire customer directory as CSV."""
    if not _check_admin(x_admin_key):
        return Response(content="Unauthorized", status_code=401)
    csv_data = export_csv()
    return PlainTextResponse(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sharda_customers.csv"},
    )


@app.post("/admin/customers/import")
async def import_customers(file: UploadFile = File(...), x_admin_key: str | None = Header(None)):
    """Upload a CSV file to import customers.

    CSV must have at least a 'phone' column. Optional: name, tags, notes.
    """
    if not _check_admin(x_admin_key):
        return Response(content="Unauthorized", status_code=401)
    contents = await file.read()
    csv_text = contents.decode("utf-8-sig")
    result = import_csv(csv_text)
    return {"status": "imported", **result}


@app.get("/admin/customers/{phone}")
async def get_single_customer(phone: str, x_admin_key: str | None = Header(None)):
    """Get a single customer's details."""
    if not _check_admin(x_admin_key):
        return Response(content="Unauthorized", status_code=401)
    cust = get_customer(phone)
    if not cust:
        return Response(content="Customer not found", status_code=404)
    return cust


@app.put("/admin/customers/{phone}/tags")
async def set_customer_tags(
    phone: str,
    tags: str = Query(..., description="Comma-separated tags, e.g. 'vip,bride'"),
    x_admin_key: str | None = Header(None),
):
    """Set tags for a customer (e.g. vip, bride, regular)."""
    if not _check_admin(x_admin_key):
        return Response(content="Unauthorized", status_code=401)
    if update_tags(phone, tags):
        return {"status": "updated", "phone": phone, "tags": tags}
    return Response(content="Customer not found", status_code=404)


@app.put("/admin/customers/{phone}/notes")
async def set_customer_notes(
    phone: str,
    request: Request,
    x_admin_key: str | None = Header(None),
):
    """Set notes for a customer. Send JSON body: {"notes": "..."}."""
    if not _check_admin(x_admin_key):
        return Response(content="Unauthorized", status_code=401)
    body = await request.json()
    notes = body.get("notes", "")
    if update_notes(phone, notes):
        return {"status": "updated", "phone": phone}
    return Response(content="Customer not found", status_code=404)


@app.delete("/admin/customers/{phone}")
async def remove_customer(phone: str, x_admin_key: str | None = Header(None)):
    """Delete a customer from the directory."""
    if not _check_admin(x_admin_key):
        return Response(content="Unauthorized", status_code=401)
    if delete_customer(phone):
        return {"status": "deleted", "phone": phone}
    return Response(content="Customer not found", status_code=404)


@app.post("/admin/broadcast")
async def broadcast_message(request: Request, x_admin_key: str | None = Header(None)):
    """Broadcast a message to all customers (or filtered by tag).

    JSON body:
      {
        "message": "text to send",       // for 24hr-window customers
        "template": "template_name",     // for template-based broadcast
        "tag": "vip"                     // optional filter
      }

    Use 'message' for customers who messaged in last 24hrs.
    Use 'template' (pre-approved in Meta) for all customers.
    """
    if not _check_admin(x_admin_key):
        return Response(content="Unauthorized", status_code=401)

    body = await request.json()
    message = body.get("message", "")
    template_name = body.get("template", "")
    tag_filter = body.get("tag", "")

    if not message and not template_name:
        return Response(content="Provide 'message' or 'template' in body", status_code=400)

    targets = get_broadcast_targets(tag_filter)
    sent = failed = 0

    for cust in targets:
        phone = cust["phone"]
        if phone in OWNER_PHONES:
            continue
        try:
            if template_name:
                ok = await send_template(phone, template_name)
            else:
                ok = await send_text(phone, message)
            if ok:
                sent += 1
            else:
                failed += 1
        except Exception:
            logger.error("Broadcast failed for %s", phone, exc_info=True)
            failed += 1
        await asyncio.sleep(0.1)

    return {"status": "broadcast_complete", "sent": sent, "failed": failed, "total_targets": len(targets)}


@app.get("/admin/stats")
async def admin_stats(x_admin_key: str | None = Header(None)):
    """Quick dashboard stats."""
    if not _check_admin(x_admin_key):
        return Response(content="Unauthorized", status_code=401)
    return {"total_customers": get_customer_count()}


