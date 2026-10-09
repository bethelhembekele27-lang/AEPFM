"""SMS sending for invoice links (Phase 4).

Everything the rest of the app needs from SMS lives in this file:

    normalize_phone(raw)             -> '251XXXXXXXXX' or None
    public_link(invoice)             -> the bidder's /invoice/<token> URL
    build_message(invoice, link, d)  -> default Amharic SMS text (staff can edit it)
    send_sms(phone, message)         -> (success: bool, response_text: str)

send_sms() is the ONLY function that talks to a provider. To change provider later,
rewrite _send_afromessage() or add a new _send_<provider>() and one line in
send_sms(). Models, endpoints, logging and the frontend do not change.

Settings (auction_crm/settings.py):
    SMS_BACKEND              'console' (default: logs only, sends nothing) or 'afromessage'
    SMS_ALLOWED_NUMBERS      optional allowlist; when non-empty ONLY these numbers can be texted
    AFROMESSAGE_TOKEN        API token (environment variable only, never in source)
    AFROMESSAGE_IDENTIFIER_ID  optional sender id issued by the provider
    AFROMESSAGE_SENDER       optional display sender name
"""
import logging
import re

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


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
        f"ውድ {name}፣ የአክሽን ኢትዮጵያ የጨረታ ፕሮሰሲንግ ክፍያ ደረሰኝዎ ተዘጋጅቷል። "
        f"ደረሰኙን ለማየት እና የክፍያ ደረሰኝ ለመላክ፦ {link} "
        f"እባክዎ እስከ {due} ድረስ ይክፈሉ።"
    )


AFRO_SEND_URL = 'https://api.afromessage.com/api/send'


def _send_afromessage(phone, message):
    if not settings.AFROMESSAGE_TOKEN:
        return False, 'AFROMESSAGE_TOKEN is not set on the server.'
    payload = {'to': f'+{phone}', 'message': message}
    if settings.AFROMESSAGE_IDENTIFIER_ID:
        payload['from'] = settings.AFROMESSAGE_IDENTIFIER_ID
    if settings.AFROMESSAGE_SENDER:
        payload['sender'] = settings.AFROMESSAGE_SENDER
    try:
        res = requests.post(AFRO_SEND_URL, headers={'Authorization': f'Bearer {settings.AFROMESSAGE_TOKEN}'},
                            json=payload, timeout=20)
    except requests.RequestException as exc:
        return False, f'Network error talking to Afro Message: {exc}'
    body = res.text[:1000]
    if not 200 <= res.status_code < 300:
        return False, f'Afro Message HTTP {res.status_code}: {body}'
    try:
        data = res.json()
    except ValueError:
        return False, f'Afro Message returned a non-JSON body: {body}'
    if data.get('acknowledge') != 'success':
        return False, f'Afro Message reported failure: {body}'
    return True, f'Afro Message HTTP {res.status_code}: {body}'


def build_rejection_message(invoice, note='', remaining=None, wrong_account=False):
    """Amharic - needs native-speaker review like the other SMS texts."""
    winner = invoice.winner
    name = winner.bidderNameAmharic or winner.bidderName
    link = public_link(invoice)
    reason = f" ምክንያት፡ {note}" if note else ""
    if remaining is not None and remaining > 0:      # underpaid only; never mention overpayment
        return (f"ውድ {name}፣ የላኩት ክፍያ ከሚጠበቀው ያነሰ ነው።{reason} ቀሪ መክፈል የሚገባዎት ብር {remaining:,.2f} ነው። "
                f"ቀሪውን ከፍለው ደረሰኙን በዚህ አገናኝ ይላኩ፦ {link}")
    if wrong_account:
        acct = settings.VERIFY_ET_SETTLEMENT_ACCOUNTS.get('cbe', '')
        return (f"ውድ {name}፣ የላኩት ክፍያ ወደ አክሽን ኢትዮጵያ ሂሳብ አልገባም።{reason} እባክዎ ወደ ኢትዮጵያ ንግድ ባንክ ሂሳብ ቁጥር {acct} "
                f"ከፍለው ደረሰኙን በዚህ አገናኝ ይላኩ፦ {link}")
    return f"ውድ {name}፣ የላኩት የክፍያ ደረሰኝ ውድቅ ተደርጓል።{reason} እባክዎ በዚሁ አገናኝ በድጋሚ ይላኩ፦ {link}"


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
    if backend == 'afromessage':
        return _send_afromessage(phone, message)
    return False, f'Unknown SMS_BACKEND "{backend}".'
