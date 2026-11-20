"""TextSMS Kenya send protocol for CUE leak alerts."""

from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def normalize_ke_mobile(phone: str) -> str | None:
    """Normalize to 2547XXXXXXXX (TextSMS expects country code, no +)."""
    mobile = "".join(ch for ch in str(phone or "") if ch.isdigit() or ch == "+")
    if not mobile:
        return None
    if mobile.startswith("+"):
        mobile = mobile[1:]
    if mobile.startswith("0") and len(mobile) == 10:
        mobile = "254" + mobile[1:]
    elif len(mobile) == 9 and mobile.startswith("7"):
        mobile = "254" + mobile
    if not (mobile.startswith("254") and len(mobile) == 12):
        return None
    return mobile


def sms_configured() -> bool:
    return bool(
        getattr(settings, "TEXTSMS_API_KEY", "")
        and getattr(settings, "TEXTSMS_PARTNER_ID", "")
        and list(getattr(settings, "ALERT_PHONES", []) or [])
    )


def send_sms(message: str, phones: list[str] | None = None) -> list[dict[str, Any]]:
    """
    POST to TextSMS sendsms API for each alert phone.

    Protocol (JSON body):
      apikey, partnerID, message, shortcode, mobile
    Success when HTTP OK and response-code / respose-code == 200.
    """
    key = getattr(settings, "TEXTSMS_API_KEY", "") or ""
    partner = getattr(settings, "TEXTSMS_PARTNER_ID", "") or ""
    url = getattr(
        settings,
        "TEXTSMS_API_URL",
        "https://sms.textsms.co.ke/api/services/sendsms/",
    )
    shortcode = getattr(settings, "TEXTSMS_SHORTCODE", "TEXTSms") or "TEXTSms"
    targets = phones if phones is not None else list(getattr(settings, "ALERT_PHONES", []) or [])

    if not key or not partner:
        return [{"ok": False, "error": "SMS not configured (missing API key / partner ID)"}]
    if not targets:
        return [{"ok": False, "error": "SMS not configured (no ALERT_PHONES)"}]

    results: list[dict[str, Any]] = []
    for phone in targets:
        mobile = normalize_ke_mobile(phone)
        if not mobile:
            results.append({"mobile": phone, "ok": False, "error": "invalid phone format"})
            continue
        try:
            resp = requests.post(
                url,
                json={
                    "apikey": key,
                    "partnerID": str(partner),
                    "message": message,
                    "shortcode": shortcode,
                    "mobile": mobile,
                },
                timeout=30,
            )
            data = resp.json() if resp.content else {}
            ok = resp.ok
            rows = data.get("responses") or data.get("response") or []
            if isinstance(rows, dict):
                rows = [rows]
            if rows:
                row = rows[0] if isinstance(rows[0], dict) else {}
                code = (
                    row.get("respose-code")
                    or row.get("response-code")
                    or row.get("response_code")
                    or row.get("code")
                )
                try:
                    ok = ok and int(code) == 200
                except (TypeError, ValueError):
                    ok = ok and str(code) == "200"
            results.append(
                {
                    "mobile": mobile,
                    "ok": ok,
                    "http_status": resp.status_code,
                    "body": data,
                }
            )
            if ok:
                logger.info("SMS sent to %s", mobile)
                try:
                    from finance.services import record_sms_cost

                    record_sms_cost(
                        mobile=mobile,
                        leak_event_id=getattr(settings, "_CUE_LEAK_EVENT_ID", None),
                        ok=True,
                    )
                except Exception:
                    logger.exception("Finance SMS cost record failed for %s", mobile)
            else:
                logger.warning("SMS failed for %s: %s", mobile, data)
        except Exception as exc:
            logger.exception("SMS request error for %s", phone)
            results.append({"mobile": mobile or phone, "ok": False, "error": str(exc)})
    return results
