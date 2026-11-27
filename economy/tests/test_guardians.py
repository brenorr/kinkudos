from datetime import timedelta
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from economy.models import (
    CaregiverProfile,
    ChildProfile,
    GuardianMessage,
    GuardianProfile,
    MissionHelpRequest,
    MissionStatus,
    RequestStatus,
    StoryStatus,
)


class GuardianParticipationTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.guardian = users.create_user("private-login")
        self.guardian_client = Client()
        self.guardian_client.force_login(self.guardian)
        self.child = ChildProfile.objects.create(name="Lia", balance=45, theme_selected=True)
        self.sibling = ChildProfile.objects.create(name="Bia", theme_selected=True)
        self.child_client = self.device(self.child)
        self.wall = reverse("parent_guardian_child", args=[self.child.pk])

    def device(self, child):
        client = Client()
        session = client.session
        session["child_id"] = child.pk
        session.save()
        return client

    def new_story(self, mode="prepared", **extras):
        response = self.guardian_client.post(self.wall, {"action": "story", "mode": mode, **extras})
        self.assertEqual(response.status_code, 302)
        return self.child.story_sessions.latest("pk")

    def test_prepared_story_two_devices_pause_and_economy(self):
        story = self.new_story()
        parent_view = reverse("parent_story", args=[story.pk])
        parent_state = reverse("parent_story_state", args=[story.pk])
        child_view = reverse("child_story", args=[story.pk])
        self.assertContains(self.child_client.get(reverse("child_dashboard")), child_view)
        self.assertContains(self.child_client.get(child_view), "The forest bridge")
        self.assertContains(self.guardian_client.get(parent_view), parent_state)
        accounting = (self.child.balance, list(self.child.ledger_entries.all()), list(self.child.occurrence_credits.all()))
        initial_child_state = self.child_client.get(reverse("child_state")).json()["signature"]
        initial_parent_state = self.guardian_client.get(parent_state).json()["signature"]

        self.child_client.post(child_view, {"action": "choice", "choice": story.choices[0], "version": 1})
        story.refresh_from_db()
        selected = story.last_choice
        self.assertEqual(selected, story.choices[0])
        self.assertNotEqual(self.child_client.get(reverse("child_state")).json()["signature"], initial_child_state)
        self.assertNotEqual(self.guardian_client.get(parent_state).json()["signature"], initial_parent_state)
        stale = self.guardian_client.post(parent_view, {"action": "advance", "passage": "Draft next scene", "version": 1})
        self.assertContains(stale, "The scene has changed.")
        self.assertContains(stale, "Draft next scene")
        self.guardian_client.post(parent_view, {"action": "pause", "version": story.version})
        story.refresh_from_db()
        self.assertEqual(story.status, StoryStatus.PAUSED)
        self.assertContains(self.child_client.get(child_view), "Session paused")
        self.assertContains(self.child_client.post(child_view, {
            "action": "choice", "choice": story.choices[1], "version": story.version,
        }), "Resume the session before continuing.")
        duplicate = self.guardian_client.post(self.wall, {"action": "story", "mode": "prepared"})
        self.assertContains(duplicate, "This child already has a session to resume.")

        self.guardian_client.post(parent_view, {"action": "resume", "version": story.version})
        story.refresh_from_db()
        self.assertEqual(story.passage, story.opening)
        self.assertEqual(story.last_choice, selected)
        self.guardian_client.post(parent_view, {
            "action": "advance", "version": story.version, "passage": "The fox opens the gate.",
            "choices": "Enter\nWait",
        })
        story.refresh_from_db()
        self.assertEqual(story.choices, ["Enter", "Wait"])
        self.assertFalse(story.choice_recorded)
        self.assertContains(self.child_client.get(child_view), "The fox opens the gate.")
        finish = {"action": "finish", "version": story.version, "summary": "Crossed the bridge.", "praise": "Boa ideia!"}
        self.guardian_client.post(parent_view, finish)
        self.guardian_client.post(parent_view, finish)
        story.refresh_from_db()
        self.assertEqual(story.status, StoryStatus.FINISHED)
        self.assertContains(self.child_client.get(child_view), story.summary)
        self.assertEqual(self.child.guardian_messages.get().text, "Boa ideia!")
        self.child.refresh_from_db()
        self.assertEqual(accounting, (
            self.child.balance, list(self.child.ledger_entries.all()), list(self.child.occurrence_credits.all()),
        ))
        self.assertFalse(self.child.missions.exists())

    def test_story_free_mode_and_access(self):
        bad = self.guardian_client.post(self.wall, {"action": "story", "mode": "free"})
        self.assertContains(bad, "Complete this field for free mode.")
        story = self.new_story("free", title="Lanternas", passage="Acenda a lanterna.", choices="Entrar")
        parent_url = reverse("parent_story", args=[story.pk])
        child_url = reverse("child_story", args=[story.pk])
        neighbor = self.device(self.sibling)
        self.assertEqual(neighbor.get(child_url).status_code, 404)
        other_adult = Client()
        other_adult.force_login(get_user_model().objects.create_user("other_adult"))
        self.assertEqual(other_adult.get(parent_url).status_code, 404)
        self.assertEqual(other_adult.get(reverse("parent_story_state", args=[story.pk])).status_code, 404)
        self.assertEqual(self.child_client.post(child_url, {"action": "pause", "version": 1}).status_code, 404)
        self.assertContains(self.child_client.post(child_url, {
            "action": "choice", "choice": "Invented remotely", "version": 1,
        }), "Choose an option shown in this scene.")
        self.guardian_client.post(parent_url, {"action": "choice", "choice": "Vou acender duas", "version": 1})
        story.refresh_from_db()
        self.assertEqual(story.last_choice, "Vou acender duas")
        self.assertTrue(story.choice_recorded)

    def test_guardian_profile_wall_privacy_and_avatar(self):
        target = reverse("parent_guardian_profile")
        pixels = BytesIO()
        Image.new("RGB", (12, 12), "purple").save(pixels, format="PNG")
        uploaded = SimpleUploadedFile("avatar.png", pixels.getvalue(), content_type="image/png")
        with TemporaryDirectory() as media, self.settings(MEDIA_ROOT=media):
            self.guardian_client.post(target, {"display_name": "Tia", "title": "Maga", "avatar": uploaded})
            profile = GuardianProfile.objects.get()
            self.assertEqual(profile.user, self.guardian)
            avatar = reverse("child_guardian_avatar", args=[profile.pk])
            self.assertEqual(self.child_client.get(avatar).status_code, 404)
            for i in range(16):
                response = self.guardian_client.post(self.wall, {
                    "action": "message", "kind": "praise", "operation_token": uuid4(), "text": f"Mensagem {i}",
                })
                self.assertRedirects(response, self.wall, fetch_redirect_response=False)
            self.assertEqual(self.child_client.get(avatar)["Content-Type"], "image/webp")
            self.assertEqual(self.device(self.sibling).get(avatar).status_code, 404)
            child_wall = reverse("child_guardian_wall")
            self.assertNotContains(self.child_client.get(child_wall), "Mensagem 0")
            page = self.child_client.get(child_wall + "?page=2")
            self.assertContains(page, "Mensagem 0")
            self.assertContains(page, "Tia · Maga")
            self.assertNotContains(page, "private-login")

        login = get_user_model().objects.create_user("temporary")
        caregiver = CaregiverProfile.objects.create(
            user=login, login_code="ABCD", label="Temporary", access_until=timezone.localdate() + timedelta(days=1),
        )
        caregiver.children.add(self.child)
        guest = Client()
        guest.force_login(login)
        self.assertRedirects(guest.get(self.wall), reverse("parent_dashboard"), fetch_redirect_response=False)
        guest.post(target, {"display_name": "Alterado"})
        self.assertEqual(GuardianProfile.objects.count(), 1)
        caregiver.access_until = timezone.localdate() - timedelta(days=1)
        caregiver.save(update_fields=["access_until"])
        self.assertRedirects(guest.get(self.wall), reverse("home"), fetch_redirect_response=False)

    def mission(self, kind="special", **fields):
        data = {
            "action": "mission", "token": uuid4(), "kind": kind, "title": "Montar cabana",
            "instructions": "Use as almofadas.", "coins": 7, "xp": 11,
            "day": timezone.localdate().isoformat(), "requires_approval": "on",
        }
        data.update(fields)
        response = self.guardian_client.post(self.wall, data)
        self.assertRedirects(response, self.wall, fetch_redirect_response=False)
        return self.child.missions.latest("pk"), data

    def test_guardian_mission_surprise_cooperative_help_and_approval(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        future, _ = self.mission(kind="surprise", title="Ainda segredo", day=tomorrow.isoformat())
        self.assertEqual(self.child_client.get(reverse("child_mission", args=[future.pk])).status_code, 404)
        self.assertEqual(self.child_client.post(reverse("child_mission_action", args=[future.pk]), {
            "action": "skip",
        }).status_code, 404)
        surprise, data = self.mission(kind="surprise", title="Surpresa revelada")
        self.guardian_client.post(self.wall, data)
        self.assertEqual(self.child.missions.count(), 2)
        self.assertNotContains(self.child_client.get(reverse("child_dashboard")), "Surpresa revelada")
        surprise_page = self.child_client.get(reverse("child_mission", args=[surprise.pk]))
        self.assertContains(surprise_page, "Surpresa revelada")
        self.assertContains(surprise_page, "11 XP and 7 coins")
        self.assertTrue(surprise.requires_approval)

        coop, _ = self.mission("cooperative")
        action_url = reverse("child_mission_action", args=[coop.pk])
        self.child_client.post(action_url, {"action": "help"})
        self.child_client.post(action_url, {"action": "help"})
        thread = coop.help_requests.get()
        reply_url = reverse("parent_answer_mission_help", args=[self.child.pk, thread.pk])
        self.guardian_client.post(reply_url, {"text": "Eu seguro as almofadas."})
        self.guardian_client.post(reply_url, {"text": "Eu seguro as almofadas."})
        self.assertEqual(self.child.guardian_messages.count(), 1)
        self.assertContains(self.child_client.get(reverse("child_mission", args=[coop.pk])), "Eu seguro as almofadas.")
        self.child_client.post(action_url, {"action": "help"})
        self.assertEqual(coop.help_requests.count(), 1)
        self.child_client.post(action_url, {"action": "help", "reopen_after": thread.pk})
        self.assertEqual(coop.help_requests.count(), 2)
        self.assertEqual(MissionHelpRequest.objects.filter(occurrence=coop, answered_at=None).count(), 1)
        self.assertFalse(self.child.ledger_entries.exists())

        self.child_client.post(action_url, {"action": "submit"})
        claim = coop.claim
        self.assertEqual(claim.status, RequestStatus.PENDING)
        decision = reverse("parent_decide_task", args=[claim.pk, "approve"])
        with patch("economy.views.parent_actions.send_guardian_message", side_effect=ValidationError("invalid")):
            self.guardian_client.post(decision, {"praise": "Ótima colaboração."})
        claim.refresh_from_db()
        self.assertEqual(claim.status, RequestStatus.PENDING)
        self.assertFalse(self.child.occurrence_credits.exists())
        with patch("economy.views.parent_actions.notify_task_decision") as notify:
            self.guardian_client.post(decision, {"praise": "Ótima colaboração."})
            self.guardian_client.post(decision, {"praise": "Agora outro elogio."})
            notify.assert_called_once()
        self.assertEqual(self.child.occurrence_credits.get().xp, 11)
        self.assertEqual(self.child.ledger_entries.get().delta, 7)
        self.assertEqual(GuardianMessage.objects.filter(mission=coop, kind="praise").get().text, "Ótima colaboração.")
        coop.refresh_from_db()
        self.assertEqual(coop.status, MissionStatus.COMPLETED)
        participants = reverse("parent_record_cooperative_participants", args=[self.child.pk, coop.pk])
        self.guardian_client.post(participants, {"participants": "Lia e Tia"})
        self.assertContains(self.child_client.get(reverse("child_mission", args=[coop.pk])), "Lia e Tia")

    def test_prepared_scene_is_localized(self):
        self.guardian_client.cookies[settings.LANGUAGE_COOKIE_NAME] = "pt-br"
        self.child_client.cookies[settings.LANGUAGE_COOKIE_NAME] = "pt-br"
        story = self.new_story()
        self.assertEqual(story.title, "A ponte da floresta")
        self.assertContains(self.child_client.get(reverse("child_story", args=[story.pk])), "Atravessar a ponte")
