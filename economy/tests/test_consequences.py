from datetime import datetime, timedelta, timezone as utc
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from economy.consequences import (
    apply_episode_debit,
    complete_repair,
    propose_repair,
    record_episode,
    send_guardian_message,
)
from economy.models import (
    BehaviorCategory,
    CaregiverProfile,
    ChildProfile,
    ConsequenceEpisode,
    FamilySettings,
    GuardianMessage,
    LedgerKind,
    OccurrenceCredit,
    PenaltyTemplate,
)
from economy.services import credit_occurrence, reverse_ledger_entry


class ConsequenceTests(TestCase):
    def setUp(self):
        self.parent = get_user_model().objects.create_user("guardian", is_staff=True)
        self.child = ChildProfile.objects.create(name="Aventureira", balance=15, min_balance=0, theme_selected=True)
        self.other = ChildProfile.objects.create(name="Outra criança", theme_selected=True)
        self.family = FamilySettings.load()
        self.family.timezone_name = "America/Sao_Paulo"
        self.family.daily_penalty_limit = 5
        self.family.save()
        self.penalty = PenaltyTemplate.objects.create(title="Modelo", amount=-3)
        self.category = BehaviorCategory.objects.get(default_code="other")

    def episode(self, **kwargs):
        return record_episode(
            child=self.child, actor=self.parent, token=uuid4(), category=self.category,
            reason="Registro privado do responsável", **kwargs,
        )

    def debit(self, episode, *, reason="Decisão privada"):
        return apply_episode_debit(
            child=self.child, actor=self.parent, episode_id=episode.pk,
            penalty_ids=[self.penalty.pk], reason=reason,
        )

    def test_all_penalty_routes_share_one_episode_debit(self):
        episode = self.episode(warning=True)
        self.client.force_login(self.parent)
        common = {"reason": "Decisão privada", "episode_id": episode.pk}
        for route, args, extra in [
            ("parent_apply_penalty", [self.child.pk], {"penalty_id": self.penalty.pk}),
            ("parent_assign_child_penalty", [self.child.pk], {"penalty_ids": [self.penalty.pk]}),
            ("parent_assign_penalty", [self.penalty.pk], {"child_id": self.child.pk}),
        ]:
            response = self.client.post(reverse(route, args=args), {**common, **extra})
            self.assertEqual(response.status_code, 302)
        self.child.refresh_from_db()
        episode.refresh_from_db()
        self.assertEqual(self.child.balance, 12)
        self.assertEqual(episode.warning_by, self.parent)
        self.assertEqual(episode.debit.actor, self.parent)
        self.assertEqual(self.child.ledger_entries.get().source_id, episode.pk)
        self.assertEqual(episode.template_snapshot[0]["delta"], -3)
        with self.assertRaisesMessage(ValidationError, "already has a coin decision"):
            self.debit(episode, reason="Outras condições")
        self.penalty.amount = -4
        self.penalty.save(update_fields=["amount"])
        with self.assertRaisesMessage(ValidationError, "already has a coin decision"):
            self.debit(episode)

    def test_repeated_creation_token_returns_the_original_debit(self):
        data = {
            "child": self.child, "actor": self.parent, "category": self.category,
            "token": uuid4(), "penalty_ids": [self.penalty.pk], "reason": "Same episode",
        }
        result = apply_episode_debit(**data)
        self.assertEqual(apply_episode_debit(**data).pk, result.pk)
        with self.assertRaises(ValidationError):
            apply_episode_debit(**{**data, "reason": "Different decision"})
        self.assertEqual(ConsequenceEpisode.objects.count(), 1)
        self.assertEqual(self.child.ledger_entries.count(), 1)

    def test_reason_is_required_on_all_paths(self):
        self.client.force_login(self.parent)
        for route, args, extra in [
            ("parent_apply_penalty", [self.child.pk], {"penalty_id": self.penalty.pk}),
            ("parent_assign_child_penalty", [self.child.pk], {"penalty_ids": [self.penalty.pk]}),
            ("parent_assign_penalty", [self.penalty.pk], {"child_id": self.child.pk}),
        ]:
            reply = self.client.post(reverse(route, args=args), {
                **extra, "operation_token": uuid4(), "reason": "   ",
            })
            self.assertEqual(reply.status_code, 302)
        self.assertFalse(ConsequenceEpisode.objects.exists())
        self.assertFalse(self.child.ledger_entries.exists())

    def test_debit_limits_and_reversal_keep_xp_and_use_local_day(self):
        credit = credit_occurrence(child=self.child, occurrence_key="consequences-test", xp=20, coins=0, description="Missão")
        first, second = self.episode(), self.episode()
        before = datetime(2026, 8, 10, 2, 59, tzinfo=utc.utc)
        after = before + timedelta(minutes=1)
        with patch("django.utils.timezone.now", return_value=before):
            debit = self.debit(first)
            with self.assertRaisesMessage(ValidationError, "2 coins"):
                self.debit(second)
            undo = reverse_ledger_entry(entry=debit, actor=self.parent, reason="Revisão")
            self.assertEqual(reverse_ledger_entry(entry=debit, actor=self.parent, reason="Revisão").pk, undo.pk)
            self.assertEqual(self.debit(first).pk, debit.pk)
            with self.assertRaisesMessage(ValidationError, "2 coins"):
                self.debit(second)
        with patch("django.utils.timezone.now", return_value=after):
            self.assertEqual(self.debit(second).local_date.day, 10)
        self.assertEqual(OccurrenceCredit.objects.get(), credit)
        self.assertEqual(credit.xp, 20)
        self.assertEqual(self.child.ledger_entries.filter(kind=LedgerKind.REFUND).count(), 1)

    def test_negative_floor_even_when_the_daily_limit_is_disabled(self):
        self.family.daily_penalty_limit = None
        self.family.save(update_fields=["daily_penalty_limit"])
        self.child.balance = -4
        self.child.min_balance = -5
        self.child.save(update_fields=["balance", "min_balance"])
        episode = self.episode()
        with self.assertRaisesMessage(ValidationError, "1 coins"):
            self.debit(episode)
        self.child.refresh_from_db()
        episode.refresh_from_db()
        self.assertEqual(self.child.balance, -4)
        self.assertIsNone(episode.debit_id)

    def test_warning_repair_and_encouragement_never_touch_the_ledger(self):
        self.client.force_login(self.parent)
        url = reverse("parent_child_consequences", args=[self.child.pk])
        self.assertContains(self.client.get(url), "Consequences and encouragement")
        self.client.post(url, {
            "action": "warning", "operation_token": uuid4(), "category": self.category.pk,
            "reason": "Relato reservado", "child_note": "Vamos combinar o próximo passo.",
        })
        episode = ConsequenceEpisode.objects.get()
        propose_repair(
            child=self.child, actor=self.parent, episode_id=episode.pk,
            text="Guardar junto", share_with_child=True,
        )
        self.client.post(url, {"action": "complete_repair", "episode_id": episode.pk})
        self.assertIsNotNone(complete_repair(child=self.child, actor=self.parent, episode_id=episode.pk).completed_at)
        message = {"action": "encouragement", "text": "Você pediu ajuda. Boa ideia!", "operation_token": uuid4()}
        self.client.post(url, message)
        self.client.post(url, message)
        self.assertEqual(GuardianMessage.objects.count(), 1)
        self.assertFalse(self.child.ledger_entries.exists())
        self.assertFalse(self.child.occurrence_credits.exists())
        self.client.logout()
        session = self.client.session
        session["child_id"] = self.child.pk
        session.save()
        dashboard = self.client.get(reverse("child_dashboard"))
        self.assertContains(dashboard, "Guardar junto")
        self.assertContains(dashboard, "Você pediu ajuda. Boa ideia!")
        self.assertNotContains(dashboard, "Relato reservado")

    def test_child_ledger_shows_debits_without_private_reasons(self):
        self.debit(self.episode())
        session = self.client.session
        session["child_id"] = self.child.pk
        session.save()
        dashboard = self.client.get(reverse("child_dashboard"))
        self.assertContains(dashboard, "Coin consequence")
        self.assertNotContains(dashboard, "Decisão privada")

    def test_caregiver_can_only_act_for_children_in_scope(self):
        guest = get_user_model().objects.create_user("guest")
        profile = CaregiverProfile.objects.create(
            user=guest, label="Guest", login_code="guest-code", pin_hash="!",
            access_until=timezone.localdate() + timedelta(days=1),
        )
        profile.children.add(self.child)
        record_episode(child=self.child, actor=guest, token=uuid4(), category=self.category, reason="Allowed")
        with self.assertRaises(ValidationError):
            record_episode(child=self.other, actor=guest, token=uuid4(), category=self.category, reason="Denied")
        with self.assertRaises(ValidationError):
            send_guardian_message(child=self.child, actor=guest, token=uuid4(), text="No scope for messages")

    def test_failed_debit_leaves_no_episode_or_history(self):
        with patch("economy.consequences.post_ledger_entry", side_effect=RuntimeError("abort")):
            with self.assertRaises(RuntimeError):
                apply_episode_debit(
                    child=self.child, actor=self.parent, category=self.category, token=uuid4(),
                    penalty_ids=[self.penalty.pk], reason="Mandatory justification",
                )
        self.assertFalse(ConsequenceEpisode.objects.exists())
        self.assertFalse(self.child.ledger_entries.exists())
