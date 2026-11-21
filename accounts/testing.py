"""Shared helpers for tests."""
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import University, User

PW = "S7rong-Pass-9x!"
PNG = b"\x89PNG\r\n\x1a\n" + b"fake-image-bytes"


def make_user(email="a@uiu.ac.bd", **kw):
    return User.objects.create_user(email=email, password=PW, **kw)


class APITestCase(TestCase):
    def setUp(self):
        cache.clear()  # reset throttles between tests
        self.uni = University.objects.get_or_create(
            email_domain="uiu.ac.bd", defaults={"name": "UIU", "short_name": "UIU"}
        )[0]

    def client_for(self, user=None):
        c = APIClient()
        if user:
            c.force_authenticate(user)
        return c

    def verified_user(self, email="v@uiu.ac.bd"):
        return make_user(email, university=self.uni, is_university_verified=True)
