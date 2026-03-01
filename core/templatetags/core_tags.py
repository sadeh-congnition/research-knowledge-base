import re
from django import template
from django.utils.safestring import mark_safe
from django.urls import reverse
from core.models import Node

register = template.Library()


@register.filter
def wikilinks(node):
    content = node.content

    def replace_link(match):
        title = match.group(1)
        linked_node = Node.objects.filter(title=title).first()
        if linked_node:
            url = reverse("node_detail", args=[linked_node.pk])
            return f'<a href="{url}">[[{title}]]</a>'
        return f"[[{title}]]"

    html = re.sub(r"\[\[(.*?)\]\]", replace_link, content)
    return mark_safe(html.replace("\n", "<br>"))
