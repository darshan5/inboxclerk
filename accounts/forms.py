from django import forms
from django.contrib.auth.forms import AuthenticationForm

from accounts.models import UserSettings


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent",
            "placeholder": "Username",
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent",
            "placeholder": "Password",
        })
    )


class UserSettingsForm(forms.ModelForm):
    class Meta:
        model = UserSettings
        fields = [
            "imap_host",
            "imap_port",
            "imap_username",
            "imap_password",
            "imap_use_ssl",
            "resend_inbound_address",
            "sync_filter_to_address",
            "ai_extraction_enabled",
            "ai_extraction_prompt",
            "webhook_url",
            "notification_email",
        ]
        widgets = {
            "imap_host": forms.TextInput(attrs={
                "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500",
                "placeholder": "imap.gmail.com",
            }),
            "imap_port": forms.NumberInput(attrs={
                "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500",
            }),
            "imap_username": forms.EmailInput(attrs={
                "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500",
                "placeholder": "you@gmail.com",
            }),
            "imap_password": forms.PasswordInput(attrs={
                "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500",
                "placeholder": "App password",
                "autocomplete": "new-password",
            }, render_value=True),
            "imap_use_ssl": forms.CheckboxInput(attrs={
                "class": "h-4 w-4 text-blue-600 rounded border-gray-300",
            }),
            "resend_inbound_address": forms.EmailInput(attrs={
                "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500",
                "placeholder": "your-inbox@inbound.resend.dev",
            }),
            "sync_filter_to_address": forms.TextInput(attrs={
                "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500",
                "placeholder": "automate@inboxclerk.com",
            }),
            "ai_extraction_enabled": forms.CheckboxInput(attrs={
                "class": "h-4 w-4 text-blue-600 rounded border-gray-300",
            }),
            "ai_extraction_prompt": forms.Textarea(attrs={
                "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500",
                "rows": 4,
            }),
            "webhook_url": forms.URLInput(attrs={
                "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500",
                "placeholder": "https://your-app.com/webhook",
            }),
            "notification_email": forms.EmailInput(attrs={
                "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500",
                "placeholder": "notify@example.com",
            }),
        }
