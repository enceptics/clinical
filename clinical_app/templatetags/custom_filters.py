from django import template

register = template.Library()

@register.filter
def underscore_to_space(value):
    """
    Replaces underscores with spaces and capitalizes the first letter of each word.
    For example: "receptionist_admin" becomes "Receptionist Admin".
    """
    if isinstance(value, str):
        # Replace underscores with spaces, then title case each word
        return value.replace('_', ' ').title()
    return value

# You can keep other custom filters here if you have them, e.g., 'multiply'
@register.filter
def multiply(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''