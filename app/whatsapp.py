"""WhatsApp Cloud API integration for sending and parsing messages."""

import logging
import httpx
from app.config import WHATSAPP_TOKEN, WHATSAPP_API_URL

logger = logging.getLogger(__name__)


def extract_message(payload: dict) -> dict | None:
    """Pull sender phone and text from a WhatsApp webhook payload.

    Returns {"from": "91...", "text": "...", "name": "..."} or None.
    """
    try:
        entry = payload["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        if "messages" not in value:
            return None

        msg = value["messages"][0]
        if msg.get("type") != "text":
            return None

        contact = value.get("contacts", [{}])[0]
        return {
            "from": msg["from"],
            "text": msg["text"]["body"],
            "name": contact.get("profile", {}).get("name", ""),
            "msg_id": msg["id"],
        }
    except (KeyError, IndexError):
        logger.warning("Could not parse webhook payload", exc_info=True)
        return None


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
