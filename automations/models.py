from django.db import models
from django.conf import settings


class AutomationRule(models.Model):
    class TriggerField(models.TextChoices):
        SENDER = "sender", "Sender"
        SUBJECT = "subject", "Subject"
        BODY = "body", "Body"
        ATTACHMENT_NAME = "attachment_name", "Attachment Name"
        EXTRACTED_TEXT = "extracted_text", "Extracted Text"

    class Operator(models.TextChoices):
        CONTAINS = "contains", "Contains"
        EQUALS = "equals", "Equals"
        STARTS_WITH = "starts_with", "Starts With"
        ENDS_WITH = "ends_with", "Ends With"
        REGEX = "regex", "Regex"

    class ActionType(models.TextChoices):
        LABEL = "label", "Add Label"
        FORWARD = "forward", "Forward Email"
        WEBHOOK = "webhook", "Call Webhook"
        EXTRACT = "extract", "Extract Data (AI)"
        NOTIFY = "notify", "Send Notification"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="automation_rules")
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    trigger_field = models.CharField(max_length=30, choices=TriggerField.choices)
    operator = models.CharField(max_length=20, choices=Operator.choices)
    trigger_value = models.CharField(max_length=500)
    action_type = models.CharField(max_length=20, choices=ActionType.choices)
    action_config = models.JSONField(default=dict)
    priority = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "-created_at"]

    def __str__(self):
        return self.name


class AutomationExecution(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    rule = models.ForeignKey(AutomationRule, on_delete=models.CASCADE, related_name="executions")
    email = models.ForeignKey("mail.Email", on_delete=models.CASCADE, related_name="automation_executions")
    status = models.CharField(max_length=10, choices=Status.choices)
    result = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(default="", blank=True)
    executed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-executed_at"]
