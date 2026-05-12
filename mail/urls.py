from django.urls import path

from mail.views import compare_pdf, dashboard, email_detail, reprocess_email, resend_webhook, sync_emails_view

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("sync/", sync_emails_view, name="sync_emails"),
    path("email/<int:email_id>/", email_detail, name="email_detail"),
    path("email/<int:email_id>/reprocess/", reprocess_email, name="reprocess_email"),
    path("attachment/<int:attachment_id>/compare/", compare_pdf, name="compare_pdf"),
    path("webhook/resend/<str:api_key>/", resend_webhook, name="resend_webhook"),
]
