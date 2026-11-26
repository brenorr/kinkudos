from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from economy.models import (
    ChildProfile,
    FamilySettings,
    LevelAdvance,
    LevelUnlock,
    OccurrenceCredit,
    PracticeSkill,
    Task,
)
from economy.progression import calculate_progress, practiced_skills, reconcile_unlocks, set_curve_factor
from economy.services import credit_occurrence, reverse_ledger_entry, submit_task


class ProgressionTests(TestCase):
    def setUp(self):
        self.child = ChildProfile.objects.create(name="Aventureira", theme_selected=True)
        self.parent = get_user_model().objects.create_user("guardiao", is_staff=True)

    def credit(self, key, xp, coins=0, skills=()):
        return credit_occurrence(
            child=self.child, occurrence_key=key, xp=xp, coins=coins,
            description="Missão", actor=self.parent, skills=skills,
        )

    def test_curve_matches_roadmap_at_boundaries_and_high_levels(self):
        for level, total in [(1, 0), (2, 100), (3, 300), (5, 1000), (10, 4500), (20, 19000)]:
            with self.subTest(level=level):
                self.assertEqual(calculate_progress(total, 100).level, level)
                self.assertEqual(calculate_progress(total + 1, 100).level, level)
                if total:
                    self.assertEqual(calculate_progress(total - 1, 100).level, level - 1)
        self.assertEqual(calculate_progress(140, 100).remaining_xp, 160)
        high_level = 10**12
        high_threshold = high_level * (high_level - 1) // 2
        self.assertEqual(calculate_progress(high_threshold, 1).level, high_level)

    @patch("economy.push.notify_level_advance")
    def test_level_jump_grants_every_unlock_once_and_notifies_after_commit(self, notify):
        with self.captureOnCommitCallbacks(execute=True):
            award = self.credit("first", xp=1_000)
            self.assertEqual(self.credit("first", xp=1_000), award)
            notify.assert_not_called()
        event = LevelAdvance.objects.get(credit=award)
        self.assertEqual((event.previous_level, event.current_level), (1, 5))
        notify.assert_called_once_with(event.pk)
        self.assertEqual(set(event.grants.values_list("unlock__code", flat=True)), {"adventurer", "adventurer-cape"})
        self.assertEqual(self.child.unlock_grants.count(), 3)

    @patch("economy.push.notify_level_advance", side_effect=RuntimeError("Push unavailable"))
    def test_notification_failure_leaves_progress_awarded(self, notify):
        with self.assertLogs("django.test", level="ERROR"):
            with self.captureOnCommitCallbacks(execute=True):
                result = self.credit("no push", xp=300)
        notify.assert_called_once()
        self.assertEqual(result.level_advance.current_level, 3)
        self.assertTrue(self.child.unlock_grants.filter(unlock__code="adventurer").exists())

    def test_curve_cannot_promote_or_reduce_existing_profiles(self):
        set_curve_factor(120)
        self.credit("below current", xp=90)
        with self.assertRaises(ValidationError):
            set_curve_factor(80)
        self.assertEqual(FamilySettings.load().xp_curve_factor, 120)
        self.credit("advance", xp=30)
        with self.assertRaises(ValidationError):
            set_curve_factor(200)
        self.assertEqual(FamilySettings.load().xp_curve_factor, 120)

    def test_silent_reconciliation_archives_without_revoking_and_preserves_xp(self):
        unlock = LevelUnlock.objects.get(code="adventurer-cape")
        unlock.is_active = False
        unlock.save(update_fields=["is_active"])
        self.credit("legacy", xp=1_000)
        self.assertFalse(self.child.unlock_grants.filter(unlock=unlock).exists())
        self.client.force_login(self.parent)
        url = reverse("parent_set_unlock_active", args=[unlock.pk])
        self.client.post(url, {"active": "1"})
        self.client.post(url, {"active": "1"})
        self.client.post(url, {"active": "0"})
        reconcile_unlocks()
        call_command("reconcile_progression")
        self.assertEqual(self.child.unlock_grants.filter(unlock=unlock).count(), 1)
        self.assertEqual(OccurrenceCredit.objects.get().xp, 1_000)
        self.assertEqual(LevelAdvance.objects.count(), 1)

    def test_skill_snapshot_counts_completion_once_and_has_no_bonus(self):
        task = Task.objects.create(
            title="Preparar materiais", reward=4, xp_reward=0, requires_approval=False,
            practice_skills=[PracticeSkill.ORGANIZATION, PracticeSkill.LEARNING],
        )
        claim = submit_task(child=self.child, task=task)
        task.practice_skills = [PracticeSkill.CARE]
        task.save(update_fields=["practice_skills"])
        self.assertEqual(submit_task(child=self.child, task=task), claim)
        self.assertEqual(dict(practiced_skills(self.child)), {"Organization": 1, "Learning": 1})
        self.assertEqual(OccurrenceCredit.objects.get().xp, 0)
        self.child.refresh_from_db()
        self.assertEqual(self.child.balance, 4)

    def test_class_is_cosmetic_and_child_only_sees_own_unlocks(self):
        other = ChildProfile.objects.create(name="Outra")
        credit_occurrence(child=other, occurrence_key="sibling", xp=1_000, coins=0, description="Outra missão")
        session = self.client.session
        session["child_id"] = self.child.pk
        session.save()
        url = reverse("child_set_character_class")
        self.client.post(url, {"character_class": "mage"})
        self.child.refresh_from_db()
        self.assertEqual(self.child.character_class, "mage")
        self.assertFalse(self.child.occurrence_credits.exists())
        dashboard = self.client.get(reverse("child_dashboard"))
        self.assertContains(dashboard, "Mage")
        self.assertContains(dashboard, "Apprentice")
        self.assertNotContains(dashboard, "Adventurer cape")

    def test_reversing_coins_does_not_remove_progress_or_grants(self):
        credit = self.credit("award", xp=300, coins=10)
        reverse_ledger_entry(entry=credit.coin_entry, actor=self.parent, reason="Ajuste de moedas")
        self.child.refresh_from_db()
        self.assertEqual(self.child.balance, 0)
        self.assertEqual(self.child.occurrence_credits.get().xp, 300)
        self.assertTrue(self.child.unlock_grants.filter(unlock__code="adventurer").exists())
