import shutil
import tempfile
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import University, User, VerificationRequest
from matching.models import Match, Swipe
from moderation.models import Block
from profiles.models import Profile

PW = "S7rong-Pass-9x!"


def make_user(email="a@uiu.ac.bd", **kw):
    return User.objects.create_user(email=email, password=PW, **kw)


class HealthTests(TestCase):
    def test_health_is_public_and_ok(self):
        r = self.client.get("/api/health/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"status": "ok", "database": "up"})


class UserModelTests(TestCase):
    def test_email_is_login_and_lowercased(self):
        u = make_user("MixedCase@UIU.ac.bd")
        self.assertEqual(u.email, "mixedcase@uiu.ac.bd")
        self.assertTrue(self.client.login(email="mixedcase@uiu.ac.bd", password=PW) or
                        self.client.login(username="mixedcase@uiu.ac.bd", password=PW))

    def test_unique_email(self):
        make_user()
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_user()

    def test_superuser_flags(self):
        s = User.objects.create_superuser(email="root@uiu.ac.bd", password=PW)
        self.assertTrue(s.is_staff and s.is_superuser)

    def test_domain_matching(self):
        uni = University(name="UIU", email_domain="uiu.ac.bd")
        self.assertTrue(uni.matches_email("x@uiu.ac.bd"))
        self.assertTrue(uni.matches_email("x@bscse.uiu.ac.bd"))
        self.assertFalse(uni.matches_email("x@evil-uiu.ac.bd"))
        self.assertFalse(uni.matches_email("x@gmail.com"))


class AuthApiTests(TestCase):
    def setUp(self):
        University.objects.create(name="UIU", short_name="UIU", email_domain="uiu.ac.bd")
        self.c = APIClient()

    def test_register_with_university_email(self):
        r = self.c.post("/api/auth/register/", {"email": "s@bscse.uiu.ac.bd", "password": PW}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertIn("token", r.json())
        self.assertFalse(r.json()["user"]["is_university_verified"])

    def test_register_rejects_non_university_email(self):
        r = self.c.post("/api/auth/register/", {"email": "s@gmail.com", "password": PW}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_register_rejects_weak_password(self):
        r = self.c.post("/api/auth/register/", {"email": "s@uiu.ac.bd", "password": "123"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_login_me_logout(self):
        make_user("s@uiu.ac.bd")
        r = self.c.post("/api/auth/login/", {"email": "s@uiu.ac.bd", "password": PW}, format="json")
        self.assertEqual(r.status_code, 200)
        self.c.credentials(HTTP_AUTHORIZATION="Token " + r.json()["token"])
        self.assertEqual(self.c.get("/api/auth/me/").json()["email"], "s@uiu.ac.bd")
        self.assertEqual(self.c.post("/api/auth/logout/").status_code, 204)
        self.assertEqual(self.c.get("/api/auth/me/").status_code, 401)

    def test_bad_login(self):
        make_user("s@uiu.ac.bd")
        r = self.c.post("/api/auth/login/", {"email": "s@uiu.ac.bd", "password": "wrong"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_me_requires_auth(self):
        self.assertEqual(self.c.get("/api/auth/me/").status_code, 401)


class ProfileTests(TestCase):
    def _dob(self, years):
        return date.today().replace(year=date.today().year - years) - timedelta(days=1)

    def test_adult_profile_ok_and_private_by_default(self):
        p = Profile.objects.create(user=make_user(), display_name="A", date_of_birth=self._dob(20), gender="male")
        self.assertFalse(p.is_discoverable)
        self.assertFalse(p.consent_mystery_game)
        self.assertGreaterEqual(p.age, 20)

    def test_minor_rejected(self):
        with self.assertRaises(ValidationError):
            Profile.objects.create(user=make_user(), display_name="M", date_of_birth=self._dob(17), gender="male")


class ConstraintTests(TestCase):
    def setUp(self):
        self.a, self.b = make_user("a@uiu.ac.bd"), make_user("b@uiu.ac.bd")

    def test_no_self_swipe(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Swipe.objects.create(actor=self.a, target=self.a, action="like")

    def test_unique_swipe(self):
        Swipe.objects.create(actor=self.a, target=self.b, action="like")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Swipe.objects.create(actor=self.a, target=self.b, action="pass")

    def test_match_is_order_independent_and_unique(self):
        m1, c1 = Match.create_for(self.a, self.b)
        m2, c2 = Match.create_for(self.b, self.a)
        self.assertTrue(c1)
        self.assertFalse(c2)
        self.assertEqual(m1.pk, m2.pk)

    def test_unordered_match_rejected(self):
        hi, lo = sorted([self.a, self.b], key=lambda u: u.pk, reverse=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Match.objects.create(user_a=hi, user_b=lo)

    def test_no_self_block(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Block.objects.create(blocker=self.a, blocked=self.a)


class PrivateDocumentTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ov = override_settings(PRIVATE_MEDIA_ROOT=self.tmp, MEDIA_ROOT=self.tmp + "_public")
        self.ov.enable()
        self.addCleanup(self.ov.disable)
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.uni = University.objects.create(name="UIU", email_domain="uiu.ac.bd")
        self.owner, self.other = make_user("o@uiu.ac.bd"), make_user("x@uiu.ac.bd")
        self.staff = make_user("s@uiu.ac.bd", is_staff=True)
        self.vr = VerificationRequest.objects.create(
            user=self.owner, university=self.uni, student_id_number="011",
            document=SimpleUploadedFile("id.png", b"\x89PNG-secret", content_type="image/png"),
        )
        self.url = reverse("verification-document", args=[self.vr.pk])

    def _get(self, user=None):
        c = APIClient()
        if user:
            c.force_authenticate(user)
        return c.get(self.url)

    def test_anonymous_denied(self):
        self.assertEqual(self._get().status_code, 401)

    def test_other_student_gets_404(self):
        self.assertEqual(self._get(self.other).status_code, 404)

    def test_owner_and_staff_allowed(self):
        for u in (self.owner, self.staff):
            r = self._get(u)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(b"".join(r.streaming_content), b"\x89PNG-secret")
            self.assertIn("no-store", r["Cache-Control"])

    def test_document_has_no_public_url(self):
        with self.assertRaises(ValueError):
            self.vr.document.url

    def test_only_one_pending_request(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            VerificationRequest.objects.create(
                user=self.owner, university=self.uni, student_id_number="011",
                document=SimpleUploadedFile("b.png", b"x"),
            )


class AdminTests(TestCase):
    def test_admin_pages_load(self):
        su = User.objects.create_superuser(email="root@uiu.ac.bd", password=PW)
        uni = University.objects.create(name="UIU", email_domain="uiu.ac.bd")
        u = make_user("o@uiu.ac.bd")
        with tempfile.TemporaryDirectory() as tmp, override_settings(PRIVATE_MEDIA_ROOT=tmp):
            vr = VerificationRequest.objects.create(
                user=u, university=uni, student_id_number="1",
                document=SimpleUploadedFile("id.png", b"x"))
            self.client.force_login(su)
            for url in ["/admin/", "/admin/accounts/user/", f"/admin/accounts/user/{u.pk}/change/",
                        "/admin/accounts/verificationrequest/",
                        f"/admin/accounts/verificationrequest/{vr.pk}/change/",
                        "/admin/profiles/profile/", "/admin/matching/match/",
                        "/admin/mystery_game/gamesession/", "/admin/chat/message/",
                        "/admin/notifications/notification/", "/admin/moderation/report/"]:
                self.assertEqual(self.client.get(url).status_code, 200, url)
