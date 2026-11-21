from rest_framework import serializers

from .models import Clue

MAX_CLUES = 5


class ClueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clue
        fields = ["id", "text", "position", "is_active"]
        read_only_fields = ["id", "position"]

    def validate_text(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("A clue cannot be blank.")
        return value

    def validate(self, attrs):
        request = self.context["request"]
        if self.instance is None and Clue.objects.filter(owner=request.user).count() >= MAX_CLUES:
            raise serializers.ValidationError(f"You can have at most {MAX_CLUES} clues.")
        return attrs
