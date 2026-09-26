import uuid
import uuid as uuid_lib
from django.db import models
from django.conf import settings
from django.db.models import Sum
from decimal import Decimal


def receipt_upload_path(instance, filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    new_name = f"{uuid_lib.uuid4().hex}.{ext}" if ext else uuid_lib.uuid4().hex
    return f"receipts/{new_name}"

# Create your models here.
class Role(models.Model):
    """
    Database-backed role. Built-in rows (Administrator, Auction Manager,
    Finance Manager, CRM/Call Center Officer, Viewer) are seeded via data
    migration and marked isBuiltIn=True - they can still be edited, just
    not deleted, to protect the 5 the frontend/permissions checks assume
    exist as sane defaults. Custom roles created via "New role" have
    isBuiltIn=False.
    """
    name = models.CharField(max_length=100, unique=True)
    defaultPrivileges = models.JSONField(default=list, blank=True)
    isBuiltIn = models.BooleanField(default=False)
    createdAt = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class StaffProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name='staff')
    privileges = models.JSONField(default=list, blank=True)
    isActive = models.BooleanField(default=True)
    lastPasswordChange = models.DateTimeField(null=True, blank=True)
    lastUsernameChange = models.DateTimeField(null=True, blank=True)
    lastPasswordChangedBy = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    lastUsernameChangedBy = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )

    def __str__(self):
        return f"{self.user.get_username()} ({self.role.name})"

class ImportBatch(models.Model):

    """
    One upload of bid_data_report.xlsx = one ImportBatch.
    Winner and Invoice both point back to this so you can always answer
    "which upload did this invoice come from" and re-group by batch.
    Think of this like a C# "ImportJob" record you'd log before processing a file.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ]

    fileName = models.CharField(max_length=255)
    batchName = models.CharField(max_length=200, blank=True)
    companyName = models.CharField(max_length=200)
    auctionDate = models.DateField()
    uploadDate = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    totalRecords = models.IntegerField(default=0)
    validRecords = models.IntegerField(default=0)
    invalidRecords = models.IntegerField(default=0)
    importedBy = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='import_batches'
    )
    columnMapping = models.JSONField(
        default=dict, blank=True,
        help_text="Snapshot of which original spreadsheet column supplied each "
                   "known field for this batch, e.g. {'lotNumber': 'Lot No', "
                   "'auctionName': 'Auction', ...}. Captured at import time so "
                   "it stays accurate for this batch even if the alias list "
                   "changes later."
    )
    class Meta:
        verbose_name_plural = "Import batches"
    def __str__(self):
        return self.batchName or self.fileName


class FeeConfig(models.Model):
    """
    Holds the default processing-fee percentage (0.95%).
    Only one row should have is_active=True at a time - enforce that in the
    admin/serializer save logic (flip old active row off before saving new one),
    not with a DB constraint, since you want history of past configs.
    """
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.95'))
    configured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    configured_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.percentage}% ({'active' if self.is_active else 'inactive'})"

    @classmethod
    def get_active_percentage(cls):
        active = cls.objects.filter(is_active=True).first()
        return active.percentage if active else Decimal('0.95')

class OfficeSettings(models.Model):
    """Reusable Amharic office address printed/attached to invoices. Same
    single-active-row + history pattern as FeeConfig."""
    address = models.TextField(blank=True, default='')
    configuredBy = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    configuredAt = models.DateTimeField(auto_now=True)
    isActive = models.BooleanField(default=True)

    def __str__(self):
        return f"Office address ({'active' if self.isActive else 'inactive'})"


class Auction(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    seller_name = models.CharField(max_length=255)
    auctionName = models.CharField(max_length=300)
    auctionDate = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    createdAt = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.auctionName


class Winner(models.Model):
    bidderName = models.CharField(max_length=255)
    companyName = models.CharField(max_length=200, blank=True)  # always optional, filled in manually after import
    winnerPhone = models.CharField(max_length=20)
    winnerEmail = models.EmailField(blank=True, default='')  # dropped null=True - see note above
    auction = models.ForeignKey(
        Auction, on_delete=models.SET_NULL, null=True, blank=True, related_name='winners'
    )
    importBatch = models.ForeignKey(
        ImportBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name='winners'
    )
    winningAmount = models.DecimalField(max_digits=15, decimal_places=2)
    cpoAmount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cpoBank = models.CharField(max_length=100, blank=True)
    submittedAt = models.DateTimeField(null=True, blank=True)
    initialPrice = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    createdAt = models.DateTimeField(auto_now_add=True)
    bidderNameAmharic = models.CharField(max_length=255, blank=True, default='')

    def __str__(self):
        return f"{self.bidderName} - {self.winningAmount}"


class Invoice(models.Model):
    """
    One Invoice per (winner, importBatch) pair - created when staff confirms
    the import preview. feePercentage lives on InvoiceLot now, not here,
    because different lots on the same invoice can carry different negotiated
    rates. totalAmount is a computed property (sum of lots), not a stored
    column - see explanation above.
    """
    STATUS_CHOICES = [
        ('invoice_generated', 'Invoice Generated'),
        ('pending_payment', 'Pending Payment'),
        ('payment_submitted', 'Payment Submitted'),
        ('under_verification', 'Under Verification'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
        ('waived', 'Waived'),
    ]

    winner = models.ForeignKey(Winner, on_delete=models.CASCADE, related_name='invoices')
    importBatch = models.ForeignKey(
        ImportBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices'
    )
    invoiceNumber = models.CharField(max_length=50, unique=True)
    invoiceDate = models.DateField()
    dueDate = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='invoice_generated')
    remarks = models.TextField(blank=True, default='')
    callNotes = models.TextField(blank=True, default='', help_text="Call Center follow-up note - single mutable field, not a history log.")
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    # Phase 1: unauthenticated bidders use this token to view their invoice
    # and upload a payment receipt without logging in. Never expires unless
    # we decide otherwise later.
    publicToken = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    # Phase 4: SMS tracking + the letter wording used when the PDF was generated
    smsSentAt = models.DateTimeField(null=True, blank=True)
    smsSendCount = models.PositiveIntegerField(default=0)
    letterData = models.JSONField(
        default=dict, blank=True,
        help_text="Values entered when the invoice PDF was last generated; reused by the public PDF so bidders see the same letter.",
    )

    @property
    def totalAmount(self):
        return self.lots.aggregate(total=Sum('lotFee'))['total'] or Decimal('0.00')

    def __str__(self):
        return f"{self.invoiceNumber} - {self.winner.bidderName}"


class InvoiceLot(models.Model):
    """
    One row per lot won, under a single Invoice. lotFee is auto-calculated
    on save from winningAmount * feePercentage - same idea as overriding a
    setter/property in C#: callers never compute lotFee themselves, save()
    does it for them so it can never drift out of sync with the inputs.
    """
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='lots')
    lotNumber = models.CharField(max_length=50)
    auctionName = models.CharField(max_length=300)
    initialPrice = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    winningAmount = models.DecimalField(max_digits=15, decimal_places=2)
    cpoAmount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cpoBank = models.CharField(max_length=100, blank=True)
    feePercentage = models.DecimalField(max_digits=5, decimal_places=2)
    lotFee = models.DecimalField(max_digits=15, decimal_places=2, editable=False)
    submittedAt = models.DateTimeField(null=True, blank=True)

    # Phase 0: any column in the uploaded sheet that isn't one of the
    # REQUIRED_COLUMNS gets captured here automatically as {columnName: value}.
    # Lets a company add new spreadsheet columns without a code/migration change.
    extraFields = models.JSONField(default=dict, blank=True)

    def save(self, *args, **kwargs):
        self.lotFee = (self.winningAmount * self.feePercentage / Decimal('100')).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.lotNumber} - fee {self.lotFee}"


class Payment(models.Model):
    """
    A record of a payment CLAIM against an invoice. Two ways a Payment gets
    created:
      1. Staff enters it manually after checking the bank/Telebirr statement
         themselves (existing flow - paymentStatus pending/verified/rejected,
         set by Finance).
      2. A bidder self-submits it through the public invoice link, attaching
         a photo/PDF of their receipt (submittedViaPublicLink=True). This
         starts a SEPARATE review step - verificationStatus - that an
         Auction Manager works through BEFORE it's treated as a normal
         Payment for Finance. Kept separate from paymentStatus on purpose:
         paymentStatus is Finance's final word; verificationStatus is the
         manager's "is this receipt legit" checkpoint that happens first.
         (Planned to eventually be automated - kept as its own field/step
         specifically so that automation can slot in later without touching
         paymentStatus or Finance's side of things at all.)
    """
    METHOD_CHOICES = [
        ('bank_transfer', 'Bank Transfer'),
        ('telebirr', 'Telebirr'),
        ('cpo', 'CPO'),
        ('other', 'Other'),
        ('unspecified', 'Unspecified'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]
    VERIFICATION_STATUS_CHOICES = [
        ('not_applicable', 'Not applicable'),         # staff-entered payments skip this step entirely
        ('pending_manager_review', 'Pending Manager Review'),
        ('manager_approved', 'Manager Approved'),
        ('manager_rejected', 'Manager Rejected'),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amountPaid = models.DecimalField(max_digits=15, decimal_places=2)
    paymentMethod = models.CharField(max_length=20, choices=METHOD_CHOICES)
    paymentDate = models.DateField()
    uploadedAt = models.DateTimeField(auto_now_add=True)
    verifiedBy = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='verified_payments'
    )
    verifiedDate = models.DateTimeField(null=True, blank=True)
    paymentStatus = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    remarks = models.TextField(blank=True)

    # Phase 1 additions - the public receipt-upload + manager-review flow
    receiptFile = models.FileField(upload_to=receipt_upload_path, null=True, blank=True)
    submittedViaPublicLink = models.BooleanField(default=False)
    verificationStatus = models.CharField(
        max_length=30, choices=VERIFICATION_STATUS_CHOICES, default='not_applicable'
    )
    managerVerifiedBy = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='manager_verified_payments'
    )
    managerVerifiedDate = models.DateTimeField(null=True, blank=True)
    managerNote = models.TextField(blank=True, default='')

    def __str__(self):
        return f"{self.amountPaid} on {self.invoice.invoiceNumber}"


class Attachment(models.Model):
    DOC_TYPE_CHOICES = [
        ('bank_slip', 'Bank Slip'),
        ('transfer_proof', 'Transfer Proof'),
        ('cpo', 'CPO Document'),
        ('invoice', 'Invoice Document'),
        ('payment_confirmation', 'Payment Confirmation'),
        ('supporting_document', 'Supporting Document'),
        ('other', 'Other'),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='attachments')
    fileName = models.CharField(max_length=255)
    filePath = models.FileField(upload_to='attachments/')  # S3 once boto3/django-storages creds land
    fileExtension = models.CharField(max_length=10, blank=True)
    documentType = models.CharField(max_length=30, choices=DOC_TYPE_CHOICES, default='other')
    uploadDate = models.DateTimeField(auto_now_add=True)
    fileSize = models.DecimalField(max_digits=10, decimal_places=2, help_text="KB")
    uploadedBy = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return self.fileName


class AuditLog(models.Model):
    """
    Append-only trail. Every status change, payment verification, due-date
    extension, etc. writes one of these - you'll hook this into the views
    at step 16, not here. userRole is a snapshot string (not a live FK to
    StaffProfile) on purpose: if someone's role changes later, the log
    should still say what role they held *at the time* of the action.
    """
    ACTION_TYPE_CHOICES = [
        ('change_status', 'Status changed'),
        ('generate_invoice_pdf', 'Generate invoice PDF'),
        ('extend_due_date', 'Extend due date'),
        ('upload_payment', 'Payment uploaded'),
        ('add_call_note', 'Call center note updated'),
        ('send_sms', 'SMS sent'),
        ('other', 'Other'),
    ]
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=255)
    actionType = models.CharField(max_length=40, blank=True, default='other', choices=ACTION_TYPE_CHOICES)
    performedBy = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    userRole = models.CharField(max_length=30, blank=True)
    previousValue = models.CharField(max_length=100, blank=True)
    newValue = models.CharField(max_length=100, blank=True)
    reason = models.TextField(blank=True)
    actionDate = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return f"{self.invoice.invoiceNumber}: {self.action}"


class SmsLog(models.Model):
    """One row per SMS attempt (successful or not). Never edited."""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='sms_logs')
    phone = models.CharField(max_length=20)
    message = models.TextField()
    success = models.BooleanField(default=False)
    providerResponse = models.TextField(blank=True, default='')
    sentBy = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    sentAt = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sentAt']

    def __str__(self):
        return f"{self.invoice.invoiceNumber} -> {self.phone} ({'ok' if self.success else 'failed'})"


class GeneratedReport(models.Model):
    """
    One row per PDF actually generated from the Reports page - backs the
    "Recently generated" list. Preview alone (screen-only) does NOT create
    one of these; only clicking "Generate PDF" does.
    """
    reportType = models.CharField(max_length=30)
    title = models.CharField(max_length=200)
    periodLabel = models.CharField(max_length=100, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    rowCount = models.IntegerField(default=0)
    totalAmount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    file = models.FileField(upload_to='reports/%Y/%m/')
    generatedBy = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    generatedAt = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.generatedAt:%Y-%m-%d %H:%M}"


class ReceiptExtraction(models.Model):
    """
    AI-extracted data from a Payment's receipt image, run manually by a
    reviewer AFTER the receipt is already manager_approved — this is
    record-keeping / auto-fill, not a decision aid, so it never blocks or
    influences the approve/reject step itself. Kept as its own model
    rather than fields on Payment because this data is fallible AI
    output, not trusted system data: keeping it separate makes it easy to
    re-run extraction, compare attempts, or ignore it entirely without
    touching the real payment record.
    """
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='extraction')
    tin = models.CharField(max_length=50, blank=True, default='')
    receiptNumber = models.CharField(max_length=100, blank=True, default='')
    extractedDate = models.CharField(max_length=100, blank=True, default='', help_text="As printed on the receipt — no calendar conversion is done, may be Ethiopian or Gregorian.")
    bankReferenceNumber = models.CharField(max_length=100, blank=True, default='', help_text="Bank transfer / transaction reference printed on the receipt, distinct from the receipt or invoice number. Used to pre-fill Verify.ET checks.")
    convertedGregorianDate = models.CharField(max_length=20, blank=True, default='', help_text="Best-effort Ethiopian->Gregorian conversion of extractedDate, ISO format. Empty if extractedDate wasn't a parseable, plausible dd/mm/yy(yy) Ethiopian date.")
    customerName = models.CharField(max_length=255, blank=True, default='')
    totalAmount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    vatAmount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    description = models.TextField(blank=True, default='')
    extractionConfidence = models.CharField(max_length=20, blank=True, default='')  # 'high' / 'medium' / 'low', model's own self-report
    rawResponse = models.JSONField(default=dict, blank=True)
    extractedAt = models.DateTimeField(auto_now_add=True)
    extractedBy = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Extraction for payment #{self.payment_id}"


class VerifyEtCheck(models.Model):
    """
    Result of a Verify.ET bank/wallet transaction lookup against a Payment.
    Kept separate from both the Payment and its ReceiptExtraction because it
    is a third-party assertion that can be re-run and can disagree with what
    the receipt image says — the reviewer needs to see both, not have one
    overwrite the other. OneToOne because we keep the latest check per
    payment; rawResponse preserves the full provider payload for disputes.
    """
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='verifyEtCheck')
    bank = models.CharField(max_length=30, blank=True, default='')
    referenceNumber = models.CharField(max_length=100)
    accountSuffix = models.CharField(max_length=20, blank=True, default='')
    phoneNumber = models.CharField(max_length=20, blank=True, default='')
    requestId = models.CharField(max_length=100, blank=True, default='')
    processingStatus = models.CharField(max_length=20, blank=True, default='')
    verified = models.BooleanField(null=True, blank=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, blank=True, default='')
    senderName = models.CharField(max_length=255, blank=True, default='')
    receiverName = models.CharField(max_length=255, blank=True, default='')
    receiverAccount = models.CharField(max_length=100, blank=True, default='')
    settlementMatched = models.BooleanField(null=True, blank=True)
    rawResponse = models.JSONField(default=dict, blank=True)
    errorMessage = models.TextField(blank=True, default='')
    checkedAt = models.DateTimeField(auto_now_add=True)
    checkedBy = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Verify.ET check for payment #{self.payment_id}: {self.referenceNumber}"


class TokenActivity(models.Model):
    """
    One row per DRF auth Token, tracking last use for sliding idle-expiry.
    Kept separate from rest_framework.authtoken's Token model (not ours to
    modify) rather than monkeypatching it. A TokenActivity row with no
    matching Token is harmless dead weight — auth re-creates it on demand.
    """
    token_key = models.CharField(max_length=40, unique=True)
    lastUsed = models.DateTimeField(auto_now=True)