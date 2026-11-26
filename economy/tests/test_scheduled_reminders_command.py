from datetime import date, datetime, timezone as utc
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.utils import timezone, translation

from economy.models import BirthdayAward, ChildProfile, FamilySettings


class ScheduledRemindersCommandTests(SimpleTestCase):
    def test_later_steps_run_when_lottery_step_fails(self):
        calls = []

        def boom():
            calls.append("lottery")
            self.assertEqual(timezone.get_current_timezone_name(), "America/Sao_Paulo")
            self.assertEqual(translation.get_language(), "pt-br")
            raise RuntimeError("lottery failed")

        def nudge():
            calls.append("nudge")
            return ["nudge-1"]

        def presets():
            calls.append("presets")
            return ["preset-1"]

        with (
            patch(
                "economy.management.commands.run_scheduled_reminders.send_due_lottery_reminders",
                side_effect=boom,
            ),
            patch(
                "economy.management.commands.run_scheduled_reminders.send_due_assigned_task_nudges",
                side_effect=nudge,
            ),
            patch(
                "economy.management.commands.run_scheduled_reminders.run_due_assignment_presets",
                side_effect=presets,
            ),
            patch(
                "economy.management.commands.run_scheduled_reminders.FamilySettings"
            ) as family_settings,
        ):
            family_settings.load.return_value.timezone_name = "America/Sao_Paulo"
            family_settings.load.return_value.default_language = "pt-br"
            with self.assertRaises(SystemExit) as raised:
                call_command(
                    "run_scheduled_reminders",
                    stdout=StringIO(),
                    stderr=StringIO(),
                )

        self.assertEqual(calls, ["lottery", "nudge", "presets"])
        self.assertIn("lottery reminders", str(raised.exception))

    def test_legacy_alias_delegates_to_scheduled_reminders(self):
        with (
            patch(
                "economy.management.commands.run_scheduled_reminders.send_due_lottery_reminders",
                return_value=[],
            ),
            patch(
                "economy.management.commands.run_scheduled_reminders.send_due_assigned_task_nudges",
                return_value=[],
            ),
            patch(
                "economy.management.commands.run_scheduled_reminders.run_due_assignment_presets",
                return_value=[],
            ),
            patch(
                "economy.management.commands.run_scheduled_reminders.FamilySettings"
            ) as family_settings,
        ):
            family_settings.load.return_value.timezone_name = "America/Sao_Paulo"
            family_settings.load.return_value.default_language = "pt-br"
            call_command(
                "send_lottery_reminders",
                stdout=StringIO(),
                stderr=StringIO(),
            )


class DailyMaintenanceCommandTests(TestCase):
    def test_birthday_waits_for_the_family_date_and_is_awarded_once(self):
        family = FamilySettings.load()
        family.timezone_name = "America/Sao_Paulo"
        family.birthday_points = 5
        family.save(update_fields=["timezone_name", "birthday_points"])
        child = ChildProfile.objects.create(name="Audit child", birth_date=date(2020, 8, 10))

        with patch("django.utils.timezone.now", return_value=datetime(2026, 8, 10, 2, 59, tzinfo=utc.utc)):
            call_command("run_maintenance", stdout=StringIO())
        self.assertFalse(BirthdayAward.objects.filter(child=child).exists())

        with patch("django.utils.timezone.now", return_value=datetime(2026, 8, 10, 3, 0, tzinfo=utc.utc)):
            call_command("run_maintenance", stdout=StringIO())
            call_command("run_maintenance", stdout=StringIO())
        award = BirthdayAward.objects.get(child=child, year=2026)
        self.assertEqual(award.points, 5)
