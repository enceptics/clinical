# clinical/templatetags/clinical_filters.py
from django import template
import json

register = template.Library()

@register.filter(name='json_pretty')
def json_pretty(value):
    try:
        return json.dumps(json.loads(value), indent=2)
    except (TypeError, json.JSONDecodeError):
        return value # Return original value if it's not valid JSON