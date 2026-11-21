from datetime import date

from accounts.testing import APITestCase, make_user

URL = "/api/profiles/me/"


def dob(years):
    t = date.today()
    return date(t.year - years, t.month, 1).isoformat()


def payload(**kw):
    base = {"display_name": "Rashik", "date_of_birth": dob(21), "gender": "male"}
    base.update(kw)
    return base


class ProfileApiTests(APITestCase):
    def test_requires_login(self):
        c = self.client_for()
        for call in (c.get, c.post, c.patch):
            self.assertEqual(call(URL).status_code, 401)

    def test_no_profile_yet_is_404(self):
        self.assertEqual(self.client_for(make_user()).get(URL).status_code, 404)

    def test_create_is_private_by_default(self):
        r = self.client_for(make_user()).post(URL, payload(), format="json")
        self.assertEqual(r.status_code, 201)
        self.assertFalse(r.json()["is_discoverable"])
        self.assertFalse(r.json()["consent_mystery_game"])
        self.assertGreaterEqual(r.json()["age"], 20)

    def test_minor_rejected(self):
        r = self.client_for(make_user()).post(URL, payload(date_of_birth=dob(17)), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("date_of_birth", r.json())

    def test_future_and_absurd_dob_rejected(self):
        c = self.client_for(make_user())
        self.assertEqual(c.post(URL, payload(date_of_birth="2999-01-01"), format="json").status_code, 400)
        self.assertEqual(c.post(URL, payload(date_of_birth="1800-01-01"), format="json").status_code, 400)

    def test_blank_name_rejected(self):
        self.assertEqual(self.client_for(make_user()).post(URL, payload(display_name="  "), format="json").status_code, 400)

    def test_duplicate_create_rejected(self):
        c = self.client_for(make_user())
        c.post(URL, payload(), format="json")
        self.assertEqual(c.post(URL, payload(), format="json").status_code, 400)

    def test_unverified_user_cannot_go_public(self):
        c = self.client_for(make_user())
        for field in ("is_discoverable", "consent_mystery_game"):
            self.assertEqual(c.post(URL, payload(**{field: True}), format="json").status_code, 400)
        c.post(URL, payload(), format="json")
        self.assertEqual(c.patch(URL, {"is_discoverable": True}, format="json").status_code, 400)

    def test_verified_user_can_opt_in_and_out(self):
        c = self.client_for(self.verified_user())
        c.post(URL, payload(), format="json")
        r = c.patch(URL, {"is_discoverable": True, "consent_mystery_game": True}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["consent_mystery_game"])
        r = c.patch(URL, {"consent_mystery_game": False}, format="json")
        self.assertFalse(r.json()["consent_mystery_game"])

    def test_age_is_read_only_and_patch_is_partial(self):
        c = self.client_for(make_user())
        c.post(URL, payload(), format="json")
        r = c.patch(URL, {"age": 99, "bio": "Hi"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["bio"], "Hi")
        self.assertNotEqual(r.json()["age"], 99)
        self.assertEqual(r.json()["display_name"], "Rashik")

    def test_patch_cannot_make_user_a_minor(self):
        c = self.client_for(make_user())
        c.post(URL, payload(), format="json")
        self.assertEqual(c.patch(URL, {"date_of_birth": dob(16)}, format="json").status_code, 400)

    def test_users_only_see_their_own_profile(self):
        a, b = make_user("a@uiu.ac.bd"), make_user("b@uiu.ac.bd")
        self.client_for(a).post(URL, payload(display_name="Alice"), format="json")
        self.client_for(b).post(URL, payload(display_name="Bob"), format="json")
        self.assertEqual(self.client_for(a).get(URL).json()["display_name"], "Alice")
        self.assertEqual(self.client_for(b).get(URL).json()["display_name"], "Bob")
