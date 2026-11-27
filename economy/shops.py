from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Max, Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import (
    ChildProfile,
    FamilySettings,
    LedgerEntry,
    LedgerKind,
    RequestStatus,
    Reward,
    RewardRequest,
    UnlockGrant,
    UnlockKind,
    VirtualOffer,
)


def shop_family():
    family = FamilySettings.load()
    family.refresh_from_db(fields=["real_shop_enabled", "reward_budget_cents", "reward_currency", "timezone_name"])
    return family


def shop_day(family, now):
    return timezone.localdate(now, timezone=ZoneInfo(family.timezone_name or settings.TIME_ZONE))


def check_real_policy(order, family, now, day):
    reward = order.reward
    if (
        not reward.is_active or reward.is_deleted
        or (reward.available_from and day < reward.available_from)
        or (reward.available_until and day > reward.available_until)
    ):
        raise ValidationError(_("This reward is unavailable for redemption."))
    if reward.stock == 0:
        raise ValidationError(_("This reward has no remaining stock."))

    committed = RewardRequest.objects.filter(
        child=order.child, reward=reward, effective_on__isnull=False,
    )
    for limit, start in (
        (reward.daily_limit, day),
        (reward.weekly_limit, day - timedelta(days=day.weekday())),
        (reward.monthly_limit, day.replace(day=1)),
    ):
        if limit is not None and committed.filter(effective_on__range=(start, day)).count() >= limit:
            raise ValidationError(_("The redemption limit for this reward has been reached."))
    if reward.interval_hours:
        latest = committed.aggregate(latest=Max("decided_at"))["latest"]
        if latest and now - latest < timedelta(hours=reward.interval_hours):
            raise ValidationError(_("Wait before redeeming this reward again."))

    if order.financial_cost_cents:
        if order.financial_currency != family.reward_currency:
            raise ValidationError(_("This request uses a different family currency."))
        if family.reward_budget_cents is not None:
            used = RewardRequest.objects.filter(
                effective_on__range=(day.replace(day=1), day),
                financial_currency=family.reward_currency, refunded_at__isnull=True,
            ).aggregate(total=Sum("financial_cost_cents", default=0))["total"]
            if used + order.financial_cost_cents > family.reward_budget_cents:
                raise ValidationError(_("This redemption exceeds the monthly family budget."))


@transaction.atomic
def fulfill_real_reward(order, actor):
    locked = RewardRequest.objects.select_for_update().get(pk=order.pk)
    if locked.status != RequestStatus.APPROVED or locked.refunded_at:
        raise ValidationError(_("Only an approved redemption can be delivered."))
    if locked.fulfilled_at is None:
        locked.fulfilled_at = timezone.now()
        locked.fulfilled_by = actor
        locked.save(update_fields=["fulfilled_at", "fulfilled_by"])
    return locked


def release_real_reward(entry):
    """Called inside the transaction that creates the compensating ledger entry."""
    order = RewardRequest.objects.select_for_update().filter(debit=entry).first()
    if order is None:
        # Pre-upgrade approvals did not manage stock or financial commitments.
        order = RewardRequest.objects.select_for_update().filter(pk=entry.source_id).first()
        if (
            order is None or entry.source_type not in ("", "reward_request")
            or order.child_id != entry.child_id or order.status != RequestStatus.APPROVED
            or -entry.delta != order.cost_snapshot
        ):
            return
    if order.fulfilled_at:
        raise ValidationError(_("Delivered redemptions require a separate administrative decision."))
    if order.stock_consumed:
        Reward.objects.filter(pk=order.reward_id, stock__isnull=False).update(stock=F("stock") + 1)
    order.refunded_at = timezone.now()
    order.save(update_fields=["refunded_at"])


@transaction.atomic
def purchase_cosmetic(*, child, offer, token, confirmed_price):
    from .services import assigned_tasks_block_rewards, post_ledger_entry

    child = ChildProfile.objects.select_for_update().get(pk=child.pk, is_active=True)
    if token is None:
        raise ValidationError(_("Reload the shop before making a purchase."))
    key = f"cosmetic:{child.pk}:{token}"
    previous = LedgerEntry.objects.filter(operation_key=key).first()
    if previous:
        if previous.source_id != offer.pk or previous.requested_delta != -confirmed_price:
            raise ValidationError(_("This purchase request was already used with different details."))
        return previous.cosmetic_grant

    offer = VirtualOffer.objects.select_related("unlock").get(pk=offer.pk)
    item = offer.unlock
    if not offer.is_active or not item.is_active or item.earned_by_level or item.kind != UnlockKind.COSMETIC:
        raise ValidationError(_("This cosmetic is not available to buy."))
    if confirmed_price != offer.cost:
        raise ValidationError(_("The price changed. Review the offer again."))
    if UnlockGrant.objects.filter(child=child, unlock=item).exists():
        raise ValidationError(_("You already own this item."))
    if assigned_tasks_block_rewards(child):
        raise ValidationError(_("Complete the assigned tasks before requesting a new reward."))
    if child.balance < offer.cost:
        raise ValidationError(_("You do not have enough coins for this cosmetic."))
    entry = post_ledger_entry(
        child=child, delta=-offer.cost, kind=LedgerKind.COSMETIC_PURCHASE, description=str(item),
        source_id=offer.pk, source_type="virtual_offer", operation_key=key, enforce_limit=True,
    )
    return UnlockGrant.objects.create(child=child, unlock=item, purchase_entry=entry)
