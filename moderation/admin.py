from django.contrib import admin

from .models import Block, Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["reported_user", "reporter", "reason", "status", "created_at"]
    list_filter = ["status", "reason"]


admin.site.register(Block)
