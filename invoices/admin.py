from django import forms
from django.contrib import admin
from django.contrib import messages as admin_messages
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.urls import path
from django.utils import timezone

from .models import (
    StaffProfile, Auction, Winner, ImportBatch, FeeConfig,
    Invoice, InvoiceLot, Payment, Attachment, AuditLog,GeneratedReport,Role, SmsLog,
    PaymentReceiptFile, SystemAuditLog, ServiceApiKey,
)

from .services.service_keys import generate_service_api_key

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'privilege_count', 'isBuiltIn', 'createdAt')
    list_filter = ('isBuiltIn',)
    search_fields = ('name',)
    readonly_fields = ('createdAt',)

    def privilege_count(self, obj):
        return len(obj.defaultPrivileges)
    privilege_count.short_description = 'Privileges'


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'isActive', 'lastPasswordChange', 'lastUsernameChange')
    list_filter = ('role', 'isActive')
    search_fields = ('user__username', 'user__email')

@admin.register(Auction)
class AuctionAdmin(admin.ModelAdmin):
    list_display = ('auctionName', 'seller_name', 'auctionDate', 'status', 'createdAt')
    list_filter = ('status',)
    search_fields = ('auctionName', 'seller_name')
    date_hierarchy = 'auctionDate'


@admin.register(Winner)
class WinnerAdmin(admin.ModelAdmin):
    list_display = ('bidderName', 'companyName', 'winnerPhone', 'winningAmount', 'auction', 'importBatch', 'createdAt')
    list_filter = ('auction', 'importBatch')
    search_fields = ('bidderName', 'winnerPhone', 'companyName')


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ('batchName', 'fileName', 'companyName', 'auctionDate', 'status', 'validRecords', 'totalRecords', 'uploadDate', 'importedBy')
    list_filter = ('status',)
    search_fields = ('batchName', 'fileName', 'companyName')
    readonly_fields = ('uploadDate',)



@admin.register(FeeConfig)
class FeeConfigAdmin(admin.ModelAdmin):
    # Match the exact snake_case fields defined in models.py
    list_display = ['percentage', 'is_active', 'configured_by', 'configured_at']
    list_filter = ['is_active']
    readonly_fields = ['configured_at']

class InvoiceLotInline(admin.TabularInline):
    model = InvoiceLot
    extra = 0
    fields = ('lotNumber', 'auctionName', 'winningAmount', 'feePercentage', 'lotFee', 'cpoAmount', 'cpoBank', 'submittedAt')
    readonly_fields = ('lotFee',)  # calculated in InvoiceLot.save() — visible, never hand-edited


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ('amountPaid', 'paymentMethod', 'paymentDate', 'paymentStatus', 'verifiedBy', 'verifiedDate', 'remarks')


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    fields = ('fileName', 'filePath', 'documentType', 'uploadedBy', 'uploadDate')
    readonly_fields = ('uploadDate',)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoiceNumber', 'winner', 'status', 'total_amount_display', 'invoiceDate', 'dueDate')
    list_filter = ('status',)
    search_fields = ('invoiceNumber', 'winner__bidderName', 'winner__winnerPhone')
    date_hierarchy = 'dueDate'
    readonly_fields = ('createdAt', 'updatedAt', 'publicToken')
    inlines = [InvoiceLotInline, PaymentInline, AttachmentInline]

    def total_amount_display(self, obj):
        # totalAmount is a @property (sum of lots), not a real column, so it
        # can't go straight into list_display — this wraps it. Reads the
        # annotation from get_queryset below rather than obj.totalAmount,
        # which would otherwise re-run a fresh Sum() query per row.
        return obj._lot_total or 0
    total_amount_display.short_description = 'Total amount'
    total_amount_display.admin_order_field = '_lot_total'

    def get_queryset(self, request):
        # Pre-sums each invoice's lot fees in the same query as the list
        # page, instead of one extra Sum() query per row (classic admin
        # list N+1 — same problem you'd hit with a computed EF Core
        # property shown in a grid without .Include()/projection).
        qs = super().get_queryset(request)
        return qs.annotate(_lot_total=Sum('lots__lotFee'))


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'amountPaid', 'paymentMethod', 'paymentStatus', 'paymentDate', 'verifiedBy')
    list_filter = ('paymentStatus', 'paymentMethod')
    search_fields = ('invoice__invoiceNumber',)


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'fileName', 'documentType', 'uploadDate', 'uploadedBy')
    list_filter = ('documentType',)
    search_fields = ('invoice__invoiceNumber', 'fileName')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Read-only by design — this is the system's audit trail. Nobody should
    be able to add, edit, or delete an entry from the Django admin, even
    an Administrator. Entries only ever get created by application code
    (status-transition views, the overdue management command, etc.).
    """
    list_display = ('invoice', 'action', 'performedBy', 'userRole', 'previousValue', 'newValue', 'actionDate')
    list_filter = ('userRole', 'actionDate')
    search_fields = ('invoice__invoiceNumber', 'action', 'performedBy__username')
    date_hierarchy = 'actionDate'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
# Add to admin.py

@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    list_display = ('title', 'periodLabel', 'rowCount', 'totalAmount', 'generatedBy', 'generatedAt')
    list_filter = ('reportType',)
    readonly_fields = ('generatedAt',)


@admin.register(SmsLog)
class SmsLogAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'phone', 'success', 'sentBy', 'sentAt')
    list_filter = ('success',)
    search_fields = ('invoice__invoiceNumber', 'phone')
    readonly_fields = ('invoice', 'phone', 'message', 'success', 'providerResponse', 'sentBy', 'sentAt')

    def has_add_permission(self, request):
        return False


@admin.register(SystemAuditLog)
class SystemAuditLogAdmin(admin.ModelAdmin):
    list_display = ('createdAt', 'action', 'performedByName', 'target')
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


class _CreateKeyForm(forms.Form):
    name = forms.CharField(max_length=100)


@admin.register(ServiceApiKey)
class ServiceApiKeyAdmin(admin.ModelAdmin):
    """
    Keys for the companion CRM's read-only export. The raw key is never
    stored, so it cannot be typed into a field or edited here — creation
    goes through generate_service_api_key(), which returns the plaintext
    exactly once, and the add button is disabled to stop anyone hashing a
    key by hand and creating an unusable row.

    Revoke rather than delete: lastUsedAt and the audit history stay
    meaningful, and a deleted key can't be distinguished from one that
    never existed.
    """
    list_display = ('name', 'isActive', 'createdAt', 'lastUsedAt', 'createdBy')
    list_filter = ('isActive',)
    search_fields = ('name',)
    readonly_fields = ('hashedKey', 'createdAt', 'lastUsedAt', 'createdBy', 'revokedAt')
    actions = ['revoke_keys']

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        # Prepended so this wins over the default catch-all admin URL.
        return [
            path('create-key/', self.admin_site.admin_view(self.create_key_view),
                 name='invoices_serviceapikey_create'),
        ] + super().get_urls()

    def create_key_view(self, request):
        if request.method == 'POST':
            form = _CreateKeyForm(request.POST)
            if form.is_valid():
                raw, _ = generate_service_api_key(form.cleaned_data['name'], request.user)
                admin_messages.success(
                    request,
                    f'Key created. COPY THIS NOW — it will never be shown again: {raw}',
                )
                return redirect('..')
        else:
            form = _CreateKeyForm()
        return render(request, 'admin/invoices/serviceapikey_create.html',
                      {'form': form, 'opts': self.model._meta})

    def revoke_keys(self, request, queryset):
        updated = queryset.filter(isActive=True).update(
            isActive=False, revokedAt=timezone.now())
        self.message_user(request, f'{updated} key(s) revoked.')
    revoke_keys.short_description = 'Revoke selected keys'
