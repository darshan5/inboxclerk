from django.urls import path

from accounts.views import CustomLoginView, CustomLogoutView, settings_view

urlpatterns = [
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", CustomLogoutView.as_view(), name="logout"),
    path("settings/", settings_view, name="settings"),
]
