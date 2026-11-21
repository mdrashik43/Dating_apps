from rest_framework.permissions import BasePermission


class IsUniversityVerified(BasePermission):
    message = "University verification is required."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_university_verified)
