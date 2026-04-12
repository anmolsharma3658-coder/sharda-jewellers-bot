import os
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "sharda-jewellers-bot-2024")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# Imagen (same Google AI key — billing / model access may apply). Docs: https://ai.google.dev/gemini-api/docs/imagen
GEMINI_IMAGEN_MODEL = os.getenv("GEMINI_IMAGEN_MODEL", "imagen-4.0-fast-generate-001")
AI_IMAGE_GENERATION_ENABLED = os.getenv("AI_IMAGE_GENERATION", "true").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
GOLD_API_KEY = os.getenv("GOLD_API_KEY", "")
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")

OWNER_PHONES = ["919425561850", "917000344110"]

ADMIN_KEY = os.getenv("ADMIN_KEY", "sharda-admin-2024")

WHATSAPP_GRAPH_VERSION = "v21.0"
WHATSAPP_GRAPH_BASE = f"https://graph.facebook.com/{WHATSAPP_GRAPH_VERSION}"
WHATSAPP_API_URL = f"{WHATSAPP_GRAPH_BASE}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
WHATSAPP_MEDIA_UPLOAD_URL = f"{WHATSAPP_GRAPH_BASE}/{WHATSAPP_PHONE_NUMBER_ID}/media"
