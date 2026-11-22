from django.test import override_settings

from accounts.models import University
from accounts.testing import APITestCase, make_user
from matching.models import Match, Swipe
from moderation.models import Block
from mystery_game.models import Clue, GameSession
from notifications.models import Notification
from profiles.models import Profile

S = "/api/game/sessions/"
LEAK_KEYS = {"email", "date_of_birth", "user", "user_id", "mystery_user", "owner", "password"}


class StartTests(APITestCase):
    def test_auth_and_gates(self):
        self.assertEqual(self.client_for().post(S).status_code, 401)
        unverified = make_user("u@uiu.ac.bd", university=self.uni)
        self.assertEqual(self.client_for(unverified).post(S).status_code, 403)
        no_consent = self.player("nc@uiu.ac.bd", consent=False)
        r = self.client_for(no_consent).post(S)
        self.assertEqual(r.status_code, 403)

    def test_no_candidates_is_404(self):
        me = self.player("me@uiu.ac.bd")
        self.assertEqual(self.client_for(me).post(S).status_code, 404)

    def test_start_hides_identity_and_unlocks_one_clue(self):
        me, them = self.player("me@uiu.ac.bd"), self.player("t@uiu.ac.bd", name="Zorblax")
        r = self.client_for(me).post(S)
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertEqual((body["clues_unlocked"], body["clues_total"], body["status"]), (1, 3, "active"))
        self.assertEqual(len(body["clues"]), 1)
        self.assertNotIn("profile", body)
        text = r.content.decode()
        for secret in ("Zorblax", them.email, str(them.pk), "t@uiu"):
            self.assertNotIn(secret, text)
        self.assertFalse(LEAK_KEYS & set(body))

    def test_start_is_idempotent_while_a_session_is_open(self):
        me, _ = self.player("me@uiu.ac.bd"), self.player("t@uiu.ac.bd")
        c = self.client_for(me)
        a, b = c.post(S), c.post(S)
        self.assertEqual((a.status_code, b.status_code), (201, 200))
        self.assertEqual(a.json()["id"], b.json()["id"])
        self.assertEqual(c.get(S + "current/").json()["id"], a.json()["id"])

    def test_current_is_404_without_a_game(self):
        self.assertEqual(self.client_for(self.player("me@uiu.ac.bd")).get(S + "current/").status_code, 404)

    def test_pool_excludes_everyone_who_should_be_excluded(self):
        me = self.player("me@uiu.ac.bd")
        good = self.player("good@uiu.ac.bd")
        self.player("unverified@uiu.ac.bd", verified=False)
        self.player("noconsent@uiu.ac.bd", consent=False)
        self.player("hidden@uiu.ac.bd", discoverable=False)
        self.player("noclues@uiu.ac.bd", clues=0)
        inactive = self.player("inactive@uiu.ac.bd")
        inactive.is_active = False
        inactive.save()
        blocked = self.player("blocked@uiu.ac.bd")
        Block.objects.create(blocker=me, blocked=blocked)
        blocker = self.player("blocker@uiu.ac.bd")
        Block.objects.create(blocker=blocker, blocked=me)
        swiped = self.player("swiped@uiu.ac.bd")
        Swipe.objects.create(actor=me, target=swiped, action="pass")
        seen = self.player("seen@uiu.ac.bd")
        GameSession.objects.create(player=me, mystery_user=seen, status="abandoned")
        other_uni = University.objects.create(name="Other", email_domain="other.edu")
        foreign = self.player("foreign@uiu.ac.bd")
        foreign.university = other_uni
        foreign.save()
        for _ in range(5):
            GameSession.objects.filter(player=me, status="active").delete()
            r = self.client_for(me).post(S)
            self.assertEqual(r.status_code, 201)
            self.assertEqual(GameSession.objects.get(pk=r.json()["id"]).mystery_user, good)

    @override_settings(GAME_DAILY_SESSION_LIMIT=1)
    def test_daily_session_limit(self):
        me = self.player("me@uiu.ac.bd")
        self.player("a@uiu.ac.bd"), self.player("b@uiu.ac.bd")
        c = self.client_for(me)
        sid = c.post(S).json()["id"]
        c.post(f"{S}{sid}/abandon/")
        self.assertEqual(c.post(S).status_code, 429)


class GuessAndRevealTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.me = self.player("me@uiu.ac.bd")
        self.them = self.player("t@uiu.ac.bd", name="Zorblax", clues=3)
        self.c = self.client_for(self.me)
        self.sid = self.c.post(S).json()["id"]
        self.url = f"{S}{self.sid}/"

    def test_each_guess_unlocks_the_next_clue_up_to_the_total(self):
        r = self.c.post(self.url + "guess/", {"text": "  CSE?  "}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["clues_unlocked"], 2)
        self.assertEqual(r.json()["guesses"][0]["text"], "CSE?")
        for _ in range(4):
            r = self.c.post(self.url + "guess/", {"text": "again"}, format="json")
        self.assertEqual(r.json()["clues_unlocked"], 3)

    def test_guess_validation_and_limit(self):
        for bad in ({"text": "  "}, {}, {"text": "x" * 201}):
            self.assertEqual(self.c.post(self.url + "guess/", bad, format="json").status_code, 400)
        for _ in range(10):
            self.assertEqual(self.c.post(self.url + "guess/", {"text": "g"}, format="json").status_code, 200)
        self.assertEqual(self.c.post(self.url + "guess/", {"text": "g"}, format="json").status_code, 400)

    def test_other_players_cannot_touch_my_session(self):
        spy = self.client_for(self.player("spy@uiu.ac.bd"))
        for method, path in (("get", ""), ("post", "guess/"), ("post", "reveal/"), ("post", "decision/"), ("post", "abandon/")):
            r = getattr(spy, method)(self.url + path, {"text": "x", "action": "like"}, format="json") if method == "post" else spy.get(self.url)
            self.assertEqual(r.status_code, 404, path)
        self.assertEqual(GameSession.objects.get(pk=self.sid).status, "active")

    def test_reveal_returns_only_the_public_profile(self):
        r = self.c.post(self.url + "reveal/")
        self.assertEqual(r.status_code, 200)
        p = r.json()["profile"]
        self.assertEqual(p["display_name"], "Zorblax")
        self.assertEqual(set(p), {"display_name", "age", "gender", "looking_for", "bio", "department", "batch"})
        for secret in (self.them.email, str(self.them.pk), "2001-01-15"):
            self.assertNotIn(secret, r.content.decode())

    def test_guess_after_reveal_is_rejected(self):
        self.c.post(self.url + "reveal/")
        self.assertEqual(self.c.post(self.url + "guess/", {"text": "late"}, format="json").status_code, 400)

    def test_reveal_refused_if_student_withdrew_consent(self):
        Profile.objects.filter(user=self.them).update(consent_mystery_game=False)
        r = self.c.post(self.url + "reveal/")
        self.assertEqual(r.status_code, 409)
        self.assertNotIn("Zorblax", r.content.decode())
        self.assertEqual(GameSession.objects.get(pk=self.sid).status, "abandoned")

    def test_reveal_refused_if_student_blocked_me(self):
        Block.objects.create(blocker=self.them, blocked=self.me)
        self.assertEqual(self.c.post(self.url + "reveal/").status_code, 409)

    def test_profile_visible_only_between_reveal_and_decision(self):
        self.assertNotIn("profile", self.c.get(self.url).json())
        self.c.post(self.url + "reveal/")
        self.assertIn("profile", self.c.get(self.url).json())
        self.c.post(self.url + "decision/", {"action": "pass"}, format="json")
        after = self.c.get(self.url)
        self.assertEqual(after.json()["status"], "decided")
        self.assertNotIn("profile", after.json())
        self.assertNotIn("Zorblax", after.content.decode())

    def test_clue_edits_by_owner_are_reflected_and_inactive_clues_hidden(self):
        Clue.objects.filter(owner=self.them, position=0).update(is_active=False)
        body = self.c.get(self.url).json()
        self.assertEqual(body["clues_total"], 2)
        self.assertEqual(body["clues"][0]["text"], "clue number 1")


class DecisionTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.a, self.b = self.player("a@uiu.ac.bd", name="Alice"), self.player("b@uiu.ac.bd", name="Bob")

    def play(self, user, action):
        c = self.client_for(user)
        sid = c.post(S).json()["id"]
        c.post(f"{S}{sid}/reveal/")
        return sid, c.post(f"{S}{sid}/decision/", {"action": action}, format="json")

    def test_cannot_decide_before_reveal(self):
        c = self.client_for(self.a)
        sid = c.post(S).json()["id"]
        self.assertEqual(c.post(f"{S}{sid}/decision/", {"action": "like"}, format="json").status_code, 400)
        self.assertFalse(Swipe.objects.exists())

    def test_invalid_action_rejected(self):
        c = self.client_for(self.a)
        sid = c.post(S).json()["id"]
        c.post(f"{S}{sid}/reveal/")
        self.assertEqual(c.post(f"{S}{sid}/decision/", {"action": "superlike"}, format="json").status_code, 400)

    def test_pass_never_matches_and_cannot_be_repeated(self):
        sid, r = self.play(self.a, "pass")
        self.assertEqual(r.json(), {"matched": False})
        self.assertEqual(Swipe.objects.get().action, "pass")
        again = self.client_for(self.a).post(f"{S}{sid}/decision/", {"action": "like"}, format="json")
        self.assertEqual(again.status_code, 400)

    def test_one_sided_like_creates_no_match_and_tells_nobody(self):
        _, r = self.play(self.a, "like")
        self.assertEqual(r.json(), {"matched": False})
        self.assertFalse(Match.objects.exists())
        self.assertFalse(Notification.objects.filter(user=self.b).exists())

    def test_mutual_like_creates_match_conversation_and_notifications(self):
        _, first = self.play(self.a, "like")
        _, second = self.play(self.b, "like")
        self.assertFalse(first.json()["matched"])
        self.assertTrue(second.json()["matched"])
        m = Match.objects.get()
        self.assertTrue(m.is_active)
        self.assertEqual(m.conversation.pk, second.json()["conversation_id"])
        for u, other in ((self.a, "Bob"), (self.b, "Alice")):
            n = Notification.objects.get(user=u, kind="match")
            self.assertIn(other, n.body)

    def test_like_then_pass_does_not_match(self):
        self.play(self.a, "like")
        _, r = self.play(self.b, "pass")
        self.assertFalse(r.json()["matched"])
        self.assertFalse(Match.objects.exists())

    def test_decided_student_never_returns_to_the_pool(self):
        self.play(self.a, "pass")
        self.assertEqual(self.client_for(self.a).post(S).status_code, 404)

    def test_new_session_possible_after_decision(self):
        c3 = self.player("c@uiu.ac.bd")
        self.play(self.a, "pass")
        first = GameSession.objects.get(player=self.a, status="decided").mystery_user
        r = self.client_for(self.a).post(S)
        self.assertEqual(r.status_code, 201)
        second = GameSession.objects.get(pk=r.json()["id"]).mystery_user
        self.assertNotEqual(first, second)
        self.assertIn(second, (self.b, c3))
