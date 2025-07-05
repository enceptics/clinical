from django import template

register = template.Library()

@register.filter(name='add_attributes')
def add_attributes(field, css_class):
    """
    Adds a CSS class and optionally a placeholder to a form field.
    Usage: {{ field|add_attributes:"form-control,Username" }}
    If only class is needed: {{ field|add_attributes:"form-control" }}
    """
    attrs = {}
    parts = css_class.split(',')
    if len(parts) > 0:
        attrs['class'] = parts[0].strip()
    if len(parts) > 1:
        attrs['placeholder'] = parts[1].strip()

    return field.as_widget(attrs=attrs)

@register.filter(name='add_class')
def add_class(field, css_class):
    """
    Adds a CSS class to a form field.
    Usage: {{ field|add_class:"form-control" }}
    """
    return field.as_widget(attrs={'class': css_class})

@register.filter(name='add_placeholder')
def add_placeholder(field, placeholder_text):
    """
    Adds a placeholder to a form field.
    Usage: {{ field|add_placeholder:"Enter your username" }}
    """
    return field.as_widget(attrs={'placeholder': placeholder_text})

@register.filter
def multiply(value, arg):
    """
    Multiplies the value by the argument.
    Usage: {{ some_value|multiply:0.2 }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def add(value, arg):
    """
    Adds the argument to the value.
    Usage: {{ some_value|add:1.0 }}
    """
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return ''


