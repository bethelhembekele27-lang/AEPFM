"""
Verify.ET bank/wallet transaction verification — isolated like sms.py and
receipt_extraction.py. If the provider changes, only this file changes.

check_transaction never raises: it returns (result_dict | None, error | None)
so callers can decide whether a failure is fatal (manual endpoint returns it
to the reviewer) or merely logged (nothing here auto-approves anything — a
Verify.ET result is evidence for a human, never an automatic decision).
"""
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

VERIFY_ET_URL = 'https://verify.et/api/verify'
TIMEOUT_SECONDS = 20

SUFFIX_BANKS = {'cbe', 'boa'}
PHONE_BANKS = {'cbebirr'}

NOT_CONFIGURED = 'Verify.ET is not configured on this server.'


def check_transaction(bank, reference, suffix='', phone_number='', settlement_account=None, wait_ms=5000):
    """Returns (result_dict | None, error_string | None). Never raises."""
    if not settings.VERIFY_ET_API_KEY:
        return None, NOT_CONFIGURED
    if not reference:
        return None, 'A reference number is required.'

    body = {}
    if bank:
        body['bank'] = bank
        body['referenceNumber'] = reference
        if suffix:
            body['accountSuffix'] = suffix
        if phone_number:
            body['phoneNumber'] = phone_number
    else:
        body['reference'] = reference
        if suffix:
            body['suffix'] = suffix
        if phone_number:
            body['phoneNumber'] = phone_number
    if settlement_account:
        body['settlementAccount'] = settlement_account

    try:
        res = requests.post(
            f'{VERIFY_ET_URL}?waitMs={wait_ms}',
            headers={'x-api-key': settings.VERIFY_ET_API_KEY, 'Content-Type': 'application/json'},
            json=body,
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        logger.exception('Verify.ET network error')
        return None, f'Network error contacting Verify.ET: {exc}'

    try:
        payload = res.json()
    except ValueError:
        return None, f'Verify.ET returned an unreadable response (HTTP {res.status_code}).'

    if res.status_code == 200:
        items = payload.get('data') or []
        first = items[0] if items else {}
        settlement = first.get('settlementAccountMatch') or {}
        return {
            'bank': first.get('bank', bank or ''),
            'requestId': payload.get('requestId', ''),
            'processingStatus': 'completed',
            'verified': first.get('verified'),
            'amount': first.get('amount'),
            'currency': first.get('currency', ''),
            'senderName': first.get('senderName', ''),
            'receiverName': first.get('receiverName', ''),
            'receiverAccount': first.get('receiverAccount', ''),
            'settlementMatched': settlement.get('matched'),
            'rawResponse': payload,
            'errorMessage': '',
        }, None

    if res.status_code == 202:
        verification = payload.get('verification') or {}
        return {
            'bank': bank or '',
            'requestId': payload.get('requestId', ''),
            'processingStatus': verification.get('processingStatus', 'queued'),
            'verified': None,
            'amount': None, 'currency': '', 'senderName': '', 'receiverName': '',
            'receiverAccount': '', 'settlementMatched': None,
            'rawResponse': payload,
            'errorMessage': '',
        }, None

    error_map = {
        401: 'Invalid Verify.ET API key.',
        402: 'Verify.ET verification credits are exhausted.',
        403: 'Permission denied by Verify.ET.',
        409: 'Duplicate request (idempotency conflict).',
        422: 'Invalid data for this bank — check the reference/suffix/phone fields.',
        429: 'Verify.ET rate limit reached, try again shortly.',
        503: 'Verify.ET is temporarily unavailable.',
    }
    return None, error_map.get(res.status_code, f'Verify.ET error (HTTP {res.status_code}): {payload.get("message", "")}')
