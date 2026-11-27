from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import (
    BehaviorCategory,
    CaregiverProfile,
    ChildProfile,
    ConsequenceEpisode,
    GuardianMessage,
    GuardianMessageKind,
    LedgerKind,
    PenaltyTemplate,
    RepairAction,
)
from .services import post_ledger_entry


def _lock_child(child, actor, *, guardian_only=False):
    locked = ChildProfile.objects.select_for_update().filter(pk=child.pk, is_active=True).first()
    caregiver = CaregiverProfile.objects.filter(user=actor).first()
    if not locked or not actor.is_active or (
        caregiver and (guardian_only or not caregiver.has_access or caregiver.is_locked
                       or not caregiver.children.filter(pk=child.pk).exists())
    ):
        raise ValidationError(_("You cannot record this for this child."))
    return locked


def _validate_text(value, message):
    value = value.strip()
    if not value or len(value) > 240:
        raise ValidationError(message)
    return value


def _episode_for(child, actor, *, episode_id, token, category, reason, child_note=""):
    if episode_id is not None:
        episode = ConsequenceEpisode.objects.filter(child=child, pk=episode_id).first()
        if episode is None:
            raise ValidationError(_("Choose an episode for this child."))
        return episode
    if token is None:
        raise ValidationError(_("Reload the dashboard before recording a new episode."))
    existing = ConsequenceEpisode.objects.filter(child=child, create_token=token).first()
    if existing:
        if (existing.created_by_id != actor.pk or existing.reason != reason
                or existing.child_note != child_note or (category and existing.category_id != category.pk)):
            raise ValidationError(_("This episode request has already been used with different details."))
        return existing
    category_filter = {"pk": category.pk} if category else {"default_code": "other"}
    active_category = BehaviorCategory.objects.filter(is_active=True, **category_filter).first()
    if not active_category:
        raise ValidationError(_("Choose an active behavior category."))
    return ConsequenceEpisode.objects.create(
        child=child, category=active_category, category_name=active_category.name, created_by=actor,
        reason=reason, create_token=token, child_note=child_note,
    )


@transaction.atomic
def record_episode(*, child, actor, token, category, reason, child_note="", warning=False):
    child = _lock_child(child, actor)
    reason = _validate_text(reason, _("A reason is required."))
    if len(child_note.strip()) > 240:
        raise ValidationError(_("Use up to 240 characters."))
    episode = _episode_for(
        child, actor, episode_id=None, token=token, category=category, reason=reason,
        child_note=child_note.strip(),
    )
    if warning and episode.warned_at is None:
        if episode.debit_id:
            raise ValidationError(_("This episode already has a coin decision."))
        episode.warning_by = actor
        episode.warned_at = timezone.now()
        episode.save(update_fields=["warning_by", "warned_at"])
    return episode


@transaction.atomic
def apply_episode_debit(*, child, actor, penalty_ids, reason, episode_id=None, token=None, category=None):
    child = _lock_child(child, actor)
    reason = _validate_text(reason, _("A reason is required."))
    ids = sorted(set(penalty_ids))
    if not ids:
        raise ValidationError(_("Choose at least one active penalty."))
    episode = _episode_for(child, actor, episode_id=episode_id, token=token, category=category, reason=reason)
    penalties = list(PenaltyTemplate.objects.filter(pk__in=ids).order_by("pk"))
    snapshot = [{"id": item.pk, "title": item.title, "delta": item.amount} for item in penalties]
    if episode.debit_id:
        if (
            episode.debit.actor_id == actor.pk and episode.debit.reason == reason
            and [item["id"] for item in episode.template_snapshot] == ids
            and [item["delta"] for item in episode.template_snapshot] == [item["delta"] for item in snapshot]
        ):
            return episode.debit
        raise ValidationError(_("This episode already has a coin decision."))
    if len(penalties) != len(ids) or any(
        item.amount >= 0 or not item.is_active or item.is_deleted for item in penalties
    ):
        raise ValidationError(_("Choose at least one active penalty."))
    label = ", ".join(item.title for item in penalties)
    debit = post_ledger_entry(
        child=child, delta=sum(item.amount for item in penalties), kind=LedgerKind.PENALTY,
        description=f"{label[:140]}: {reason[:98]}", actor=actor, source_id=episode.pk,
        source_type="consequence_episode", operation_key=f"consequence:{episode.pk}",
        reason=reason,
    )
    episode.debit = debit
    episode.template_snapshot = snapshot
    episode.save(update_fields=["debit", "template_snapshot"])
    return debit


@transaction.atomic
def propose_repair(*, child, actor, episode_id, text, share_with_child):
    child = _lock_child(child, actor)
    episode = _episode_for(child, actor, episode_id=episode_id, token=None, category=None, reason="")
    text = _validate_text(text, _("Describe the agreed repair."))
    repair, created = RepairAction.objects.get_or_create(
        episode=episode, defaults={"text": text, "share_with_child": share_with_child, "proposed_by": actor},
    )
    if not created and (repair.text != text or repair.share_with_child != share_with_child):
        raise ValidationError(_("This episode already has a repair action."))
    return repair


@transaction.atomic
def complete_repair(*, child, actor, episode_id):
    child = _lock_child(child, actor)
    repair = RepairAction.objects.filter(episode_id=episode_id, episode__child=child).first()
    if not repair:
        raise ValidationError(_("Choose an episode with a repair action."))
    if repair.completed_at is None:
        repair.completed_at = timezone.now()
        repair.completed_by = actor
        repair.save(update_fields=["completed_at", "completed_by"])
    return repair


@transaction.atomic
def send_guardian_message(*, child, actor, text, token, kind=GuardianMessageKind.ENCOURAGEMENT, mission=None):
    child = _lock_child(child, actor, guardian_only=True)
    text = _validate_text(text, _("Write a message for the child."))
    if kind not in GuardianMessageKind.values or (mission is not None and mission.child_id != child.pk):
        raise ValidationError(_("Choose a message type and mission for this child."))
    details = {"author": actor, "text": text, "kind": kind, "mission": mission}
    message, created = GuardianMessage.objects.get_or_create(
        child=child, operation_token=token, defaults=details,
    )
    if not created and any(getattr(message, field) != value for field, value in details.items()):
        raise ValidationError(_("This message request has already been used."))
    return message
