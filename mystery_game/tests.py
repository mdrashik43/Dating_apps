from accounts.testing import APITestCase, make_user
from mystery_game.models import Clue

URL = "/api/game/clues/"


class ClueApiTests(APITestCase):
    def test_anonymous_gets_401(self):
        self.assertEqual(self.client_for().get(URL).status_code, 401)

    def test_unverified_user_gets_403(self):
        c = self.client_for(make_user("u@uiu.ac.bd", university=self.uni))
        self.assertEqual(c.get(URL).status_code, 403)
        self.assertEqual(c.post(URL, {"text": "I love chai"}, format="json").status_code, 403)

    def test_create_list_update_delete(self):
        c = self.client_for(self.verified_user())
        r = c.post(URL, {"text": "  I love chai  "}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["text"], "I love chai")
        self.assertEqual(r.json()["position"], 0)
        pk = r.json()["id"]
        self.assertEqual(c.post(URL, {"text": "Second"}, format="json").json()["position"], 1)
        self.assertEqual(len(c.get(URL).json()), 2)
        self.assertEqual(c.patch(f"{URL}{pk}/", {"text": "Edited"}, format="json").json()["text"], "Edited")
        self.assertEqual(c.delete(f"{URL}{pk}/").status_code, 204)
        self.assertEqual(len(c.get(URL).json()), 1)

    def test_position_cannot_be_set_by_client(self):
        c = self.client_for(self.verified_user())
        self.assertEqual(c.post(URL, {"text": "x", "position": 99}, format="json").json()["position"], 0)

    def test_blank_clue_rejected(self):
        self.assertEqual(self.client_for(self.verified_user()).post(URL, {"text": "   "}, format="json").status_code, 400)

    def test_maximum_five_clues(self):
        c = self.client_for(self.verified_user())
        for i in range(5):
            self.assertEqual(c.post(URL, {"text": f"clue {i}"}, format="json").status_code, 201)
        self.assertEqual(c.post(URL, {"text": "one too many"}, format="json").status_code, 400)

    def test_cannot_touch_someone_elses_clue(self):
        owner, other = self.verified_user("o@uiu.ac.bd"), self.verified_user("p@uiu.ac.bd")
        clue = Clue.objects.create(owner=owner, text="secret", position=0)
        c = self.client_for(other)
        self.assertEqual(c.get(f"{URL}{clue.pk}/").status_code, 404)
        self.assertEqual(c.patch(f"{URL}{clue.pk}/", {"text": "hacked"}, format="json").status_code, 404)
        self.assertEqual(c.delete(f"{URL}{clue.pk}/").status_code, 404)
        self.assertEqual(c.get(URL).json(), [])
        clue.refresh_from_db()
        self.assertEqual(clue.text, "secret")
