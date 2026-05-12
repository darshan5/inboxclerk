import json
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import UserSettings
from automations.engine import run_automations
from mail.models import Email, ProcessingLog
from mail.services.ai_extractor import extract_with_ai
from mail.services.email_parser import parse_resend_inbound, process_email

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    emails = Email.objects.filter(user=request.user)

    status_filter = request.GET.get("status")
    search = request.GET.get("search", "").strip()

    if status_filter:
        emails = emails.filter(status=status_filter)
    if search:
        emails = emails.filter(
            Q(subject__icontains=search)
            | Q(from_address__icontains=search)
            | Q(body_text__icontains=search)
        )

    stats = {
        "total": Email.objects.filter(user=request.user).count(),
        "received": Email.objects.filter(user=request.user, status="received").count(),
        "processing": Email.objects.filter(user=request.user, status="processing").count(),
        "processed": Email.objects.filter(user=request.user, status="processed").count(),
        "failed": Email.objects.filter(user=request.user, status="failed").count(),
    }

    return render(request, "mail/dashboard.html", {
        "emails": emails[:50],
        "stats": stats,
        "status_filter": status_filter or "",
        "search": search,
    })


@login_required
def email_detail(request, email_id):
    email = get_object_or_404(Email, id=email_id, user=request.user)
    attachments = email.attachments.all()
    logs = email.logs.all()[:20]
    executions = email.automation_executions.select_related("rule").all()[:20]

    return render(request, "mail/email_detail.html", {
        "email": email,
        "attachments": attachments,
        "logs": logs,
        "executions": executions,
    })


@login_required
@require_POST
def reprocess_email(request, email_id):
    email = get_object_or_404(Email, id=email_id, user=request.user)
    process_email(email)

    user_settings = getattr(request.user, "settings", None)
    if user_settings and user_settings.ai_extraction_enabled:
        extract_with_ai(email, custom_prompt=user_settings.ai_extraction_prompt)

    run_automations(email)
    return JsonResponse({"status": "ok", "email_status": email.status})


@csrf_exempt
@require_POST
def resend_webhook(request):
    if not _verify_resend_signature(request):
        logger.warning("Invalid Resend webhook signature")
        return JsonResponse({"error": "Invalid signature"}, status=401)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    event_type = payload.get("type", "")
    if event_type != "email.received":
        return JsonResponse({"status": "ignored", "event": event_type})

    email_data = payload.get("data", {})
    to_addresses = email_data.get("to", [])
    if isinstance(to_addresses, str):
        to_addresses = [to_addresses]

    user = None
    user_settings = None
    for addr in to_addresses:
        try:
            user_settings = UserSettings.objects.get(resend_inbound_address=addr)
            user = user_settings.user
            break
        except UserSettings.DoesNotExist:
            continue

    if not user:
        logger.warning("No user found for inbound addresses: %s", to_addresses)
        return JsonResponse({"error": "Unknown recipient"}, status=404)

    email = parse_resend_inbound(email_data, user)
    process_email(email)

    if user_settings.ai_extraction_enabled:
        extract_with_ai(email, custom_prompt=user_settings.ai_extraction_prompt)

    run_automations(email)

    return JsonResponse({"status": "ok", "email_id": email.id})


def _verify_resend_signature(request):
    import hashlib
    import hmac

    secret = settings.RESEND_WEBHOOK_SECRET
    if not secret:
        return True

    signature = request.headers.get("resend-signature", "")
    if not signature:
        return False

    expected = hmac.new(
        secret.encode(), request.body, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected)
