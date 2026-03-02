import re
from django import template
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.utils.html import escape
from core.models import Node, Question

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

    def replace_question(match):
        text = match.group(1).strip()
        question = Question.objects.filter(node=node, text=text).first()
        if question:
            url = reverse("question_detail", args=[question.pk])
            answer_text = (
                escape(question.answer) if question.answer else "No answer yet"
            )
            return (
                f'<span class="question-wrapper">'
                f'<a href="{url}" class="question-link">[? {text} ?]</a>'
                f'<span class="question-bubble">{answer_text}</span>'
                f"</span>"
            )
        return f"[? {text} ?]"

    html = re.sub(r"\[\[(.*?)\]\]", replace_link, content)
    html = re.sub(r"\[\?(.*?)\?\]", replace_question, html)
    return mark_safe(html.replace("\n", "<br>"))
