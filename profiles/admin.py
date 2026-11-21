from django.contrib import admin

from .models import Profile, ProfilePhoto


class PhotoInline(admin.TabularInline):
    model = ProfilePhoto
    extra = 0


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["display_name", "user", "gender", "is_discoverable", "consent_mystery_game"]
    list_filter = ["gender", "is_discoverable", "consent_mystery_game"]
    search_fields = ["display_name", "user__email"]
    inlines = [PhotoInline]
