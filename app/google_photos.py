"""Fetch photos from Sharda Jewellers' Google Business Profile via Places API."""

import time
import logging
import httpx
from app.config import GOOGLE_PLACES_API_KEY

logger = logging.getLogger(__name__)

STORE_QUERY = "Sharda Jewellers Bemetara Chhattisgarh"
PLACES_BASE = "https://places.googleapis.com/v1"

CACHE_TTL = 24 * 60 * 60  # 24 hours

_cache: dict = {
    "place_id": None,
    "photo_urls": [],
    "fetched_at": 0.0,
}


async def _find_place_id() -> str | None:
    """Look up the Place ID for Sharda Jewellers via Text Search."""
    if _cache["place_id"]:
        return _cache["place_id"]

    url = f"{PLACES_BASE}/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": "places.id,places.displayName",
    }
    body = {"textQuery": STORE_QUERY}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, headers=headers, json=body)
            if resp.status_code == 200:
                data = resp.json()
                places = data.get("places", [])
                if places:
                    _cache["place_id"] = places[0]["id"]
                    logger.info("Found Place ID: %s", _cache["place_id"])
                    return _cache["place_id"]
            logger.error("Places Text Search failed: %s %s", resp.status_code, resp.text)
    except Exception:
        logger.error("Places Text Search call failed", exc_info=True)
    return None


async def _fetch_photo_refs(place_id: str) -> list[dict]:
    """Fetch photo references for a place."""
    url = f"{PLACES_BASE}/places/{place_id}"
    headers = {
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": "photos",
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("photos", [])
            logger.error("Places Details failed: %s %s", resp.status_code, resp.text)
    except Exception:
        logger.error("Places Details call failed", exc_info=True)
    return []


async def _resolve_photo_url(photo_name: str, max_width: int = 800) -> str | None:
    """Resolve a photo reference to a direct image URL via skipHttpRedirect."""
    url = (
        f"{PLACES_BASE}/{photo_name}/media"
        f"?key={GOOGLE_PLACES_API_KEY}"
        f"&maxWidthPx={max_width}"
        f"&skipHttpRedirect=true"
    )
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("photoUri")
            logger.error("Photo resolve failed: %s %s", resp.status_code, resp.text)
    except Exception:
        logger.error("Photo resolve call failed", exc_info=True)
    return None


async def _resolve_all_photos(photo_refs: list[dict], max_count: int = 10) -> list[str]:
    """Resolve multiple photo references to direct URLs."""
    urls = []
    for ref in photo_refs[:max_count]:
        direct_url = await _resolve_photo_url(ref["name"])
        if direct_url:
            urls.append(direct_url)
    return urls


async def get_store_photos(count: int = 5) -> list[str]:
    """Return up to `count` direct photo URLs for Sharda Jewellers.

    Uses a 24-hour cache to minimize API calls.
    """
    if not GOOGLE_PLACES_API_KEY:
        logger.warning("GOOGLE_PLACES_API_KEY not set")
        return []

    now = time.time()
    if _cache["photo_urls"] and (now - _cache["fetched_at"]) < CACHE_TTL:
        return _cache["photo_urls"][:count]

    place_id = await _find_place_id()
    if not place_id:
        return []

    photo_refs = await _fetch_photo_refs(place_id)
    if not photo_refs:
        return _cache["photo_urls"][:count] if _cache["photo_urls"] else []

    resolved = await _resolve_all_photos(photo_refs, max_count=10)
    if resolved:
        _cache["photo_urls"] = resolved
        _cache["fetched_at"] = now
        return resolved[:count]

    return _cache["photo_urls"][:count] if _cache["photo_urls"] else []
