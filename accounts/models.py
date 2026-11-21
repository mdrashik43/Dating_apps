import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import FileExtensionValidator
from django.db import models, transaction
from django.utils import timezone

from .storage import private_storage


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("Superuser needs is_staff=True and is_superuser=True.")
        return self._create(email, password, **extra)


class University(models.Model):
    name = models.CharField(max_length=200, unique=True)
    short_name = models.CharField(max_length=20, blank=True)
    email_domain = models.CharField(
        max_length=150, unique=True, help_text="e.g. bscse.uiu.ac.bd or uiu.ac.bd"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "universities"
        ordering = ["name"]

    def __str__(self):
        return self.short_name or self.name

    def matches_email(self, email: str) -> bool:
        """True if the email's domain equals, or is a subdomain of, email_domain."""
        domain = email.rsplit("@", 1)[-1].lower()
        base = self.email_domain.lower()
        return domain == base or domain.endswith("." + base)


class User(AbstractUser):
    """Custom user: email is the login identifier."""

    username = None
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    university = models.ForeignKey(
        University, null=True, blank=True, on_delete=models.PROTECT, related_name="users"
    )
    is_university_verified = models.BooleanField(
        default=False, help_text="Set only after staff approve a verification request."
    )
    email_confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []
    objects = UserManager()

    class Meta:
        indexes = [models.Index(fields=["university", "is_university_verified"])]

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class VerificationRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="verification_requests")
    university = models.ForeignKey(University, on_delete=models.PROTECT)
    student_id_number = models.CharField(max_length=50)
    document = models.FileField(
        storage=private_storage,
        upload_to="verification/%Y/%m/",
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "pdf"])],
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status="pending"),
                name="one_pending_verification_per_user",
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.status}"

    def approve(self, reviewer):
        self._review(reviewer, self.Status.APPROVED, "")
        self.user.is_university_verified = True
        self.user.university = self.university
        self.user.save(update_fields=["is_university_verified", "university"])
        self._notify("Verification approved", "You are verified. You can now join Vibe Match.")

    def reject(self, reviewer, reason=""):
        self._review(reviewer, self.Status.REJECTED, reason)
        self._notify("Verification rejected", reason or "Please upload a clearer document.")

    def _review(self, reviewer, status, reason):
        if self.status != self.Status.PENDING:
            raise ValueError("This request was already reviewed.")
        self.status = status
        self.rejection_reason = reason[:300]
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save(update_fields=["status", "rejection_reason", "reviewed_by", "reviewed_at"])

    def _notify(self, title, body):
        from notifications.models import Notification

        Notification.objects.create(
            user=self.user, kind=Notification.Kind.VERIFICATION, title=title, body=body[:300]
        )
