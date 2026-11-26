from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from economy.auth import get_accessible_child_or_404, parent_required
from economy.consequences import complete_repair, propose_repair, record_episode, send_guardian_message
from economy.forms import BehaviorCategoryForm, GuardianMessageForm, RecordEpisodeForm, RepairActionForm
from economy.models import BehaviorCategory, PenaltyTemplate


def _validated(form):
    if not form.is_valid():
        raise ValidationError(next(iter(form.errors.values()))[0])
    return form.cleaned_data


@parent_required
@require_http_methods(["GET", "HEAD", "POST"])
def parent_child_consequences(request, child_id):
    child = get_accessible_child_or_404(request, child_id)
    is_caregiver = request.caregiver is not None
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action in {"record", "warning"}:
                data = _validated(RecordEpisodeForm(request.POST))
                record_episode(
                    child=child, actor=request.user, token=data["operation_token"],
                    category=data["category"], reason=data["reason"], child_note=data["child_note"],
                    warning=action == "warning",
                )
                messages.success(request, _("Episode recorded."))
            elif action == "repair":
                data = _validated(RepairActionForm(request.POST))
                propose_repair(child=child, actor=request.user, **data)
                messages.success(request, _("Repair action recorded."))
            elif action == "complete_repair":
                complete_repair(
                    child=child, actor=request.user, episode_id=request.POST.get("episode_id", ""),
                )
                messages.success(request, _("Repair completed."))
            elif action == "encouragement" and not is_caregiver:
                data = _validated(GuardianMessageForm(request.POST))
                send_guardian_message(child=child, actor=request.user, text=data["text"], token=data["operation_token"])
                messages.success(request, _("Encouragement sent."))
            elif action == "category" and not is_caregiver:
                category_id = request.POST.get("category_id")
                category = get_object_or_404(BehaviorCategory, pk=category_id) if category_id else None
                form = BehaviorCategoryForm(request.POST, instance=category)
                _validated(form)
                form.save()
                messages.success(request, _("Category saved."))
            else:
                raise Http404
        except (ValidationError, ValueError) as exc:
            messages.error(request, exc.messages[0] if isinstance(exc, ValidationError) else _("Check the entered data."))
        return redirect("parent_child_consequences", child_id=child.pk)

    episodes = child.consequence_episodes.select_related(
        "created_by", "debit__actor", "debit__reversal__actor", "repair__proposed_by", "repair__completed_by",
        "warning_by",
    )
    recent_episodes = episodes[:20]
    requested_episode = request.GET.get("episode")
    if requested_episode:
        try:
            recent_episodes = [get_object_or_404(episodes, pk=int(requested_episode))]
        except ValueError as exc:
            raise Http404 from exc
    return render(request, "economy/consequences.html", {
        "child": child,
        "is_caregiver": is_caregiver,
        "categories": BehaviorCategory.objects.filter(is_active=True),
        "category_items": BehaviorCategory.objects.all() if not is_caregiver else (),
        "episodes": recent_episodes,
        "penalties": PenaltyTemplate.objects.filter(is_active=True, is_deleted=False),
        "encouragements": child.guardian_messages.select_related("author")[:5] if not is_caregiver else (),
    })
