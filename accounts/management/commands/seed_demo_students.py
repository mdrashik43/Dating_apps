from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.models import University, User
from mystery_game.models import Clue
from profiles.models import Profile

PASSWORD = "DemoPass-12345!"
STUDENTS = [
    ("Aarav", "male", "CSE", "221", ["I always carry a chess set.", "I can recite every cafeteria menu.", "I sleep best during thunderstorms."]),
    ("Maya", "female", "EEE", "222", ["I have read the same novel four times.", "My playlist is mostly rain sounds.", "I collect old bus tickets."]),
    ("Rafi", "male", "BBA", "231", ["I never miss a sunrise.", "I can cook biryani for twenty.", "My bike has a name."]),
    ("Nila", "female", "Civil", "221", ["I sketch strangers on the bus.", "I once walked the whole campus barefoot.", "Tea over coffee, always."]),
    ("Sami", "non_binary", "Pharmacy", "232", ["I know every stray cat nearby.", "I journal before every exam.", "Mountains beat beaches."]),
]


class Command(BaseCommand):
    help = "DEV ONLY: create fake verified students so you can try Guess Your Vibe alone."

    def handle(self, *args, **opts):
        if not settings.DEBUG:
            raise CommandError("Refusing to create demo accounts when DEBUG is off.")
        uni, _ = University.objects.get_or_create(
            email_domain="uiu.ac.bd",
            defaults={"name": "United International University", "short_name": "UIU"},
        )
        for i, (name, gender, dept, batch, clues) in enumerate(STUDENTS, start=1):
            email = f"demo{i}@bscse.uiu.ac.bd"
            user, created = User.objects.get_or_create(
                email=email,
                defaults={"university": uni, "is_university_verified": True, "email_confirmed": True},
            )
            if created:
                user.set_password(PASSWORD)
                user.save()
            Profile.objects.update_or_create(
                user=user,
                defaults=dict(display_name=name, date_of_birth=date(2002, 3, 10 + i), gender=gender,
                              department=dept, batch=batch, bio=f"Demo account for {name}.",
                              is_discoverable=True, consent_mystery_game=True),
            )
            if not user.clues.exists():
                for pos, text in enumerate(clues):
                    Clue.objects.create(owner=user, text=text, position=pos)
            self.stdout.write(f"{'Created' if created else 'Exists '}: {email}")
        self.stdout.write(self.style.SUCCESS(f"Done. Password for all demo accounts: {PASSWORD}"))
