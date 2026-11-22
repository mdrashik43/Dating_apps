from accounts.testing import APITestCase
from matching.models import Match
from moderation.models import Block, Report
from mystery_game.models import GameSession
from mystery_game.tests_helpers import mutual_match

S = "/api/game/sessions/"
BLOCK, REPORT = "/api/moderation/block/", "/api/moderation/report/"


class ModerationTests(APITestCase):
    def setUp(self):
        super().setUp()
        self.me, self.them = self.player("me@uiu.ac.bd"), self.player("t@uiu.ac.bd")
        self.c = self.client_for(self.me)

    def session(self):
        return self.c.post(S).json()["id"]

    def test_auth_required(self):
        self.assertEqual(self.client_for().post(BLOCK, {"session_id": 1}, format="json").status_code, 401)
        self.assertEqual(self.client_for().post(REPORT, {"session_id": 1, "reason": "fake"}, format="json").status_code, 401)

    def test_block_during_game_ends_session_and_removes_both_from_each_others_pool(self):
        sid = self.session()
        self.assertEqual(self.c.post(BLOCK, {"session_id": sid}, format="json").status_code, 201)
        self.assertTrue(Block.objects.filter(blocker=self.me, blocked=self.them).exists())
        self.assertEqual(GameSession.objects.get(pk=sid).status, "abandoned")
        self.assertEqual(self.c.post(S).status_code, 404)
        self.assertEqual(self.client_for(self.them).post(S).status_code, 404)

    def test_block_by_match_deactivates_the_match(self):
        match = mutual_match(self, self.me, self.them)
        self.assertEqual(self.c.post(BLOCK, {"match_id": match.pk}, format="json").status_code, 201)
        self.assertFalse(Match.objects.get().is_active)
        self.assertEqual(self.c.get("/api/matches/").json(), [])

    def test_report_records_the_right_people(self):
        sid = self.session()
        r = self.c.post(REPORT, {"session_id": sid, "reason": "harassment", "details": "rude clue"}, format="json")
        self.assertEqual(r.status_code, 201)
        rep = Report.objects.get()
        self.assertEqual((rep.reporter, rep.reported_user, rep.status), (self.me, self.them, "open"))

    def test_report_validation(self):
        sid = self.session()
        bad = (
            {"session_id": sid, "reason": "nonsense"},
            {"session_id": sid},
            {"reason": "fake"},
            {"session_id": sid, "match_id": 1, "reason": "fake"},
        )
        for body in bad:
            self.assertEqual(self.c.post(REPORT, body, format="json").status_code, 400, body)
        self.assertFalse(Report.objects.exists())

    def test_cannot_target_other_peoples_sessions_or_matches(self):
        sid = self.session()
        stranger = self.client_for(self.player("x@uiu.ac.bd"))
        self.assertEqual(stranger.post(BLOCK, {"session_id": sid}, format="json").status_code, 404)
        self.assertEqual(stranger.post(REPORT, {"session_id": sid, "reason": "fake"}, format="json").status_code, 404)
        self.assertEqual(stranger.post(BLOCK, {"match_id": 999}, format="json").status_code, 404)
        self.assertFalse(Block.objects.exists() or Report.objects.exists())
