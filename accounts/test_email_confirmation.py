import re

from django.core import mail, signing
from django.test import override_settings

from accounts import emailing
from accounts.models import User
from accounts.testing import PW, APITestCase, make_user


def token_from_outbox():
    return re.search(r"token=([^\s]+)", mail.outbox[-1].body).group(1)


class EmailConfirmationTests(APITestCase):
    def register(self, email="s@bscse.uiu.ac.bd"):
        return self.client_for().post("/api/auth/register/", {"email": email, "password": PW}, format="json")

    def test_register_sends_one_confirmation_email(self):
        self.assertEqual(self.register().status_code, 201)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["s@bscse.uiu.ac.bd"])

    def test_confirm_marks_user_verified(self):
        self.register()
        r = self.client_for().post("/api/auth/email/confirm/", {"token": token_from_outbox()}, format="json")
        self.assertEqual(r.status_code, 200)
        u = User.objects.get(email="s@bscse.uiu.ac.bd")
        self.assertTrue(u.email_confirmed and u.is_university_verified)

    def test_confirm_is_idempotent(self):
        self.register()
        t = token_from_outbox()
        for _ in range(2):
            self.assertEqual(self.client_for().post("/api/auth/email/confirm/", {"token": t}, format="json").status_code, 200)

    def test_tampered_token_rejected(self):
        self.register()
        r = self.client_for().post("/api/auth/email/confirm/", {"token": token_from_outbox() + "x"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(User.objects.get(email="s@bscse.uiu.ac.bd").email_confirmed)

    def test_garbage_and_missing_token_rejected(self):
        for body in ({"token": "nonsense"}, {}):
            self.assertEqual(self.client_for().post("/api/auth/email/confirm/", body, format="json").status_code, 400)

    @override_settings(EMAIL_CONFIRM_MAX_AGE=-1)
    def test_expired_token_rejected(self):
        u = make_user("e@uiu.ac.bd", university=self.uni)
        r = self.client_for().post("/api/auth/email/confirm/", {"token": emailing.make_token(u)}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("expired", r.json()["detail"])

    def test_token_for_changed_email_rejected(self):
        u = make_user("old@uiu.ac.bd", university=self.uni)
        t = emailing.make_token(u)
        u.email = "new@uiu.ac.bd"
        u.save()
        self.assertEqual(self.client_for().post("/api/auth/email/confirm/", {"token": t}, format="json").status_code, 400)

    def test_token_signed_with_other_salt_rejected(self):
        u = make_user("o@uiu.ac.bd", university=self.uni)
        forged = signing.dumps({"uid": str(u.pk), "email": u.email}, salt="something-else")
        self.assertEqual(self.client_for().post("/api/auth/email/confirm/", {"token": forged}, format="json").status_code, 400)

    def test_user_without_university_confirms_but_is_not_verified(self):
        u = make_user("x@gmail.com")
        r = self.client_for().post("/api/auth/email/confirm/", {"token": emailing.make_token(u)}, format="json")
        self.assertEqual(r.status_code, 200)
        u.refresh_from_db()
        self.assertTrue(u.email_confirmed)
        self.assertFalse(u.is_university_verified)

    def test_resend_requires_login_and_stops_once_confirmed(self):
        self.assertEqual(self.client_for().post("/api/auth/email/resend/").status_code, 401)
        u = make_user("r@uiu.ac.bd", university=self.uni)
        c = self.client_for(u)
        self.assertEqual(c.post("/api/auth/email/resend/").status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        u.email_confirmed = True
        u.save()
        self.assertEqual(c.post("/api/auth/email/resend/").status_code, 400)

    def test_resend_is_rate_limited(self):
        c = self.client_for(make_user("t@uiu.ac.bd", university=self.uni))
        codes = [c.post("/api/auth/email/resend/").status_code for _ in range(7)]
        self.assertEqual(codes[:5], [200] * 5)
        self.assertEqual(codes[5], 429)


class PlainConsoleBackendTests(APITestCase):
    def test_link_is_printed_unmangled(self):
        import io
        from contextlib import redirect_stdout

        from django.core.mail import EmailMessage
        from accounts.mail import PlainConsoleEmailBackend

        u = make_user("c@uiu.ac.bd", university=self.uni)
        link = f"http://localhost:5173/confirm-email?token={emailing.make_token(u)}"
        buf = io.StringIO()
        with redirect_stdout(buf):
            PlainConsoleEmailBackend().send_messages([EmailMessage("Hi", link, "a@b.c", ["c@uiu.ac.bd"])])
        self.assertIn(link, buf.getvalue())
        self.assertNotIn("=3D", buf.getvalue())
