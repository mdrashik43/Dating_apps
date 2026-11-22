from django.urls import path

from . import views

urlpatterns = [
    path("", views.MatchListView.as_view(), name="match-list"),
    path("<int:pk>/unmatch/", views.UnmatchView.as_view(), name="match-unmatch"),
]
