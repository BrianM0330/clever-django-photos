from pathlib import Path

from django import template
from django.conf import settings
from django.utils.html import conditional_escape, format_html
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def dom_id(obj, suffix=None):
    base = f"{obj._meta.model_name}-{obj.pk}"
    return f"{base}-{suffix}" if suffix else base


@register.simple_tag
def inline_svg(filename, css_class="", aria_hidden=True, data_icon=""):
    path = Path(settings.BASE_DIR) / "static" / "images" / filename
    svg = path.read_text()

    attributes = f'class="{conditional_escape(css_class)}"'
    if aria_hidden:
        attributes += ' aria-hidden="true"'
    if data_icon:
        attributes += f' data-icon="{conditional_escape(data_icon)}"'

    return mark_safe(svg.replace("<svg", f"<svg {attributes}", 1))


@register.simple_tag
def pluralize_count(count, singular, plural=""):
    label = plural or f"{singular}s"
    return format_html("{} {}", count, singular if count == 1 else label)
