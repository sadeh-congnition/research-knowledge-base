from ninja import NinjaAPI, ModelSchema, Schema
from typing import List
from .models import Project, Node
from django.shortcuts import get_object_or_404

api = NinjaAPI()

class NodeSchema(ModelSchema):
    class Meta:
        model = Node
        fields = ["id", "title"]

class EdgeSchema(Schema):
    # We'll construct edges manually
    source: int
    target: int

@api.get("/project/{project_id}/graph")
def get_project_graph(request, project_id: int):
    project = get_object_or_404(Project, id=project_id)
    nodes = project.nodes.all()
    
    elements = []
    # Add nodes
    for node in nodes:
        elements.append({
            "data": {"id": str(node.id), "label": node.title}
        })
    
    # Add edges
    for node in nodes:
        for link in node.links.all():
            elements.append({
                "data": {
                    "id": f"e{node.id}-{link.id}",
                    "source": str(node.id),
                    "target": str(link.id)
                }
            })
            
    return elements
