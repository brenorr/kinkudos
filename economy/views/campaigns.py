import hashlib
import json

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from economy import campaigns, guardians
from economy.auth import (
    accessible_children_qs,
    child_required,
    get_accessible_child_or_404,
    parent_account_required,
)
from economy.campaign_forms import (
    CatalogMissionForm,
    ChapterFormSet,
    EditionForm,
    LinkMissionForm,
    LinkStoryForm,
    StartCampaignForm,
)
from economy.guardian_forms import StartStoryForm
from economy.models import (
    OPEN_STORY_STATUSES,
    AdventureRegion,
    Campaign,
    CampaignActivity,
    CampaignActivityKind,
    CampaignRequirement,
    CampaignRun,
    CampaignRunStatus,
)
from economy.push import notify_assigned_tasks
from economy.services import assign_tasks


@parent_account_required
@never_cache
@require_safe
def parent_campaigns(request):
    return render(request, "economy/campaign_catalog.html", {
        "children": accessible_children_qs(request), "editions": campaigns.latest_editions(),
    })


def _chapter_initial(edition):
    if edition is None:
        return []
    return [{
        "region": chapter.region_id,
        "title": chapter.display_title,
        "opening": chapter.display_opening,
        "npc": chapter.display_npc,
        "dialogue": chapter.display_dialogue,
        "reward": chapter.reward_id,
        "mission_count": sum(requirement.kind == CampaignActivityKind.MISSION for requirement in chapter.requirements.all()),
        "story_count": sum(requirement.kind == CampaignActivityKind.STORY for requirement in chapter.requirements.all()),
    } for chapter in edition.chapters.prefetch_related("requirements")]


@parent_account_required
@never_cache
@require_http_methods(["GET", "HEAD", "POST"])
def parent_campaign_editor(request, campaign_id=None):
    campaign = get_object_or_404(Campaign, pk=campaign_id) if campaign_id is not None else None
    latest = campaign.editions.first() if campaign else None
    data = request.POST if request.method == "POST" else None
    definition = EditionForm(data, initial={
        "title": latest.display_title, "description": latest.display_description,
    } if latest else {})
    chapters = ChapterFormSet(data, prefix="chapter", initial=_chapter_initial(latest))
    if request.method == "POST" and definition.is_valid() and chapters.is_valid():
        fields = ChapterFormSet.form.base_fields
        selected = [
            {field: form.cleaned_data[field] for field in fields}
            for form in chapters.ordered_forms
        ]
        campaigns.publish_edition(campaign=campaign, details=definition.cleaned_data, chapters=selected)
        messages.success(request, _("Campaign edition published."))
        return redirect("parent_campaigns")
    return render(request, "economy/campaign_editor.html", {
        "definition": definition, "chapters": chapters, "latest": latest,
    })


def _run_cards(child, *, parent):
    cards = []
    today = timezone.localdate()
    open_story = child.story_sessions.filter(status__in=OPEN_STORY_STATUSES).first() if parent else None
    for run in child.campaign_runs.select_related("edition").prefetch_related(
        "activities__mission", "activities__story__narrator__guardian_profile", "completions", "edition__chapters__requirements",
        "edition__chapters__region", "edition__chapters__reward",
    ):
        completed = {entry.chapter_id: entry for entry in run.completions.all()}
        activities = {activity.requirement_id: activity for activity in run.activities.all()}
        current = None
        chapters = []
        edition_chapters = list(run.edition.chapters.all())
        cards.append({"run": run, "chapters": chapters, "done": len(completed), "total": len(edition_chapters)})
        for chapter in edition_chapters:
            completion = completed.get(chapter.pk)
            is_current = current is None and completion is None
            if is_current:
                current = chapter
            if completion is None and not is_current:
                continue
            steps = []
            chapters.append({"chapter": chapter, "completion": completion, "current": is_current, "steps": steps})
            counts = {kind: 0 for kind in CampaignActivityKind.values}
            for requirement in chapter.requirements.all():
                counts[requirement.kind] += 1
                activity = activities.get(requirement.pk)
                step = {
                    "requirement": requirement, "activity": activity, "number": counts[requirement.kind],
                    "replaceable": activity and campaigns.replaceable(activity),
                    "complete": activity and campaigns.activity_complete(activity),
                    "available": activity and (not activity.mission_id or activity.mission.local_date <= today),
                }
                if parent and is_current and (activity is None or step["replaceable"]):
                    prefix = f"step_{requirement.pk}_%s"
                    if requirement.kind == CampaignActivityKind.MISSION:
                        step["link_form"] = LinkMissionForm(child=child, auto_id=prefix)
                        step["create_form"] = CatalogMissionForm(auto_id=f"create_{prefix}")
                    else:
                        step["link_form"] = LinkStoryForm(child=child, auto_id=prefix)
                        step["open_story"] = open_story
                        if open_story is None:
                            step["create_form"] = StartStoryForm(auto_id=f"create_{prefix}")
                steps.append(step)
    return cards


@parent_account_required
@never_cache
@require_http_methods(["GET", "HEAD", "POST"])
def parent_campaign_child(request, child_id):
    child = get_accessible_child_or_404(request, child_id)
    form = StartCampaignForm(request.POST if request.method == "POST" else None, child=child)
    if form.is_bound and form.is_valid():
        try:
            run = campaigns.start_run(child=child, edition=form.cleaned_data["edition"])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect(f"{reverse('parent_campaign_child', args=[child.pk])}#run-{run.pk}")
    return render(request, "economy/child_campaigns.html", {
        "child": child, "parent_view": True, "cards": _run_cards(child, parent=True), "start_form": form,
    })


def _change_run(request, child, run_id, *, parent):
    action = request.POST.get("action")
    if action not in {"pause", "resume", "continue"}:
        raise Http404
    try:
        run = campaigns.change_run(run_id=run_id, child=child, action=action)
    except CampaignRun.DoesNotExist as exc:
        raise Http404 from exc
    if parent:
        return redirect(f"{reverse('parent_campaign_child', args=[child.pk])}#run-{run.pk}")
    if action == "continue" and run.status == CampaignRunStatus.ACTIVE:
        chapter = campaigns.current_chapter(run)
        if chapter:
            for activity in run.activities.filter(requirement__chapter=chapter).select_related("mission", "story").order_by("requirement_id"):
                if campaigns.activity_complete(activity):
                    continue
                if activity.story_id:
                    return redirect("child_story", session_id=activity.story_id)
                if activity.mission.local_date <= timezone.localdate() and not campaigns.replaceable(activity):
                    return redirect("child_mission", occurrence_id=activity.mission_id)
    return redirect(f"{reverse('child_adventures')}#run-{run.pk}")


@parent_account_required
@require_POST
def parent_campaign_run_action(request, child_id, run_id):
    return _change_run(request, get_accessible_child_or_404(request, child_id), run_id, parent=True)


@child_required
@require_POST
def child_campaign_run_action(request, run_id):
    return _change_run(request, request.child, run_id, parent=False)


@parent_account_required
@require_POST
def parent_campaign_link(request, child_id, run_id, requirement_id):
    child = get_accessible_child_or_404(request, child_id)
    run = get_object_or_404(child.campaign_runs, pk=run_id)
    requirement = get_object_or_404(CampaignRequirement, pk=requirement_id, chapter__edition=run.edition)
    mission = requirement.kind == CampaignActivityKind.MISSION
    action = request.POST.get("action")
    try:
        with transaction.atomic():
            if action == "link":
                try:
                    source_id = int(request.POST.get("mission" if mission else "story") or "0")
                except ValueError as exc:
                    raise ValidationError(_("Choose an activity for the chapter.")) from exc
            elif action == "create":
                form = CatalogMissionForm(request.POST) if mission else StartStoryForm(request.POST)
                if not form.is_valid():
                    raise ValidationError(next(iter(form.errors.values()))[0])
                if mission:
                    batch = assign_tasks(child=child, actor=request.user, tasks=[form.cleaned_data["task"]])
                    source_id = batch.items.get().occurrence_id
                    notify_assigned_tasks(batch)
                else:
                    story = guardians.start_story(child=child, narrator=request.user, **form.cleaned_data)
                    source_id = story.pk
            else:
                raise Http404
            campaigns.link_activity(child=child, run_id=run.pk, requirement_id=requirement.pk, source_id=source_id)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    return redirect(f"{reverse('parent_campaign_child', args=[child.pk])}#run-{run.pk}")


@child_required
@never_cache
@require_safe
def child_adventures(request):
    child = request.child
    state = _adventure_signature(child)
    cards = _run_cards(child, parent=False)
    regions = {region.pk: {"region": region, "chapters": [], "open": region.code == "village"}
               for region in AdventureRegion.objects.all()}
    for card in cards:
        for row in card["chapters"]:
            location = regions[row["chapter"].region_id]
            location["open"] = True
            location["chapters"].append({"row": row, "run": card["run"]})
    return render(request, "economy/child_campaigns.html", {
        "child": child, "cards": cards, "regions": list(regions.values()),
        "state_signature": state,
    })


def _adventure_signature(child):
    progress = list(child.campaign_runs.order_by("pk", "completions__pk").values_list(
        "pk", "status", "completions__pk",
    ))
    activities = list(CampaignActivity.objects.filter(run__child=child).order_by("pk").values_list(
        "pk", "mission_id", "mission__status", "story_id", "story__version",
    ))
    state = json.dumps([timezone.localdate().isoformat(), progress, activities])
    return hashlib.sha256(state.encode("utf-8")).hexdigest()


@child_required
@never_cache
@require_safe
def child_adventure_state(request):
    return JsonResponse({"signature": _adventure_signature(request.child)})
