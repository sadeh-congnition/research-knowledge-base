import re
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from .models import Project, Node

def project_list(request):
    projects = Project.objects.all().order_by('-created_at')
    return render(request, 'core/project_list.html', {'projects': projects})

def project_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        project = Project.objects.create(name=name, description=description)
        # For HTMX, return only the new project card
        return HttpResponse(f"""
            <div class="project-card">
                <h3><a href="/project/{project.id}/">{project.name}</a></h3>
                <p>{project.description}</p>
            </div>
        """)
    return redirect('project_list')

def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    return render(request, 'core/project_detail.html', {'project': project})

def node_create(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        node = Node.objects.create(project=project, title=title, content=content)
        process_links(node)
        # For HTMX, return the new node card
        return HttpResponse(f"""
            <div class="node-card">
                <h4><a href="/nodes/{node.id}/">{node.title}</a></h4>
                <p>{node.content[:100]}...</p>
            </div>
        """)
    return redirect('project_detail', pk=project_pk)

def node_detail(request, pk):
    node = get_object_or_404(Node, pk=pk)
    other_nodes = Node.objects.filter(project=node.project).exclude(pk=pk)
    return render(request, 'core/node_detail.html', {'node': node, 'other_nodes': other_nodes})

def node_update(request, pk):
    node = get_object_or_404(Node, pk=pk)
    if request.method == 'POST':
        node.title = request.POST.get('title')
        node.content = request.POST.get('content')
        node.save()
        process_links(node)
        # HTMX will reload the whole content area via hx-select
        other_nodes = Node.objects.filter(project=node.project).exclude(pk=pk)
        return render(request, 'core/node_detail.html', {'node': node, 'other_nodes': other_nodes})
    return redirect('node_detail', pk=pk)

def node_add_link(request, pk):
    node = get_object_or_404(Node, pk=pk)
    if request.method == 'POST':
        target_node_id = request.POST.get('target_node_id')
        target_node = get_object_or_404(Node, pk=target_node_id)
        node.links.add(target_node)
        # HTMX will reload the whole content area
        other_nodes = Node.objects.filter(project=node.project).exclude(pk=pk)
        return render(request, 'core/node_detail.html', {'node': node, 'other_nodes': other_nodes})
    return redirect('node_detail', pk=pk)

def process_links(node):
    # Find all occurrences of [[Title]]
    titles = set(re.findall(r'\[\[(.*?)\]\]', node.content))
    # We'll just add new ones to avoid clearing manual links from dropdown
    for title in titles:
        linked_node = node.project.nodes.filter(title=title).first()
        if linked_node:
            node.links.add(linked_node)
