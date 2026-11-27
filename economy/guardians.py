from uuid import NAMESPACE_URL, uuid5

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _

from economy import missions
from economy.consequences import send_guardian_message
from economy.models import (
    OPEN_STORY_STATUSES,
    GuardianMessageKind,
    MissionHelpRequest,
    MissionOccurrence,
    StoryMode,
    StorySession,
    StoryStatus,
)


def guardian_name(user):
    profile = getattr(user, "guardian_profile", None)
    return (profile and profile.display_name) or user.get_full_name().strip() or _("Guardian")


def available_help(queryset):
    return queryset.filter(
        answered_at__isnull=True, occurrence__status__in=(*missions.EDITABLE, *missions.WAITING),
    ).filter(
        Q(occurrence__status__in=missions.WAITING) | Q(occurrence__local_date=timezone.localdate()),
    )


@transaction.atomic
def ask_for_help(*, child, occurrence, reopen_after=None):
    mission = MissionOccurrence.objects.select_for_update().get(pk=occurrence.pk, child=child)
    if mission.status in missions.EDITABLE:
        missions.check_availability(mission)
    elif mission.status not in missions.WAITING:
        raise ValidationError(_("This mission is no longer accepting help requests."))
    latest = mission.help_requests.first()
    if latest and (latest.answered_at is None or latest.pk != reopen_after):
        return latest, False
    request = MissionHelpRequest.objects.create(occurrence=mission)
    MissionOccurrence.objects.filter(pk=mission.pk).update(help_requested_at=request.requested_at)
    return request, True


@transaction.atomic
def answer_help(*, request_id, child, actor, text):
    request = MissionHelpRequest.objects.select_for_update().select_related("occurrence").get(
        pk=request_id, occurrence__child=child,
    )
    if request.answered_at is None and not available_help(MissionHelpRequest.objects.filter(pk=request.pk)).exists():
        raise ValidationError(_("This mission is no longer accepting help requests."))
    response = send_guardian_message(
        child=child, actor=actor, text=text, token=uuid5(NAMESPACE_URL, f"kinkudos:help:{request.pk}"),
        kind=GuardianMessageKind.HELP, mission=request.occurrence,
    )
    if request.answered_at is None:
        request.answered_at = timezone.now()
        request.response = response
        request.save(update_fields=["answered_at", "response"])
    return response


@transaction.atomic
def start_story(*, child, narrator, mode, title="", passage="", choices=()):
    if StorySession.objects.filter(child=child, status__in=OPEN_STORY_STATUSES).exists():
        raise ValidationError(_("This child already has a session to resume."))
    scene_code = ""
    if mode == StoryMode.PREPARED:
        scene_code = "forest-bridge"
        title = _("The forest bridge")
        passage = _("A wooden bridge crosses a quiet stream. A fox keeps watch and asks where you are going.")
        choices = [_("Cross the bridge"), _("Look for another path"), _("Talk to the fox")]
    return StorySession.objects.create(
        child=child, narrator=narrator, mode=mode, scene_code=scene_code, title=title,
        opening=passage, passage=passage, choices=list(choices),
    )


@transaction.atomic
def change_story(*, session_id, actor_scope, action, version, data):
    session = StorySession.objects.select_for_update().get(pk=session_id, **actor_scope)
    if version != session.version:
        raise ValidationError(_("The scene has changed. Read the latest version and try again."))
    if session.status == StoryStatus.FINISHED:
        raise ValidationError(_("This session has ended."))
    if session.status == StoryStatus.PAUSED and action not in {"resume", "finish"}:
        raise ValidationError(_("Resume the session before continuing."))

    fields = ["version"]
    if action == "choice":
        choice = data["choice"]
        if session.choice_recorded:
            raise ValidationError(_("A choice was already recorded for this passage."))
        if "child" in actor_scope and choice not in session.choices:
            raise ValidationError(_("Choose an option shown in this scene."))
        session.last_choice = choice
        session.choice_recorded = True
        fields.extend(["last_choice", "choice_recorded"])
    elif action == "advance":
        session.passage = data["passage"]
        session.choices = data["choices"]
        session.choice_recorded = False
        fields.extend(["passage", "choices", "choice_recorded"])
    else:
        next_status = {"pause": StoryStatus.PAUSED, "resume": StoryStatus.ACTIVE, "finish": StoryStatus.FINISHED}
        if action == "resume" and session.status != StoryStatus.PAUSED:
            raise ValidationError(_("This session is already in progress."))
        session.status = next_status[action]
        fields.append("status")
        if action == "finish":
            session.summary = data["summary"]
            fields.append("summary")
            if data["praise"]:
                send_guardian_message(
                    child=session.child, actor=session.narrator, text=data["praise"],
                    token=uuid5(NAMESPACE_URL, f"kinkudos:story:{session.pk}:finish"), kind=GuardianMessageKind.PRAISE,
                )
    session.version += 1
    session.save(update_fields=fields)
    if action == "finish":
        from economy.campaigns import activity_finished

        activity_finished("story", session.pk)
    return session
