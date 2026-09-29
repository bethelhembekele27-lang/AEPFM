"""Gemini-based receipt data extraction - isolated so only this file changes if the provider does."""
import json
import logging
import mimetypes
import re
from decimal import Decimal

import google.generativeai as genai
from django.conf import settings

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are looking at a photo of a bank or VAT receipt/invoice submitted as proof of payment.
Extract the following fields as JSON only, no other text:
{
  "tin": "the TIN number of the issuing company/bank, if visible",
  "receiptNumber": "the receipt or invoice number",
  "bankReferenceNumber": "the bank transfer or transaction reference number, if any - different from the receipt/invoice number, look for something labeled reference, transaction ID, or FT number; null if not present or this isn't a bank-transfer receipt",
  "detectedBank": "cbe if this is a Commercial Bank of Ethiopia transfer receipt, other if it is another bank or wallet, null if not a bank transfer receipt",
  "detectedPhoneNumber": "if this is a Telebirr/CBE Birr receipt showing the sender's phone number, extract it; null otherwise",
  "extractedDate": "the date exactly as printed, including which calendar if stated",
  "customerName": "the name of the person/company the receipt was issued to",
  "totalAmount": "the final total amount as a plain number, no currency symbol or commas",
  "vatAmount": "the VAT amount as a plain number, if shown separately",
  "description": "a short description of what was paid for",
  "extractionConfidence": "high, medium, or low, your own honest assessment of how legible/clear this receipt was"
}
If a field is not visible or not present, use null for that field. Do not guess."""


def extract_receipt_data(image_bytes, mime_type):
    """Returns (data: dict | None, error: str | None, raw_response: dict)."""
    if not settings.GEMINI_API_KEY:
        return None, 'GEMINI_API_KEY is not set on the server.', {}
    text = ''
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)
        response = model.generate_content(
            [EXTRACTION_PROMPT, {'mime_type': mime_type, 'data': image_bytes}],
            request_options={'timeout': 45},
        )
        text = (response.text or '').strip()
        if text.startswith('```'):
            text = text.strip('`').removeprefix('json').strip()
        data = json.loads(text)
        if not isinstance(data, dict):
            return None, 'The AI returned an unexpected format.', {'text': text}
        return data, None, {'text': text}
    except json.JSONDecodeError:
        logger.exception('Gemini returned non-JSON')
        return None, 'The AI response could not be parsed as JSON.', {'text': text}
    except Exception as e:
        logger.exception('Gemini extraction failed')
        return None, f'Gemini error ({type(e).__name__}): {str(e)[:300]}', {}


def _receipt_files(payment):
    files = [payment.receiptFile] if payment.receiptFile else []
    return files + [rf.file for rf in payment.receipt_files.all()]


def _clip(value, length):
    return ('' if value is None else str(value)).strip()[:length]


def _num(value):
    """'1,235.00' / 'ETB 1235' -> Decimal, anything unparseable -> None (never raises)."""
    if value in (None, ''):
        return None
    try:
        cleaned = re.sub(r'[^\d.\-]', '', str(value).replace(',', ''))
        return Decimal(cleaned).quantize(Decimal('0.01'))
    except Exception:
        return None


def run_and_save_extraction(payment, user):
    """Returns (extraction, None) or (None, error_string)."""
    from .models import ReceiptExtraction
    from .sms import normalize_phone
    from .ethiopian_calendar import parse_and_convert

    if not payment.receiptFile:
        return None, 'This payment has no receipt file.'

    best, last_error = None, None
    for f in _receipt_files(payment):
        try:
            f.open('rb'); image_bytes = f.read(); f.close()
        except Exception as exc:
            last_error = f'Could not read receipt file: {exc}'; continue
        mime_type = mimetypes.guess_type(f.name)[0] or 'image/jpeg'
        data, error, raw = extract_receipt_data(image_bytes, mime_type)
        if error:
            last_error = error; continue
        if best is None:
            best = (data, raw)
        if data.get('bankReferenceNumber'):
            best = (data, raw); break
    if best is None:
        return None, last_error or 'This payment has no receipt file.'
    data, raw = best

    try:
        extracted_date = _clip(data.get('extractedDate'), 100)
        extraction, _ = ReceiptExtraction.objects.update_or_create(
            payment=payment,
            defaults={
                'tin': _clip(data.get('tin'), 50),
                'receiptNumber': _clip(data.get('receiptNumber'), 100),
                'bankReferenceNumber': _clip(data.get('bankReferenceNumber'), 100).replace(' ', ''),
                'detectedBank': _clip(data.get('detectedBank'), 30).lower(),
                'detectedPhoneNumber': normalize_phone(data.get('detectedPhoneNumber') or '') or '',
                'extractedDate': extracted_date,
                'convertedGregorianDate': parse_and_convert(extracted_date) or '',
                'customerName': _clip(data.get('customerName'), 255),
                'totalAmount': _num(data.get('totalAmount')),
                'vatAmount': _num(data.get('vatAmount')),
                'description': _clip(data.get('description'), 2000),
                'extractionConfidence': _clip(data.get('extractionConfidence'), 20),
                'rawResponse': raw,
                'extractedBy': user,
            },
        )
    except Exception as exc:
        logger.exception('Saving extraction failed')
        return None, f'Could not save the extraction: {type(exc).__name__}: {exc}'
    return extraction, None
