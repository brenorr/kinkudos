from django import forms
from django.utils import formats, timezone
from django.utils.translation import gettext_lazy as _

from economy.campaigns import latest_editions
from economy.forms import StyledFormMixin
from economy.models import (
    AdventureRegion,
    CampaignEdition,
    LevelUnlock,
    MissionOccurrence,
    MissionStatus,
    StorySession,
    Task,
    UnlockKind,
)


class EditionForm(StyledFormMixin, forms.Form):
    title = forms.CharField(label=_("Title"), max_length=100)
    description = forms.CharField(
        label=_("Description"), max_length=400, required=False, widget=forms.Textarea(attrs={"rows": 2}),
    )


class ChapterForm(StyledFormMixin, forms.Form):
    region = forms.ModelChoiceField(label=_("Region"), queryset=AdventureRegion.objects.all())
    title = forms.CharField(label=_("Title"), max_length=100)
    opening = forms.CharField(label=_("Chapter opening"), max_length=800, widget=forms.Textarea(attrs={"rows": 3}))
    npc = forms.CharField(label=_("Story character"), max_length=80, required=False)
    dialogue = forms.CharField(
        label=_("Dialogue"), max_length=400, required=False, widget=forms.Textarea(attrs={"rows": 2}),
    )
    mission_count = forms.IntegerField(label=_("Required missions"), min_value=0, max_value=3, required=False)
    story_count = forms.IntegerField(label=_("Required narrated sessions"), min_value=0, max_value=3, required=False)
    reward = forms.ModelChoiceField(
        label=_("Chapter cosmetic"), queryset=LevelUnlock.objects.filter(
            campaign_reward=True, is_active=True, earned_by_level=False, kind=UnlockKind.COSMETIC, offer__isnull=True,
        ), required=False,
    )

    def clean(self):
        data = super().clean()
        data["mission_count"] = data.get("mission_count") or 0
        data["story_count"] = data.get("story_count") or 0
        if not (data["mission_count"] or data["story_count"]):
            raise forms.ValidationError(_("A chapter needs at least one mission or narrated session."))
        if bool(data.get("npc")) != bool(data.get("dialogue")):
            raise forms.ValidationError(_("Enter both the character and their dialogue."))
        return data


ChapterFormSet = forms.formset_factory(
    ChapterForm, extra=8, min_num=1, max_num=8, absolute_max=8,
    validate_min=True, validate_max=True, can_delete=True, can_order=True,
)


class EditionChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, edition):
        return edition.display_title


class StartCampaignForm(StyledFormMixin, forms.Form):
    edition = EditionChoiceField(label=_("Campaign"), queryset=CampaignEdition.objects.none())

    def __init__(self, *args, child, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["edition"].queryset = latest_editions().exclude(
            campaign_id__in=child.campaign_runs.values("campaign_id"),
        )


class MissionChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, mission):
        day = formats.date_format(mission.local_date, "SHORT_DATE_FORMAT")
        return f"{mission.title} · {day} · {mission.get_status_display()}"


class StoryChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, story):
        return f"{story.title} · {story.get_status_display()}"


class LinkMissionForm(StyledFormMixin, forms.Form):
    mission = MissionChoiceField(label=_("Existing mission"), queryset=MissionOccurrence.objects.none())

    def __init__(self, *args, child, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mission"].queryset = child.missions.filter(campaignactivity__isnull=True).exclude(
            status__in=(MissionStatus.CANCELLED, MissionStatus.REJECTED, MissionStatus.SKIPPED),
        ).exclude(
            status__in=(MissionStatus.AVAILABLE, MissionStatus.IN_PROGRESS), local_date__lt=timezone.localdate(),
        ).exclude(
            status__in=(MissionStatus.AVAILABLE, MissionStatus.IN_PROGRESS), deadline__lt=timezone.now(),
        ).order_by("-local_date", "-pk")


class LinkStoryForm(StyledFormMixin, forms.Form):
    story = StoryChoiceField(label=_("Existing narrated session"), queryset=StorySession.objects.none())

    def __init__(self, *args, child, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["story"].queryset = child.story_sessions.filter(campaignactivity__isnull=True)


class CatalogMissionForm(StyledFormMixin, forms.Form):
    task = forms.ModelChoiceField(
        label=_("Task from the catalog"), queryset=Task.objects.filter(is_active=True, is_deleted=False),
    )
