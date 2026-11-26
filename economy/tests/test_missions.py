from datetime import date, datetime, time, timezone as utc
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from economy.forms import TaskForm
from economy.missions import record_catalog_completion, resolve_catalog_occurrence, submit_mission
from economy.models import (
    AssignedTaskBatch,
    AssignedTaskStatus,
    AssignmentPresetCadence,
    ChildProfile,
    FamilySettings,
    LedgerEntry,
    MissionOccurrence,
    MissionStatus,
    OccurrenceCredit,
    RequestStatus,
    Task,
    TaskClaim,
)
from economy.services import (
    approve_task_claim,
    assign_tasks,
    cancel_assigned_task,
    complete_assigned_task,
    save_assignment_preset,
    submit_task,
)


class MissionWorkflowTests(TestCase):
    def setUp(self):
        self.parent = get_user_model().objects.create_user("responsavel")
        self.child = ChildProfile.objects.create(name="Aventureira", theme_selected=True)
        self.task = Task.objects.create(title="Organizar a mochila", reward=7, xp_reward=20)

    def sign_in_child(self, child=None):
        session = self.client.session
        session["child_id"] = (child or self.child).pk
        session.save()

    def assign(self):
        return assign_tasks(child=self.child, actor=self.parent, tasks=[self.task]).items.get()

    def test_assigned_catalog_and_direct_paths_settle_same_occurrence(self):
        assignment = self.assign()
        self.assertIsNone(complete_assigned_task(assigned_task=assignment, child=self.child))
        claim = submit_task(child=self.child, task=self.task)
        self.assertEqual(claim.occurrence_id, assignment.occurrence_id)
        self.assertFalse(LedgerEntry.objects.exists())
        entry = record_catalog_completion(child=self.child, task=self.task, actor=self.parent)
        retry = approve_task_claim(claim=claim, actor=self.parent)
        self.assertEqual(retry.pk, entry.pk)
        self.assertEqual(complete_assigned_task(assigned_task=assignment, child=self.child).pk, entry.pk)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, AssignedTaskStatus.COMPLETED)
        self.assertEqual(OccurrenceCredit.objects.get().xp, 20)
        self.assertEqual(LedgerEntry.objects.count(), 1)

    def test_checklist_revision_and_cap_preserve_full_xp(self):
        self.task.checklist = ["Estojo", "Cadernos"]
        self.task.save()
        family = FamilySettings.load()
        family.daily_coin_limit = 0
        family.save(update_fields=["daily_coin_limit"])
        self.sign_in_child()
        reply = self.client.post(reverse("child_start_mission", args=[self.task.pk]))
        occurrence = MissionOccurrence.objects.get()
        target = reverse("child_mission_action", args=[occurrence.pk])
        self.assertContains(self.client.get(reply.url), "Estojo")
        self.client.post(target, {"action": "checklist", "steps": ["0"]})
        self.client.post(target, {"action": "submit"})
        self.assertFalse(TaskClaim.objects.exists())
        self.client.post(target, {"action": "checklist", "steps": ["0", "1"]})
        self.client.post(target, {"action": "submit"})
        claim = TaskClaim.objects.get(occurrence=occurrence)
        self.client.force_login(self.parent)
        decision = reverse("parent_decide_task", args=[claim.pk, "revise"])
        self.client.post(decision, {"reason": "Confira o estojo."})
        occurrence.refresh_from_db()
        self.assertEqual(occurrence.status, MissionStatus.IN_REVIEW)
        self.assertEqual(occurrence.checked_steps, [0, 1])
        self.sign_in_child()
        self.client.post(reverse("child_resubmit_task", args=[claim.pk]))
        claim.refresh_from_db()
        self.assertEqual(claim.status, RequestStatus.PENDING)
        approve_task_claim(claim=claim, actor=self.parent)
        result = OccurrenceCredit.objects.get()
        self.assertEqual((result.xp, result.coin_entry.delta), (20, 0))

    def test_no_approval_and_explicit_repeat_have_independent_credits(self):
        self.task.requires_approval = False
        self.task.save()
        first = submit_task(child=self.child, task=self.task)
        self.assertEqual(first.status, RequestStatus.APPROVED)
        self.assertEqual(submit_task(child=self.child, task=self.task).pk, first.pk)
        token = uuid4()
        additional = resolve_catalog_occurrence(self.child, self.task, extra_token=token)
        self.assertEqual(resolve_catalog_occurrence(self.child, self.task, extra_token=token), additional)
        submit_mission(child=self.child, occurrence=additional)
        self.child.refresh_from_db()
        self.assertEqual(self.child.balance, 14)
        self.assertEqual(OccurrenceCredit.objects.count(), 2)

    def test_legacy_pending_records_block_new_settlement_without_changing_their_credit(self):
        legacy = TaskClaim.objects.create(
            child=self.child, task=self.task, task_title=self.task.title,
            reward_snapshot=13, use_coin_limits=False,
        )
        with self.assertRaises(ValidationError):
            record_catalog_completion(child=self.child, task=self.task, actor=self.parent)
        with self.assertRaises(ValidationError):
            self.assign()
        with self.assertRaises(ValidationError):
            submit_task(child=self.child, task=self.task)
        self.assertEqual(approve_task_claim(claim=legacy, actor=self.parent).delta, 13)
        self.assertFalse(OccurrenceCredit.objects.exists())

    def test_cancel_after_submission_prevents_approval(self):
        assignment = self.assign()
        complete_assigned_task(assigned_task=assignment, child=self.child)
        claim = TaskClaim.objects.get(occurrence=assignment.occurrence)
        cancel_assigned_task(assigned_task=assignment, actor=self.parent)
        with self.assertRaises(ValidationError):
            approve_task_claim(claim=claim, actor=self.parent)
        self.assertFalse(OccurrenceCredit.objects.exists())

    def test_ownership_help_and_skip(self):
        assignment = self.assign()
        url = reverse("child_mission_action", args=[assignment.occurrence_id])
        sibling = ChildProfile.objects.create(name="Sibling", theme_selected=True)
        self.sign_in_child(sibling)
        self.assertEqual(self.client.post(url, {"action": "help"}).status_code, 404)
        self.sign_in_child()
        with patch("economy.views.child.notify_mission_help") as notify:
            self.client.post(url, {"action": "help"})
            self.client.post(url, {"action": "help"})
        notify.assert_called_once()
        self.client.post(url, {"action": "skip"})
        assignment.occurrence.refresh_from_db()
        self.assertEqual(assignment.occurrence.status, MissionStatus.SKIPPED)
        self.assertFalse(LedgerEntry.objects.exists())

    def test_monthly_scheduler_uses_sao_paulo_and_skips_vacations(self):
        family = FamilySettings.load()
        family.timezone_name = "America/Sao_Paulo"
        family.vacation_start = family.vacation_end = date(2026, 1, 31)
        family.save()
        preset = save_assignment_preset(
            child=self.child, actor=self.parent, name="Fim do mês", tasks=[self.task],
            cadence=AssignmentPresetCadence.MONTHLY, monthly_day=31, run_at=time(0),
        )
        for instant in (
            datetime(2026, 1, 31, 3, tzinfo=utc.utc),
            datetime(2026, 2, 28, 2, 59, tzinfo=utc.utc),
        ):
            with patch("django.utils.timezone.now", return_value=instant):
                call_command("run_scheduled_reminders", stdout=StringIO())
        self.assertFalse(AssignedTaskBatch.objects.exists())
        with patch("django.utils.timezone.now", return_value=datetime(2026, 2, 28, 3, tzinfo=utc.utc)):
            call_command("run_scheduled_reminders", stdout=StringIO())
            call_command("run_scheduled_reminders", stdout=StringIO())
        batch = AssignedTaskBatch.objects.get(preset=preset)
        self.assertEqual(batch.assigned_on, date(2026, 2, 28))
        self.assertEqual(batch.items.get().occurrence.local_date, batch.assigned_on)

    def test_approval_after_midnight_uses_approval_day_for_the_budget(self):
        family = FamilySettings.load()
        family.timezone_name = "America/Sao_Paulo"
        family.save()
        with timezone.override(family.timezone_name):
            with patch("django.utils.timezone.now", return_value=datetime(2026, 8, 10, 2, 59, tzinfo=utc.utc)):
                claim = submit_task(child=self.child, task=self.task)
            with patch("django.utils.timezone.now", return_value=datetime(2026, 8, 10, 3, tzinfo=utc.utc)):
                entry = approve_task_claim(claim=claim, actor=self.parent)
        self.assertEqual(claim.occurrence.local_date, date(2026, 8, 9))
        self.assertEqual(entry.local_date, date(2026, 8, 10))

    def test_catalog_rejects_prerequisite_cycles(self):
        preparation = Task.objects.create(title="Preparar cadernos", reward=1, prerequisite=self.task)
        form = TaskForm(
            instance=self.task,
            data={"title": self.task.title, "reward": 7, "icon": "⭐", "prerequisite": preparation.pk},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("prerequisite", form.errors)
