import hmac
import json
import logging
from datetime import date, datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
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
        "today": date.today().isoformat(),
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


@login_required
def compare_pdf(request, attachment_id):
    from mail.models import Attachment
    from mail.services.pdf_compare import compare_processors_from_bytes

    attachment = get_object_or_404(Attachment, id=attachment_id, email__user=request.user)

    if not attachment.is_pdf:
        messages.error(request, "This attachment is not a PDF.")
        return redirect("email_detail", email_id=attachment.email_id)

    content = attachment.file.read()
    results = compare_processors_from_bytes(content)

    return render(request, "mail/pdf_compare.html", {
        "attachment": attachment,
        "email": attachment.email,
        "results": results,
    })


@login_required
@require_POST
def sync_emails_view(request):
    from mail.services.resend_sync import sync_emails

    date_from_str = request.POST.get("date_from", "")
    date_to_str = request.POST.get("date_to", "")

    today = date.today()
    try:
        date_from = datetime.strptime(date_from_str, "%Y-%m-%d").date() if date_from_str else today
    except ValueError:
        date_from = today
    try:
        date_to = datetime.strptime(date_to_str, "%Y-%m-%d").date() if date_to_str else today
    except ValueError:
        date_to = today

    if date_to < date_from:
        date_to = date_from

    result = sync_emails(request.user, date_from, date_to)

    if "error" in result:
        messages.error(request, result["error"])
    else:
        filtered = result.get('filtered', 0)
        parts = [f"{result['synced']} new", f"{result['skipped']} already synced"]
        if filtered:
            parts.append(f"{filtered} filtered out")
        if result['errors']:
            parts.append(f"{result['errors']} errors")
        messages.success(request, f"Sync complete: {', '.join(parts)}.")

    return redirect("dashboard")


@csrf_exempt
@require_POST
def resend_webhook(request, api_key):
    if not settings.WEBHOOK_API_KEY or not hmac.compare_digest(api_key, settings.WEBHOOK_API_KEY):
        logger.warning("Invalid webhook API key")
        return JsonResponse({"error": "Unauthorized"}, status=401)

    if not _verify_svix_signature(request):
        logger.warning("Invalid Resend/Svix webhook signature")
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
        from django.contrib.auth.models import User
        user = User.objects.filter(is_superuser=True).first()
        if user:
            user_settings, _ = UserSettings.objects.get_or_create(user=user)

    if not user:
        logger.warning("No user found for inbound addresses: %s", to_addresses)
        return JsonResponse({"error": "Unknown recipient"}, status=404)

    from mail.services.resend_sync import sync_single_email

    resend_id = email_data.get("id", "")
    if resend_id:
        result = sync_single_email(user, resend_id)
    else:
        email_obj = parse_resend_inbound(email_data, user)
        process_email(email_obj)
        result = {"email_id": email_obj.id}

    if user_settings and user_settings.ai_extraction_enabled:
        email_id = result.get("email_id")
        if email_id:
            try:
                email_obj = Email.objects.get(id=email_id)
                extract_with_ai(email_obj, custom_prompt=user_settings.ai_extraction_prompt)
                run_automations(email_obj)
            except Email.DoesNotExist:
                pass

    return JsonResponse({"status": "ok", **result})


def _verify_svix_signature(request):
    import base64
    import hashlib
    import hmac

    secret = settings.RESEND_WEBHOOK_SECRET
    if not secret:
        return True

    svix_id = request.headers.get("svix-id", "")
    svix_timestamp = request.headers.get("svix-timestamp", "")
    svix_signature = request.headers.get("svix-signature", "")

    if not svix_id or not svix_timestamp or not svix_signature:
        logger.warning("Missing svix headers: id=%s ts=%s sig=%s", bool(svix_id), bool(svix_timestamp), bool(svix_signature))
        return False

    # Svix signs: "{msg_id}.{timestamp}.{body}"
    to_sign = f"{svix_id}.{svix_timestamp}.{request.body.decode()}".encode()

    # Secret comes as "whsec_..." — strip prefix and base64 decode
    secret_bytes = secret
    if secret_bytes.startswith("whsec_"):
        secret_bytes = secret_bytes[6:]
    secret_bytes = base64.b64decode(secret_bytes)

    expected = base64.b64encode(
        hmac.new(secret_bytes, to_sign, hashlib.sha256).digest()
    ).decode()

    # svix-signature can have multiple signatures: "v1,sig1 v1,sig2"
    for sig in svix_signature.split(" "):
        if sig.startswith("v1,"):
            sig_value = sig[3:]
            if hmac.compare_digest(sig_value, expected):
                return True

    return False
