import logging

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail

log = logging.getLogger(__name__)
SALT = "vibematch.email-confirm"


def make_token(user) -> str:
    return signing.dumps({"uid": str(user.pk), "email": user.email}, salt=SALT)


def read_token(token: str) -> dict:
    """Raises signing.BadSignature / SignatureExpired on any problem."""
    return signing.loads(token, salt=SALT, max_age=settings.EMAIL_CONFIRM_MAX_AGE)


def send_confirmation_email(user) -> bool:
    link = f"{settings.FRONTEND_URL}/confirm-email?token={make_token(user)}"
    try:
        send_mail(
            "Confirm your Vibe Match email",
            f"Welcome to Vibe Match!\n\nConfirm your university email:\n{link}\n\n"
            "If you did not sign up, ignore this message.",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        )
        return True
    except Exception:  # never break signup because of a mail outage
        log.exception("Could not send confirmation email")
        return False
