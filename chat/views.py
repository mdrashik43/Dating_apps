from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.permissions import IsUniversityVerified
from moderation.models import Block
from profiles.public import public_profile

from .models import Conversation, Message

MAX_LEN = 2000


def my_conversations(user):
    """Only conversations of ACTIVE matches the user belongs to."""
    return Conversation.objects.filter(
        Q(match__user_a=user) | Q(match__user_b=user), match__is_active=True
    ).select_related("match__user_a__profile", "match__user_b__profile")


def _other(conv, user):
    m = conv.match
    return m.user_b if m.user_a_id == user.pk else m.user_a


def _msg(m, me):
    return {"id": m.pk, "body": m.body, "created_at": m.created_at, "mine": m.sender_id == me.pk, "read": m.read_at is not None}


class ConversationListView(APIView):
    permission_classes = [IsUniversityVerified]

    def get(self, request):
        rows = []
        for c in my_conversations(request.user):
            last = c.messages.order_by("-id").first()
            rows.append((
                (last.created_at if last else c.created_at),
                {
                    "id": c.pk,
                    "match_id": c.match_id,
                    "profile": public_profile(_other(c, request.user).profile),
                    "last_message": _msg(last, request.user) if last else None,
                    "unread": c.messages.filter(read_at__isnull=True).exclude(sender=request.user).count(),
                },
            ))
        rows.sort(key=lambda r: r[0], reverse=True)
        return Response([r[1] for r in rows])


class MessagesView(APIView):
    permission_classes = [IsUniversityVerified]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "chat"

    def _conv(self, request, pk):
        return get_object_or_404(my_conversations(request.user), pk=pk)  # not yours: 404

    def get(self, request, pk):
        conv = self._conv(request, pk)
        qs = conv.messages.all()
        after = request.query_params.get("after", "")
        if after.isdigit():
            qs = qs.filter(pk__gt=int(after))
        msgs = list(qs.order_by("-id")[:100])[::-1]
        data = [_msg(m, request.user) for m in msgs]
        conv.messages.filter(read_at__isnull=True).exclude(sender=request.user).update(read_at=timezone.now())
        return Response(data)

    def post(self, request, pk):
        conv = self._conv(request, pk)
        other = _other(conv, request.user)
        if Block.objects.filter(Q(blocker=request.user, blocked=other) | Q(blocker=other, blocked=request.user)).exists():
            return Response({"detail": "You can't message this student."}, status=403)
        body = str(request.data.get("body", "")).strip()
        if not body or len(body) > MAX_LEN:
            return Response({"detail": f"Write a message (up to {MAX_LEN} characters)."}, status=400)
        m = Message.objects.create(conversation=conv, sender=request.user, body=body)
        return Response(_msg(m, request.user), status=201)
