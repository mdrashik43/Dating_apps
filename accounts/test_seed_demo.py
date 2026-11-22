from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from accounts.models import User
from mystery_game.models import Clue


class SeedDemoTests(TestCase):
    @override_settings(DEBUG=False)
    def test_refuses_outside_debug(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo_students", stdout=StringIO())
        self.assertFalse(User.objects.exists())

    @override_settings(DEBUG=True)
    def test_creates_playable_students_idempotently(self):
        call_command("seed_demo_students", stdout=StringIO())
        call_command("seed_demo_students", stdout=StringIO())
        self.assertEqual(User.objects.count(), 5)
        self.assertTrue(all(u.is_university_verified and u.profile.consent_mystery_game for u in User.objects.all()))
        self.assertEqual(Clue.objects.count(), 15)
