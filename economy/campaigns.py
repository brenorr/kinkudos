from functools import partial
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.translation import gettext as _

from economy import missions
from economy.models import (
    Campaign,
    CampaignActivity,
    CampaignActivityKind,
    CampaignChapter,
    CampaignEdition,
    CampaignRequirement,
    CampaignRun,
    CampaignRunStatus,
    ChapterCompletion,
    MissionOccurrence,
    MissionStatus,
    StorySession,
    StoryStatus,
    UnlockGrant,
)


def latest_editions():
    latest_ids = CampaignEdition.objects.values("campaign_id").annotate(latest=Max("pk")).values("latest")
    return CampaignEdition.objects.filter(pk__in=latest_ids)


def current_chapter(run):
    return run.edition.chapters.exclude(pk__in=run.completions.values("chapter_id")).first()


def activity_complete(activity):
    if activity.mission_id:
        return activity.mission.status == MissionStatus.COMPLETED
    return activity.story.status == StoryStatus.FINISHED


def replaceable(activity):
    if not activity.mission_id:
        return False
    mission = activity.mission
    if mission.status in (MissionStatus.CANCELLED, MissionStatus.SKIPPED, MissionStatus.REJECTED):
        return True
    return mission.status in missions.EDITABLE and (
        mission.local_date < timezone.localdate()
        or (mission.deadline is not None and mission.deadline < timezone.now())
    )


@transaction.atomic
def publish_edition(*, campaign, details, chapters):
    if campaign is None:
        campaign = Campaign.objects.create(code=uuid4().hex)
    campaign = Campaign.objects.select_for_update().get(pk=campaign.pk)
    latest = campaign.editions.first()
    edition = CampaignEdition.objects.create(
        campaign=campaign, number=latest.number + 1 if latest else 1, **details,
    )
    for position, chapter_data in enumerate(chapters, start=1):
        data = chapter_data.copy()
        kinds = (
            [CampaignActivityKind.MISSION] * data.pop("mission_count")
            + [CampaignActivityKind.STORY] * data.pop("story_count")
        )
        chapter = CampaignChapter.objects.create(edition=edition, position=position, **data)
        CampaignRequirement.objects.bulk_create([
            CampaignRequirement(chapter=chapter, kind=kind) for kind in kinds
        ])
    return edition


@transaction.atomic
def start_run(*, child, edition):
    run = child.campaign_runs.filter(campaign=edition.campaign).first()
    if run:
        return run
    if edition.pk != edition.campaign.editions.first().pk or not edition.chapters.exists():
        raise ValidationError(_("Choose a published campaign edition."))
    return CampaignRun.objects.create(child=child, edition=edition, campaign=edition.campaign)


@transaction.atomic
def reconcile(run_id):
    run = CampaignRun.objects.select_for_update().select_related("edition").get(pk=run_id)
    return _advance(run)


def _advance(run):
    if run.status == CampaignRunStatus.ACTIVE:
        completed = set(run.completions.values_list("chapter_id", flat=True))
        activities = {
            activity.requirement_id: activity
            for activity in run.activities.select_related("mission", "story")
        }
        for chapter in run.edition.chapters.exclude(pk__in=completed).select_related("reward").prefetch_related("requirements"):
            requirements = list(chapter.requirements.all())
            if not requirements or any(
                requirement.pk not in activities or not activity_complete(activities[requirement.pk])
                for requirement in requirements
            ):
                return run
            completion, _created = ChapterCompletion.objects.get_or_create(run=run, chapter=chapter)
            if chapter.reward_id:
                UnlockGrant.objects.get_or_create(
                    child=run.child, unlock=chapter.reward, defaults={"campaign_completion": completion},
                )
        run.status = CampaignRunStatus.FINISHED
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "finished_at"])
    return run


@transaction.atomic
def change_run(*, run_id, child, action):
    run = CampaignRun.objects.select_for_update().get(pk=run_id, child=child)
    if action == "pause" and run.status == CampaignRunStatus.ACTIVE:
        run.status = CampaignRunStatus.PAUSED
        run.save(update_fields=["status"])
    elif action == "resume" and run.status == CampaignRunStatus.PAUSED:
        run.status = CampaignRunStatus.ACTIVE
        run.save(update_fields=["status"])
        _advance(run)
    elif action == "continue":
        _advance(run)
    return run


def _source_for(requirement, child, source_id):
    if requirement.kind == CampaignActivityKind.MISSION:
        mission = MissionOccurrence.objects.filter(pk=source_id, child=child).first()
        if not mission:
            raise ValidationError(_("Choose a mission for this child."))
        if mission.status in (MissionStatus.CANCELLED, MissionStatus.REJECTED, MissionStatus.SKIPPED) or (
            mission.status in missions.EDITABLE
            and (mission.local_date < timezone.localdate() or (mission.deadline and mission.deadline < timezone.now()))
        ):
            raise ValidationError(_("Choose a mission that can still be completed."))
        return "mission", mission
    story = StorySession.objects.filter(pk=source_id, child=child).first()
    if not story:
        raise ValidationError(_("Choose a session for this child."))
    return "story", story


@transaction.atomic
def link_activity(*, child, run_id, requirement_id, source_id):
    run = CampaignRun.objects.select_for_update().select_related("edition").get(pk=run_id, child=child)
    requirement = CampaignRequirement.objects.filter(pk=requirement_id, chapter__edition=run.edition).first()
    if not requirement:
        raise ValidationError(_("Choose a requirement from this campaign."))
    field, source = _source_for(requirement, child, source_id)
    existing = run.activities.select_related("mission", "story").filter(requirement=requirement).first()
    if existing and getattr(existing, f"{field}_id") == source.pk:
        return _advance(run)
    chapter = current_chapter(run)
    if chapter is None or chapter.pk != requirement.chapter_id:
        raise ValidationError(_("Choose a requirement from the current chapter."))
    if existing and not replaceable(existing):
        raise ValidationError(_("This requirement already has an activity."))
    if CampaignActivity.objects.filter(**{field: source}).exists():
        raise ValidationError(_("This activity already belongs to another requirement."))
    CampaignActivity.objects.update_or_create(run=run, requirement=requirement, defaults={field: source})
    return _advance(run)


def _reconcile_source(field, source_id):
    run_id = CampaignActivity.objects.filter(**{f"{field}_id": source_id}).values_list("run_id", flat=True).first()
    if run_id is not None:
        reconcile(run_id)


def activity_finished(field, source_id):
    transaction.on_commit(partial(_reconcile_source, field, source_id), robust=True)
