import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from automations.forms import AutomationRuleForm
from automations.models import AutomationExecution, AutomationRule


@login_required
def rule_list(request):
    rules = AutomationRule.objects.filter(user=request.user)
    return render(request, "automations/rule_list.html", {"rules": rules})


@login_required
def rule_create(request):
    if request.method == "POST":
        form = AutomationRuleForm(request.POST)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.user = request.user
            rule.save()
            messages.success(request, f"Rule '{rule.name}' created.")
            return redirect("rule_list")
    else:
        form = AutomationRuleForm()

    return render(request, "automations/rule_form.html", {"form": form, "title": "Create Rule"})


@login_required
def rule_edit(request, rule_id):
    rule = get_object_or_404(AutomationRule, id=rule_id, user=request.user)

    if request.method == "POST":
        form = AutomationRuleForm(request.POST, instance=rule)
        if form.is_valid():
            form.save()
            messages.success(request, f"Rule '{rule.name}' updated.")
            return redirect("rule_list")
    else:
        initial = {"action_config": json.dumps(rule.action_config, indent=2)}
        form = AutomationRuleForm(instance=rule, initial=initial)

    return render(request, "automations/rule_form.html", {"form": form, "title": "Edit Rule"})


@login_required
def rule_delete(request, rule_id):
    rule = get_object_or_404(AutomationRule, id=rule_id, user=request.user)
    if request.method == "POST":
        rule.delete()
        messages.success(request, "Rule deleted.")
    return redirect("rule_list")


@login_required
def execution_log(request):
    executions = AutomationExecution.objects.filter(
        rule__user=request.user
    ).select_related("rule", "email")[:100]
    return render(request, "automations/execution_log.html", {"executions": executions})
