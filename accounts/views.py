from django.core import signing
from django.db import IntegrityError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from rest_framework.views import APIView

from . import emailing
from .models import User, VerificationRequest
from .serializers import (
    LoginSerializer,
    MeSerializer,
    RegisterSerializer,
    ReviewSerializer,
    StaffVerificationSerializer,
    VerificationCreateSerializer,
    VerificationRequestSerializer,
)


class AuthThrottle(AnonRateThrottle):
    rate = "10/min"


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        s = RegisterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = s.save()
        emailing.send_confirmation_email(user)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": MeSerializer(user).data}, status=201)


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        s = LoginSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        token, _ = Token.objects.get_or_create(user=s.validated_data["user"])
        return Response({"token": token.key, "user": MeSerializer(s.validated_data["user"]).data})


class LogoutView(APIView):
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        return Response(MeSerializer(request.user).data)


@api_view(["GET"])
def verification_document(request, pk):
    """Only the owner or staff may download a verification document."""
    try:
        vr = VerificationRequest.objects.get(pk=pk)
    except VerificationRequest.DoesNotExist:
        raise Http404
    if not (request.user.is_staff or vr.user_id == request.user.id):
        raise Http404  # do not reveal existence
    resp = FileResponse(vr.document.open("rb"))
    resp["Cache-Control"] = "private, no-store"
    resp["X-Content-Type-Options"] = "nosniff"
    return resp


class ConfirmEmailView(APIView):
    """The signed link is the credential, so no login is needed."""

    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]

    def post(self, request):
        token = request.data.get("token", "")
        try:
            data = emailing.read_token(token)
        except signing.SignatureExpired:
            return Response({"detail": "This link has expired. Request a new one."}, status=400)
        except signing.BadSignature:
            return Response({"detail": "Invalid link."}, status=400)
        user = User.objects.filter(pk=data["uid"], email=data["email"]).select_related("university").first()
        if user is None:
            return Response({"detail": "Invalid link."}, status=400)
        user.email_confirmed = True
        fields = ["email_confirmed"]
        # A confirmed address on the university's own domain proves enrolment.
        if user.university and user.university.matches_email(user.email):
            user.is_university_verified = True
            fields.append("is_university_verified")
        user.save(update_fields=fields)
        return Response(MeSerializer(user).data)


class ResendConfirmationView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_resend"

    def post(self, request):
        if request.user.email_confirmed:
            return Response({"detail": "Email already confirmed."}, status=400)
        emailing.send_confirmation_email(request.user)
        return Response({"detail": "Confirmation email sent."})


class VerificationView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        qs = request.user.verification_requests.all()
        return Response(VerificationRequestSerializer(qs, many=True).data)

    def post(self, request):
        user = request.user
        if user.is_university_verified:
            return Response({"detail": "You are already verified."}, status=400)
        if not user.university_id:
            return Response({"detail": "No university is linked to your account."}, status=400)
        if user.verification_requests.filter(status=VerificationRequest.Status.PENDING).exists():
            return Response({"detail": "You already have a pending request."}, status=400)
        s = VerificationCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            vr = s.save(user=user, university=user.university)
        except IntegrityError:
            return Response({"detail": "You already have a pending request."}, status=400)
        return Response(VerificationRequestSerializer(vr).data, status=201)


class StaffVerificationListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        status_ = request.query_params.get("status", "pending")
        qs = VerificationRequest.objects.filter(status=status_).select_related("user", "university")
        return Response(StaffVerificationSerializer(qs, many=True).data)


class StaffVerificationReviewView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        vr = get_object_or_404(VerificationRequest, pk=pk)
        s = ReviewSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            if s.validated_data["decision"] == "approve":
                vr.approve(request.user)
            else:
                vr.reject(request.user, s.validated_data["reason"])
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(StaffVerificationSerializer(vr).data)
