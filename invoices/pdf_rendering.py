"""
Shared invoice-letter PDF rendering — used by BOTH the authenticated
"Generate invoice PDF" button (InvoiceViewSet.generate_pdf in views.py)
and the public, token-gated PDF endpoint (PublicInvoicePdfView in
public_views.py). Extracted here so there is exactly ONE template to
maintain — if the letter wording/layout changes, both paths update
automatically.

This is a straight extraction of the html-building logic that used to
live as InvoiceViewSet._render_invoice_html — same signature, same
output. views.py's generate_pdf action should be updated to import and
call render_invoice_html(...) from here instead of calling
self._render_invoice_html(...), and its own copy of the method can be
deleted once that's done.
"""
import base64
import os
from decimal import Decimal

from django.conf import settings


def _join_amharic_list(items):
    """'A' / 'A እና B' / 'A, B እና C' — Amharic-style list joining."""
    items = [str(i) for i in items]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} እና {items[1]}"
    return ", ".join(items[:-1]) + f" እና {items[-1]}"


def load_invoice_images():
    """
    Loads the fixed logo/stamp/signature/footer/watermark images used on
    every invoice letter, base64-encoded for inline embedding in the PDF
    HTML. Missing files degrade gracefully to an empty string rather than
    raising, matching the original behavior.
    """
    images = {}
    static_dir = os.path.join(settings.BASE_DIR, 'invoices', 'static')
    for filename, key in [
        ('logo.png', 'logo'), ('stamp.png', 'stamp'),
        ('signature.png', 'signature'), ('footer.png', 'footer'),
        ('watermark.png', 'watermark'),
    ]:
        filepath = os.path.join(static_dir, filename)
        images[key] = ''
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                images[key] = base64.b64encode(f.read()).decode('utf-8')
    return images


def render_invoice_html(
    invoice, auction_ref_number, images,
    amount_in_words='', fee_in_words='', office_address='',
    total_amount_override=None, fee_amount_override=None,
    bank_account_override='', paragraph1_override='', paragraph2_override='',
):
    """
    Builds the full HTML string for the invoice letter. Pass invoice.lots
    already prefetched if possible to avoid an extra query. Overrides let
    the authenticated "Generate PDF" flow apply staff edits (fee %, custom
    wording) at generation time; the public endpoint calls this with no
    overrides, using whatever is currently saved on the invoice.
    """
    winner = invoice.winner
    display_name = winner.bidderNameAmharic or winner.bidderName
    lots = list(invoice.lots.all())

    total_amount = (
        Decimal(str(total_amount_override))
        if total_amount_override not in (None, '')
        else sum((lot.winningAmount for lot in lots), Decimal('0.00'))
    )
    total_fee = (
        Decimal(str(fee_amount_override))
        if fee_amount_override not in (None, '')
        else sum((lot.lotFee for lot in lots), Decimal('0.00'))
    )
    fee_percentage = lots[0].feePercentage.normalize() if lots else Decimal('0')
    auction_name = lots[0].auctionName if lots else ''
    lot_numbers = _join_amharic_list([lot.lotNumber for lot in lots])
    bank_account = bank_account_override or "1000547266289"

    if paragraph1_override:
        paragraph1 = paragraph1_override
    else:
        amount_words_part = f" ({amount_in_words})" if amount_in_words else ""
        fee_words_part = f" ({fee_in_words})" if fee_in_words else ""
        paragraph1 = (
            f"{auction_name} ለኩባንያው አገልግሎት የማያሰጡ የተለያዩ ዕቃዎችን በጨረታ አወዳድሮ ለመሸጥ ባወጣው የጨረታ ቁጥር {auction_ref_number} "
            f"ተሳትፈው በሎት ቁጥር {lot_numbers} የተጠቀሱትን ለመግዛት ባቀረቡት ጠቅላላ ዋጋ ቫትን ጨምሮ ብር {total_amount:,.2f}{amount_words_part} ሲሆን "
            f"የንብረቶቹን ርክክብ መመሪያ ተመልክተው ከተረከቡ በኋላ ከአሸነፉበት ዋጋ ላይ የሚታሰብ {fee_percentage}% (processing fee) {total_fee:,.2f}{fee_words_part} "
            f"ለአክሽን ኢትዮጵያ የሚከፍሉ ይሆናል፡፡"
        )

    if paragraph2_override:
        paragraph2 = paragraph2_override
    else:
        default_address = "ቦሌ አትላስ ከአውሮፓ ዩኒየን ዝቅ ብሎ ከለላ ህንጻ 3ኛ ፎቅ ቢሮ ቁጥር 301"
        address_text = office_address or default_address
        paragraph2 = f"ስለሆነም በኢትዮጵያ ንግድ ባንክ የሂሳብ ቁጥር {bank_account} ገቢ በማድረግ {address_text} በአካል በመገኘት ደረሰኝ እንዲያስገቡ እንጠይቃለን፡፡"

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{ size: A4; margin: 0; }}
            body {{ font-family: 'Noto Sans Ethiopic', sans-serif; font-size: 16.5px; color: #111; margin: 0; padding: 45px 55px 0 55px; }}
            .header {{ display: flex; justify-content: space-between; align-items: flex-start; }}
            .logo img {{ width: 240px; }}
            .ref-block {{ text-align: right; font-size: 14.5px; }}
            .ref-block div {{ margin-bottom: 6px; }}
            .ref-block .val {{ text-decoration: underline; }}
            hr.rule {{ border: none; border-top: 1px solid #999; margin: 12px 0 30px 0; }}
            .salutation {{ margin: 0 0 15px 0; font-size: 14.5px; }}
            .subject {{ text-align: center; font-weight: bold; text-decoration: underline; margin: 20px 0; font-size: 14.5px; }}
            .body-text {{ text-align: justify; line-height: 2.1; font-size: 14.5px; margin-bottom: 18px; }}
            .closing {{ text-align: right; margin-top: 50px; font-size: 14.5px; }}
            .stamp-sig-row {{ display: flex; justify-content: space-between; align-items: center; margin-top: 40px; }}
            .watermark {{ position: fixed; left: 25%; top: 50%; transform: translate(-50%, -25%); opacity: 0.3; z-index: -1; width: 900px; }}
            .stamp-img {{ width: 250px; margin-left: 50px; }}
            .sig-block {{ text-align: right; font-size: 10.5px; }}
            .sig-img {{ width: 60px; display: block; margin-left: auto; margin-bottom: 4px; }}
            .footer-band {{ position: fixed; bottom: 0; left: 0; width: 100%; }}
            .footer-band img {{ width: 100%; display: block; }}
        </style>
    </head>
    <body>
        <img class="watermark" src="data:image/png;base64,{images['watermark']}">
        <div class="header">
            <div class="logo"><img src="data:image/png;base64,{images['logo']}"></div>
            <div class="ref-block">
                <div>ቀን: <span class="val">{invoice.invoiceDate.strftime('%d/%m/%Y')}</span></div>
                <div>ቁጥር: <span class="val">{invoice.invoiceNumber}</span></div>
            </div>
        </div>
        <hr class="rule">
        <div class="salutation">
            <div>ለ {display_name}</div>
            <div>ባሉበት</div>
        </div>
        <div class="subject">ጉዳይ፡- የጨረታ processing fee እንዲከፍሉ ስለማሳወቅ</div>
        <div class="body-text">{paragraph1}</div>
        <div class="body-text">{paragraph2}</div>
        <div class="body-text">ማሳሰቢያ፡- ለጨረታ መወዳደሪያ ያስያዙት ሲ.ፒ.ኦ ተመላሽ የሚደረገው processing fee መከፈላችሁ ከተረጋገጠ በኋላ ነው፡፡</div>
        <div class="closing">ከሰላምታ ጋር</div>
        <div class="stamp-sig-row">
            <img class="stamp-img" src="data:image/png;base64,{images['stamp']}">
        </div>
        <div class="footer-band"><img src="data:image/png;base64,{images['footer']}"></div>
    </body>
    </html>
    """