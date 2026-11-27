from uuid import uuid4

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db import transaction
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from economy import guardians
from economy.auth import (
    accessible_children_qs,
    child_required,
    get_accessible_child_or_404,
    parent_account_required,
)
from economy.consequences import send_guardian_message
from economy.forms import GuardianTextForm
from economy.guardian_forms import (
    AdvanceStoryForm,
    FinishStoryForm,
    GuardianMissionForm,
    GuardianProfileForm,
    StartStoryForm,
    StoryChoiceForm,
    StoryVersionForm,
    WallMessageForm,
)
from economy.images import ImageProcessingError, process_avatar
from economy.models import (
    OPEN_STORY_STATUSES,
    GuardianProfile,
    MissionHelpRequest,
    MissionKind,
    MissionStatus,
    StorySession,
    StoryStatus,
)
from economy.progression import CHARACTER_STYLES
from economy.push import notify_assigned_tasks
from economy.services import assign_tasks
from economy.views.character import equipped_character
from economy.views.child import _child_state_signature


def _errors(request, form):
    messages.error(request, next(iter(form.errors.values()))[0])


@parent_account_required
@never_cache
@require_safe
def parent_guardians(request):
    children = accessible_children_qs(request)
    return render(request, "economy/guardians.html", {
        "children": children,
        "profile_form": GuardianProfileForm(instance=getattr(request.user, "guardian_profile", None)),
        "stories": StorySession.objects.filter(narrator=request.user, child__in=children).select_related("child")[:20],
    })


@parent_account_required
@never_cache
@require_POST
def parent_guardian_profile(request):
    profile = getattr(request.user, "guardian_profile", None)
    form = GuardianProfileForm(request.POST, request.FILES, instance=profile)
    if not form.is_valid():
        _errors(request, form)
        return redirect("parent_guardians")

    upload = form.cleaned_data["avatar"]
    try:
        content = process_avatar(upload) if upload else None
    except ImageProcessingError as exc:
        messages.error(request, str(exc))
        return redirect("parent_guardians")

    with transaction.atomic():
        profile, _created = GuardianProfile.objects.select_for_update().get_or_create(user=request.user)
        profile.display_name = form.cleaned_data["display_name"]
        profile.title = form.cleaned_data["title"]
        fields = ["display_name", "title"]
        if content is not None:
            old_name = profile.avatar.name
            storage = profile.avatar.storage
            profile.avatar.save(f"{uuid4().hex}.webp", ContentFile(content), save=False)
            if old_name:
                transaction.on_commit(lambda: storage.delete(old_name), robust=True)
            fields.append("avatar")
        profile.save(update_fields=fields)
    messages.success(request, _("Guardian profile saved."))
    return redirect("parent_guardians")


@child_required
@never_cache
@require_safe
def child_guardian_avatar(request, profile_id):
    profile = get_object_or_404(GuardianProfile.objects.exclude(avatar=""), pk=profile_id)
    child = request.child
    if not (
        child.guardian_messages.filter(author=profile.user_id).exists()
        or child.story_sessions.filter(narrator=profile.user_id).exists()
        or child.missions.filter(
            assignment__batch__assigned_by=profile.user_id, local_date__lte=timezone.localdate(),
            mission_kind__in=(MissionKind.SPECIAL, MissionKind.COOPERATIVE),
        ).exists()
    ):
        raise Http404
    try:
        stream = profile.avatar.open("rb")
    except FileNotFoundError as exc:
        raise Http404 from exc
    response = FileResponse(stream, content_type="image/webp")
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _wall_page(child, request):
    rows = child.guardian_messages.select_related("author__guardian_profile", "mission")
    return Paginator(rows, 15).get_page(request.GET.get("page"))


def _cooperative_missions(child):
    return child.missions.filter(
        mission_kind=MissionKind.COOPERATIVE, status=MissionStatus.COMPLETED,
    ).order_by("-completed_at", "-pk")[:20]


@child_required
@never_cache
@require_safe
def child_guardian_wall(request):
    return render(request, "economy/guardian_wall.html", {
        "child": request.child, "wall": _wall_page(request.child, request), "child_view": True,
        "state_signature": _child_state_signature(request.child),
        "cooperative_missions": _cooperative_missions(request.child),
        "finished_stories": request.child.story_sessions.filter(status=StoryStatus.FINISHED)[:20],
    })


@parent_account_required
@never_cache
@require_http_methods(["GET", "HEAD", "POST"])
def parent_guardian_child(request, child_id):
    child = get_accessible_child_or_404(request, child_id)
    message_form = WallMessageForm(
        child=child, auto_id="wall_%s", initial={"operation_token": uuid4(), "kind": "praise"},
    )
    mission_form = GuardianMissionForm(auto_id="mission_%s", initial={"token": uuid4(), "day": timezone.localdate()})
    story_form = StartStoryForm(auto_id="story_%s")
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "message":
                message_form = WallMessageForm(request.POST, child=child, auto_id="wall_%s")
                if message_form.is_valid():
                    data = message_form.cleaned_data
                    send_guardian_message(
                        child=child, actor=request.user, text=data["text"], token=data["operation_token"],
                        kind=data["kind"], mission=data["mission"],
                    )
                    messages.success(request, _("Message sent."))
                    return redirect("parent_guardian_child", child_id=child.pk)
            elif action == "mission":
                mission_form = GuardianMissionForm(request.POST, auto_id="mission_%s")
                if mission_form.is_valid():
                    data = mission_form.cleaned_data
                    surprise = data["kind"] == "surprise"
                    batch = assign_tasks(
                        child=child, actor=request.user, tasks=[], custom_title=data["title"],
                        custom_note=data["instructions"], custom_points=data["coins"], custom_xp=data["xp"],
                        custom_requires_approval=data["requires_approval"], custom_surprise=surprise,
                        custom_mission_kind=MissionKind.SPECIAL if surprise else data["kind"],
                        day=data["day"], operation_token=data["token"],
                    )
                    if data["day"] == timezone.localdate() and not getattr(batch, "was_replayed", False):
                        notify_assigned_tasks(batch)
                    messages.success(request, _("Mission sent."))
                    return redirect("parent_guardian_child", child_id=child.pk)
            elif action == "story":
                story_form = StartStoryForm(request.POST, auto_id="story_%s")
                if story_form.is_valid():
                    story = guardians.start_story(child=child, narrator=request.user, **story_form.cleaned_data)
                    return redirect("parent_story", session_id=story.pk)
            else:
                raise Http404
        except ValidationError as exc:
            messages.error(request, exc.messages[0])

    open_story = child.story_sessions.filter(status__in=OPEN_STORY_STATUSES).first()
    return render(request, "economy/guardian_wall.html", {
        "child": child, "wall": _wall_page(child, request), "open_story": open_story,
        "message_form": message_form, "mission_form": mission_form, "story_form": story_form,
        "help_requests": guardians.available_help(
            MissionHelpRequest.objects.filter(occurrence__child=child).select_related("occurrence"),
        ),
        "cooperative_missions": _cooperative_missions(child),
    })


@parent_account_required
@require_POST
def parent_answer_mission_help(request, child_id, help_id):
    child = get_accessible_child_or_404(request, child_id)
    form = GuardianTextForm(request.POST)
    if form.is_valid():
        try:
            guardians.answer_help(request_id=help_id, child=child, actor=request.user, text=form.cleaned_data["text"])
        except MissionHelpRequest.DoesNotExist as exc:
            raise Http404 from exc
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
        else:
            messages.success(request, _("Reply sent."))
    else:
        _errors(request, form)
    return redirect("parent_guardian_child", child_id=child.pk)


@parent_account_required
@require_POST
def parent_record_cooperative_participants(request, child_id, occurrence_id):
    child = get_accessible_child_or_404(request, child_id)
    mission = get_object_or_404(
        child.missions, pk=occurrence_id, mission_kind=MissionKind.COOPERATIVE, status=MissionStatus.COMPLETED,
    )
    participants = request.POST.get("participants", "").strip()
    if len(participants) > 240:
        messages.error(request, _("Use up to 240 characters."))
    else:
        mission.cooperative_participants = participants
        mission.save(update_fields=["cooperative_participants"])
        messages.success(request, _("Participants saved."))
    return redirect("parent_guardian_child", child_id=child.pk)


def _story_page(request, *, session_id, child_view):
    actor_scope = {"child": request.child} if child_view else {"narrator": request.user, "child__is_active": True}
    story = get_object_or_404(
        StorySession.objects.select_related("child", "narrator__guardian_profile"), pk=session_id, **actor_scope,
    )
    advance = AdvanceStoryForm()
    finish = FinishStoryForm()
    choice = StoryChoiceForm()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "choice":
            choice = StoryChoiceForm(request.POST)
            form = choice
        elif not child_view and action == "advance":
            advance = AdvanceStoryForm(request.POST)
            form = advance
        elif not child_view and action == "finish":
            finish = FinishStoryForm(request.POST)
            form = finish
        elif not child_view and action in {"pause", "resume"}:
            form = None
        else:
            raise Http404
        version = StoryVersionForm(request.POST)
        if not version.is_valid():
            _errors(request, version)
        elif form is None or form.is_valid():
            try:
                guardians.change_story(
                    session_id=session_id, actor_scope=actor_scope, action=action,
                    version=version.cleaned_data["version"], data=form.cleaned_data if form else {},
                )
            except StorySession.DoesNotExist as exc:
                raise Http404 from exc
            except ValidationError as exc:
                messages.error(request, exc.messages[0])
                story.refresh_from_db()
            else:
                return redirect("child_story" if child_view else "parent_story", session_id=session_id)

    return render(request, "economy/story.html", {
        **equipped_character(story.child),
        "story": story, "child": story.child, "child_view": child_view, "advance_form": advance,
        "finish_form": finish, "choice_form": choice, "character_style": CHARACTER_STYLES.get(story.child.character_class),
        "narrator_name": guardians.guardian_name(story.narrator),
        "state_signature": _child_state_signature(story.child) if child_view else story.version,
    })


@parent_account_required
@never_cache
@require_http_methods(["GET", "HEAD", "POST"])
def parent_story(request, session_id):
    return _story_page(request, session_id=session_id, child_view=False)


@parent_account_required
@never_cache
@require_safe
def parent_story_state(request, session_id):
    story = get_object_or_404(
        StorySession.objects.only("version"), pk=session_id, narrator=request.user, child__is_active=True,
    )
    return JsonResponse({"signature": str(story.version)})


@child_required
@never_cache
@require_http_methods(["GET", "HEAD", "POST"])
def child_story(request, session_id):
    return _story_page(request, session_id=session_id, child_view=True)
