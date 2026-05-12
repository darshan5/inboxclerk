import json

from django import template

register = template.Library()


@register.filter
def format_json(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, default=str)
    return value
