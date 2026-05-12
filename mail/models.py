from django.db import models
from django.conf import settings


class Email(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        PROCESSING = "processing", "Processing"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="emails")
    message_id = models.CharField(max_length=512, unique=True)
    from_address = models.EmailField()
    to_address = models.EmailField()
    subject = models.CharField(max_length=1000, default="")
    body_text = models.TextField(default="")
    body_html = models.TextField(default="")
    received_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED)
    raw_payload = models.JSONField(default=dict)
    extracted_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.from_address}: {self.subject[:50]}"


class Attachment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"

    email = models.ForeignKey(Email, on_delete=models.CASCADE, related_name="attachments")
    filename = models.CharField(max_length=500)
    content_type = models.CharField(max_length=200)
    size = models.IntegerField(default=0)
    file = models.FileField(upload_to="attachments/%Y/%m/%d/")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    extracted_text = models.TextField(default="", blank=True)
    extracted_data = models.JSONField(default=dict, blank=True)
    ocr_applied = models.BooleanField(default=False)
    page_count = models.IntegerField(default=0)
    error_message = models.TextField(default="", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.filename

    @property
    def is_pdf(self):
        return self.content_type == "application/pdf" or self.filename.lower().endswith(".pdf")


class ProcessingLog(models.Model):
    class Level(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"

    email = models.ForeignKey(Email, on_delete=models.CASCADE, related_name="logs")
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.INFO)
    message = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
