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
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content([
            EXTRACTION_PROMPT,
            {'mime_type': mime_type, 'data': image_bytes},
        ])
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