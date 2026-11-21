from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Profile
from .serializers import ProfileSerializer


class MyProfileView(APIView):
    """A user can only ever read or change their own profile here."""

    def _get(self, request):
        return Profile.objects.filter(user=request.user).first()

    def get(self, request):
        profile = self._get(request)
        if profile is None:
            return Response({"detail": "You have no profile yet."}, status=404)
        return Response(ProfileSerializer(profile, context={"request": request}).data)

    def post(self, request):
        if self._get(request):
            return Response({"detail": "Profile already exists. Use PATCH."}, status=400)
        s = ProfileSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        s.save(user=request.user)
        return Response(s.data, status=201)

    def patch(self, request):
        profile = self._get(request)
        if profile is None:
            return Response({"detail": "You have no profile yet."}, status=404)
        s = ProfileSerializer(profile, data=request.data, partial=True, context={"request": request})
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)
