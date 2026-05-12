import json
import logging

from django.conf import settings as django_settings

from mail.models import Email, ProcessingLog

logger = logging.getLogger(__name__)


def extract_with_ai(email: Email, custom_prompt: str = "") -> dict:
    api_key = django_settings.ANTHROPIC_API_KEY
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set, skipping AI extraction")
        return {}

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    email_content = _build_email_context(email)
    prompt = custom_prompt or (
        "Extract key structured information from this email and its attachments. "
        "Return a JSON object with relevant fields such as: dates, amounts, names, "
        "addresses, invoice numbers, account numbers, and any other important data."
    )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": f"{prompt}\n\n---\n\n{email_content}",
            }
        ],
    )

    response_text = message.content[0].text

    try:
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            extracted = json.loads(response_text[start:end])
        else:
            extracted = {"raw_response": response_text}
    except json.JSONDecodeError:
        extracted = {"raw_response": response_text}

    email.extracted_data = extracted
    email.save(update_fields=["extracted_data", "updated_at"])

    ProcessingLog.objects.create(
        email=email,
        level=ProcessingLog.Level.INFO,
        message="AI extraction completed",
        details={"model": "claude-sonnet-4-6", "fields_extracted": list(extracted.keys())},
    )

    return extracted


def _build_email_context(email: Email) -> str:
    parts = [
        f"From: {email.from_address}",
        f"To: {email.to_address}",
        f"Subject: {email.subject}",
        f"Date: {email.received_at}",
        "",
        "Body:",
        email.body_text or "(no text body)",
    ]

    for attachment in email.attachments.filter(status="processed"):
        parts.append(f"\n--- Attachment: {attachment.filename} ---")
        if attachment.extracted_text:
            parts.append(attachment.extracted_text[:10000])

    return "\n".join(parts)
