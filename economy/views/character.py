from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from economy import inventory
from economy.auth import child_required
from economy.forms import CharacterStyleForm
from economy.models import CharacterSlot, UnlockGrant
from economy.progression import CHARACTER_STYLES


def _character_look(shown):
    return {
        "shown": {slot.replace("-", "_"): item for slot, item in shown.items()},
        "shown_items": [(label, shown[slot]) for slot, label in CharacterSlot.choices if slot in shown],
        "equipment_title": shown.get(CharacterSlot.TITLE),
    }


def equipped_character(child):
    shown = {}
    for outfit in child.equipped_cosmetics.filter(grant__child=child).select_related("grant__unlock"):
        unlock = outfit.grant.unlock
        if inventory.item_slot(unlock) == outfit.slot:
            shown[outfit.slot] = {"grant": outfit.grant, "visual": inventory.item_visual(unlock)}
    return _character_look(shown)


@child_required
@never_cache
@require_http_methods(["GET", "HEAD", "POST"])
def child_character(request):
    return _character_page(request)


@child_required
@never_cache
@require_http_methods(["GET", "HEAD"])
def child_preview_cosmetic(request, grant_id):
    return _character_page(request, preview_id=grant_id)


def _character_page(request, preview_id=None):
    child = request.child
    style_form = CharacterStyleForm(
        request.POST if request.method == "POST" else None,
        initial={"character_class": child.character_class, "character_appearance": child.character_appearance},
    )
    if style_form.is_bound and style_form.is_valid():
        child.character_class = style_form.cleaned_data["character_class"]
        child.character_appearance = style_form.cleaned_data["character_appearance"]
        child.save(update_fields=["character_class", "character_appearance"])
        messages.success(request, _("Character appearance saved."))
        return redirect("child_character")

    equipped_ids = dict(child.equipped_cosmetics.values_list("slot", "grant_id"))
    groups = {slot: [] for slot in CharacterSlot.values}
    groups[""] = []
    equipped = {}
    preview = None
    grants = child.unlock_grants.select_related("unlock").order_by("required_level", "unlock__code")
    for grant in grants:
        slot = inventory.item_slot(grant.unlock)
        is_equipped = equipped_ids.get(slot) == grant.pk
        item = {
            "grant": grant,
            "slot": slot,
            "visual": inventory.item_visual(grant.unlock),
            "equipped": is_equipped,
            "replaces": slot in equipped_ids and not is_equipped,
        }
        groups[slot].append(item)
        if is_equipped:
            equipped[slot] = item
        if grant.pk == preview_id and slot:
            preview = item
    if preview_id is not None and preview is None:
        raise Http404

    shown = equipped.copy()
    if preview:
        shown[preview["slot"]] = preview
    return render(request, "economy/child_character.html", {
        **_character_look(shown),
        "child": child,
        "style_form": style_form,
        "character_style": CHARACTER_STYLES.get(child.character_class),
        "collection": [(label, groups[slot]) for slot, label in CharacterSlot.choices if groups[slot]],
        "unmapped_items": groups[""],
        "preview": preview,
    })


@child_required
@require_POST
def child_change_equipment(request, grant_id, equip):
    try:
        grant, changed = inventory.set_equipment(child=request.child, grant_id=grant_id, equip=equip)
    except UnlockGrant.DoesNotExist as exc:
        raise Http404 from exc
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        options = {"item": str(grant.unlock)}
        if equip:
            messages.success(request, _("%(item)s equipped.") % options)
        elif changed:
            messages.success(request, _("%(item)s unequipped.") % options)
        else:
            messages.info(request, _("%(item)s is already unequipped.") % options)
    return redirect(f"{reverse('child_character')}#collection")
