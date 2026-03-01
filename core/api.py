from ninja import NinjaAPI, ModelSchema, Schema
from .models import Project, Node
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse
from .services import create_node_with_embedding, vector_search

api = NinjaAPI()


class NodeSchema(ModelSchema):
    class Meta:
        model = Node
        fields = ["id", "title"]


class EdgeSchema(Schema):
    # We'll construct edges manually
    source: int
    target: int


@api.get("/search")
def run_global_search(request, q: str = ""):
    return vector_search(query=q, n_results=50)


@api.get("/project/{project_id}/vector-search")
def run_project_search(request, project_id: int, q: str = ""):
    # Ensure project exists
    get_object_or_404(Project, id=project_id)
    return vector_search(query=q, project_id=project_id, n_results=50)


@api.get("/project/{project_id}/graph")
def get_project_graph(request, project_id: int):
    project = get_object_or_404(Project, id=project_id)
    nodes = project.nodes.all()

    elements = []
    # Add nodes
    for node in nodes:
        elements.append({"data": {"id": str(node.id), "label": node.title}})

    # Add edges
    for node in nodes:
        for link in node.links.all():
            elements.append(
                {
                    "data": {
                        "id": f"e{node.id}-{link.id}",
                        "source": str(node.id),
                        "target": str(link.id),
                    }
                }
            )

    return elements


@api.get("/project/{project_id}/nodes/search")
def search_nodes(request, project_id: int, q: str = ""):
    get_object_or_404(Project, id=project_id)
    if q:
        nodes = Node.objects.select_related("project").filter(title__icontains=q)[:10]
    else:
        nodes = Node.objects.select_related("project").all()[:10]
    return render(
        request,
        "core/partials/autocomplete_dropdown.html",
        {"nodes": nodes},
    )


class NodeCreateSchema(Schema):
    title: str
    content: str = ""


class NodeDetailSchema(Schema):
    id: int
    title: str
    content: str


@api.post("/project/{project_id}/nodes", response=NodeDetailSchema)
def create_node(request, project_id: int, payload: NodeCreateSchema):
    project = get_object_or_404(Project, id=project_id)
    node = create_node_with_embedding(project, payload.title, payload.content)
    return node


@api.delete("/nodes/{node_id}")
def delete_node(request, node_id: int):
    node = get_object_or_404(Node, id=node_id)
    project_id = node.project.id
    node.delete()

    response = HttpResponse()
    response["HX-Redirect"] = f"/project/{project_id}/"
    return response
