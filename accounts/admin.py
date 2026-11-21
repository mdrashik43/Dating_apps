from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.urls import reverse
from django.utils.html import format_html

from .models import University, User, VerificationRequest


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "university", "email_confirmed", "is_university_verified", "is_staff", "is_active"]
    list_filter = ["is_university_verified", "university", "is_staff", "is_active"]
    search_fields = ["email"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("University", {"fields": ("university", "email_confirmed", "is_university_verified")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ["name", "short_name", "email_domain", "is_active"]


@admin.register(VerificationRequest)
class VerificationRequestAdmin(admin.ModelAdmin):
    list_display = ["user", "university", "status", "created_at", "reviewed_by"]
    list_filter = ["status", "university"]
    exclude = ["document"]  # never rendered through a widget that needs a public URL
    readonly_fields = ["document_link", "created_at", "reviewed_by", "reviewed_at"]
    actions = ["approve", "reject"]

    @admin.display(description="Document")
    def document_link(self, obj):
        if not obj.pk:
            return "-"
        url = reverse("verification-document", args=[obj.pk])
        return format_html('<a href="{}" target="_blank">View (staff/owner only)</a>', url)

    @admin.action(description="Approve selected (verifies the user)")
    def approve(self, request, queryset):
        for vr in queryset.filter(status="pending"):
            vr.approve(request.user)

    @admin.action(description="Reject selected")
    def reject(self, request, queryset):
        for vr in queryset.filter(status="pending"):
            vr.reject(request.user, "Rejected by staff. Please upload a clearer document.")
