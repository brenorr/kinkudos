from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from economy.models import CharacterSlot, EquippedCosmetic, UnlockGrant, UnlockKind


ITEM_VISUALS = frozenset({
    "adventurer-cape",
    "travel-tunic",
    "star-hat",
    "forest-cape",
    "crystal-staff",
    "wooden-shield",
    "compass-charm",
    "camp-lantern",
    "starlit-theme",
    "fox-companion",
})


def item_slot(unlock):
    slot = unlock.slot
    if slot in CharacterSlot.values and (slot == CharacterSlot.TITLE) == (unlock.kind == UnlockKind.TITLE):
        return slot
    return ""


def item_visual(unlock):
    if unlock.visual_key in ITEM_VISUALS:
        return f"character/cosmetics/{unlock.visual_key}.webp"
    return ""


@transaction.atomic
def set_equipment(*, child, grant_id, equip):
    grant = UnlockGrant.objects.select_related("unlock").get(child=child, pk=grant_id)
    slot = item_slot(grant.unlock)
    if not equip:
        removed, _details = EquippedCosmetic.objects.filter(child=child, grant=grant).delete()
        return grant, bool(removed)
    if not slot:
        raise ValidationError(_("This item has no equipment slot."))

    choices = EquippedCosmetic.objects.filter(child=child)
    choices.filter(grant=grant).exclude(slot=slot).delete()
    EquippedCosmetic.objects.update_or_create(child=child, slot=slot, defaults={"grant": grant})
    return grant, True
