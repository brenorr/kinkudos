from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from economy import campaigns, guardians
from economy.models import (
    AdventureRegion,
    CampaignActivity,
    CampaignEdition,
    CampaignRunStatus,
    CaregiverProfile,
    ChildProfile,
    FamilySettings,
    MissionStatus,
    StoryMode,
    StoryStatus,
    Task,
)


class CampaignTests(TestCase):
    def setUp(self):
        self.guardian = get_user_model().objects.create_user("guardian", is_staff=True)
        self.parent = Client()
        self.parent.force_login(self.guardian)
        self.child = ChildProfile.objects.create(name="Lia", balance=50, theme_selected=True)
        self.sibling = ChildProfile.objects.create(name="Bia", theme_selected=True)
        self.device = self.child_device(self.child)
        self.edition = CampaignEdition.objects.get(is_builtin=True)
        self.run = campaigns.start_run(child=self.child, edition=self.edition)
        self.address = reverse("parent_campaign_child", args=[self.child.pk])
        self.map = reverse("child_adventures")
        self.action = reverse("child_campaign_run_action", args=[self.run.pk])
        self.mission_requirement = self.edition.chapters.get(position=1).requirements.get()
        self.story_requirement = self.edition.chapters.get(position=2).requirements.get()

    def child_device(self, child):
        device = Client()
        session = device.session
        session["child_id"] = child.pk
        session.save()
        return device

    def link_url(self, requirement, run=None):
        return reverse("parent_campaign_link", args=[self.child.pk, (run or self.run).pk, requirement.pk])

    def assign_task(self, requirement=None, *, requires_approval=True):
        task = Task.objects.create(title="Mochila", reward=7, xp_reward=12, requires_approval=requires_approval)
        endpoint = self.link_url(requirement or self.mission_requirement)
        response = self.parent.post(endpoint, {"action": "create", "task": task.pk}, follow=True)
        self.assertNotContains(response, "Choose a requirement from the current chapter.")
        return self.child.missions.get(task=task), task

    def submit(self, mission):
        return self.device.post(reverse("child_mission_action", args=[mission.pk]), {"action": "submit"})

    def test_pending_approval_pause_resume_and_single_economic_credit(self):
        self.assertContains(self.device.get(self.map), "Pack an explorer")
        state_url = reverse("child_adventure_state")
        initial_state = self.device.get(state_url).json()["signature"]
        mission, task = self.assign_task()
        self.assertNotEqual(self.device.get(state_url).json()["signature"], initial_state)
        claim_state = self.submit(mission)
        self.assertEqual(claim_state.status_code, 302)
        self.assertContains(self.device.get(self.map), "Awaiting approval")
        self.assertFalse(self.run.completions.exists())
        self.device.post(self.action, {"action": "pause"})
        url = reverse("parent_decide_task", args=[mission.claim.pk, "approve"])
        with self.captureOnCommitCallbacks(execute=True):
            self.parent.post(url)
            self.parent.post(url)
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, CampaignRunStatus.PAUSED)
        self.assertFalse(self.run.completions.exists())
        self.device.post(self.action, {"action": "resume"})
        self.assertEqual(self.run.completions.get().chapter, self.mission_requirement.chapter)

        story = guardians.start_story(child=self.child, narrator=self.guardian, mode=StoryMode.FREE,
                                      title="Floresta", passage="Nosso caminho.")
        self.parent.post(self.link_url(self.story_requirement), {"action": "link", "story": story.pk})
        self.assertRedirects(
            self.device.post(self.action, {"action": "continue"}),
            reverse("child_story", args=[story.pk]),
        )
        view = reverse("parent_story", args=[story.pk])
        self.parent.post(view, {"action": "pause", "version": 1})
        self.assertContains(self.device.get(self.map), "Session paused")
        self.parent.post(view, {"action": "resume", "version": 2})
        with self.captureOnCommitCallbacks(execute=True):
            for _ in range(2):
                self.parent.post(view, {"action": "finish", "version": 3, "summary": "Atravessamos a ponte."})
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, CampaignRunStatus.FINISHED)
        self.assertEqual(self.run.completions.count(), 2)
        self.assertEqual(self.child.occurrence_credits.get().xp, task.xp_reward)
        self.assertEqual(self.child.ledger_entries.get().delta, task.reward)
        grant = self.child.unlock_grants.get(unlock__code="trail-brooch")
        self.assertEqual(grant.campaign_completion.chapter, self.story_requirement.chapter)
        self.assertContains(self.device.get(self.map), "Atravessamos a ponte.")
        self.assertContains(self.device.get(reverse("child_character")), "Earned on an adventure")

    def test_can_reconcile_existing_activities_and_lost_completion_callback(self):
        family = FamilySettings.load()
        family.coin_balance_limit = self.child.balance
        family.save(update_fields=["coin_balance_limit"])
        mission, _task = self.assign_task(requires_approval=False)
        self.submit(mission)
        self.assertEqual(self.child.ledger_entries.get().delta, 0)
        self.assertFalse(self.run.completions.exists())
        self.device.post(self.action, {"action": "continue"})
        self.assertEqual(self.run.completions.count(), 1)
        story = guardians.start_story(child=self.child, narrator=self.guardian, mode=StoryMode.PREPARED)
        guardians.change_story(session_id=story.pk, actor_scope={"narrator": self.guardian}, action="finish",
                               version=1, data={"summary": "", "praise": ""})
        self.parent.post(self.link_url(self.story_requirement), {"action": "link", "story": story.pk})
        self.parent.post(self.link_url(self.story_requirement), {"action": "link", "story": story.pk})
        self.run.refresh_from_db()
        self.assertEqual(self.run.status, CampaignRunStatus.FINISHED)
        self.assertEqual(self.child.unlock_grants.filter(unlock__code="trail-brooch").count(), 1)

    def test_edition_keeps_started_runs_and_accepts_multiple_requirements(self):
        catalog = reverse("parent_campaigns")
        region = AdventureRegion.objects.get(code="forest")
        reward = self.story_requirement.chapter.reward
        endpoint = reverse("parent_campaign_edit", args=[self.edition.campaign_id])
        data = {
            "title": "Mudança", "description": "",
            "chapter-TOTAL_FORMS": 2, "chapter-INITIAL_FORMS": 2,
            "chapter-0-region": region.pk, "chapter-0-title": "Novo capítulo",
            "chapter-0-opening": "A trilha mudou.", "chapter-0-mission_count": 2, "chapter-0-story_count": 1,
            "chapter-0-reward": reward.pk, "chapter-0-ORDER": 1, "chapter-1-DELETE": "on",
        }
        response = self.parent.post(endpoint, data)
        self.assertRedirects(response, catalog)
        new = CampaignEdition.objects.get(campaign=self.edition.campaign, number=2)
        self.assertEqual(new.chapters.get().requirements.count(), 3)
        self.run.refresh_from_db()
        self.assertEqual(self.run.edition, self.edition)
        self.assertContains(self.device.get(self.map), "Pack an explorer")
        self.assertNotContains(self.device.get(self.map), "Novo capítulo")
        with self.assertRaisesMessage(ValidationError, "published campaign edition"):
            campaigns.start_run(child=self.sibling, edition=self.edition)
        self.assertEqual(campaigns.start_run(child=self.sibling, edition=new).edition, new)

    def test_reuse_is_scoped_and_expired_missions_can_be_replaced(self):
        mission, task = self.assign_task()
        other_story = guardians.start_story(child=self.sibling, narrator=self.guardian, mode=StoryMode.PREPARED)
        unauthorized = self.child_device(self.sibling)
        self.assertEqual(unauthorized.post(self.action, {"action": "pause"}).status_code, 404)
        with self.assertRaisesMessage(ValidationError, "current chapter"):
            story = guardians.start_story(child=self.child, narrator=self.guardian, mode=StoryMode.PREPARED)
            campaigns.link_activity(child=self.child, run_id=self.run.pk,
                                    requirement_id=self.story_requirement.pk, source_id=story.pk)
        with self.assertRaisesMessage(ValidationError, "session for this child"):
            campaigns.link_activity(child=self.child, run_id=self.run.pk,
                                    requirement_id=self.story_requirement.pk, source_id=other_story.pk)
        with timezone.override(ZoneInfo("America/Sao_Paulo")):
            link = self.run.activities.select_related("mission").get()
            link.mission.local_date = datetime(2026, 11, 27, tzinfo=UTC).date()
            with patch("django.utils.timezone.now", return_value=datetime(2026, 11, 28, 2, 59, tzinfo=UTC)):
                self.assertFalse(campaigns.replaceable(link))
            with patch("django.utils.timezone.now", return_value=datetime(2026, 11, 28, 3, 0, tzinfo=UTC)):
                self.assertTrue(campaigns.replaceable(link))
            mission.local_date = timezone.localdate() - timedelta(days=1)
            mission.save(update_fields=["local_date"])
            self.assertContains(self.device.get(self.map), "A replacement mission is needed.")
            replacement, _ = self.assign_task()
            self.assertEqual(self.run.activities.get().mission, replacement)
        self.assertEqual(task.title, "Mochila")
        self.assertEqual(StoryStatus.ACTIVE, story.status)
        self.assertEqual(mission.status, MissionStatus.AVAILABLE)
        helper_user = get_user_model().objects.create_user("helper")
        caregiver = CaregiverProfile.objects.create(
            user=helper_user, login_code="A234", label="Helper",
            access_until=timezone.localdate() + timedelta(days=1),
        )
        caregiver.children.add(self.child)
        helper = Client()
        helper.force_login(helper_user)
        self.assertRedirects(helper.get(self.address), reverse("parent_dashboard"), fetch_redirect_response=False)

    def test_same_activity_and_cosmetic_cannot_be_granted_twice(self):
        mission, _task = self.assign_task(requires_approval=False)
        self.submit(mission)
        self.device.post(self.action, {"action": "continue"})
        reward = self.story_requirement.chapter.reward
        original = self.child.unlock_grants.create(unlock=reward, required_level=9)
        story = guardians.start_story(child=self.child, narrator=self.guardian, mode=StoryMode.PREPARED)
        guardians.change_story(session_id=story.pk, actor_scope={"narrator": self.guardian}, action="finish",
                               version=1, data={"summary": "", "praise": ""})
        self.parent.post(self.link_url(self.story_requirement), {"action": "link", "story": story.pk})
        self.assertEqual(self.child.unlock_grants.get(unlock=reward).pk, original.pk)
        self.assertIsNone(self.child.unlock_grants.get(unlock=reward).campaign_completion)
        edition = campaigns.publish_edition(
            campaign=None, details={"title": "Outra", "description": ""},
            chapters=[{"title": "Cena", "opening": "Cena", "mission_count": 0, "story_count": 1,
                       "region": self.story_requirement.chapter.region}],
        )
        other_run = campaigns.start_run(child=self.child, edition=edition)
        requirement = edition.chapters.get().requirements.get()
        with self.assertRaisesMessage(ValidationError, "another requirement"):
            campaigns.link_activity(child=self.child, run_id=other_run.pk, requirement_id=requirement.pk, source_id=story.pk)
        self.assertEqual(CampaignActivity.objects.filter(story=story).count(), 1)
