from django.db.models import Max
from rest_framework import viewsets

from accounts.permissions import IsUniversityVerified

from .models import Clue
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
