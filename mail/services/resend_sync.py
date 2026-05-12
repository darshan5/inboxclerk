import email as email_lib
import logging
from datetime import date

import requests
from django.conf import settings as django_settings
from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from mail.models import Attachment, Email, ProcessingLog
from mail.services.pdf_processor import process_pdf_bytes

logger = logging.getLogger(__name__)

BASE_URL = "https://api.resend.com"


def _headers():
    return {"Authorization": f"Bearer {django_settings.RESEND_API_KEY}"}


def sync_emails(user, date_from: date, date_to: date) -> dict:
    api_key = django_settings.RESEND_API_KEY
    if not api_key:
        return {"error": "RESEND_API_KEY not configured on the server."}

    from accounts.models import UserSettings
    user_settings, _ = UserSettings.objects.get_or_create(user=user)
    filter_to = user_settings.sync_filter_to_address.strip().lower()

    try:
        all_emails = _fetch_all_received(date_from, date_to)
    except Exception as e:
        logger.exception("Resend API error")
        return {"error": f"Resend API error: {e}"}

    synced = 0
    skipped = 0
    filtered = 0
    errors = 0

    for email_data in all_emails:
        if filter_to:
            to_list = [addr.lower() for addr in email_data.get("to", [])]
            if filter_to not in to_list:
                filtered += 1
                continue
        try:
            message_id = email_data.get("message_id") or email_data.get("id", "")

            existing = Email.objects.filter(message_id=message_id).first()
            if existing and existing.body_text and existing.body_html:
                skipped += 1
                continue

            detail = _fetch_email_detail(email_data["id"])
            if not detail:
                errors += 1
                continue

            if existing:
                existing.body_text = detail.get("text", "") or ""
                existing.body_html = detail.get("html", "") or ""
                existing.save(update_fields=["body_text", "body_html", "updated_at"])

                # Re-fetch attachments if any had 0 bytes
                if existing.attachments.filter(size=0).exists():
                    existing.attachments.all().delete()
                    _process_attachments_from_raw(detail, existing)
                    for att in existing.attachments.filter(content_type="application/pdf"):
                        _process_pdf(existing, att)

                existing.status = Email.Status.PROCESSED
                existing.save(update_fields=["status", "updated_at"])
                synced += 1
                continue

            email_obj = _create_email(detail, message_id, user)
            _process_attachments_from_raw(detail, email_obj)

            for att in email_obj.attachments.filter(content_type="application/pdf"):
                _process_pdf(email_obj, att)

            email_obj.status = Email.Status.PROCESSED
            email_obj.save(update_fields=["status", "updated_at"])

            ProcessingLog.objects.create(
                email=email_obj,
                level=ProcessingLog.Level.INFO,
                message="Email synced and processed via Resend API",
            )
            synced += 1

        except Exception as e:
            logger.exception("Error processing Resend email %s", email_data.get("id"))
            errors += 1

    return {"synced": synced, "skipped": skipped, "filtered": filtered, "errors": errors}


def sync_single_email(user, resend_id: str) -> dict:
    api_key = django_settings.RESEND_API_KEY
    if not api_key:
        return {"error": "RESEND_API_KEY not configured"}

    try:
        detail = _fetch_email_detail(resend_id)
        if not detail:
            return {"error": "Could not fetch email details"}

        message_id = detail.get("message_id") or resend_id

        if Email.objects.filter(message_id=message_id).exists():
            email_obj = Email.objects.get(message_id=message_id)
            return {"email_id": email_obj.id, "skipped": True}

        email_obj = _create_email(detail, message_id, user)
        _process_attachments_from_raw(detail, email_obj)

        for att in email_obj.attachments.filter(content_type="application/pdf"):
            _process_pdf(email_obj, att)

        email_obj.status = Email.Status.PROCESSED
        email_obj.save(update_fields=["status", "updated_at"])

        ProcessingLog.objects.create(
            email=email_obj,
            level=ProcessingLog.Level.INFO,
            message="Email synced via webhook + Resend API",
        )
        return {"email_id": email_obj.id}

    except Exception as e:
        logger.exception("Error in sync_single_email for %s", resend_id)
        return {"error": str(e)}


def _fetch_all_received(date_from: date, date_to: date) -> list:
    all_emails = []
    params = {"limit": 100}
    has_more = True

    while has_more:
        resp = requests.get(f"{BASE_URL}/emails/receiving", headers=_headers(), params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("data", []):
            created = parse_datetime(item.get("created_at", ""))
            if created:
                item_date = created.date()
                if item_date < date_from:
                    return all_emails
                if item_date <= date_to:
                    all_emails.append(item)

        has_more = data.get("has_more", False)
        if has_more and data.get("data"):
            params["after"] = data["data"][-1]["id"]

    return all_emails


def _fetch_email_detail(email_id: str) -> dict:
    resp = requests.get(f"{BASE_URL}/emails/receiving/{email_id}", headers=_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def _create_email(detail: dict, message_id: str, user) -> Email:
    to_list = detail.get("to", [])
    to_addr = to_list[0] if to_list else ""

    created_at = parse_datetime(detail.get("created_at", ""))
    if not created_at:
        created_at = timezone.now()
    elif timezone.is_naive(created_at):
        created_at = timezone.make_aware(created_at)

    return Email.objects.create(
        user=user,
        message_id=message_id,
        from_address=detail.get("from", ""),
        to_address=to_addr,
        subject=detail.get("subject", "(no subject)"),
        body_text=detail.get("text", "") or "",
        body_html=detail.get("html", "") or "",
        received_at=created_at,
        status=Email.Status.PROCESSING,
        raw_payload={"source": "resend", "resend_id": detail.get("id", "")},
    )


def _process_attachments_from_raw(detail: dict, email_obj: Email):
    raw_info = detail.get("raw", {})
    download_url = raw_info.get("download_url", "") if raw_info else ""

    attachments_meta = detail.get("attachments", [])
    if not attachments_meta:
        return

    if not download_url:
        for att_meta in attachments_meta:
            Attachment.objects.create(
                email=email_obj,
                filename=att_meta.get("filename", "attachment"),
                content_type=att_meta.get("content_type", "application/octet-stream"),
                size=att_meta.get("size", 0),
                status=Attachment.Status.PENDING,
            )
        return

    try:
        resp = requests.get(download_url, timeout=60)
        resp.raise_for_status()
        raw_email = email_lib.message_from_bytes(resp.content)

        for part in raw_email.walk():
            disposition = part.get("Content-Disposition")
            if not disposition or "attachment" not in disposition.lower():
                continue

            filename = part.get_filename() or "attachment"
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

    except Exception as e:
        logger.exception("Error downloading raw email for attachments")
        ProcessingLog.objects.create(
            email=email_obj,
            level=ProcessingLog.Level.ERROR,
            message=f"Failed to download raw email for attachments: {e}",
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
