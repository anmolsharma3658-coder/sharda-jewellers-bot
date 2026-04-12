"""Live chat relay — bridges customer ↔ owner through the bot.

Flow:
  1. Customer triggers [CONNECT_OWNER] → session created, owners notified
  2. Owner replies to bot → auto-linked to that customer, message forwarded
  3. All subsequent messages relayed both ways until session ends
  4. Owner sends "close"/"end"/"बंद" → session ends, bot resumes AI for customer
  5. Sessions auto-expire after 2 hours of inactivity
"""

import re
import time
import logging

logger = logging.getLogger(__name__)

SESSION_TIMEOUT = 2 * 60 * 60  # 2 hours

_sessions: dict[str, dict] = {}
_owner_to_customer: dict[str, str] = {}


def start_session(customer_phone: str, customer_name: str = "") -> None:
    """Create a pending live-chat session (no owner linked yet)."""
    end_session_for_customer(customer_phone)
    _sessions[customer_phone] = {
        "customer_name": customer_name,
        "owner_phone": None,
        "started_at": time.time(),
        "last_activity": time.time(),
    }
    logger.info("Live chat session started for customer %s", customer_phone)


def get_session(customer_phone: str) -> dict | None:
    """Return active session or None (auto-cleans expired)."""
    session = _sessions.get(customer_phone)
    if not session:
        return None
    if time.time() - session["last_activity"] > SESSION_TIMEOUT:
        end_session_for_customer(customer_phone)
        return None
    return session


def customer_in_session(customer_phone: str) -> bool:
    return get_session(customer_phone) is not None


def owner_has_session(owner_phone: str) -> str | None:
    """If this owner is linked to a customer, return the customer phone."""
    customer_phone = _owner_to_customer.get(owner_phone)
    if not customer_phone:
        return None
    session = get_session(customer_phone)
    if not session or session.get("owner_phone") != owner_phone:
        _owner_to_customer.pop(owner_phone, None)
        return None
    return customer_phone


def find_pending_session() -> str | None:
    """Find a customer waiting for an owner (no owner assigned yet)."""
    for phone, session in list(_sessions.items()):
        if time.time() - session["last_activity"] > SESSION_TIMEOUT:
            end_session_for_customer(phone)
            continue
        if session["owner_phone"] is None:
            return phone
    return None


def link_owner(owner_phone: str, customer_phone: str) -> bool:
    """Link an owner to a pending customer session."""
    session = get_session(customer_phone)
    if not session:
        return False
    if session["owner_phone"] is not None:
        return session["owner_phone"] == owner_phone
    session["owner_phone"] = owner_phone
    session["last_activity"] = time.time()
    _owner_to_customer[owner_phone] = customer_phone
    logger.info("Owner %s linked to customer %s", owner_phone, customer_phone)
    return True


def touch(customer_phone: str) -> None:
    session = _sessions.get(customer_phone)
    if session:
        session["last_activity"] = time.time()


def end_session_for_customer(customer_phone: str) -> bool:
    session = _sessions.pop(customer_phone, None)
    if not session:
        return False
    owner = session.get("owner_phone")
    if owner and _owner_to_customer.get(owner) == customer_phone:
        _owner_to_customer.pop(owner, None)
    logger.info("Live chat session ended for customer %s", customer_phone)
    return True


def end_session_for_owner(owner_phone: str) -> str | None:
    """End session from the owner side. Returns customer phone or None."""
    customer_phone = _owner_to_customer.pop(owner_phone, None)
    if customer_phone:
        _sessions.pop(customer_phone, None)
        logger.info("Owner %s ended session with customer %s", owner_phone, customer_phone)
    return customer_phone


END_KEYWORDS = frozenset({
    "close", "end", "done", "stop", "exit",
    "बंद", "समाप्त", "खत्म", "ok done", "band",
})


def is_end_command(text: str) -> bool:
    return text.strip().lower() in END_KEYWORDS


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


# Only these patterns may start a live owner relay (stops AI from paging owners for every prompt).
_OWNER_INTENT_ROMAN = (
    "malik se baat",
    "malik se bat",
    "owner se baat",
    "owner se bat",
    "baat karao malik",
    "baat karao owner",
    "mujhe malik",
    "mujhe owner",
    "malik ko bula",
    "owner ko bula",
    "insaan se baat",
    "human se baat",
    "real person",
    "bande se baat",
    "manager se baat",
    "speak to the owner",
    "talk to the owner",
    "talk with the owner",
    "connect me to owner",
    "connect me to the owner",
    "need the owner",
    "human agent",
    "customer care executive",
)

_OWNER_INTENT_DEVANAGARI = (
    "मालिक से बात",
    "मालिक से मिल",
    "मालिक को बुल",
    "ओनर से बात",
    "मालिक जी से बात",
    "इंसान से बात",
    "व्यक्ति से बात",
)

_COMPLAINT_MARKERS_ROMAN = (
    "complaint",
    "refund",
    "defective",
    "duplicate piece",
    "fraud",
    "police",
    "court",
    "consumer court",
    "cheat",
    "scam",
)

_COMPLAINT_MARKERS_HI = (
    "शिकायत",
    "पैसा वापस",
    "गलत सामान",
    "ठग",
)

_ORDER_CONTEXT = (
    "order",
    "खरीद",
    "खरीदा",
    "purchase",
    "गहना",
    "jewel",
    "piece",
    "item",
    "डिलीवर",
    "deliver",
    "payment",
    "पेमेंट",
    "bill",
    "रसीद",
    "invoice",
)


def owner_escalation_allowed(customer_message: str) -> bool:
    """True only when the customer clearly wants the owner or a serious purchase dispute.

    The bot must handle rates, photos, collections, custom orders, and general questions alone.
    """
    raw = (customer_message or "").strip()
    if not raw:
        return False

    low = _norm(raw)

    for phrase in _OWNER_INTENT_ROMAN:
        if phrase in low:
            return True

    for phrase in _OWNER_INTENT_DEVANAGARI:
        if phrase in raw:
            return True

    complaint = any(m in low for m in _COMPLAINT_MARKERS_ROMAN) or any(
        m in raw for m in _COMPLAINT_MARKERS_HI
    )
    if complaint:
        order_ctx = any(c in low for c in _ORDER_CONTEXT) or any(
            c in raw for c in ("गहना", "ऑर्डर", "खरीद", "बिल", "रसीद")
        )
        if order_ctx:
            return True

    return False
