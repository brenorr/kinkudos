from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.test import Client, TestCase
from django.urls import reverse

from economy.inventory import item_visual
from economy.models import (
    AssignedTask,
    AssignedTaskBatch,
    ChildProfile,
    EquippedCosmetic,
    FamilySettings,
    LevelUnlock,
    UnlockGrant,
    VirtualOffer,
)
from economy.services import assigned_tasks_block_rewards, credit_occurrence


class CharacterInventoryTests(TestCase):
    def setUp(self):
        self.profile = ChildProfile.objects.create(name="Lia", balance=100, theme_selected=True)
        self.second_device = Client()
        for device in (self.client, self.second_device):
            session = device.session
            session["child_id"] = self.profile.pk
            session.save()
        credit_occurrence(
            child=self.profile, occurrence_key="mission", xp=1_000, coins=0, description="Missão",
        )
        self.title = self.profile.unlock_grants.get(unlock__code="apprentice")
        self.cape = self.profile.unlock_grants.get(unlock__code="adventurer-cape")
        self.offer = VirtualOffer.objects.get(unlock__code="forest-cape")

    def equipment_url(self, action, grant):
        return reverse(f"child_{action}_cosmetic", args=[grant.pk])

    def buy_cape(self):
        response = self.client.post(reverse("child_purchase_cosmetic", args=[self.offer.pk]), {
            "operation_token": uuid4(),
            "confirmed_price": self.offer.cost,
        })
        self.assertRedirects(response, reverse("child_character") + "#collection")
        return self.profile.unlock_grants.get(unlock=self.offer.unlock)

    def test_preview_and_swap_owned_items_without_economic_effects(self):
        purchased = self.buy_cape()
        self.offer.is_active = False
        self.offer.save(update_fields=["is_active"])
        LevelUnlock.objects.filter(pk=self.cape.unlock_id).update(is_active=False)
        family = FamilySettings.load()
        family.real_shop_enabled = False
        family.save(update_fields=["real_shop_enabled"])
        parent = get_user_model().objects.create_user("parent", is_staff=True)
        batch = AssignedTaskBatch.objects.create(child=self.profile, assigned_by=parent, blocks_rewards=True)
        AssignedTask.objects.create(batch=batch, title_snapshot="Arrumar a mesa", reward_snapshot=1)
        self.assertTrue(assigned_tasks_block_rewards(self.profile))
        self.profile.balance = -5
        self.profile.save(update_fields=["balance"])
        accounting = (
            list(self.profile.ledger_entries.values()),
            list(self.profile.occurrence_credits.values()),
            list(self.profile.unlock_grants.values()),
        )

        page = self.client.get(reverse("child_character"))
        self.assertContains(page, "Unlocked at level 5")
        self.assertContains(page, "Acquired in the virtual shop")
        self.assertContains(page, "No items equipped.")
        signature = self.second_device.get(reverse("child_state")).json()["signature"]
        preview = self.client.get(self.equipment_url("preview", self.cape))
        cape_image = static(item_visual(self.cape.unlock))
        self.assertContains(preview, f'data-visual="adventurer-cape"><img src="{cape_image}"')
        self.assertFalse(EquippedCosmetic.objects.exists())
        self.assertEqual(self.second_device.get(reverse("child_state")).json()["signature"], signature)

        self.client.post(self.equipment_url("equip", self.title))
        self.client.post(self.equipment_url("equip", self.cape))
        self.client.post(self.equipment_url("equip", self.cape))
        self.assertEqual(self.profile.equipped_cosmetics.count(), 2)
        self.assertNotEqual(self.second_device.get(reverse("child_state")).json()["signature"], signature)
        dashboard = self.second_device.get(reverse("child_dashboard"))
        self.assertEqual(dashboard.context["equipped_title"].grant, self.title)

        self.assertContains(self.second_device.get(self.equipment_url("preview", purchased)), "Swap to this item")
        self.second_device.post(self.equipment_url("equip", purchased))
        self.client.post(self.equipment_url("unequip", self.cape))
        self.assertEqual(self.profile.equipped_cosmetics.get(slot="cape").grant, purchased)
        purchased_image = static(item_visual(purchased.unlock))
        self.assertContains(
            self.second_device.get(reverse("child_character")),
            f'data-visual="forest-cape"><img src="{purchased_image}"',
        )
        self.client.post(self.equipment_url("unequip", purchased))
        self.client.post(self.equipment_url("unequip", purchased))
        self.assertFalse(self.profile.equipped_cosmetics.filter(slot="cape").exists())
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.balance, -5)
        self.assertEqual(accounting, (
            list(self.profile.ledger_entries.values()),
            list(self.profile.occurrence_credits.values()),
            list(self.profile.unlock_grants.values()),
        ))

    def test_actions_are_session_scoped_and_enforce_post_and_csrf(self):
        neighbor = ChildProfile.objects.create(name="Irmã", theme_selected=True)
        other_title = neighbor.unlock_grants.get(unlock__code="apprentice")
        self.assertEqual(self.client.get(self.equipment_url("preview", other_title)).status_code, 404)
        self.assertEqual(self.client.post(self.equipment_url("equip", other_title)).status_code, 404)
        self.assertEqual(self.client.post(self.equipment_url("unequip", other_title)).status_code, 404)
        self.assertEqual(self.client.get(self.equipment_url("equip", self.title)).status_code, 405)
        self.assertEqual(self.client.post(self.equipment_url("preview", self.title)).status_code, 405)
        protected_client = Client(enforce_csrf_checks=True)
        session = protected_client.session
        session["child_id"] = self.profile.pk
        session.save()
        self.assertEqual(protected_client.post(self.equipment_url("equip", self.title)).status_code, 403)
        self.client.logout()
        self.assertRedirects(self.client.post(self.equipment_url("equip", self.title)), reverse("child_select"),
                             fetch_redirect_response=False)
        self.assertFalse(EquippedCosmetic.objects.exists())

    def test_unmapped_or_incompatible_item_and_visual_fallback(self):
        item = LevelUnlock.objects.create(code="legacy", kind="cosmetic", name="Legacy skin", minimum_level=1)
        grant = UnlockGrant.objects.create(child=self.profile, unlock=item, required_level=1)
        for slot in ("", "title"):
            with self.subTest(slot=slot):
                LevelUnlock.objects.filter(pk=item.pk).update(slot=slot)
                page = self.client.get(reverse("child_character"))
                self.assertContains(page, "Legacy skin")
                self.assertContains(page, "No equipment slot")
                self.assertNotContains(page, self.equipment_url("equip", grant))
                self.assertEqual(self.client.get(self.equipment_url("preview", grant)).status_code, 404)
                response = self.client.post(self.equipment_url("equip", grant), follow=True)
                self.assertContains(response, "This item has no equipment slot.")
        self.assertFalse(EquippedCosmetic.objects.exists())
        LevelUnlock.objects.filter(pk=item.pk).update(slot="accessory", visual_key="missing-glyph")
        self.client.post(self.equipment_url("equip", grant))
        self.assertContains(self.client.get(reverse("child_character")), 'character-piece-accessory">◇')

    def test_style_persists_and_portuguese_labels_are_available(self):
        url = reverse("child_character")
        self.profile.avatar = "avatars/profile.webp"
        self.profile.randomize_theme_daily = True
        self.profile.save(update_fields=["avatar", "randomize_theme_daily"])
        original_signature = self.second_device.get(reverse("child_state")).json()["signature"]
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "pt-br"
        self.assertContains(self.client.get(url), "Meu personagem")
        self.assertContains(self.client.get(url), "Experimentar")
        response = self.client.post(url, {"character_class": "mage", "character_appearance": "moss"}, follow=True)
        self.assertContains(response, "Aparência do personagem salva.")
        self.assertContains(response, 'data-appearance="moss"')
        self.assertNotEqual(self.second_device.get(reverse("child_state")).json()["signature"], original_signature)
        self.client.post(url, {"character_class": "explorer", "character_appearance": "invented"})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.character_class, "mage")
        self.assertEqual(self.profile.character_appearance, "moss")
        self.assertEqual(self.profile.avatar.name, "avatars/profile.webp")
        self.assertTrue(self.profile.randomize_theme_daily)

    def test_collection_can_be_empty(self):
        self.profile.unlock_grants.all().delete()
        self.assertContains(self.client.get(reverse("child_character")), "Your collection is empty.")

    def test_catalog_cosmetics_have_packaged_artwork(self):
        cosmetics = LevelUnlock.objects.filter(kind="cosmetic").exclude(visual_key="")
        self.assertEqual(cosmetics.count(), 11)
        for cosmetic in cosmetics:
            with self.subTest(cosmetic=cosmetic.code):
                self.assertTrue(item_visual(cosmetic))
                self.assertIsNotNone(finders.find(item_visual(cosmetic)))
