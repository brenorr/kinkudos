from datetime import date, datetime, timezone as utc
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from economy.lottery import purchase_lottery_ticket, send_due_lottery_reminders
from economy.models import (
    ChildProfile,
    FamilySettings,
    LedgerKind,
    RequestStatus,
    Reward,
    RewardRequest,
    VirtualOffer,
)
from economy.services import (
    approve_reward_request,
    reject_reward_request,
    reverse_ledger_entry,
    submit_reward_request,
)
from economy.shops import fulfill_real_reward, purchase_cosmetic


class RewardShopTests(TestCase):
    def setUp(self):
        self.parent = get_user_model().objects.create_user("guardian", is_staff=True)
        self.child = ChildProfile.objects.create(name="Aventureira", balance=100, min_balance=-20, theme_selected=True)
        self.other = ChildProfile.objects.create(name="Segunda criança", balance=100, theme_selected=True)
        self.family = FamilySettings.load()
        self.family.timezone_name = "America/Sao_Paulo"
        self.family.save()
        self.reward = Reward.objects.create(title="Escolher um filme", cost=25)
        self.offer = VirtualOffer.objects.get(unlock__code="star-hat")

    def _sign_in_child(self):
        self.client.logout()
        session = self.client.session
        session["child_id"] = self.child.pk
        session.save()

    def test_parent_can_turn_off_only_the_real_shop_and_resolve_pending(self):
        order = submit_reward_request(child=self.child, reward=self.reward)
        self.client.force_login(self.parent)
        settings_url = reverse("parent_reward_shops")
        self.client.post(settings_url, {"action": "settings", "reward_currency": "BRL"})
        self.assertFalse(FamilySettings.load().real_shop_enabled)
        self._sign_in_child()
        dashboard = self.client.get(reverse("child_dashboard"))
        self.assertContains(dashboard, "The real rewards shop is turned off.")
        self.assertContains(dashboard, reverse("child_cancel_reward", args=[order.pk]))
        self.assertContains(dashboard, reverse("child_purchase_cosmetic", args=[self.offer.pk]))
        self.assertNotContains(dashboard, reverse("child_request_reward", args=[self.reward.pk]))
        blocked = self.client.post(
            reverse("child_request_reward", args=[self.reward.pk]), {"operation_token": uuid4()},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(blocked.status_code, 400)
        self.assertEqual(RewardRequest.objects.count(), 1)
        entry = approve_reward_request(request=order, actor=self.parent)
        self.assertEqual(entry.delta, -25)
        self.client.force_login(self.parent)
        self.client.post(settings_url, {"action": "settings", "real_shop_enabled": "on", "reward_currency": "BRL"})
        self.assertTrue(FamilySettings.load().real_shop_enabled)
        self.assertTrue(Reward.objects.filter(pk=self.reward.pk, is_active=True).exists())

    def test_immediate_approval_reuses_order_token_and_debits_once(self):
        self.reward.approval_required = False
        self.reward.save()
        token = uuid4()
        first = submit_reward_request(child=self.child, reward=self.reward, operation_token=token, confirmed_price=25)
        retry = submit_reward_request(child=self.child, reward=self.reward, operation_token=token, confirmed_price=25)
        self.assertEqual(retry, first)
        self.assertEqual(first.status, RequestStatus.APPROVED)
        self.assertIsNotNone(first.debit_id)
        self.assertEqual(self.child.ledger_entries.get().delta, -25)

    def test_immediate_redemption_rejects_a_stale_price(self):
        self.reward.approval_required = False
        self.reward.save()
        with self.assertRaisesMessage(ValidationError, "price changed"):
            submit_reward_request(
                child=self.child, reward=self.reward, operation_token=uuid4(), confirmed_price=15,
            )
        self.assertFalse(self.child.ledger_entries.exists())

    def test_refusing_pending_does_not_move_balance(self):
        request = submit_reward_request(child=self.child, reward=self.reward)
        reject_reward_request(request=request, actor=self.parent, reason="Nesta semana não")
        self.assertFalse(self.child.ledger_entries.exists())

    def test_stock_only_committed_on_approval_and_refund_is_unique(self):
        self.reward.stock = 1
        self.reward.save()
        first = submit_reward_request(child=self.child, reward=self.reward)
        other = submit_reward_request(child=self.other, reward=self.reward)
        entry = approve_reward_request(request=first, actor=self.parent)
        with self.assertRaisesMessage(ValidationError, "remaining stock"):
            approve_reward_request(request=other, actor=self.parent)
        other.refresh_from_db()
        self.assertEqual(other.status, RequestStatus.PENDING)
        reversal = reverse_ledger_entry(entry=entry, actor=self.parent, reason="Cancelado")
        self.assertEqual(reversal, reverse_ledger_entry(entry=entry, actor=self.parent, reason="Repetição"))
        self.reward.refresh_from_db()
        self.assertEqual(self.reward.stock, 1)
        first.refresh_from_db()
        self.assertIsNotNone(first.refunded_at)
        approve_reward_request(request=other, actor=self.parent)

    def test_delivery_prevents_normal_refund(self):
        request = submit_reward_request(child=self.child, reward=self.reward)
        entry = approve_reward_request(request=request, actor=self.parent)
        fulfill_real_reward(request, self.parent)
        with self.assertRaisesMessage(ValidationError, "separate administrative"):
            reverse_ledger_entry(entry=entry, actor=self.parent, reason="Cancelado")
        self.assertEqual(self.child.ledger_entries.count(), 1)

    def test_budget_and_periods_use_the_family_date(self):
        self.family.reward_budget_cents = 100
        self.family.save()
        self.reward.financial_cost_cents = 75
        self.reward.monthly_limit = 1
        self.reward.save()
        with patch("django.utils.timezone.now", return_value=datetime(2026, 9, 1, 2, 59, tzinfo=utc.utc)):
            first = submit_reward_request(child=self.child, reward=self.reward)
            self.assertEqual(approve_reward_request(request=first, actor=self.parent).local_date, date(2026, 8, 31))
            with self.assertRaisesMessage(ValidationError, "monthly family budget"):
                submit_reward_request(child=self.other, reward=self.reward)
        with patch("django.utils.timezone.now", return_value=datetime(2026, 9, 1, 3, tzinfo=utc.utc)):
            second = submit_reward_request(child=self.child, reward=self.reward)
            self.assertEqual(approve_reward_request(request=second, actor=self.parent).local_date, date(2026, 9, 1))

    def test_refund_releases_financial_budget_but_not_the_child_daily_quota(self):
        self.family.reward_budget_cents = 100
        self.family.save()
        self.reward.financial_cost_cents = 75
        self.reward.daily_limit = 1
        self.reward.save()
        first = submit_reward_request(child=self.child, reward=self.reward)
        second = submit_reward_request(child=self.other, reward=self.reward)
        entry = approve_reward_request(request=first, actor=self.parent)
        with self.assertRaisesMessage(ValidationError, "monthly family budget"):
            approve_reward_request(request=second, actor=self.parent)
        reverse_ledger_entry(entry=entry, actor=self.parent, reason="Cancelado")
        approve_reward_request(request=second, actor=self.parent)
        with self.assertRaisesMessage(ValidationError, "redemption limit"):
            submit_reward_request(child=self.child, reward=self.reward)

    def test_daily_and_weekly_limits_reset_on_local_days(self):
        self.reward.daily_limit = 1
        self.reward.weekly_limit = 1
        self.reward.save()
        with patch("django.utils.timezone.now", return_value=datetime(2026, 8, 9, 3, tzinfo=utc.utc)):
            first = submit_reward_request(child=self.child, reward=self.reward)
            approve_reward_request(request=first, actor=self.parent)
            with self.assertRaisesMessage(ValidationError, "redemption limit"):
                submit_reward_request(child=self.child, reward=self.reward)
        with patch("django.utils.timezone.now", return_value=datetime(2026, 8, 10, 2, 59, tzinfo=utc.utc)):
            with self.assertRaisesMessage(ValidationError, "redemption limit"):
                submit_reward_request(child=self.child, reward=self.reward)
        with patch("django.utils.timezone.now", return_value=datetime(2026, 8, 10, 3, tzinfo=utc.utc)):
            second = submit_reward_request(child=self.child, reward=self.reward)
            self.assertEqual(approve_reward_request(request=second, actor=self.parent).local_date, date(2026, 8, 10))

    def test_legacy_pending_preserves_price_and_bypasses_enabled_shop_rules(self):
        self.reward.stock = 0
        self.reward.save(update_fields=["stock"])
        legacy = RewardRequest.objects.create(
            child=self.child, reward=self.reward, reward_title=self.reward.title,
            cost_snapshot=19, use_shop_rules=False,
        )
        self.assertEqual(approve_reward_request(request=legacy, actor=self.parent).delta, -19)
        self.reward.refresh_from_db()
        self.assertEqual(self.reward.stock, 0)

    def test_cosmetic_purchase_and_reconciliation_use_one_grant(self):
        call_command("reconcile_progression")
        self.assertFalse(self.child.unlock_grants.filter(unlock=self.offer.unlock).exists())
        token = uuid4()
        kwargs = {"child": self.child, "offer": self.offer, "confirmed_price": self.offer.cost}
        grant = purchase_cosmetic(**kwargs, token=token)
        self.assertEqual(purchase_cosmetic(**kwargs, token=token), grant)
        with self.assertRaisesMessage(ValidationError, "already own"):
            purchase_cosmetic(**kwargs, token=uuid4())
        self.assertEqual(self.child.unlock_grants.filter(unlock=self.offer.unlock).count(), 1)
        self.assertEqual(grant.purchase_entry.kind, LedgerKind.COSMETIC_PURCHASE)
        self.assertFalse(self.child.occurrence_credits.exists())
        self.offer.is_active = False
        self.offer.save(update_fields=["is_active"])
        self.assertEqual(purchase_cosmetic(**kwargs, token=token), grant)

    def test_cosmetic_rejects_stale_price_and_credit_balance(self):
        with self.assertRaisesMessage(ValidationError, "price changed"):
            purchase_cosmetic(child=self.child, offer=self.offer, confirmed_price=1, token=uuid4())
        self.child.balance = self.offer.cost - 1
        self.child.save(update_fields=["balance"])
        with self.assertRaisesMessage(ValidationError, "not have enough coins"):
            purchase_cosmetic(child=self.child, offer=self.offer, confirmed_price=self.offer.cost, token=uuid4())
        self.assertFalse(self.child.ledger_entries.exists())

    def test_retired_tickets_are_inaccessible_and_send_no_reminders(self):
        self._sign_in_child()
        response = self.client.post(reverse("child_purchase_lottery_ticket"))
        self.assertEqual(response.status_code, 404)
        with self.assertRaises(ValidationError):
            purchase_lottery_ticket(child=self.child)
        self.assertEqual(send_due_lottery_reminders(), [])
        dashboard = self.client.get(reverse("child_dashboard"))
        self.assertNotContains(dashboard, "data-lottery-card")
