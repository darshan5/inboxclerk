import base64
import logging
from datetime import datetime

from django.core.files.base import ContentFile
from django.utils import timezone

from mail.models import Attachment, Email, ProcessingLog
from mail.services.pdf_processor import process_pdf_bytes

logger = logging.getLogger(__name__)


def parse_resend_inbound(payload: dict, user) -> Email:
    email = Email.objects.create(
        user=user,
        message_id=payload.get("message_id", f"resend-{timezone.now().timestamp()}"),
        from_address=payload.get("from", ""),
        to_address=payload.get("to", ""),
        subject=payload.get("subject", "(no subject)"),
        body_text=payload.get("text", ""),
        body_html=payload.get("html", ""),
        received_at=timezone.now(),
        status=Email.Status.RECEIVED,
        raw_payload=payload,
    )

    ProcessingLog.objects.create(
        email=email,
        level=ProcessingLog.Level.INFO,
        message="Email received via Resend webhook",
    )

    for att_data in payload.get("attachments", []):
        _save_attachment(email, att_data)

    return email


def _save_attachment(email: Email, att_data: dict) -> Attachment:
    filename = att_data.get("filename", "attachment")
    content_type = att_data.get("content_type", "application/octet-stream")
    content_b64 = att_data.get("content", "")

    content_bytes = base64.b64decode(content_b64) if content_b64 else b""

    attachment = Attachment(
        email=email,
        filename=filename,
        content_type=content_type,
        size=len(content_bytes),
    )
    attachment.file.save(filename, ContentFile(content_bytes), save=False)
    attachment.save()

    ProcessingLog.objects.create(
        email=email,
        level=ProcessingLog.Level.INFO,
        message=f"Attachment saved: {filename} ({content_type}, {len(content_bytes)} bytes)",
    )

    return attachment


def process_email(email: Email):
    email.status = Email.Status.PROCESSING
    email.save(update_fields=["status", "updated_at"])

    try:
        for attachment in email.attachments.all():
            if attachment.is_pdf:
                _process_pdf_attachment(email, attachment)

        email.status = Email.Status.PROCESSED
        email.save(update_fields=["status", "updated_at"])

        ProcessingLog.objects.create(
            email=email,
            level=ProcessingLog.Level.INFO,
            message="Email processing completed",
        )

    except Exception as e:
        logger.exception("Error processing email %s", email.id)
        email.status = Email.Status.FAILED
        email.error_message = str(e)
        email.save(update_fields=["status", "error_message", "updated_at"])

        ProcessingLog.objects.create(
            email=email,
            level=ProcessingLog.Level.ERROR,
            message=f"Processing failed: {e}",
        )


def _process_pdf_attachment(email: Email, attachment: Attachment):
    attachment.status = Attachment.Status.PROCESSING
    attachment.save(update_fields=["status"])

    try:
        content = attachment.file.read()
        result = process_pdf_bytes(content, attachment.filename)

        attachment.extracted_text = result.get("text", "")
        attachment.extracted_data = {
            "tables": result.get("tables", []),
            "method": result.get("method", ""),
        }
        attachment.ocr_applied = result.get("ocr_applied", False)
        attachment.page_count = result.get("page_count", 0)
        attachment.status = Attachment.Status.PROCESSED
        attachment.save()

        ProcessingLog.objects.create(
            email=email,
            level=ProcessingLog.Level.INFO,
            message=f"PDF processed: {attachment.filename} "
            f"({attachment.page_count} pages, OCR: {attachment.ocr_applied})",
        )

    except Exception as e:
        logger.exception("Error processing PDF %s", attachment.filename)
        attachment.status = Attachment.Status.FAILED
        attachment.error_message = str(e)
        attachment.save(update_fields=["status", "error_message"])

        ProcessingLog.objects.create(
            email=email,
            level=ProcessingLog.Level.ERROR,
            message=f"PDF processing failed for {attachment.filename}: {e}",
        )
