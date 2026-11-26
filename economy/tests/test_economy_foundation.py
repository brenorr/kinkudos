from datetime import date, datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase
from django.urls import reverse

from economy.models import (
    ChildProfile,
    FamilySettings,
    LedgerEntry,
    LedgerKind,
    OccurrenceCredit,
    Task,
    TaskClaim,
)
from economy.services import (
    approve_task_claim,
    credit_occurrence,
    post_ledger_entry,
    reverse_ledger_entry,
    transfer_points,
)


class EconomyFoundationTests(TestCase):
    def setUp(self):
        self.child = ChildProfile.objects.create(name="Exploradora", balance=-12, min_balance=-30)
        self.admin = get_user_model().objects.create_user("guardian", is_staff=True)
        self.family = FamilySettings.load()
        self.family.timezone_name = "America/Sao_Paulo"
        self.family.daily_coin_limit = 10
        self.family.coin_balance_limit = 500
        self.family.daily_penalty_limit = 4
        self.family.save()

    def credit(self, key, *, xp=8, coins=7):
        return credit_occurrence(
            child=self.child, occurrence_key=key, xp=xp, coins=coins, description="Missão",
            actor=self.admin,
        )

    def test_credit_is_idempotent_and_xp_is_independent_of_the_coin_limit(self):
        result = self.credit("routine:1")
        self.assertEqual(self.credit("routine:1").pk, result.pk)
        with self.assertRaises(ValidationError):
            self.credit("routine:1", xp=99)
        reduced = self.credit("routine:2")
        exhausted = self.credit("routine:3")
        self.assertEqual(self.credit("routine:3").pk, exhausted.pk)
        self.assertEqual((result.coin_entry.delta, reduced.coin_entry.delta, exhausted.coin_entry.delta), (7, 3, 0))
        self.assertEqual(reduced.coin_entry.requested_delta, 7)
        self.assertEqual(reduced.coin_entry.limit_reason, "daily_earnings")
        self.assertEqual(result.coin_entry.previous_balance, -12)
        self.assertEqual(list(OccurrenceCredit.objects.values_list("xp", flat=True)), [8, 8, 8])
        self.child.refresh_from_db()
        self.assertEqual(self.child.balance, -2)

    def test_credit_rolls_back_with_the_callers_transaction(self):
        with self.assertRaises(RuntimeError), transaction.atomic():
            self.credit("routine:rollback")
            raise RuntimeError("abort")
        self.child.refresh_from_db()
        self.assertEqual(self.child.balance, -12)
        self.assertFalse(LedgerEntry.objects.exists())
        self.assertFalse(OccurrenceCredit.objects.exists())

    def test_daily_budget_uses_sao_paulo_and_ceiling_does_not_remove_balance(self):
        for hour, minute, day in [(2, 59, 9), (3, 0, 10)]:
            with patch("django.utils.timezone.now", return_value=datetime(2026, 8, 10, hour, minute, tzinfo=timezone.utc)):
                entry = self.credit(f"routine:{day}", coins=10).coin_entry
            self.assertEqual(entry.delta, 10)
            self.assertEqual(entry.local_date, date(2026, 8, day))

        ChildProfile.objects.filter(pk=self.child.pk).update(balance=530)
        result = self.credit("routine:above-ceiling")
        self.assertEqual(result.coin_entry.delta, 0)
        self.assertEqual(result.coin_entry.balance_after, 530)
        self.assertEqual(result.xp, 8)

    def test_pending_legacy_claim_keeps_promised_payment_and_has_no_xp(self):
        task = Task.objects.create(title="Organizar mochila", reward=20)
        claim = TaskClaim.objects.create(
            child=self.child, task=task, task_title=task.title, reward_snapshot=20,
            use_coin_limits=False,
        )
        entry = approve_task_claim(claim=claim, actor=self.admin)
        self.assertEqual(entry.delta, 20)
        self.assertFalse(self.child.occurrence_credits.exists())

    def test_penalty_limit_reversal_and_floor(self):
        debit = post_ledger_entry(
            child=self.child, delta=-4, kind=LedgerKind.PENALTY, description="Consequence",
            actor=self.admin,
        )
        reversal = reverse_ledger_entry(entry=debit, actor=self.admin, reason="Reviewed")
        self.assertEqual(reversal.delta, 4)
        self.assertEqual(reversal.reverses_id, debit.pk)
        self.assertEqual(reverse_ledger_entry(entry=debit, actor=self.admin, reason="Retry"), reversal)
        with self.assertRaises(ValidationError):
            post_ledger_entry(child=self.child, delta=-1, kind=LedgerKind.PENALTY, description="Consequence")
        with self.assertRaises(ValidationError):
            post_ledger_entry(child=self.child, delta=-19, kind=LedgerKind.ADJUSTMENT, description="Below floor")
        self.child.refresh_from_db()
        self.assertEqual(self.child.balance, -12)
        self.assertEqual(self.child.ledger_entries.count(), 2)

    def test_gift_replay_and_reversal_keep_both_sides_consistent(self):
        self.child.balance = 10
        self.child.save(update_fields=["balance"])
        other = ChildProfile.objects.create(name="Companion", balance=498, min_balance=0)
        with self.assertRaises(ValidationError):
            transfer_points(sender=self.child, recipient=other, amount=10)
        other.balance = 490
        other.save(update_fields=["balance"])
        token = uuid4()
        gift = transfer_points(sender=self.child, recipient=other, amount=10, operation_token=token)
        replay = transfer_points(sender=self.child, recipient=other, amount=10, operation_token=token)
        self.assertEqual(replay.pk, gift.pk)

        original = other.ledger_entries.get(kind=LedgerKind.GIFT)
        reverse_ledger_entry(entry=original, actor=self.admin, reason="Gift reversed")
        self.child.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual((self.child.balance, other.balance), (10, 490))
        self.assertEqual(LedgerEntry.objects.filter(kind=LedgerKind.REFUND).count(), 2)

    def test_admin_can_reverse_from_history_and_adjustment_form_is_idempotent(self):
        self.client.force_login(self.admin)
        adjust_url = reverse("parent_adjust_balance", args=[self.child.pk])
        payload = {"amount": 5, "description": "Correction", "operation_token": str(uuid4())}
        self.assertEqual(self.client.post(adjust_url, payload).status_code, 302)
        self.assertEqual(self.client.post(adjust_url, payload).status_code, 302)
        debit = self.child.ledger_entries.get()
        self.assertEqual(debit.delta, 5)
        reverse_url = reverse("parent_reverse_ledger_entry", args=[debit.pk])
        parent = get_user_model().objects.create_user("other-parent")
        self.client.force_login(parent)
        self.assertEqual(self.client.post(reverse_url, {"reason": "Correction"}).status_code, 404)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("parent_dashboard")), reverse_url)
        self.assertEqual(self.client.post(reverse_url, {"reason": "Correction"}).status_code, 302)
        self.child.refresh_from_db()
        self.assertEqual(self.child.balance, -12)
