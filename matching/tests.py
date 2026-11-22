from accounts.testing import APITestCase
from mystery_game.tests_helpers import mutual_match

URL = "/api/matches/"


class MatchApiTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.a, self.b = self.player("a@uiu.ac.bd", name="Alice"), self.player("b@uiu.ac.bd", name="Bob")
        self.c = self.player("c@uiu.ac.bd", name="Carol", discoverable=False)
        self.match = mutual_match(self, self.a, self.b)

    def test_requires_login(self):
        self.assertEqual(self.client_for().get(URL).status_code, 401)

    def test_each_side_sees_the_other_public_profile_only(self):
        r = self.client_for(self.a).get(URL)
        self.assertEqual(r.status_code, 200)
        item = r.json()[0]
        self.assertEqual(item["profile"]["display_name"], "Bob")
        self.assertIsNotNone(item["conversation_id"])
        for secret in (self.b.email, str(self.b.pk), "2001-01-15"):
            self.assertNotIn(secret, r.content.decode())
        self.assertEqual(self.client_for(self.b).get(URL).json()[0]["profile"]["display_name"], "Alice")

    def test_outsiders_see_nothing(self):
        self.assertEqual(self.client_for(self.c).get(URL).json(), [])

    def test_unmatch_hides_the_match_for_both_and_is_owner_only(self):
        self.assertEqual(self.client_for(self.c).post(f"{URL}{self.match.pk}/unmatch/").status_code, 404)
        self.assertEqual(self.client_for(self.a).post(f"{URL}{self.match.pk}/unmatch/").status_code, 204)
        self.assertEqual(self.client_for(self.a).get(URL).json(), [])
        self.assertEqual(self.client_for(self.b).get(URL).json(), [])
