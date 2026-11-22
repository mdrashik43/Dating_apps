from django.db.models import Q

from matching.models import Match
from mystery_game.models import GameSession

from .models import Block


def resolve_target(user, session_id=None, match_id=None):
    """Identities are hidden in the game, so reports/blocks refer to a session
    or match the caller is part of. Anything else returns None (404)."""
    if session_id is not None:
        s = GameSession.objects.filter(pk=session_id, player=user).select_related("mystery_user").first()
        return s.mystery_user if s else None
    m = Match.objects.filter(Q(user_a=user) | Q(user_b=user), pk=match_id).first()
    if m is None:
        return None
    return m.user_b if m.user_a_id == user.pk else m.user_a


def block_user(blocker, target):
    Block.objects.get_or_create(blocker=blocker, blocked=target)
    pair = Q(user_a=blocker, user_b=target) | Q(user_a=target, user_b=blocker)
    Match.objects.filter(pair).update(is_active=False)
    sess = Q(player=blocker, mystery_user=target) | Q(player=target, mystery_user=blocker)
    GameSession.objects.filter(sess, status__in=["active", "revealed"]).update(status="abandoned")
