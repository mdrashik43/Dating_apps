from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from accounts.models import User
from chat.models import Conversation
from matching.models import Match, Swipe
from moderation.models import Block
from notifications.models import Notification
from profiles.models import Profile
from profiles.public import public_profile

from .models import Clue, GameSession, Guess

MAX_GUESSES = 10
OPEN = (GameSession.Status.ACTIVE, GameSession.Status.REVEALED)


class GameError(Exception):
    def __init__(self, detail, status=400):
        super().__init__(detail)
        self.detail, self.status = detail, status


def _blocked_ids(user):
    a = Block.objects.filter(blocker=user).values_list("blocked_id", flat=True)
    b = Block.objects.filter(blocked=user).values_list("blocker_id", flat=True)
    return set(a) | set(b)


def is_available(target, player) -> bool:
    """Is `target` still a consenting, verified, unblocked student for `player`?"""
    if not (target.is_active and target.is_university_verified):
        return False
    if not player.university_id or target.university_id != player.university_id:
        return False
    if not Profile.objects.filter(user=target, is_discoverable=True, consent_mystery_game=True).exists():
        return False
    return target.pk not in _blocked_ids(player)


def candidates_for(player):
    if not player.university_id:
        return User.objects.none()
    return (
        User.objects.filter(
            is_active=True,
            is_university_verified=True,
            university_id=player.university_id,
            profile__is_discoverable=True,
            profile__consent_mystery_game=True,
        )
        .exclude(pk=player.pk)
        .exclude(pk__in=_blocked_ids(player))
        .exclude(swipes_received__actor=player)
        .exclude(pk__in=GameSession.objects.filter(player=player).values("mystery_user_id"))
        .annotate(n_clues=Count("clues", filter=Q(clues__is_active=True)))
        .filter(n_clues__gt=0)
    )


def active_clues(user):
    return Clue.objects.filter(owner=user, is_active=True).order_by("position", "id")


def start_session(player):
    profile = getattr(player, "profile", None)
    if not (profile and profile.is_discoverable and profile.consent_mystery_game):
        raise GameError("Turn on discoverability and Guess Your Vibe in your profile to play.", 403)
    existing = GameSession.objects.filter(player=player, status__in=OPEN).first()
    if existing:
        return existing, False
    since = timezone.now() - timedelta(hours=24)
    if GameSession.objects.filter(player=player, started_at__gte=since).count() >= settings.GAME_DAILY_SESSION_LIMIT:
        raise GameError("You have reached today's limit. Come back tomorrow.", 429)
    target = candidates_for(player).order_by("?").first()
    if target is None:
        raise GameError("No one is available right now. Check back soon.", 404)
    try:
        with transaction.atomic():
            return GameSession.objects.create(player=player, mystery_user=target), True
    except IntegrityError:  # two requests raced; reuse the winner
        existing = GameSession.objects.filter(player=player, status__in=OPEN).first()
        if existing is None:
            raise
        return existing, False


def state(session) -> dict:
    """What the player may see. The mystery student's identity is never included
    until the session is revealed, and then only the public profile shape."""
    clues = list(active_clues(session.mystery_user))
    unlocked = min(session.clues_unlocked, len(clues))
    data = {
        "id": session.pk,
        "status": session.status,
        "clues_total": len(clues),
        "clues_unlocked": unlocked,
        "clues": [{"position": i + 1, "text": c.text} for i, c in enumerate(clues[:unlocked])],
        "guesses": [
            {"id": g.pk, "text": g.text, "created_at": g.created_at}
            for g in session.guesses.order_by("created_at", "id")
        ],
        "started_at": session.started_at,
    }
    if session.status == GameSession.Status.REVEALED:
        data["profile"] = public_profile(session.mystery_user.profile)
    return data


def submit_guess(session, text):
    if session.status != GameSession.Status.ACTIVE:
        raise GameError("This session is no longer in the guessing stage.")
    text = (text or "").strip()
    if not text or len(text) > 200:
        raise GameError("Enter a guess (up to 200 characters).")
    if session.guesses.count() >= MAX_GUESSES:
        raise GameError("You have used all your guesses. Reveal to continue.")
    Guess.objects.create(session=session, text=text)
    total = active_clues(session.mystery_user).count()
    session.clues_unlocked = min(session.clues_unlocked + 1, max(total, 1))
    session.save(update_fields=["clues_unlocked"])


def reveal(session) -> bool:
    """False means the student is no longer available (session is closed)."""
    if session.status == GameSession.Status.REVEALED:
        return True
    if session.status != GameSession.Status.ACTIVE:
        raise GameError("This session is over.")
    if not is_available(session.mystery_user, session.player):
        session.status = GameSession.Status.ABANDONED
        session.save(update_fields=["status"])
        return False
    session.status = GameSession.Status.REVEALED
    session.revealed_at = timezone.now()
    session.save(update_fields=["status", "revealed_at"])
    return True


def _notify_match(user, other):
    Notification.objects.create(
        user=user,
        kind=Notification.Kind.MATCH,
        title="It's a match!",
        body=f"You and {other.profile.display_name} liked each other.",
    )


def decide(session, action) -> dict:
    if action not in (Swipe.Action.LIKE, Swipe.Action.PASS):
        raise GameError("Choose like or pass.")
    if session.status != GameSession.Status.REVEALED:
        raise GameError("Reveal the student before choosing.")
    player, target = session.player, session.mystery_user
    # Lock both rows so two simultaneous likes cannot miss each other.
    list(User.objects.select_for_update().filter(pk__in=[player.pk, target.pk]).order_by("pk"))
    if Swipe.objects.filter(actor=player, target=target).exists():
        raise GameError("You already chose for this student.", 409)
    Swipe.objects.create(actor=player, target=target, action=action)
    session.status = GameSession.Status.DECIDED
    session.save(update_fields=["status"])
    mutual = (
        action == Swipe.Action.LIKE
        and Swipe.objects.filter(actor=target, target=player, action=Swipe.Action.LIKE).exists()
        and target.pk not in _blocked_ids(player)
    )
    if not mutual:
        return {"matched": False}
    match, created = Match.create_for(player, target)
    conversation, _ = Conversation.objects.get_or_create(match=match)
    if created:
        _notify_match(player, target)
        _notify_match(target, player)
    return {"matched": True, "match_id": match.pk, "conversation_id": conversation.pk}


def abandon(session):
    if session.status in OPEN:
        session.status = GameSession.Status.ABANDONED
        session.save(update_fields=["status"])
