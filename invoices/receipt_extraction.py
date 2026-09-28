"""
Gemini-based receipt data extraction — isolated in its own file, same
reasoning as sms.py: if you ever swap providers later, only this file
changes.
"""
import json
import logging

import google.generativeai as genai
from django.conf import settings

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are looking at a photo of a bank or VAT receipt/invoice submitted as proof of payment.
Extract the following fields as JSON only, no other text:
{
  "tin": "the TIN number of the issuing company/bank, if visible",
  "receiptNumber": "the receipt or invoice number",
  "bankReferenceNumber": "the bank transfer or transaction reference number, if any — different from the receipt/invoice number, look for something labeled reference, transaction ID, or FT number; null if not present or this isn't a bank-transfer receipt",
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

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-3.8-flash')
        response = model.generate_content([EXTRACTION_PROMPT, {'mime_type': mime_type, 'data': image_bytes}], request_options={'timeout': 20})
        text = response.text.strip()
        if text.startswith('```'):
            text = text.strip('`').removeprefix('json').strip()
        data = json.loads(text)
        return data, None, {'text': response.text}
    except json.JSONDecodeError:
        logger.exception('Gemini returned non-JSON')
        return None, 'The AI response could not be parsed. Try again.', {'text': getattr(response, 'text', '')}
    except Exception as e:
        logger.exception('Gemini extraction failed')
        return None, f'Extraction failed: {e}', {}


def _receipt_files(payment):
    files = [payment.receiptFile] if payment.receiptFile else []
    return files + [rf.file for rf in payment.receipt_files.all()]


def run_and_save_extraction(payment, user):
    """
    Runs extraction and saves it, or returns (None, error_string) on
    failure. Shared by the manual "Extract with AI" endpoint and the
    best-effort auto-trigger on approval — callers decide what to do with
    a failure (the manual endpoint returns it as an error response; the
    auto-trigger on approval just logs it and moves on).
    """
    import mimetypes
    from .models import ReceiptExtraction
    from .sms import normalize_phone

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

    def to_decimal(v):
        return None if v in (None, '') else v

    from .ethiopian_calendar import parse_and_convert
    converted = parse_and_convert(data.get('extractedDate') or '') or ''

    extraction, _ = ReceiptExtraction.objects.update_or_create(
        payment=payment,
        defaults={
            'tin': data.get('tin') or '',
            'receiptNumber': data.get('receiptNumber') or '',
            'bankReferenceNumber': data.get('bankReferenceNumber') or '',
            'detectedBank': (data.get('detectedBank') or '').strip().lower(),
            'detectedPhoneNumber': normalize_phone(data.get('detectedPhoneNumber') or '') or '',
            'extractedDate': data.get('extractedDate') or '',
            'convertedGregorianDate': converted,
            'customerName': data.get('customerName') or '',
            'totalAmount': to_decimal(data.get('totalAmount')),
            'vatAmount': to_decimal(data.get('vatAmount')),
            'description': data.get('description') or '',
            'extractionConfidence': data.get('extractionConfidence') or '',
            'rawResponse': raw,
            'extractedBy': user,
        },
    )
    return extraction, None