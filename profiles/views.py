from django.shortcuts import get_object_or_404
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


# ---------------------------------------------------------------- photos
from django.db.models import Q  # noqa: E402
from django.http import FileResponse, Http404  # noqa: E402
from rest_framework import serializers  # noqa: E402
from rest_framework.parsers import FormParser, MultiPartParser  # noqa: E402

from matching.models import Match  # noqa: E402
from mystery_game.models import GameSession  # noqa: E402

from .models import ProfilePhoto  # noqa: E402
from .photos import MAX_PHOTOS, clean_image  # noqa: E402


def _photo_json(p):
    return {"id": p.pk, "position": p.position, "url": f"/api/profiles/photos/{p.pk}/"}


class MyPhotosView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        photos = ProfilePhoto.objects.filter(profile__user=request.user)
        return Response([_photo_json(p) for p in photos])

    def post(self, request):
        profile = Profile.objects.filter(user=request.user).first()
        if profile is None:
            return Response({"detail": "Create your profile first."}, status=400)
        upload = request.FILES.get("image")
        if upload is None:
            return Response({"detail": "Attach an image."}, status=400)
        used = set(profile.photos.values_list("position", flat=True))
        free = [i for i in range(MAX_PHOTOS) if i not in used]
        if not free:
            return Response({"detail": f"You can have at most {MAX_PHOTOS} photos."}, status=400)
        photo = ProfilePhoto.objects.create(profile=profile, image=clean_image(upload), position=free[0])
        return Response(_photo_json(photo), status=201)


class MyPhotoDeleteView(APIView):
    def delete(self, request, pk):
        photo = get_object_or_404(ProfilePhoto, pk=pk, profile__user=request.user)
        photo.image.delete(save=False)
        photo.delete()
        return Response(status=204)


def can_view_photo(viewer, photo) -> bool:
    owner = photo.profile.user
    if owner.pk == viewer.pk:
        return True
    if GameSession.objects.filter(player=viewer, mystery_user=owner, status="revealed").exists():
        return True  # currently looking at their revealed profile
    pair = Q(user_a=viewer, user_b=owner) | Q(user_a=owner, user_b=viewer)
    return Match.objects.filter(pair, is_active=True).exists()


class PhotoFileView(APIView):
    """Photos are private files: only the owner, a player who is viewing the
    revealed profile, or an active match may fetch them. Everyone else gets 404."""

    def get(self, request, pk):
        photo = ProfilePhoto.objects.filter(pk=pk).select_related("profile__user").first()
        if photo is None or not can_view_photo(request.user, photo):
            raise Http404
        resp = FileResponse(photo.image.open("rb"), content_type="image/jpeg")
        resp["Cache-Control"] = "private, no-store"
        resp["X-Content-Type-Options"] = "nosniff"
        return resp
