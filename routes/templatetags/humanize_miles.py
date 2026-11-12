from django import template

register = template.Library()


@register.filter
def miles(value):
    """1110 becomes 1,110. Empty stays empty."""
    return "" if value is None else f"{value:,}"
