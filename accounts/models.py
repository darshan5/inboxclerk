from django.db import models
from django.conf import settings


class UserSettings(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="settings")
    resend_inbound_address = models.EmailField(blank=True, default="")
    sync_filter_to_address = models.CharField(
        max_length=500, blank=True, default="",
        help_text="Only sync emails sent to this address. Leave blank to sync all.",
    )
    imap_host = models.CharField(max_length=200, blank=True, default="")
    imap_port = models.IntegerField(default=993)
    imap_username = models.EmailField(blank=True, default="")
    imap_password = models.CharField(max_length=500, blank=True, default="")
    imap_use_ssl = models.BooleanField(default=True)
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
