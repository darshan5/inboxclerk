import logging
import re

from automations.models import AutomationExecution, AutomationRule
from mail.models import Email
from mail.services.ai_extractor import extract_with_ai

logger = logging.getLogger(__name__)


def run_automations(email: Email):
    rules = AutomationRule.objects.filter(user=email.user, is_active=True)

    for rule in rules:
        try:
            if _matches(rule, email):
                _execute(rule, email)
        except Exception as e:
            logger.exception("Error running rule %s on email %s", rule.id, email.id)
            AutomationExecution.objects.create(
                rule=rule,
                email=email,
                status=AutomationExecution.Status.FAILED,
                error_message=str(e),
            )


def _get_field_value(rule: AutomationRule, email: Email) -> str:
    field_map = {
        AutomationRule.TriggerField.SENDER: email.from_address,
        AutomationRule.TriggerField.SUBJECT: email.subject,
        AutomationRule.TriggerField.BODY: email.body_text,
        AutomationRule.TriggerField.ATTACHMENT_NAME: " ".join(
            a.filename for a in email.attachments.all()
        ),
        AutomationRule.TriggerField.EXTRACTED_TEXT: " ".join(
            a.extracted_text for a in email.attachments.filter(status="processed")
        ),
    }
    return field_map.get(rule.trigger_field, "")


def _matches(rule: AutomationRule, email: Email) -> bool:
    value = _get_field_value(rule, email).lower()
    pattern = rule.trigger_value.lower()

    match rule.operator:
        case AutomationRule.Operator.CONTAINS:
            return pattern in value
        case AutomationRule.Operator.EQUALS:
            return value == pattern
        case AutomationRule.Operator.STARTS_WITH:
            return value.startswith(pattern)
        case AutomationRule.Operator.ENDS_WITH:
            return value.endswith(pattern)
        case AutomationRule.Operator.REGEX:
            return bool(re.search(rule.trigger_value, _get_field_value(rule, email)))
        case _:
            return False


def _execute(rule: AutomationRule, email: Email):
    action_handlers = {
        AutomationRule.ActionType.LABEL: _action_label,
        AutomationRule.ActionType.EXTRACT: _action_extract,
        AutomationRule.ActionType.WEBHOOK: _action_webhook,
        AutomationRule.ActionType.FORWARD: _action_forward,
        AutomationRule.ActionType.NOTIFY: _action_notify,
    }

    handler = action_handlers.get(rule.action_type)
    if handler:
        result = handler(rule, email)
        AutomationExecution.objects.create(
            rule=rule,
            email=email,
            status=AutomationExecution.Status.SUCCESS,
            result=result or {},
        )
    else:
        AutomationExecution.objects.create(
            rule=rule,
            email=email,
            status=AutomationExecution.Status.SKIPPED,
            error_message=f"Unknown action type: {rule.action_type}",
        )


def _action_label(rule: AutomationRule, email: Email) -> dict:
    label = rule.action_config.get("label", "unlabeled")
    data = email.extracted_data or {}
    labels = data.get("labels", [])
    labels.append(label)
    data["labels"] = labels
    email.extracted_data = data
    email.save(update_fields=["extracted_data", "updated_at"])
    return {"label": label}


def _action_extract(rule: AutomationRule, email: Email) -> dict:
    prompt = rule.action_config.get("prompt", "")
    result = extract_with_ai(email, custom_prompt=prompt)
    return {"extracted_fields": list(result.keys())}


def _action_webhook(rule: AutomationRule, email: Email) -> dict:
    import requests

    url = rule.action_config.get("url", "")
    if not url:
        return {"error": "No webhook URL configured"}

    payload = {
        "email_id": email.id,
        "from": email.from_address,
        "subject": email.subject,
        "extracted_data": email.extracted_data,
    }
    resp = requests.post(url, json=payload, timeout=30)
    return {"status_code": resp.status_code}


def _action_forward(rule: AutomationRule, email: Email) -> dict:
    forward_to = rule.action_config.get("to", "")
    logger.info("Would forward email %s to %s (not implemented yet)", email.id, forward_to)
    return {"forward_to": forward_to, "note": "Forwarding via Resend not yet implemented"}


def _action_notify(rule: AutomationRule, email: Email) -> dict:
    logger.info("Notification for email %s (not implemented yet)", email.id)
    return {"note": "Notification not yet implemented"}
