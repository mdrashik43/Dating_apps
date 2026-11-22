from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from accounts.storage import private_storage

MIN_AGE = 18


def calculate_age(dob: date, today: date | None = None) -> int:
    today = today or date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def validate_adult(dob: date):
    if calculate_age(dob) < MIN_AGE:
        raise ValidationError(f"You must be at least {MIN_AGE} years old.")


class Profile(models.Model):
    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        NON_BINARY = "non_binary", "Non-binary"
        OTHER = "other", "Other"

    class Intent(models.TextChoices):
        DATING = "dating", "Dating"
        FRIENDSHIP = "friendship", "Friendship"
        BOTH = "both", "Open to both"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(max_length=60)
    date_of_birth = models.DateField(validators=[validate_adult])
    gender = models.CharField(max_length=12, choices=Gender.choices)
    looking_for = models.CharField(max_length=12, choices=Intent.choices, default=Intent.BOTH)
    bio = models.TextField(max_length=500, blank=True)
    department = models.CharField(max_length=100, blank=True)
    batch = models.CharField(max_length=20, blank=True)
    # Privacy: nothing is shown to others unless the user opts in.
    is_discoverable = models.BooleanField(default=False)
    consent_mystery_game = models.BooleanField(
        default=False, help_text="Explicit opt-in to appear in Guess Your Vibe."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["is_discoverable", "consent_mystery_game"])]

    def clean(self):
        if self.date_of_birth:
            validate_adult(self.date_of_birth)

    def save(self, *args, **kwargs):
        self.full_clean(exclude=["user"])  # enforce 18+ on every save
        super().save(*args, **kwargs)

    @property
    def age(self):
        return calculate_age(self.date_of_birth)

    def __str__(self):
        return self.display_name


class ProfilePhoto(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(storage=private_storage, upload_to="profile_photos/%Y/%m/")
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["profile", "position"], name="unique_photo_position"),
            models.CheckConstraint(condition=models.Q(position__lt=6), name="max_six_photos"),
        ]
