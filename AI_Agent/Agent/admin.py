from django.contrib import admin

from .models import Approval, AuditLog, Document, LedgerEntry, Plan, Session, University


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'user_type', 'corridor', 'tier', 'created_at', 'updated_at')
    list_filter = ('tier', 'user_type', 'created_at')
    search_fields = ('user__username', 'user__email', 'corridor')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'doc_type', 'confidence', 'verified', 'created_at')
    list_filter = ('doc_type', 'verified', 'created_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'target_amount', 'target_ccy', 'total_cost', 'status', 'created_at')
    list_filter = ('status', 'target_ccy', 'created_at')
    search_fields = ('user__username', 'user__email', 'target_ccy')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Approval)
class ApprovalAdmin(admin.ModelAdmin):
    list_display = ('plan', 'user', 'status', 'expires_at', 'created_at')
    list_filter = ('status', 'created_at', 'expires_at')
    search_fields = ('user__username', 'user__email', 'plan__id')
    readonly_fields = ('token', 'created_at')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'ts', 'tier', 'action', 'status')
    list_filter = ('tier', 'action', 'status', 'ts')
    search_fields = ('action', 'status', 'session__user__username', 'session__user__email')
    readonly_fields = ('session', 'ts', 'tier', 'action', 'status', 'meta')
    date_hierarchy = 'ts'
    ordering = ('-ts',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'entry_type', 'amount', 'currency', 'category', 'status', 'ts')
    list_filter = ('entry_type', 'category', 'status', 'currency', 'ts')
    search_fields = ('user__username', 'user__email', 'counterparty')
    readonly_fields = ('ts',)


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'country', 'updated_at')
    list_filter = ('country',)
    search_fields = ('name', 'slug', 'country')
    readonly_fields = ('created_at', 'updated_at')
