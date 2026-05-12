from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render

from accounts.forms import LoginForm, UserSettingsForm
from accounts.models import UserSettings


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm


class CustomLogoutView(LogoutView):
    next_page = "/accounts/login/"


@login_required
def settings_view(request):
    user_settings, _ = UserSettings.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = UserSettingsForm(request.POST, instance=user_settings)
        if form.is_valid():
            form.save()
            messages.success(request, "Settings saved successfully.")
            return redirect("settings")
    else:
        form = UserSettingsForm(instance=user_settings)

    return render(request, "accounts/settings.html", {"form": form})
