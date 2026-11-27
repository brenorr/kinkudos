from django import forms
from django.utils import formats, timezone
from django.utils.translation import gettext_lazy as _

from economy.forms import MAX_POINT_AMOUNT, AvatarForm, GuardianMessageForm, StyledFormMixin
from economy.models import (
    GuardianMessageKind,
    GuardianProfile,
    MissionKind,
    MissionOccurrence,
    StoryMode,
)


class GuardianProfileForm(StyledFormMixin, forms.ModelForm):
    avatar = forms.ImageField(
        label=_("New avatar"), required=False,
        widget=forms.FileInput(attrs=AvatarForm.base_fields["avatar"].widget.attrs),
    )

    class Meta:
        model = GuardianProfile
        fields = ["display_name", "title", "avatar"]
        labels = {"display_name": _("Display name"), "title": _("Narrative title")}

    def clean_avatar(self):
        if "avatar" not in self.files:
            return None
        return AvatarForm.clean_avatar(self)


class WallMessageForm(GuardianMessageForm):
    kind = forms.ChoiceField(label=_("Message type"), choices=[
        (kind, kind.label) for kind in GuardianMessageKind if kind != GuardianMessageKind.HELP
    ])
    mission = forms.ModelChoiceField(label=_("Related mission"), queryset=MissionOccurrence.objects.none(), required=False)

    def __init__(self, *args, child, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mission"].queryset = child.missions.filter(local_date__lte=timezone.localdate())
        self.fields["mission"].label_from_instance = lambda mission: (
            f"{mission.title} · {formats.date_format(mission.local_date, 'SHORT_DATE_FORMAT')}"
        )


class GuardianMissionForm(StyledFormMixin, forms.Form):
    token = forms.UUIDField(widget=forms.HiddenInput)
    kind = forms.ChoiceField(label=_("Mission type"), choices=[
        (MissionKind.SPECIAL, _("Special mission")),
        ("surprise", _("Surprise mission")),
        (MissionKind.COOPERATIVE, _("Cooperative mission")),
    ])
    title = forms.CharField(label=_("Title"), max_length=120)
    instructions = forms.CharField(label=_("Instructions"), max_length=200, widget=forms.Textarea(attrs={"rows": 3}))
    day = forms.DateField(label=_("Available on"), widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    xp = forms.IntegerField(label=_("XP"), min_value=0, max_value=MAX_POINT_AMOUNT, initial=0)
    coins = forms.IntegerField(label=_("Coins"), min_value=0, max_value=MAX_POINT_AMOUNT, initial=0)
    requires_approval = forms.BooleanField(label=_("Requires approval"), initial=True, required=False)

    def clean_day(self):
        day = self.cleaned_data["day"]
        if day < timezone.localdate():
            raise forms.ValidationError(_("Choose today or a future date."))
        return day


class StoryOptionsForm(StyledFormMixin, forms.Form):
    choices = forms.CharField(
        label=_("Choices (one per line)"), required=False, max_length=650,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def clean_choices(self):
        choices = [line.strip() for line in self.cleaned_data["choices"].splitlines() if line.strip()]
        if len(choices) > 4 or any(len(option) > 160 for option in choices) or len(choices) != len(set(choices)):
            raise forms.ValidationError(_("Enter up to four different choices, with at most 160 characters each."))
        return choices


class StartStoryForm(StoryOptionsForm):
    mode = forms.ChoiceField(label=_("Story mode"), choices=StoryMode.choices)
    title = forms.CharField(label=_("Title"), max_length=100, required=False)
    passage = forms.CharField(
        label=_("Opening for free mode"), required=False, max_length=1000,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    field_order = ["mode", "title", "passage", "choices"]

    def clean(self):
        data = super().clean()
        if data.get("mode") == StoryMode.FREE:
            for field in ("title", "passage"):
                if not data.get(field):
                    self.add_error(field, _("Complete this field for free mode."))
        return data


class AdvanceStoryForm(StoryOptionsForm):
    passage = forms.CharField(
        label=_("Next passage"), max_length=1000, widget=forms.Textarea(attrs={"rows": 4}),
    )
    field_order = ["passage", "choices"]


class StoryChoiceForm(StyledFormMixin, forms.Form):
    choice = forms.CharField(label=_("Record a spoken choice"), max_length=160)


class FinishStoryForm(StyledFormMixin, forms.Form):
    summary = forms.CharField(label=_("Session summary (optional)"), max_length=500, required=False,
                              widget=forms.Textarea(attrs={"rows": 3}))
    praise = forms.CharField(label=_("Praise for the wall (optional)"), max_length=240, required=False)


class StoryVersionForm(forms.Form):
    version = forms.IntegerField(min_value=1)
