"""WhatsApp Cloud API integration for sending and parsing messages."""

import logging
import mimetypes

import httpx
from app.config import (
    WHATSAPP_TOKEN,
    WHATSAPP_API_URL,
    WHATSAPP_GRAPH_BASE,
    WHATSAPP_MEDIA_UPLOAD_URL,
    WHATSAPP_PHONE_NUMBER_ID,
)

logger = logging.getLogger(__name__)


def extract_inbound(payload: dict) -> dict | None:
    """Parse inbound user message: text or image (incl. sticker / image-as-document).

    Returns {"kind": "text"|"image", "from", "name", "msg_id", ...} or None.
    """
    try:
        entry = payload["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        if "messages" not in value:
            return None

        msg = value["messages"][0]
        contact = value.get("contacts", [{}])[0]
        base = {
            "from": msg["from"],
            "name": contact.get("profile", {}).get("name", ""),
            "msg_id": msg["id"],
        }
        t = msg.get("type")
        if t == "text":
            return {
                **base,
                "kind": "text",
                "text": msg["text"]["body"],
            }
        if t == "image":
            img = msg["image"]
            return {
                **base,
                "kind": "image",
                "media_id": img["id"],
                "mime_type": img.get("mime_type") or "image/jpeg",
                "caption": (img.get("caption") or "").strip(),
            }
        if t == "sticker":
            st = msg["sticker"]
            return {
                **base,
                "kind": "image",
                "media_id": st["id"],
                "mime_type": st.get("mime_type") or "image/webp",
                "caption": "",
            }
        if t == "document":
            doc = msg["document"]
            mime = (doc.get("mime_type") or "").lower()
            fn = (doc.get("filename") or "").lower()
            looks_image = mime.startswith("image/") or fn.endswith(
                (".jpg", ".jpeg", ".png", ".webp", ".heic", ".gif")
            )
            if not looks_image:
                return None
            if not mime.startswith("image/"):
                mime = "image/jpeg"
            return {
                **base,
                "kind": "image",
                "media_id": doc["id"],
                "mime_type": mime,
                "caption": (doc.get("caption") or "").strip(),
            }
        logger.info("Inbound WhatsApp message type not handled: %s", t)
        return None
    except (KeyError, IndexError, TypeError):
        logger.warning("Could not parse webhook payload", exc_info=True)
        return None


def extract_message(payload: dict) -> dict | None:
    """Backward-compatible: text-only inbound (photos use extract_inbound)."""
    m = extract_inbound(payload)
    if m and m.get("kind") == "text":
        return {
            "from": m["from"],
            "text": m["text"],
            "name": m["name"],
            "msg_id": m["msg_id"],
        }
    return None


async def get_media_download_url(media_id: str) -> tuple[str | None, str | None]:
    """Graph API: resolve temporary download URL and mime type."""
    if not WHATSAPP_TOKEN or not media_id:
        return None, None
    url = f"{WHATSAPP_GRAPH_BASE}/{media_id}"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            logger.error("Media meta failed %s: %s", resp.status_code, resp.text[:500])
            return None, None
        data = resp.json()
        return data.get("url"), data.get("mime_type")


async def download_graph_url(direct_url: str) -> bytes | None:
    if not WHATSAPP_TOKEN or not direct_url:
        return None
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(direct_url, headers=headers)
        if resp.status_code != 200:
            logger.error("Media download failed %s", resp.status_code)
            return None
        return resp.content


async def download_wa_media(media_id: str) -> tuple[bytes | None, str]:
    """Download bytes for a WhatsApp-hosted media id."""
    dl, mime = await get_media_download_url(media_id)
    if not dl:
        return None, mime or ""
    data = await download_graph_url(dl)
    return data, mime or "image/jpeg"


def _guess_ext(mime: str) -> str:
    ext = mimetypes.guess_extension(mime or "") or ".bin"
    if ext == ".jpe":
        ext = ".jpg"
    return ext


def prepare_image_bytes_for_whatsapp_upload(file_bytes: bytes, mime_type: str) -> tuple[bytes, str]:
    """WhatsApp media upload accepts image/jpeg and image/png; convert WebP/HEIC/etc. when possible."""
    import io

    mt = (mime_type or "").lower().split(";")[0].strip()
    if mt == "image/jpg":
        mt = "image/jpeg"
    if mt in ("image/jpeg", "image/png") and file_bytes:
        return file_bytes, mt
    if not file_bytes:
        return file_bytes, mt or "image/jpeg"
    try:
        from PIL import Image

        try:
            from pillow_heif import register_heif_opener  # type: ignore

            register_heif_opener()
        except ImportError:
            pass
        im = Image.open(io.BytesIO(file_bytes))
        im.load()
        if im.mode in ("RGBA", "P", "LA"):
            im = im.convert("RGB")
        elif im.mode != "RGB":
            im = im.convert("RGB")
        out = io.BytesIO()
        im.save(out, format="JPEG", quality=90, optimize=True)
        converted = out.getvalue()
        logger.info("Normalized image for WA upload: %s -> image/jpeg (%s bytes)", mime_type, len(converted))
        return converted, "image/jpeg"
    except Exception as e:
        logger.warning("Could not normalize image (mime=%s): %s", mime_type, e)
        return file_bytes, mt or "image/jpeg"


async def upload_wa_media(file_bytes: bytes, mime_type: str) -> str | None:
    """Upload bytes to WhatsApp Cloud API; returns new media id for sending."""
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_NUMBER_ID or not file_bytes:
        return None
    file_bytes, mime_type = prepare_image_bytes_for_whatsapp_upload(file_bytes, mime_type)
    if mime_type not in ("image/jpeg", "image/png"):
        mime_type = "image/jpeg"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    filename = f"file{_guess_ext(mime_type)}"
    files = {"file": (filename, file_bytes, mime_type or "image/jpeg")}
    form = {"messaging_product": "whatsapp", "type": mime_type or "image/jpeg"}
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(WHATSAPP_MEDIA_UPLOAD_URL, headers=headers, data=form, files=files)
        if resp.status_code != 200:
            logger.error("Media upload failed %s: %s", resp.status_code, resp.text[:500])
            return None
        mid = resp.json().get("id")
        if not mid:
            logger.error("Media upload missing id: %s", resp.text[:500])
        return mid


async def send_image_by_media_id(to: str, media_id: str, caption: str = "") -> bool:
    """Send an image using an id returned from upload_wa_media (or Graph-hosted id if still valid)."""
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    image_payload: dict = {"id": media_id}
    if caption:
        image_payload["caption"] = caption[:1020]
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": image_payload,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(WHATSAPP_API_URL, headers=headers, json=data)
        if resp.status_code != 200:
            logger.error("send_image_by_media_id failed: %s %s", resp.status_code, resp.text[:500])
            return False
        return True


async def relay_wa_media_to_recipient(
    source_media_id: str,
    to: str,
    caption: str = "",
) -> bool:
    """Download inbound WA media and re-upload so it can be sent to another user."""
    data, mime = await download_wa_media(source_media_id)
    if not data:
        logger.error("relay: could not download media %s", source_media_id)
        return False
    new_id = await upload_wa_media(data, mime or "image/jpeg")
    if not new_id:
        return False
    return await send_image_by_media_id(to, new_id, caption=caption)


async def relay_wa_media_to_many(
    source_media_id: str,
    recipients: list[str],
    caption: str = "",
) -> bool:
    """Single download+upload, then send the same uploaded id to each recipient."""
    if not recipients:
        return True
    data, mime = await download_wa_media(source_media_id)
    if not data:
        return False
    new_id = await upload_wa_media(data, mime or "image/jpeg")
    if not new_id:
        return False
    cap = caption[:1020] if caption else ""
    ok = True
    for to in recipients:
        if not await send_image_by_media_id(to, new_id, caption=cap):
            ok = False
    return ok


async def send_text(to: str, body: str) -> bool:
    """Send a plain-text WhatsApp message."""
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(WHATSAPP_API_URL, headers=headers, json=data)
        if resp.status_code != 200:
            logger.error("WhatsApp send failed: %s %s", resp.status_code, resp.text)
            return False
        return True


async def send_interactive_buttons(to: str, body: str, buttons: list[dict]) -> bool:
    """Send an interactive button message.

    buttons: [{"id": "btn_rates", "title": "आज के भाव"}]  (max 3)
    """
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    btn_rows = [
        {"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}}
        for b in buttons[:3]
    ]
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {"buttons": btn_rows},
        },
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(WHATSAPP_API_URL, headers=headers, json=data)
        if resp.status_code != 200:
            logger.error("WhatsApp buttons failed: %s %s", resp.status_code, resp.text)
            return False
        return True


async def send_list_menu(to: str, body: str, button_text: str, sections: list[dict]) -> bool:
    """Send an interactive list message for rich menus.

    sections: [{"title": "...", "rows": [{"id": "...", "title": "...", "description": "..."}]}]
    """
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body},
            "action": {
                "button": button_text[:20],
                "sections": sections,
            },
        },
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(WHATSAPP_API_URL, headers=headers, json=data)
        if resp.status_code != 200:
            logger.error("WhatsApp list failed: %s %s", resp.status_code, resp.text)
            return False
        return True


async def send_image(to: str, image_url: str, caption: str = "") -> bool:
    """Send an image message via URL."""
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    image_payload: dict = {"link": image_url}
    if caption:
        image_payload["caption"] = caption
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": image_payload,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(WHATSAPP_API_URL, headers=headers, json=data)
        if resp.status_code != 200:
            logger.error("WhatsApp image send failed: %s %s", resp.status_code, resp.text)
            return False
        return True


async def send_template(to: str, template_name: str, language: str = "hi") -> bool:
    """Send a pre-approved WhatsApp template message (for broadcast outside 24hr window)."""
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
        },
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(WHATSAPP_API_URL, headers=headers, json=data)
        if resp.status_code != 200:
            logger.error("WhatsApp template send failed: %s %s", resp.status_code, resp.text)
            return False
        return True


async def mark_read(msg_id: str) -> None:
    """Mark a message as read (blue ticks)."""
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": msg_id,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(WHATSAPP_API_URL, headers=headers, json=data)
