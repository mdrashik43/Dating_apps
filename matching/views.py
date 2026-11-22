from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsUniversityVerified
from profiles.public import public_profile

from .models import Match


def _mine(user):
    return Match.objects.filter(Q(user_a=user) | Q(user_b=user), is_active=True)


class MatchListView(APIView):
    permission_classes = [IsUniversityVerified]

    def get(self, request):
        qs = _mine(request.user).select_related("user_a__profile", "user_b__profile", "conversation")
        out = []
        for m in qs.order_by("-created_at"):
            other = m.user_b if m.user_a_id == request.user.pk else m.user_a
            conv = getattr(m, "conversation", None)
            out.append({
                "id": m.pk,
                "conversation_id": conv.pk if conv else None,
                "matched_at": m.created_at,
                "profile": public_profile(other.profile),
            })
        return Response(out)


class UnmatchView(APIView):
    permission_classes = [IsUniversityVerified]

    def post(self, request, pk):
        match = get_object_or_404(_mine(request.user), pk=pk)
        match.is_active = False
        match.save(update_fields=["is_active"])
        return Response(status=204)
