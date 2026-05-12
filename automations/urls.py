from django.urls import path

from automations.views import execution_log, rule_create, rule_delete, rule_edit, rule_list

urlpatterns = [
    path("", rule_list, name="rule_list"),
    path("create/", rule_create, name="rule_create"),
    path("<int:rule_id>/edit/", rule_edit, name="rule_edit"),
    path("<int:rule_id>/delete/", rule_delete, name="rule_delete"),
    path("log/", execution_log, name="execution_log"),
]
