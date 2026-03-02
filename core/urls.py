from django.urls import path
from . import views

urlpatterns = [
    path("", views.project_list, name="project_list"),
    path("project/create/", views.project_create, name="project_create"),
    path("project/<int:pk>/", views.project_detail, name="project_detail"),
    path(
        "project/<int:project_pk>/nodes/create/", views.node_create, name="node_create"
    ),
    path("nodes/<int:pk>/", views.node_detail, name="node_detail"),
    path("nodes/<int:pk>/update/", views.node_update, name="node_update"),
    path("nodes/<int:pk>/add-link/", views.node_add_link, name="node_add_link"),
    path("questions/<int:pk>/", views.question_detail, name="question_detail"),
]
