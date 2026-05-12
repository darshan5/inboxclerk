from django import forms

from automations.models import AutomationRule

INPUT_CLASSES = "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"


class AutomationRuleForm(forms.ModelForm):
    class Meta:
        model = AutomationRule
        fields = ["name", "is_active", "trigger_field", "operator", "trigger_value", "action_type", "action_config", "priority"]
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASSES, "placeholder": "Rule name"}),
            "is_active": forms.CheckboxInput(attrs={"class": "h-4 w-4 text-blue-600 rounded border-gray-300"}),
            "trigger_field": forms.Select(attrs={"class": INPUT_CLASSES}),
            "operator": forms.Select(attrs={"class": INPUT_CLASSES}),
            "trigger_value": forms.TextInput(attrs={"class": INPUT_CLASSES, "placeholder": "Value to match"}),
            "action_type": forms.Select(attrs={"class": INPUT_CLASSES}),
            "action_config": forms.Textarea(attrs={"class": INPUT_CLASSES, "rows": 3, "placeholder": '{"label": "invoice"}'}),
            "priority": forms.NumberInput(attrs={"class": INPUT_CLASSES}),
        }

    def clean_action_config(self):
        import json
        value = self.cleaned_data["action_config"]
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                raise forms.ValidationError("Must be valid JSON")
        return value
