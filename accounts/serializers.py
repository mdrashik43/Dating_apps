import re

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from django.urls import reverse

from .models import University, User, VerificationRequest


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        uni = next(
            (u for u in University.objects.filter(is_active=True) if u.matches_email(value)),
            None,
        )
        if uni is None:
            raise serializers.ValidationError("Please use your university email address.")
        self.context["university"] = uni
        return value

    def validate(self, attrs):
        validate_password(attrs["password"], user=User(email=attrs["email"]))
        return attrs

    def create(self, validated):
        return User.objects.create_user(
            email=validated["email"],
            password=validated["password"],
            university=self.context["university"],
        )


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["email"].lower(),
            password=attrs["password"],
        )
        if user is None or not user.is_active:
            raise serializers.ValidationError("Invalid email or password.")
        attrs["user"] = user
        return attrs


class MeSerializer(serializers.ModelSerializer):
    university = serializers.StringRelatedField()

    class Meta:
        model = User
        fields = ["id", "email", "university", "email_confirmed", "is_university_verified"]
        read_only_fields = fields


MAX_UPLOAD_BYTES = 5 * 1024 * 1024
FILE_SIGNATURES = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"%PDF-")


class VerificationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VerificationRequest
        fields = ["student_id_number", "document"]

    def validate_student_id_number(self, value):
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9-]{3,30}", value):
            raise serializers.ValidationError("Enter a valid student ID (letters, digits, dashes).")
        return value

    def validate_document(self, f):
        if f.size > MAX_UPLOAD_BYTES:
            raise serializers.ValidationError("File too large (max 5 MB).")
        head = f.read(8)
        f.seek(0)
        if not head.startswith(FILE_SIGNATURES):  # content check, not just the extension
            raise serializers.ValidationError("File must be a real JPG, PNG or PDF.")
        return f


class VerificationRequestSerializer(serializers.ModelSerializer):
    """Never exposes a storage URL; documents download via an authenticated view."""

    document_path = serializers.SerializerMethodField()

    class Meta:
        model = VerificationRequest
        fields = ["id", "student_id_number", "status", "rejection_reason", "created_at", "document_path"]
        read_only_fields = fields

    def get_document_path(self, obj):
        return reverse("verification-document", args=[obj.pk])


class StaffVerificationSerializer(VerificationRequestSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    university = serializers.StringRelatedField()

    class Meta(VerificationRequestSerializer.Meta):
        fields = VerificationRequestSerializer.Meta.fields + ["email", "university"]
        read_only_fields = fields


class ReviewSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["approve", "reject"])
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["decision"] == "reject" and not attrs.get("reason", "").strip():
            raise serializers.ValidationError({"reason": "A reason is required when rejecting."})
        return attrs
