from django.contrib import admin
from .models import Project, Node


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name", "description")


@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "created_at")
    list_filter = ("project",)
    search_fields = ("title", "content")
    filter_horizontal = ("links",)
