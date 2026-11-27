from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST

from economy.auth import ensure_child_accessible, parent_account_required
from economy.forms import RealShopSettingsForm, VirtualOfferForm
from economy.models import LotteryTicket, LotteryTicketStatus, RequestStatus, RewardRequest, VirtualOffer
from economy.services import reverse_ledger_entry
from economy.shops import fulfill_real_reward, shop_day, shop_family


@transaction.atomic
def _update_shops(request):
    action = request.POST.get("action")
    if action == "settings":
        family = shop_family()
        old_currency = family.reward_currency
        form = RealShopSettingsForm(request.POST, instance=family)
        if not form.is_valid():
            messages.error(request, next(iter(form.errors.values()))[0])
        elif family.reward_currency != old_currency and _currency_is_locked(family):
            messages.error(request, _("Resolve financial commitments before changing currency."))
        else:
            if form.changed_data:
                form.save(commit=False).save(update_fields=form.changed_data)
            messages.success(request, _("Reward shop settings saved."))
    elif action == "offer":
        offer = get_object_or_404(VirtualOffer, pk=request.POST.get("offer_id"))
        form = VirtualOfferForm(request.POST, instance=offer)
        if form.is_valid():
            form.save()
            messages.success(request, _("Cosmetic offer saved."))
        else:
            messages.error(request, next(iter(form.errors.values()))[0])
    else:
        raise Http404
    return redirect("parent_reward_shops")


def _currency_is_locked(family):
    day = shop_day(family, timezone.now())
    incompatible = RewardRequest.objects.filter(
        financial_cost_cents__gt=0,
    ).exclude(financial_currency=family.reward_currency)
    return (
        incompatible.filter(status=RequestStatus.PENDING).exists()
        or incompatible.filter(
            effective_on__range=(day.replace(day=1), day), refunded_at__isnull=True,
        ).exists()
    )


@parent_account_required
@require_http_methods(["GET", "HEAD", "POST"])
def parent_reward_shops(request):
    if request.method == "POST":
        return _update_shops(request)
    orders = RewardRequest.objects.filter(status=RequestStatus.APPROVED).select_related(
        "child", "debit",
    ).order_by("-decided_at", "-pk")
    return render(request, "economy/reward_shops.html", {
        "shop_settings": RealShopSettingsForm(instance=shop_family()),
        "offers": VirtualOffer.objects.select_related("unlock").order_by("category", "unlock__name"),
        "orders": Paginator(orders, 30).get_page(request.GET.get("page")),
        "tickets_for_review": LotteryTicket.objects.filter(status=LotteryTicketStatus.REVIEW).select_related("child")[:30],
    })


@parent_account_required
@require_POST
def parent_reward_delivery(request, order_id, action):
    order = get_object_or_404(RewardRequest.objects.select_related("child", "debit"), pk=order_id)
    ensure_child_accessible(request, order.child)
    try:
        if action == "deliver":
            fulfill_real_reward(order, request.user)
            messages.success(request, _("Reward delivery recorded."))
        elif action == "refund" and request.user.is_staff and order.debit:
            reverse_ledger_entry(entry=order.debit, actor=request.user, reason=request.POST.get("reason", ""))
            messages.success(request, _("Redemption refunded."))
        else:
            raise Http404
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    return redirect("parent_reward_shops")
