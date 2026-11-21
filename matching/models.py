from django.conf import settings
from django.db import models
from django.db.models import F, Q

User = settings.AUTH_USER_MODEL


class Swipe(models.Model):
    """A like or pass by one user on another."""

    class Action(models.TextChoices):
        LIKE = "like", "Like"
        PASS = "pass", "Pass"

    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="swipes_made")
    target = models.ForeignKey(User, on_delete=models.CASCADE, related_name="swipes_received")
    action = models.CharField(max_length=4, choices=Action.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["actor", "target"], name="unique_swipe_pair"),
            models.CheckConstraint(condition=~Q(actor=F("target")), name="no_self_swipe"),
        ]
        indexes = [models.Index(fields=["target", "action"])]


class Match(models.Model):
    """Mutual like. user_a < user_b (by id) so each pair exists once."""

    user_a = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    user_b = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "matches"
        constraints = [
            models.UniqueConstraint(fields=["user_a", "user_b"], name="unique_match_pair"),
            models.CheckConstraint(condition=Q(user_a__lt=F("user_b")), name="match_ordered_pair"),
        ]

    @classmethod
    def create_for(cls, u1, u2):
        a, b = sorted([u1, u2], key=lambda u: u.pk)
        return cls.objects.get_or_create(user_a=a, user_b=b)

    def __str__(self):
        return f"{self.user_a} <-> {self.user_b}"
