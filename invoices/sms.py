"""SMS sending for invoice links (Phase 4).

Everything the rest of the app needs from SMS lives in this file:

    normalize_phone(raw)             -> '251XXXXXXXXX' or None
    public_link(invoice)             -> the bidder's /invoice/<token> URL
    build_message(invoice, link, d)  -> default Amharic SMS text (staff can edit it)
    send_sms(phone, message)         -> (success: bool, response_text: str)

send_sms() is the ONLY function that talks to a provider. To change provider later
(textbee -> the company's own gateway), rewrite _send_textbee() or add a new
_send_<provider>() and one line in send_sms(). Models, endpoints, logging and the
frontend do not change.

Settings (auction_crm/settings.py):
    SMS_BACKEND          'console' (default: logs only, sends nothing) or 'textbee'
    SMS_ALLOWED_NUMBERS  optional allowlist; when non-empty ONLY these numbers can be texted
    TEXTBEE_API_KEY      textbee API key (environment variable only, never in source)
    TEXTBEE_DEVICE_ID    optional; when empty textbee uses the account's default device
"""
import logging
import re

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TEXTBEE_SEND_URL = 'https://api.textbee.dev/api/v1/gateway/send-sms'
TEXTBEE_TIMEOUT_SECONDS = 20

_MOBILE_RE = re.compile(r'^251[79]\d{8}$')


def normalize_phone(raw):
    """Return digits-only 251XXXXXXXXX for an Ethiopian mobile number, else None.

    Accepts 09xxxxxxxx, 07xxxxxxxx, 9xxxxxxxx, 2519xxxxxxxx, +2519xxxxxxxx, 002519xxxxxxxx.
    """
    digits = re.sub(r'\D', '', str(raw or ''))
    if digits.startswith('00251'):
        digits = digits[2:]
    if len(digits) == 10 and digits.startswith('0'):
        digits = '251' + digits[1:]
    elif len(digits) == 9 and digits[0] in '79':
        digits = '251' + digits
    return digits if _MOBILE_RE.match(digits) else None


def public_link(invoice):
    return f"{settings.FRONTEND_BASE_URL}/invoice/{invoice.publicToken}"


def build_message(invoice, link, due_date):
    """Default Amharic SMS text. Needs a native-speaker review before real bidders get it."""
    winner = invoice.winner
    name = winner.bidderNameAmharic or winner.bidderName
    due = due_date.strftime('%d/%m/%Y')
    return (
        f"ውድ {name}፣ የአክሽን ኢትዮጵያ የጨረታ processing fee ደረሰኝዎ ተዘጋጅቷል። "
        f"ደረሰኙን ለማየት እና የክፍያ ደረሰኝ ለመላክ፦ {link} "
        f"እባክዎ እስከ {due} ድረስ ይክፈሉ።"
    )


def send_sms(phone, message):
    """Send ONE SMS. `phone` is 251XXXXXXXXX (digits only).

    Returns (success, response_text). Provider problems never raise: they come back as
    (False, reason) so the caller can log them and show them to staff.
    """
    allowed = {normalize_phone(n) for n in settings.SMS_ALLOWED_NUMBERS}
    if allowed and phone not in allowed:
        return False, 'Blocked: this number is not in SMS_ALLOWED_NUMBERS (the safety allowlist is active).'

    backend = settings.SMS_BACKEND
    if backend == 'console':
        logger.warning('SMS (console backend, NOT really sent) to +%s: %s', phone, message)
        return True, 'console backend: nothing was really sent'
    if backend == 'textbee':
        return _send_textbee(phone, message)
    return False, f'Unknown SMS_BACKEND "{backend}".'


def _send_textbee(phone, message):
    if not settings.TEXTBEE_API_KEY:
        return False, 'TEXTBEE_API_KEY is not set on the server.'

    payload = {'recipients': [f'+{phone}'], 'message': message}
    if settings.TEXTBEE_DEVICE_ID:
        payload['deviceId'] = settings.TEXTBEE_DEVICE_ID

    try:
        res = requests.post(
            TEXTBEE_SEND_URL,
            headers={'x-api-key': settings.TEXTBEE_API_KEY},
            json=payload,
            timeout=TEXTBEE_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return False, f'Network error talking to textbee: {exc}'

    body = res.text[:1000]
    if not 200 <= res.status_code < 300:
        return False, f'textbee HTTP {res.status_code}: {body}'

    # TODO(after the first real response is seen): the docs page shows no example body.
    # For now: HTTP 2xx = accepted by textbee, unless the JSON explicitly says success=false.
    # NOTE: "accepted" means queued to the paired phone, NOT delivered to the bidder.
    try:
        data = res.json()
    except ValueError:
        return True, f'textbee HTTP {res.status_code} (non-JSON body): {body}'
    if isinstance(data, dict) and data.get('success') is False:
        return False, f'textbee reported failure: {body}'
    return True, f'textbee HTTP {res.status_code}: {body}'
