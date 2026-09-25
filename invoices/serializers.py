from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from google.auth.exceptions import GoogleAuthError

from .models import (
    StaffProfile, Auction, Winner, ImportBatch, FeeConfig,
    Invoice, InvoiceLot, Payment, Attachment, AuditLog, OfficeSettings, ReceiptExtraction,
)
from .permissions import has_permission


def user_display_name(user):
    """
    The API contract shows fields like performedBy/verifiedBy/uploadedBy as
    plain display-name strings ("Sara Admin"), not user IDs or nested user
    objects.
    """
    if not user:
        return ''
    return user.get_full_name() or user.get_username()


# ---------------------------------------------------------------- Auction

class AuctionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Auction
        fields = ['id', 'seller_name', 'auctionName', 'auctionDate', 'status', 'createdAt']


# ----------------------------------------------------------------- Winner

class WinnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Winner
        fields = [
            'id', 'bidderName', 'companyName', 'winnerPhone', 'winnerEmail',
            'auction', 'importBatch', 'winningAmount', 'initialPrice',
            'cpoAmount', 'cpoBank', 'submittedAt', 'createdAt',
            'bidderNameAmharic',
        ]


# ------------------------------------------------------------- ImportBatch

class ImportBatchSerializer(serializers.ModelSerializer):
    importedBy = serializers.SerializerMethodField()

    class Meta:
        model = ImportBatch
        fields = [
            'id', 'fileName', 'batchName', 'companyName', 'auctionDate',
            'uploadDate', 'status', 'totalRecords', 'validRecords',
            'invalidRecords', 'importedBy', 'columnMapping',
        ]

    def get_importedBy(self, obj):
        return user_display_name(obj.importedBy)


# --------------------------------------------------------------- FeeConfig

class FeeConfigSerializer(serializers.ModelSerializer):
    configuredBy = serializers.SerializerMethodField()
    configuredAt = serializers.DateTimeField(source='configured_at', read_only=True)

    class Meta:
        model = FeeConfig
        fields = ['percentage', 'configuredBy', 'configuredAt']

    def get_configuredBy(self, obj):
        return user_display_name(obj.configured_by)


# ------------------------------------------------------------- InvoiceLot

class InvoiceLotSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLot
        fields = [
            'id', 'lotNumber', 'auctionName', 'initialPrice', 'winningAmount',
            'cpoAmount', 'cpoBank', 'feePercentage', 'lotFee', 'submittedAt',
            'extraFields',
        ]


# --------------------------------------------------------------- Payment

class PaymentSerializer(serializers.ModelSerializer):
    verifiedBy = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            'id', 'invoice', 'amountPaid', 'paymentMethod', 'paymentDate',
            'uploadedAt', 'verifiedBy', 'verifiedDate', 'paymentStatus', 'remarks',
        ]
        read_only_fields = ['uploadedAt', 'verifiedDate']

    def get_verifiedBy(self, obj):
        return user_display_name(obj.verifiedBy)


# ------------------------------------------------------------- Attachment

class AttachmentSerializer(serializers.ModelSerializer):
    uploadedBy = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = [
            'id', 'invoice', 'fileName', 'filePath', 'fileExtension',
            'documentType', 'uploadDate', 'fileSize', 'uploadedBy',
        ]
        read_only_fields = ['uploadDate']

    def get_uploadedBy(self, obj):
        return user_display_name(obj.uploadedBy)


# -------------------------------------------------------------- AuditLog

class AuditLogSerializer(serializers.ModelSerializer):
    performedBy = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            'id', 'invoice', 'action', 'actionType', 'performedBy', 'userRole',
            'previousValue', 'newValue', 'reason', 'actionDate',
        ]
        read_only_fields = fields

    def get_performedBy(self, obj):
        return user_display_name(obj.performedBy)

# ------------------------------------------------------- Invoice (shared)

class InvoiceWinnerFieldsMixin:
    def get_bidderName(self, obj):
        return obj.winner.bidderName

    def get_companyName(self, obj):
        return obj.winner.companyName
    
    def get_auctionCompany(self, obj):
        return obj.importBatch.companyName if obj.importBatch else ''

    def get_winnerPhone(self, obj):
        return obj.winner.winnerPhone


# ---------------------------------------------------- Invoice (list view)

class InvoiceListSerializer(InvoiceWinnerFieldsMixin, serializers.ModelSerializer):
    winner = WinnerSerializer(read_only=True)
    lots = InvoiceLotSerializer(many=True, read_only=True)
    totalAmount = serializers.ReadOnlyField()
    bidderName = serializers.SerializerMethodField()
    companyName = serializers.SerializerMethodField()
    auctionCompany = serializers.SerializerMethodField()
    winnerPhone = serializers.SerializerMethodField()
    latestReceiptStatus = serializers.SerializerMethodField()
    latestReceiptReviewedAt = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoiceNumber', 'invoiceDate', 'dueDate', 'winner',
            'totalAmount', 'status', 'createdAt', 'updatedAt',
            'bidderName', 'companyName', 'auctionCompany', 'winnerPhone',
            'callNotes', 'lots', 'smsSentAt', 'smsSendCount',
            'latestReceiptStatus', 'latestReceiptReviewedAt',
        ]

    def _latest_reviewed_payment(self, obj):
        return obj.payments.filter(
            submittedViaPublicLink=True,
            verificationStatus__in=['manager_approved', 'manager_rejected'],
        ).order_by('-managerVerifiedDate').first()

    def get_latestReceiptStatus(self, obj):
        p = self._latest_reviewed_payment(obj)
        return p.verificationStatus if p else None

    def get_latestReceiptReviewedAt(self, obj):
        p = self._latest_reviewed_payment(obj)
        return p.managerVerifiedDate if p else None
# -------------------------------------------------- Invoice (detail view)

class InvoiceDetailSerializer(InvoiceWinnerFieldsMixin, serializers.ModelSerializer):
    winner = WinnerSerializer(read_only=True)
    lots = InvoiceLotSerializer(many=True, read_only=True)
    payments = serializers.SerializerMethodField()
    attachments = AttachmentSerializer(many=True, read_only=True)
    totalAmount = serializers.ReadOnlyField()
    bidderName = serializers.SerializerMethodField()
    companyName = serializers.SerializerMethodField()
    auctionCompany = serializers.SerializerMethodField()
    winnerPhone = serializers.SerializerMethodField()
    feePercentage = serializers.SerializerMethodField()
    verifiedBy = serializers.SerializerMethodField()
    columnMapping = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoiceNumber', 'invoiceDate', 'dueDate', 'winner',
            'importBatch', 'totalAmount', 'status', 'remarks',
            'createdAt', 'updatedAt', 'lots', 'payments', 'attachments',
            'bidderName', 'companyName','auctionCompany', 'winnerPhone',
            'feePercentage', 'verifiedBy', 'columnMapping', 'smsSentAt', 'smsSendCount',
        ]

    def get_payments(self, obj):
        request = self.context.get('request')
        can_view_receipts = bool(request) and (
            has_permission(request.user, 'manager_verify_receipt')
            or has_permission(request.user, 'verify_payment')
        )
        serializer_cls = ManagerPaymentSerializer if can_view_receipts else PaymentSerializer
        return serializer_cls(obj.payments.order_by('-uploadedAt'), many=True, context=self.context).data

    def get_feePercentage(self, obj):
        percentages = {str(lot.feePercentage) for lot in obj.lots.all()}
        if len(percentages) == 1:
            return percentages.pop()
        return 'Mixed'

    def get_verifiedBy(self, obj):
        latest = obj.payments.filter(paymentStatus='verified').order_by('-verifiedDate').first()
        return user_display_name(latest.verifiedBy) if latest else ''

    def get_columnMapping(self, obj):
        # Which original spreadsheet column supplied each field, snapshotted
        # on the parent ImportBatch at confirm time. Empty dict for
        # invoices with no batch (e.g. manually created) or older batches
        # imported before this field existed.
        return obj.importBatch.columnMapping if obj.importBatch else {}

# ------------------------------------------------------- Invoice (public, unauthenticated view)

class PublicInvoiceLotSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLot
        fields = ['id', 'lotNumber', 'auctionName', 'winningAmount', 'feePercentage', 'lotFee']

class PublicInvoiceSerializer(InvoiceWinnerFieldsMixin, serializers.ModelSerializer):
    """
    Used on the public, token-gated invoice page — deliberately exposes only
    what a bidder needs to see (no internal remarks, callNotes, audit info,
    or importBatch internals).
    """
    lots = PublicInvoiceLotSerializer(many=True, read_only=True)
    totalAmount = serializers.ReadOnlyField()
    bidderName = serializers.SerializerMethodField()
    companyName = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            'invoiceNumber', 'invoiceDate', 'dueDate', 'status',
            'totalAmount', 'bidderName', 'companyName', 'lots',
        ]

# ================================================================= Auth (Login)

def _login_result(user):
    """Same response shape for password login and Google login."""
    from rest_framework.authtoken.models import Token
    token, _ = Token.objects.get_or_create(user=user)
    role_name_to_slug = {
        'Administrator': 'administrator',
        'Auction Manager': 'auction_manager',
        'Finance Manager': 'finance_manager',
        'CRM / Call Center Officer': 'call_operator',
        'Viewer': 'viewer',
    }
    role_name = user.profile.role.name
    return {
        'token': token.key,
        'username': user.get_username(),
        'role': role_name_to_slug.get(role_name, role_name),
        'privileges': list(user.profile.privileges or []),
    }


class LoginSerializer(serializers.Serializer):
    """
    Handles POST /api/auth/login/ — accepts username and password,
    returns token, username, and role.
    """
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)

    def validate(self, data):
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            raise serializers.ValidationError("Username and password are required.")

        user = authenticate(username=username, password=password)
        if not user:
            raise serializers.ValidationError("Invalid username or password.")

        # Ensure StaffProfile exists
        if not hasattr(user, 'profile'):
            raise serializers.ValidationError("User does not have a staff profile.")

        data['user'] = user
        return data

    def create(self, validated_data):
        return _login_result(validated_data['user'])


class GoogleLoginSerializer(serializers.Serializer):
    """
    POST /api/auth/google/ {id_token}. Does NOT create accounts: the verified Google
    email must match an existing User that has an active StaffProfile.
    """
    id_token = serializers.CharField()

    def validate(self, data):
        try:
            claims = google_id_token.verify_oauth2_token(
                data['id_token'], google_requests.Request(), settings.GOOGLE_CLIENT_ID,
            )
        except ValueError:
            raise serializers.ValidationError('Invalid or expired Google token.')
        except GoogleAuthError:
            raise serializers.ValidationError('Could not reach Google to verify the sign-in. Try again.')

        if not claims.get('email_verified', False):
            raise serializers.ValidationError('Google account email is not verified.')
        email = (claims.get('email') or '').strip().lower()
        if not email:
            raise serializers.ValidationError('No email on the Google account.')

        users = list(User.objects.filter(email__iexact=email)[:2])
        if not users:
            raise serializers.ValidationError('This Google account is not linked to any employee.')
        if len(users) > 1:
            raise serializers.ValidationError('Multiple accounts share this email. Contact an administrator.')
        user = users[0]

        profile = getattr(user, 'profile', None)
        if profile is None:
            raise serializers.ValidationError('This account has no staff profile.')
        if not user.is_active or not profile.isActive:
            raise serializers.ValidationError('This account has been deactivated.')

        data['user'] = user
        return data
from .models import Role
from .privileges import PRIVILEGE_CATALOG


class RoleSerializer(serializers.ModelSerializer):
    privilegeCount = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ['id', 'name', 'defaultPrivileges', 'isBuiltIn', 'privilegeCount']

    def get_privilegeCount(self, obj):
        return len(obj.defaultPrivileges)


class EmployeeSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    email = serializers.CharField(source='user.email', read_only=True)
    roleName = serializers.CharField(source='role.name', read_only=True)
    privilegeCount = serializers.SerializerMethodField()

    class Meta:
        model = StaffProfile
        fields = [
            'id', 'name', 'username', 'email', 'role', 'roleName', 'privileges',
            'privilegeCount', 'isActive', 'lastPasswordChange', 'lastUsernameChange',
        ]

    def get_name(self, obj):
        return obj.user.get_full_name() or obj.user.get_username()

    def get_username(self, obj):
        return obj.user.get_username()

    def get_privilegeCount(self, obj):
        return f"{len(obj.privileges)}/{len(PRIVILEGE_CATALOG)}"
    
class OfficeSettingsSerializer(serializers.ModelSerializer):
    configuredBy = serializers.SerializerMethodField()

    class Meta:
        model = OfficeSettings
        fields = ['address', 'configuredBy', 'configuredAt']

    def get_configuredBy(self, obj):
        return user_display_name(obj.configuredBy)


# ------------------------------------------ Manager receipt-review queue

class ReceiptExtractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReceiptExtraction
        fields = [
            'tin', 'receiptNumber', 'extractedDate', 'customerName',
            'totalAmount', 'vatAmount', 'description', 'extractionConfidence', 'extractedAt',
        ]


class ManagerPaymentSerializer(PaymentSerializer):
    """
    Extended PaymentSerializer for the manager receipt-review queue.
    Adds the signed receipt URL plus the invoice/winner fields the queue
    table needs to display — scoped to this serializer so the base
    PaymentSerializer never leaks receiptFile to Viewer or Finance roles.
    """
    receiptUrl = serializers.SerializerMethodField()
    invoiceNumber = serializers.CharField(source='invoice.invoiceNumber', read_only=True)
    bidderName = serializers.CharField(source='invoice.winner.bidderName', read_only=True)
    winnerPhone = serializers.CharField(source='invoice.winner.winnerPhone', read_only=True)
    managerVerifiedBy = serializers.SerializerMethodField()

    class Meta(PaymentSerializer.Meta):
        fields = PaymentSerializer.Meta.fields + [
            'receiptUrl',
            'invoiceNumber',
            'bidderName',
            'winnerPhone',
            'verificationStatus',
            'managerNote',
            'managerVerifiedBy',
            'managerVerifiedDate',
            'submittedViaPublicLink',
            'extraction',
        ]

    extraction = serializers.SerializerMethodField()

    def get_extraction(self, obj):
        try:
            return ReceiptExtractionSerializer(obj.extraction).data
        except ReceiptExtraction.DoesNotExist:
            return None

    def get_receiptUrl(self, obj):
        if not obj.receiptFile:
            return None
        request = self.context.get('request')
        if request is not None:
            return request.build_absolute_uri(obj.receiptFile.url)
        return obj.receiptFile.url

    def get_managerVerifiedBy(self, obj):
        return user_display_name(obj.managerVerifiedBy)