from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import get_object_or_404, redirect, render

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

    users = User.objects.all().order_by("username") if request.user.is_superuser else []

    return render(request, "accounts/settings.html", {"form": form, "users": users})


@login_required
def change_password(request):
    if request.method != "POST":
        return redirect("settings")

    old_password = request.POST.get("old_password", "")
    new_password1 = request.POST.get("new_password1", "")
    new_password2 = request.POST.get("new_password2", "")

    if not request.user.check_password(old_password):
        messages.error(request, "Current password is incorrect.")
        return redirect("settings")

    if new_password1 != new_password2:
        messages.error(request, "New passwords don't match.")
        return redirect("settings")

    if len(new_password1) < 6:
        messages.error(request, "Password must be at least 6 characters.")
        return redirect("settings")

    request.user.set_password(new_password1)
    request.user.save()
    update_session_auth_hash(request, request.user)
    messages.success(request, "Password updated successfully.")
    return redirect("settings")


@login_required
def add_user(request):
    if not request.user.is_superuser:
        messages.error(request, "Only admins can add users.")
        return redirect("settings")

    if request.method != "POST":
        return redirect("settings")

    username = request.POST.get("username", "").strip()
    email = request.POST.get("email", "").strip()
    password = request.POST.get("password", "")
    is_superuser = request.POST.get("is_superuser") == "on"

    if not username or not password:
        messages.error(request, "Username and password are required.")
        return redirect("settings")

    if User.objects.filter(username=username).exists():
        messages.error(request, f"User '{username}' already exists.")
        return redirect("settings")

    user = User.objects.create_user(username=username, email=email, password=password)
    if is_superuser:
        user.is_superuser = True
        user.is_staff = True
        user.save()

    UserSettings.objects.create(user=user)
    messages.success(request, f"User '{username}' created.")
    return redirect("settings")


@login_required
def delete_user(request, user_id):
    if not request.user.is_superuser:
        messages.error(request, "Only admins can remove users.")
        return redirect("settings")

    if request.method != "POST":
        return redirect("settings")

    target = get_object_or_404(User, id=user_id)
    if target.id == request.user.id:
        messages.error(request, "You can't delete yourself.")
        return redirect("settings")

    username = target.username
    target.delete()
    messages.success(request, f"User '{username}' removed.")
    return redirect("settings")
