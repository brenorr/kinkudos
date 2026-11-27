from dataclasses import dataclass
from math import isqrt

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Sum
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from .models import (
    CharacterClass,
    ChildProfile,
    FamilySettings,
    LevelAdvance,
    LevelUnlock,
    OccurrenceCredit,
    PracticeSkill,
    SkillPractice,
    UnlockGrant,
)


CHARACTER_STYLES = {
    CharacterClass.MAGE: ("🪄", gettext_lazy("Explores mysteries and solves puzzles with magic.")),
    CharacterClass.WARRIOR: ("⚔️", gettext_lazy("Protects the group on its adventures.")),
    CharacterClass.DRUID: ("🌿", gettext_lazy("Finds clues in nature and cares for living things.")),
    CharacterClass.ALCHEMIST: ("⚗️", gettext_lazy("Experiments with mixtures and invents tools.")),
    CharacterClass.EXPLORER: ("🧭", gettext_lazy("Maps new paths and discovers hidden places.")),
    CharacterClass.ARCHER: ("🏹", gettext_lazy("Observes carefully and helps the group from afar.")),
}


@dataclass(frozen=True)
class Progress:
    total_xp: int
    level: int
    level_xp: int
    level_target: int

    @property
    def remaining_xp(self):
        return self.level_target - self.level_xp


def calculate_progress(total_xp, factor):
    if total_xp < 0 or factor < 1:
        raise ValueError("XP must be nonnegative and the curve factor must be positive.")
    level = (1 + isqrt(1 + 8 * (total_xp // factor))) // 2
    threshold = factor * level * (level - 1) // 2
    return Progress(total_xp, level, total_xp - threshold, factor * level)


def xp_total(child):
    return child.occurrence_credits.aggregate(total=Sum("xp", default=0))["total"]


def practiced_skills(child):
    totals = dict(
        SkillPractice.objects.filter(credit__child=child).order_by().values_list("skill")
        .annotate(total=Count("pk"))
    )
    return [(skill.label, totals[skill.value]) for skill in PracticeSkill if skill.value in totals]


def grant_eligible_unlocks(child, level, *, event=None, using=None):
    granted = UnlockGrant.objects.using(using).filter(child=child).values("unlock_id")
    candidates = LevelUnlock.objects.using(using).filter(
        is_active=True, earned_by_level=True, minimum_level__lte=level,
    ).exclude(pk__in=granted)
    return UnlockGrant.objects.using(using).bulk_create([
        UnlockGrant(child=child, unlock=unlock, required_level=unlock.minimum_level, event=event)
        for unlock in candidates
    ], ignore_conflicts=True)


def grant_initial_unlocks(sender, instance, created, raw, using, **kwargs):
    if created and not raw:
        grant_eligible_unlocks(instance, 1, using=using)


def record_credit_progression(credit, skills):
    """Run inside the same write transaction that creates the occurrence credit."""
    from .push import notify_level_advance

    family = FamilySettings.load()
    family.refresh_from_db(fields=["xp_curve_factor"])
    total = xp_total(credit.child)
    previous = calculate_progress(total - credit.xp, family.xp_curve_factor)
    current = calculate_progress(total, family.xp_curve_factor)
    if skills:
        SkillPractice.objects.bulk_create([
            SkillPractice(credit=credit, skill=skill) for skill in sorted(set(skills))
        ])
    advance = None
    if current.level > previous.level:
        advance = LevelAdvance.objects.create(
            credit=credit, previous_level=previous.level, current_level=current.level,
        )
    grant_eligible_unlocks(credit.child, current.level, event=advance)
    if advance:
        transaction.on_commit(lambda: notify_level_advance(advance.pk), robust=True)


@transaction.atomic
def set_curve_factor(factor):
    if factor < 1:
        raise ValidationError(_("Enter a positive XP curve factor."))
    family = FamilySettings.load()
    family.refresh_from_db(fields=["xp_curve_factor"])
    if factor == family.xp_curve_factor:
        return
    blocked_by_xp = (
        OccurrenceCredit.objects.order_by().values("child_id").annotate(total=Sum("xp"))
        .filter(total__gte=min(factor, family.xp_curve_factor)).exists()
    )
    if blocked_by_xp or LevelAdvance.objects.exists() or UnlockGrant.objects.filter(required_level__gt=1).exists():
        raise ValidationError(_("The XP curve is locked once a profile reaches level 2."))
    family.xp_curve_factor = factor
    family.save(update_fields=["xp_curve_factor"])


@transaction.atomic
def reconcile_unlocks():
    factor = FamilySettings.load().xp_curve_factor
    totals = dict(OccurrenceCredit.objects.order_by().values_list("child_id").annotate(total=Sum("xp")))
    for child in ChildProfile.objects.iterator():
        grant_eligible_unlocks(child, calculate_progress(totals.get(child.pk, 0), factor).level)
