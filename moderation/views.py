from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsUniversityVerified

from . import services
from .models import Report


class _TargetSerializer(serializers.Serializer):
    session_id = serializers.IntegerField(required=False)
    match_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        if ("session_id" in attrs) == ("match_id" in attrs):
            raise serializers.ValidationError("Provide exactly one of session_id or match_id.")
        return attrs


class _ReportSerializer(_TargetSerializer):
    reason = serializers.ChoiceField(choices=Report.Reason.choices)
    details = serializers.CharField(max_length=1000, required=False, allow_blank=True)


def _target(request, s):
    return services.resolve_target(
        request.user, s.validated_data.get("session_id"), s.validated_data.get("match_id")
    )


class BlockView(APIView):
    permission_classes = [IsUniversityVerified]

    def post(self, request):
        s = _TargetSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        target = _target(request, s)
        if target is None:
            return Response({"detail": "Not found."}, status=404)
        services.block_user(request.user, target)
        return Response({"blocked": True}, status=201)


class ReportView(APIView):
    permission_classes = [IsUniversityVerified]

    def post(self, request):
        s = _ReportSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        target = _target(request, s)
        if target is None:
            return Response({"detail": "Not found."}, status=404)
        Report.objects.create(
            reporter=request.user,
            reported_user=target,
            reason=s.validated_data["reason"],
            details=s.validated_data.get("details", ""),
        )
        return Response({"reported": True}, status=201)


class MyBlocksView(APIView):
    """Deliberately shows no names: otherwise blocking during a game would be a
    way to learn the mystery student's identity before the reveal."""

    permission_classes = [IsUniversityVerified]

    def get(self, request):
        from .models import Block

        return Response([{"id": b.pk, "created_at": b.created_at} for b in Block.objects.filter(blocker=request.user).order_by("-created_at")])


class UnblockView(APIView):
    permission_classes = [IsUniversityVerified]

    def delete(self, request, pk):
        from django.shortcuts import get_object_or_404

        from .models import Block

        get_object_or_404(Block, pk=pk, blocker=request.user).delete()
        return Response(status=204)
