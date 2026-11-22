from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsUniversityVerified

from . import services as svc
from .models import Clue, GameSession
from .serializers import ClueSerializer


class MyClueViewSet(viewsets.ModelViewSet):
    """Owners manage their own clues. Nobody else's clues are reachable here."""

    serializer_class = ClueSerializer
    permission_classes = [IsUniversityVerified]

    def get_queryset(self):
        return Clue.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        top = self.get_queryset().aggregate(m=Max("position"))["m"]
        serializer.save(owner=self.request.user, position=0 if top is None else top + 1)


def _err(e):
    return Response({"detail": e.detail}, status=e.status)


class _SessionView(APIView):
    permission_classes = [IsUniversityVerified]

    def own(self, request, pk, lock=False):
        qs = GameSession.objects.select_for_update() if lock else GameSession.objects.all()
        return get_object_or_404(qs, pk=pk, player=request.user)  # others' sessions: 404


class StartSessionView(_SessionView):
    def post(self, request):
        try:
            with transaction.atomic():
                session, created = svc.start_session(request.user)
        except svc.GameError as e:
            return _err(e)
        return Response(svc.state(session), status=201 if created else 200)


class CurrentSessionView(_SessionView):
    def get(self, request):
        session = GameSession.objects.filter(player=request.user, status__in=svc.OPEN).first()
        if session is None:
            return Response({"detail": "No game in progress."}, status=404)
        return Response(svc.state(session))


class SessionDetailView(_SessionView):
    def get(self, request, pk):
        return Response(svc.state(self.own(request, pk)))


class GuessView(_SessionView):
    def post(self, request, pk):
        try:
            with transaction.atomic():
                session = self.own(request, pk, lock=True)
                svc.submit_guess(session, request.data.get("text"))
        except svc.GameError as e:
            return _err(e)
        return Response(svc.state(session))


class RevealView(_SessionView):
    def post(self, request, pk):
        try:
            with transaction.atomic():
                session = self.own(request, pk, lock=True)
                ok = svc.reveal(session)
        except svc.GameError as e:
            return _err(e)
        if not ok:
            return Response({"detail": "This student is no longer available."}, status=409)
        return Response(svc.state(session))


class DecisionView(_SessionView):
    def post(self, request, pk):
        try:
            with transaction.atomic():
                session = self.own(request, pk, lock=True)
                result = svc.decide(session, request.data.get("action"))
        except svc.GameError as e:
            return _err(e)
        return Response(result)


class AbandonView(_SessionView):
    def post(self, request, pk):
        with transaction.atomic():
            session = self.own(request, pk, lock=True)
            svc.abandon(session)
        return Response({"status": session.status})
