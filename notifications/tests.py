from accounts.testing import APITestCase, make_user
from notifications.models import Notification

URL = "/api/notifications/"


class NotificationTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.u, self.o = make_user("u@uiu.ac.bd"), make_user("o@uiu.ac.bd")  # unverified is fine
        self.n1 = Notification.objects.create(user=self.u, kind="system", title="One")
        self.n2 = Notification.objects.create(user=self.u, kind="system", title="Two")
        self.other = Notification.objects.create(user=self.o, kind="system", title="Theirs")

    def test_requires_login(self):
        self.assertEqual(self.client_for().get(URL).status_code, 401)
        self.assertEqual(self.client_for().post(URL + "read/").status_code, 401)

    def test_list_shows_only_own_with_unread_count(self):
        body = self.client_for(self.u).get(URL).json()
        self.assertEqual(body["unread"], 2)
        self.assertEqual(sorted(i["title"] for i in body["items"]), ["One", "Two"])

    def test_mark_some_then_all_and_never_others(self):
        c = self.client_for(self.u)
        self.assertEqual(c.post(URL + "read/", {"ids": [self.n1.pk, self.other.pk]}, format="json").json(), {"marked": 1})
        self.assertEqual(c.get(URL).json()["unread"], 1)
        self.assertEqual(c.post(URL + "read/").json(), {"marked": 1})
        self.other.refresh_from_db()
        self.assertFalse(self.other.is_read)
