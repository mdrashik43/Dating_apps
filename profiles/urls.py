from django.urls import path

from . import views

urlpatterns = [
    path("me/", views.MyProfileView.as_view(), name="my-profile"),
    path("me/photos/", views.MyPhotosView.as_view(), name="my-photos"),
    path("me/photos/<int:pk>/", views.MyPhotoDeleteView.as_view(), name="my-photo-delete"),
    path("photos/<int:pk>/", views.PhotoFileView.as_view(), name="photo-file"),
]
