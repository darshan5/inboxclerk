from django.db import models
from django.conf import settings


class UserSettings(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="settings")
    resend_inbound_address = models.EmailField(blank=True, default="")
    ai_extraction_enabled = models.BooleanField(default=True)
    ai_extraction_prompt = models.TextField(
        default="Extract key information from this email and its attachments. "
        "Return structured JSON with: dates, amounts, names, addresses, and any other relevant fields."
    )
    webhook_url = models.URLField(blank=True, default="")
    notification_email = models.EmailField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "User settings"

    def __str__(self):
        return f"Settings for {self.user.username}"
