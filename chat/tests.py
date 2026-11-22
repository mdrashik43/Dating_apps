from accounts.testing import APITestCase
from chat.models import Message
from moderation.models import Block
from mystery_game.tests_helpers import mutual_match

LIST = "/api/chat/conversations/"


class ChatTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.a, self.b = self.player("a@uiu.ac.bd", name="Alice"), self.player("b@uiu.ac.bd", name="Bob")
        self.match = mutual_match(self, self.a, self.b)
        self.conv = self.match.conversation
        self.url = f"{LIST}{self.conv.pk}/messages/"
        self.ca, self.cb = self.client_for(self.a), self.client_for(self.b)

    def send(self, client, body):
        return client.post(self.url, {"body": body}, format="json")

    def test_requires_login(self):
        self.assertEqual(self.client_for().get(LIST).status_code, 401)
        self.assertEqual(self.client_for().get(self.url).status_code, 401)

    def test_send_receive_and_read_receipts(self):
        r = self.send(self.ca, "  hello Bob  ")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["body"], "hello Bob")
        self.assertTrue(r.json()["mine"])
        listing = self.cb.get(LIST).json()[0]
        self.assertEqual((listing["unread"], listing["profile"]["display_name"]), (1, "Alice"))
        msgs = self.cb.get(self.url).json()
        self.assertEqual([m["body"] for m in msgs], ["hello Bob"])
        self.assertFalse(msgs[0]["mine"])
        self.assertEqual(self.cb.get(LIST).json()[0]["unread"], 0)
        self.assertTrue(self.ca.get(self.url).json()[0]["read"])

    def test_after_parameter_returns_only_new_messages(self):
        first = self.send(self.ca, "one").json()["id"]
        self.send(self.cb, "two")
        self.assertEqual([m["body"] for m in self.ca.get(f"{self.url}?after={first}").json()], ["two"])

    def test_validation(self):
        for bad in ("", "   ", "x" * 2001):
            self.assertEqual(self.send(self.ca, bad).status_code, 400)
        self.assertEqual(self.ca.post(self.url, {}, format="json").status_code, 400)
        self.assertFalse(Message.objects.exists())

    def test_outsiders_cannot_read_or_write(self):
        spy = self.client_for(self.player("spy@uiu.ac.bd"))
        self.send(self.ca, "private")
        self.assertEqual(spy.get(self.url).status_code, 404)
        self.assertEqual(self.send(spy, "hi").status_code, 404)
        self.assertEqual(spy.get(LIST).json(), [])

    def test_unmatch_locks_the_chat_for_both(self):
        self.ca.post(f"/api/matches/{self.match.pk}/unmatch/")
        for c in (self.ca, self.cb):
            self.assertEqual(c.get(self.url).status_code, 404)
            self.assertEqual(self.send(c, "still there?").status_code, 404)
        self.assertEqual(self.cb.get(LIST).json(), [])

    def test_block_stops_messages(self):
        Block.objects.create(blocker=self.b, blocked=self.a)  # created outside the service
        self.assertEqual(self.send(self.ca, "hey").status_code, 403)

    def test_conversations_sorted_by_latest_activity(self):
        c = self.player("c@uiu.ac.bd", name="Carol")
        m2 = mutual_match_pair(self, self.a, c)
        self.send(self.ca, "older")
        self.client_for(self.a).post(f"{LIST}{m2.conversation.pk}/messages/", {"body": "newest"}, format="json")
        self.assertEqual([x["profile"]["display_name"] for x in self.ca.get(LIST).json()], ["Carol", "Bob"])


def mutual_match_pair(case, a, b):
    from matching.models import Match, Swipe

    Swipe.objects.create(actor=a, target=b, action="like")
    Swipe.objects.create(actor=b, target=a, action="like")
    from chat.models import Conversation

    m, _ = Match.create_for(a, b)
    Conversation.objects.get_or_create(match=m)
    return m
