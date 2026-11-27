from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import (
    AssignedTask,
    AssignedTaskStatus,
    ChildProfile,
    MissionOccurrence,
    MissionStatus,
    OccurrenceCredit,
    RequestStatus,
    TaskClaim,
    TaskCompletion,
)

EDITABLE = (MissionStatus.AVAILABLE, MissionStatus.IN_PROGRESS)
WAITING = (MissionStatus.PENDING_APPROVAL, MissionStatus.IN_REVIEW)


def _lock_child(child):
    return ChildProfile.objects.select_for_update().get(pk=child.pk, is_active=True)


def legacy_pending(child, task, day):
    claim = TaskClaim.objects.filter(
        child=child, task=task, occurrence__isnull=True,
        status__in=(RequestStatus.PENDING, RequestStatus.NEEDS_CHANGES),
    ).first()
    assignment = AssignedTask.objects.filter(
        batch__child=child, batch__assigned_on=day, task=task, occurrence__isnull=True,
        status=AssignedTaskStatus.PENDING,
    ).first()
    return claim, assignment


def resolve_catalog_occurrence(child, task, *, day=None, extra_token=None):
    """Resolve the default slot while the caller holds the child's write transaction."""
    day = day or timezone.localdate()
    claim, assignment = legacy_pending(child, task, day)
    if claim or assignment:
        raise ValidationError(_("This task already has a pending record. Continue it from the dashboard."))
    slots = MissionOccurrence.objects.filter(child=child, task=task, local_date=day)
    default_slot = slots.filter(is_default_slot=True).first()
    completed_in_legacy = TaskCompletion.objects.filter(child=child, task=task, completed_on=day)
    if extra_token:
        existing = MissionOccurrence.objects.filter(child=child, create_token=extra_token).first()
        if existing:
            if existing.task_id != task.pk:
                raise ValidationError(_("This mission request has already been used."))
            return existing
        if default_slot is None and not completed_in_legacy.exists():
            raise ValidationError(_("Create the first occurrence before adding another."))
    elif default_slot:
        return default_slot
    elif completed_in_legacy.exists():
        raise ValidationError(_("This task has already been credited today."))
    return MissionOccurrence.objects.create(
        child=child,
        task=task,
        local_date=day,
        title=task.title,
        instructions=task.instructions,
        checklist=task.checklist,
        practice_skills=task.practice_skills,
        routine=task.routine,
        mission_kind=task.mission_kind,
        xp=task.xp_reward,
        coins=task.reward,
        requires_approval=task.requires_approval,
        suggested_at=task.suggested_at,
        deadline=timezone.make_aware(datetime.combine(day, task.due_at)) if task.due_at else None,
        timer_minutes=task.timer_minutes,
        prerequisite=task.prerequisite,
        is_default_slot=extra_token is None,
        create_token=extra_token,
    )


def check_availability(occurrence):
    if occurrence.local_date != timezone.localdate() or (
        occurrence.deadline is not None and timezone.now() > occurrence.deadline
    ):
        raise ValidationError(_("This mission is outside its scheduled time."))
    if occurrence.prerequisite_id and not (
        MissionOccurrence.objects.filter(
            child=occurrence.child, task=occurrence.prerequisite, status=MissionStatus.COMPLETED,
        ).exists()
        or TaskCompletion.objects.filter(
            child=occurrence.child, task=occurrence.prerequisite,
        ).exists()
    ):
        raise ValidationError(_("Complete the prerequisite mission first."))


def transition(occurrence, allowed, target, **updates):
    if not MissionOccurrence.objects.filter(pk=occurrence.pk, status__in=allowed).update(
        status=target, **updates
    ):
        raise ValidationError(_("This mission is no longer awaiting that action."))
    occurrence.status = target


def finalize(occurrence, *, allowed, actor=None, bonus=0):
    from .campaigns import activity_finished
    from .services import credit_occurrence, ensure_task_completion

    completed_at = timezone.now()
    transition(occurrence, allowed, MissionStatus.COMPLETED, completed_at=completed_at)
    result = credit_occurrence(
        child=occurrence.child, occurrence_key=occurrence.credit_key, xp=occurrence.xp,
        coins=occurrence.coins + bonus, description=occurrence.title, actor=actor, source_id=occurrence.pk,
        skills=occurrence.practice_skills,
    )
    AssignedTask.objects.filter(occurrence=occurrence).update(
        status=AssignedTaskStatus.COMPLETED, completed_at=completed_at, ledger_entry=result.coin_entry,
    )
    ensure_task_completion(
        child=occurrence.child, task=occurrence.task, completed_on=occurrence.local_date,
    )
    activity_finished("mission", occurrence.pk)
    return result


def completed_credit(occurrence):
    return OccurrenceCredit.objects.select_related("coin_entry").get(occurrence_key=occurrence.credit_key)


@transaction.atomic
def submit_mission(*, child, occurrence, note="", bonus=0):
    _lock_child(child)
    occurrence = MissionOccurrence.objects.select_related("task", "prerequisite").get(
        pk=occurrence.pk, child=child,
    )
    existing = TaskClaim.objects.filter(occurrence=occurrence).first()
    if existing and occurrence.status in (MissionStatus.PENDING_APPROVAL, MissionStatus.COMPLETED):
        existing.was_replayed = True
        return existing
    if occurrence.status not in EDITABLE:
        raise ValidationError(_("This mission is no longer awaiting that action."))
    check_availability(occurrence)
    if len(occurrence.checked_steps) != len(occurrence.checklist):
        raise ValidationError(_("Finish the checklist before submitting this mission."))
    claim = TaskClaim.objects.create(
        child=child, task=occurrence.task, occurrence=occurrence, task_title=occurrence.title,
        reward_snapshot=occurrence.coins, photo_bonus_snapshot=bonus, child_note=note.strip()[:200],
    )
    if occurrence.requires_approval:
        transition(occurrence, EDITABLE, MissionStatus.PENDING_APPROVAL)
        AssignedTask.objects.filter(occurrence=occurrence).update(status=AssignedTaskStatus.SUBMITTED)
    else:
        finalize(occurrence, allowed=EDITABLE, bonus=bonus)
        claim.status = RequestStatus.APPROVED
        claim.decided_at = timezone.now()
        claim.save(update_fields=["status", "decided_at"])
    return claim


@transaction.atomic
def record_catalog_completion(*, child, task, actor, day=None):
    _lock_child(child)
    day = day or timezone.localdate()
    legacy_claim, legacy_assignment = legacy_pending(child, task, day)
    if legacy_claim or legacy_assignment:
        raise ValidationError(_("This task already has a pending record. Continue it from the dashboard."))
    if (
        TaskCompletion.objects.filter(child=child, task=task, completed_on=day).exists()
        and not MissionOccurrence.objects.filter(
            child=child, task=task, local_date=day, is_default_slot=True, status__in=(*EDITABLE, *WAITING),
        ).exists()
    ):
        return None
    occurrence = resolve_catalog_occurrence(child, task, day=day)
    if occurrence.status == MissionStatus.COMPLETED:
        return None
    if occurrence.status in WAITING:
        from .services import approve_task_claim

        if occurrence.status != MissionStatus.PENDING_APPROVAL:
            raise ValidationError(_("This mission is waiting for the child to send corrections."))
        from .push import notify_task_decision

        entry = approve_task_claim(claim=occurrence.claim, actor=actor)
        occurrence.claim.refresh_from_db()
        notify_task_decision(occurrence.claim, approved=True, credited=entry.delta)
        return entry
    check_availability(occurrence)
    if occurrence.checklist:
        MissionOccurrence.objects.filter(pk=occurrence.pk).update(
            checked_steps=list(range(len(occurrence.checklist)))
        )
    return finalize(occurrence, allowed=EDITABLE, actor=actor).coin_entry


@transaction.atomic
def update_child_mission(*, child, occurrence, action, checked_steps=()):
    _lock_child(child)
    occurrence = MissionOccurrence.objects.get(pk=occurrence.pk, child=child)
    if action == "skip":
        transition(occurrence, EDITABLE, MissionStatus.SKIPPED)
        AssignedTask.objects.filter(occurrence=occurrence).update(status=AssignedTaskStatus.CANCELLED)
        return True
    if occurrence.status != MissionStatus.IN_REVIEW:
        check_availability(occurrence)
    if any(index < 0 or index >= len(occurrence.checklist) for index in checked_steps):
        raise ValidationError(_("Choose valid checklist steps."))
    target = MissionStatus.IN_REVIEW if occurrence.status == MissionStatus.IN_REVIEW else MissionStatus.IN_PROGRESS
    transition(occurrence, (*EDITABLE, MissionStatus.IN_REVIEW), target, checked_steps=sorted(set(checked_steps)))
    return True
