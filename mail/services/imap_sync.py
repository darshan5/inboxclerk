import email
import imaplib
import logging
from datetime import date, datetime
from email.header import decode_header
from email.utils import parsedate_to_datetime

from django.core.files.base import ContentFile
from django.utils import timezone

from mail.models import Attachment, Email, ProcessingLog
from mail.services.pdf_processor import process_pdf_bytes

logger = logging.getLogger(__name__)


def sync_emails(user, date_from: date, date_to: date) -> dict:
    user_settings = user.settings
    if not user_settings.imap_host or not user_settings.imap_username:
        return {"error": "IMAP not configured. Go to Settings to add your email credentials."}

    try:
        if user_settings.imap_use_ssl:
            conn = imaplib.IMAP4_SSL(user_settings.imap_host, user_settings.imap_port)
        else:
            conn = imaplib.IMAP4(user_settings.imap_host, user_settings.imap_port)

        conn.login(user_settings.imap_username, user_settings.imap_password)
    except Exception as e:
        logger.exception("IMAP connection failed")
        return {"error": f"IMAP connection failed: {e}"}

    try:
        conn.select("INBOX")

        since = date_from.strftime("%d-%b-%Y")
        before = date_to.strftime("%d-%b-%Y")
        _, msg_ids = conn.search(None, f'(SINCE "{since}" BEFORE "{before}")')

        if not msg_ids[0]:
            conn.logout()
            return {"synced": 0, "skipped": 0, "errors": 0}

        id_list = msg_ids[0].split()
        synced = 0
        skipped = 0
        errors = 0

        for msg_id in id_list:
            try:
                _, msg_data = conn.fetch(msg_id, "(RFC822)")
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                message_id = msg.get("Message-ID", f"imap-{msg_id.decode()}-{timezone.now().timestamp()}")

                if Email.objects.filter(message_id=message_id).exists():
                    skipped += 1
                    continue

                email_obj = _parse_imap_message(msg, message_id, user)
                _process_attachments(msg, email_obj)

                email_obj.status = Email.Status.PROCESSING
                email_obj.save(update_fields=["status"])

                for att in email_obj.attachments.filter(content_type="application/pdf"):
                    _process_pdf(email_obj, att)

                email_obj.status = Email.Status.PROCESSED
                email_obj.save(update_fields=["status", "updated_at"])

                ProcessingLog.objects.create(
                    email=email_obj,
                    level=ProcessingLog.Level.INFO,
                    message="Email synced and processed via IMAP",
                )
                synced += 1

            except Exception as e:
                logger.exception("Error processing IMAP message %s", msg_id)
                errors += 1

        conn.logout()
        return {"synced": synced, "skipped": skipped, "errors": errors}

    except Exception as e:
        logger.exception("IMAP sync error")
        conn.logout()
        return {"error": f"Sync failed: {e}"}


def _decode_header_value(value):
    if not value:
        return ""
    decoded_parts = decode_header(value)
    parts = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            parts.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(part)
    return " ".join(parts)


def _get_email_address(header_value):
    if not header_value:
        return ""
    decoded = _decode_header_value(header_value)
    if "<" in decoded and ">" in decoded:
        return decoded[decoded.index("<") + 1:decoded.index(">")]
    return decoded.strip()


def _parse_imap_message(msg, message_id, user) -> Email:
    subject = _decode_header_value(msg.get("Subject", ""))
    from_addr = _get_email_address(msg.get("From", ""))
    to_addr = _get_email_address(msg.get("To", ""))

    try:
        received_at = parsedate_to_datetime(msg.get("Date", ""))
        if timezone.is_naive(received_at):
            received_at = timezone.make_aware(received_at)
    except Exception:
        received_at = timezone.now()

    body_text = ""
    body_html = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if part.get("Content-Disposition") is not None:
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if content_type == "text/plain" and not body_text:
                body_text = text
            elif content_type == "text/html" and not body_html:
                body_html = text
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body_text = payload.decode(charset, errors="replace")

    return Email.objects.create(
        user=user,
        message_id=message_id,
        from_address=from_addr,
        to_address=to_addr,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        received_at=received_at,
        status=Email.Status.RECEIVED,
        raw_payload={"source": "imap"},
    )


def _process_attachments(msg, email_obj):
    if not msg.is_multipart():
        return

    for part in msg.walk():
        disposition = part.get("Content-Disposition")
        if disposition is None or "attachment" not in disposition.lower():
            continue

        filename = part.get_filename()
        if filename:
            filename = _decode_header_value(filename)
        else:
            filename = "attachment"

        content_type = part.get_content_type()
        payload = part.get_payload(decode=True)
        if not payload:
            continue

        att = Attachment(
            email=email_obj,
            filename=filename,
            content_type=content_type,
            size=len(payload),
        )
        att.file.save(filename, ContentFile(payload), save=False)
        att.save()

        ProcessingLog.objects.create(
            email=email_obj,
            level=ProcessingLog.Level.INFO,
            message=f"Attachment saved: {filename} ({content_type}, {len(payload)} bytes)",
        )


def _process_pdf(email_obj, attachment):
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
            email=email_obj,
            level=ProcessingLog.Level.INFO,
            message=f"PDF processed: {attachment.filename} ({attachment.page_count} pages)",
        )
    except Exception as e:
        attachment.status = Attachment.Status.FAILED
        attachment.error_message = str(e)
        attachment.save(update_fields=["status", "error_message"])
