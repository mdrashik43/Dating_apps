from django.core.management.base import BaseCommand

from accounts.models import University


class Command(BaseCommand):
    help = "Create the initial university (United International University)."

    def handle(self, *args, **opts):
        uni, created = University.objects.get_or_create(
            email_domain="uiu.ac.bd",
            defaults={"name": "United International University", "short_name": "UIU"},
        )
        self.stdout.write(f"{'Created' if created else 'Already exists'}: {uni}")
