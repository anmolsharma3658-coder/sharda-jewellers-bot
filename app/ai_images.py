"""AI-generated jewellery inspiration images via Google Imagen (Gemini API).

See: https://ai.google.dev/gemini-api/docs/imagen
Outputs are watermarked (SynthID) and for inspiration only — not real inventory.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re

from google import genai
from google.genai import types

from app.config import (
    AI_IMAGE_GENERATION_ENABLED,
    GEMINI_API_KEY,
    GEMINI_IMAGEN_MODEL,
)

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def _client_or_none() -> genai.Client | None:
    global _client
    if not GEMINI_API_KEY or not AI_IMAGE_GENERATION_ENABLED:
        return None
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


JEWELRY_PREFIX = (
    "Professional studio product photograph of a single Indian jewellery piece, "
    "macro detail, elegant, soft neutral background, photorealistic, "
    "no human face, no hands, no body parts, no text overlay, no brand logo: "
)


def _image_bytes_from_generated(gi) -> bytes | None:
    img = getattr(gi, "image", None)
    if not img:
        return None
    raw = getattr(img, "image_bytes", None)
    if not raw:
        return None
    if isinstance(raw, str):
        try:
            return base64.b64decode(raw)
        except Exception:
            return None
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    return None


async def generate_jewellery_image_bytes(english_prompt: str) -> bytes | None:
    """Return one JPEG image, or None if disabled / filtered / error."""
    client = _client_or_none()
    if not client:
        logger.info("AI image generation skipped (disabled or no API key).")
        return None
    clean = re.sub(r"\s+", " ", (english_prompt or "").strip())[:450]
    if len(clean) < 4:
        return None
    full_prompt = JEWELRY_PREFIX + clean

    def _call():
        return client.models.generate_images(
            model=GEMINI_IMAGEN_MODEL,
            prompt=full_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/jpeg",
                aspect_ratio="1:1",
                person_generation="dont_allow",
            ),
        )

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _call)
    except Exception:
        logger.exception("Imagen generate_images API error")
        return None

    if not response.generated_images:
        http = getattr(response, "sdk_http_response", None)
        sc = getattr(http, "status_code", None) if http is not None else None
        logger.warning("Imagen returned zero images (http_status=%s)", sc)
        return None

    first = response.generated_images[0]
    reason = getattr(first, "rai_filtered_reason", None)
    if reason:
        logger.warning("Imagen RAI filtered image: %s", reason)
        return None

    data = _image_bytes_from_generated(first)
    if not data:
        img = getattr(first, "image", None)
        logger.warning(
            "Imagen image had no usable image_bytes (gcs_uri=%s mime=%s)",
            getattr(img, "gcs_uri", None),
            getattr(img, "mime_type", None),
        )
    else:
        logger.info("Imagen OK: %s bytes JPEG", len(data))
    return data


async def extract_imagen_prompt_from_user_text(user_text: str) -> str:
    """Turn customer language into a short English-only jewellery description for Imagen."""
    client = _client_or_none()
    if not client:
        return ""
    text = (user_text or "").strip()[:800]
    if not text:
        return ""

    sys = (
        "You write ONE short English phrase (max 60 words) describing ONLY a jewellery piece "
        "for a product photo: metal, stones, style (e.g. temple, choker, jhumka). "
        "No people, no face, no hands. No brand names. Output ONLY the phrase, no quotes."
    )

    def _call():
        return client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[types.Content(role="user", parts=[types.Part(text=text)])],
            config=types.GenerateContentConfig(
                system_instruction=sys,
                temperature=0.4,
                max_output_tokens=200,
            ),
        )

    try:
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(None, _call)
        out = (resp.text or "").strip()
        out = re.sub(r'^["\']|["\']$', "", out)
        return out[:450]
    except Exception:
        logger.exception("extract_imagen_prompt_from_user_text failed")
        return ""
