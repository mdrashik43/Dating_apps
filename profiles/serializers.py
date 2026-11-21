from rest_framework import serializers

from .models import Profile, calculate_age


class ProfileSerializer(serializers.ModelSerializer):
    age = serializers.IntegerField(read_only=True)

    class Meta:
        model = Profile
        fields = [
            "display_name", "date_of_birth", "age", "gender", "looking_for", "bio",
            "department", "batch", "is_discoverable", "consent_mystery_game",
        ]

    def validate_display_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Display name cannot be blank.")
        return value

    def validate_date_of_birth(self, value):
        if calculate_age(value) > 100:
            raise serializers.ValidationError("Enter a valid date of birth.")
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        goes_public = attrs.get("is_discoverable") or attrs.get("consent_mystery_game")
        if goes_public and not user.is_university_verified:
            raise serializers.ValidationError(
                "You must be university-verified before your profile can be discoverable."
            )
        return attrs
