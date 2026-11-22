from django.conf import settings
from django.db import models
from django.db.models import F, Q

User = settings.AUTH_USER_MODEL


class Clue(models.Model):
    """A mystery clue the profile owner writes about themselves."""

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="clues")
    text = models.CharField(max_length=200)
    position = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "position"], name="unique_clue_position")
        ]


class GameSession(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVEALED = "revealed", "Revealed"
        DECIDED = "decided", "Decided"
        ABANDONED = "abandoned", "Abandoned"

    player = models.ForeignKey(User, on_delete=models.CASCADE, related_name="game_sessions")
    mystery_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    started_at = models.DateTimeField(auto_now_add=True)
    revealed_at = models.DateTimeField(null=True, blank=True)
    clues_unlocked = models.PositiveSmallIntegerField(default=1)

    class Meta:
        indexes = [models.Index(fields=["player", "status"])]
        constraints = [
            models.UniqueConstraint(
                fields=["player"],
                condition=Q(status__in=["active", "revealed"]),
                name="one_open_session_per_player",
            ),
            models.CheckConstraint(condition=~Q(player=F("mystery_user")), name="no_self_play")
        ]


class Guess(models.Model):
    class Meta:
        verbose_name_plural = "guesses"

    session = models.ForeignKey(GameSession, on_delete=models.CASCADE, related_name="guesses")
    text = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
