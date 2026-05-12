from django.urls import path

from mail.views import dashboard, email_detail, reprocess_email, resend_webhook

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("email/<int:email_id>/", email_detail, name="email_detail"),
    path("email/<int:email_id>/reprocess/", reprocess_email, name="reprocess_email"),
    path("webhook/resend/", resend_webhook, name="resend_webhook"),
]
