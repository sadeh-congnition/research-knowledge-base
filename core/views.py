from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from .models import Project, Node, Question


def project_list(request):
    projects = Project.objects.all().order_by("-created_at")
    return render(request, "core/project_list.html", {"projects": projects})


def project_create(request):
    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        project = Project.objects.create(name=name, description=description)
        # For HTMX, return only the new project card
        return HttpResponse(f"""
            <div class="project-card">
                <h3><a href="/project/{project.id}/">{project.name}</a></h3>
                <p>{project.description}</p>
            </div>
        """)
    return redirect("project_list")


def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    open_questions = Question.objects.filter(
        node__project=project, is_resolved=False
    ).order_by("-created_at")
    return render(
        request,
        "core/project_detail.html",
        {"project": project, "open_questions": open_questions},
    )


def node_create(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if request.method == "POST":
        title = request.POST.get("title")
        content = request.POST.get("content")

        from .services import create_node_with_embedding

        node = create_node_with_embedding(project, title, content)

        # For HTMX, return the new node card
        return HttpResponse(f"""
            <div class="node-card">
                <h4><a href="/nodes/{node.id}/">{node.title}</a></h4>
                <p>{node.content[:100]}...</p>
            </div>
        """)
    return redirect("project_detail", pk=project_pk)


def get_projects_for_node(node):
    projects = list(Project.objects.all().order_by("-created_at"))
    for p in projects:
        p.is_current = p.id == node.project.id
    return projects


def node_detail(request, pk):
    node = get_object_or_404(Node, pk=pk)
    other_nodes = Node.objects.filter(project=node.project).exclude(pk=pk)
    projects = get_projects_for_node(node)
    return render(
        request,
        "core/node_detail.html",
        {"node": node, "other_nodes": other_nodes, "projects": projects},
    )


def node_update(request, pk):
    node = get_object_or_404(Node, pk=pk)
    if request.method == "POST":
        node.title = request.POST.get("title")
        node.content = request.POST.get("content")
        node.save()
        from .services import process_links, process_questions

        process_links(node)
        process_questions(node)
        # HTMX will reload the whole content area via hx-select
        other_nodes = Node.objects.filter(project=node.project).exclude(pk=pk)
        projects = get_projects_for_node(node)
        return render(
            request,
            "core/node_detail.html",
            {"node": node, "other_nodes": other_nodes, "projects": projects},
        )
    return redirect("node_detail", pk=pk)


def node_add_link(request, pk):
    node = get_object_or_404(Node, pk=pk)
    if request.method == "POST":
        target_node_id = request.POST.get("target_node_id")
        target_node = get_object_or_404(Node, pk=target_node_id)
        node.links.add(target_node)
        # HTMX will reload the whole content area
        other_nodes = Node.objects.filter(project=node.project).exclude(pk=pk)
        projects = get_projects_for_node(node)
        return render(
            request,
            "core/node_detail.html",
            {"node": node, "other_nodes": other_nodes, "projects": projects},
        )
    return redirect("node_detail", pk=pk)


def question_detail(request, pk):
    question = get_object_or_404(Question, pk=pk)
    return render(request, "core/question_detail.html", {"question": question})
