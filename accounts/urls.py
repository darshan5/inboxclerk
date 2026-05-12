from django.urls import path

from accounts.views import (
    CustomLoginView,
    CustomLogoutView,
    add_user,
    change_password,
    delete_user,
    settings_view,
)

urlpatterns = [
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", CustomLogoutView.as_view(), name="logout"),
    path("settings/", settings_view, name="settings"),
    path("change-password/", change_password, name="change_password"),
    path("add-user/", add_user, name="add_user"),
    path("delete-user/<int:user_id>/", delete_user, name="delete_user"),
]
