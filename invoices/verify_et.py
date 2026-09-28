"""Verify.ET - CBE only. Never raises: returns (result | None, error | None)."""
import logging
import re
import requests
from django.conf import settings

logger = logging.getLogger(__name__)
VERIFY_ET_URL = 'https://verify.et/api/verify'
TIMEOUT_SECONDS = 25
NOT_CONFIGURED = 'Verify.ET is not configured on this server.'


def _headers():
    return {'x-api-key': settings.VERIFY_ET_API_KEY, 'Content-Type': 'application/json'}


def _build_result(payload, settlement_account):
    items = payload.get('data') or []
    first = items[0] if items else {}
    settlement = first.get('settlementAccountMatch') or {}
    return {
        'bank': 'cbe',
        'requestId': payload.get('requestId', ''),
        'processingStatus': 'completed',
        'verified': first.get('verified'),
        'amount': first.get('amount'),
        'currency': first.get('currency', ''),
        'senderName': first.get('senderName', ''),
        'receiverName': first.get('receiverName', ''),
        'receiverAccount': first.get('receiverAccount', ''),
        # Only meaningful when WE sent a settlement account (see earlier false-positive fix)
        'settlementMatched': settlement.get('matched') if settlement_account else None,
        'rawResponse': payload,
        'errorMessage': '',
    }


def _queued_result(payload):
    v = payload.get('verification') or {}
    raw = dict(payload)
    return {
        'bank': 'cbe', 'requestId': payload.get('requestId', ''),
        'processingStatus': v.get('processingStatus', 'queued'),
        'verified': None, 'amount': None, 'currency': '', 'senderName': '',
        'receiverName': '', 'receiverAccount': '', 'settlementMatched': None,
        'rawResponse': raw, 'errorMessage': '',
    }


ERROR_MAP = {
    401: 'Invalid Verify.ET API key.', 402: 'Verify.ET verification credits are exhausted.',
    403: 'Permission denied by Verify.ET.', 409: 'Duplicate request (idempotency conflict).',
    422: 'Verify.ET rejected the data - check the reference number and account suffix.',
    429: 'Verify.ET rate limit reached, try again shortly.', 503: 'Verify.ET is temporarily unavailable.',
}


def check_transaction(reference, suffix='', settlement_account=None, wait_ms=15000):
    if not settings.VERIFY_ET_API_KEY:
        return None, NOT_CONFIGURED
    if not reference:
        return None, 'A reference number is required.'
    suffix = re.sub(r'\D', '', suffix or settings.VERIFY_ET_CBE_SUFFIX or '')
    if len(suffix) != 8:
        return None, 'CBE needs an 8-digit account suffix.'
    body = {'bank': 'cbe', 'referenceNumber': reference, 'accountSuffix': suffix}
    if settlement_account:
        body['settlementAccount'] = settlement_account
    try:
        res = requests.post(f'{VERIFY_ET_URL}?waitMs={wait_ms}', headers=_headers(), json=body, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        logger.exception('Verify.ET network error')
        return None, f'Network error contacting Verify.ET: {exc}'
    try:
        payload = res.json()
    except ValueError:
        return None, f'Verify.ET returned an unreadable response (HTTP {res.status_code}).'
    if res.status_code == 200:
        return _build_result(payload, settlement_account), None
    if res.status_code == 202:
        return _queued_result(payload), None
    return None, ERROR_MAP.get(res.status_code, f'Verify.ET error (HTTP {res.status_code}): {payload.get("message", "")}')


def fetch_status(status_url, settlement_account=None):
    """Follow up a queued (202) check. ASSUMPTION: the status endpoint returns the same
    shape as a completed POST. Verify with a real statusUrl before relying on it."""
    if not settings.VERIFY_ET_API_KEY:
        return None, NOT_CONFIGURED
    if status_url.startswith('/'):
        status_url = 'https://verify.et' + status_url
    if not status_url.startswith('https://verify.et/'):
        return None, 'Unexpected status URL.'   # SSRF guard: never call arbitrary hosts
    try:
        res = requests.get(status_url, headers=_headers(), timeout=TIMEOUT_SECONDS)
        payload = res.json()
    except (requests.RequestException, ValueError) as exc:
        return None, f'Could not refresh the Verify.ET check: {exc}'
    if res.status_code == 200 and payload.get('data'):
        return _build_result(payload, settlement_account), None
    v = payload.get('verification') or {}
    state = v.get('processingStatus', 'queued')
    if res.status_code in (200, 202):
        result = _queued_result(payload)
        if state in ('failed', 'error', 'expired'):
            result['errorMessage'] = payload.get('message', 'Verify.ET could not complete this check.')
        return result, None
    return None, ERROR_MAP.get(res.status_code, f'Verify.ET error (HTTP {res.status_code})')
