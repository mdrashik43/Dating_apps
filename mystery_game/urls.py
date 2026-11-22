from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("clues", views.MyClueViewSet, basename="clue")

urlpatterns = router.urls + [
    path("sessions/", views.StartSessionView.as_view(), name="session-start"),
    path("sessions/current/", views.CurrentSessionView.as_view(), name="session-current"),
    path("sessions/<int:pk>/", views.SessionDetailView.as_view(), name="session-detail"),
    path("sessions/<int:pk>/guess/", views.GuessView.as_view(), name="session-guess"),
    path("sessions/<int:pk>/reveal/", views.RevealView.as_view(), name="session-reveal"),
    path("sessions/<int:pk>/decision/", views.DecisionView.as_view(), name="session-decision"),
    path("sessions/<int:pk>/abandon/", views.AbandonView.as_view(), name="session-abandon"),
]
