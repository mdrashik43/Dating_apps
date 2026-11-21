from django.urls import path

from . import views

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.MeView.as_view(), name="me"),
    path("email/confirm/", views.ConfirmEmailView.as_view(), name="email-confirm"),
    path("email/resend/", views.ResendConfirmationView.as_view(), name="email-resend"),
    path("verification/", views.VerificationView.as_view(), name="verification"),
    path("verification/pending/", views.StaffVerificationListView.as_view(), name="verification-staff-list"),
    path("verification/<uuid:pk>/review/", views.StaffVerificationReviewView.as_view(), name="verification-review"),
    path(
        "verification/<uuid:pk>/document/",
        views.verification_document,
        name="verification-document",
    ),
]
