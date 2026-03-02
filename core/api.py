from ninja import NinjaAPI, ModelSchema, Schema, Form
from .models import Project, Node, Question
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse
from .services import create_node_with_embedding, vector_search, embed_question

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
        elements.append(
            {"data": {"id": str(node.id), "label": node.title, "type": "node"}}
        )

        # Add questions for this node
        questions = node.questions.all()
        for q in questions:
            elements.append(
                {
                    "data": {
                        "id": f"q_{q.id}",
                        "label": q.text[:50] + "..." if len(q.text) > 50 else q.text,
                        "type": "question",
                        "resolved": q.is_resolved,
                    }
                }
            )

        # Add edges between questions in the same node
        if len(questions) > 1:
            q_list = list(questions)
            for i in range(len(q_list)):
                for j in range(i + 1, len(q_list)):
                    elements.append(
                        {
                            "data": {
                                "id": f"eq_{q_list[i].id}_{q_list[j].id}",
                                "source": f"q_{q_list[i].id}",
                                "target": f"q_{q_list[j].id}",
                                "type": "question_edge",
                            }
                        }
                    )

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


class NodeMoveSchema(Schema):
    project_id: int


@api.post("/nodes/{node_id}/move")
def move_node(request, node_id: int, payload: NodeMoveSchema = Form(...)):
    node = get_object_or_404(Node, id=node_id)
    project = get_object_or_404(Project, id=payload.project_id)
    node.project = project
    node.save()

    response = HttpResponse()
    response["HX-Redirect"] = f"/nodes/{node.id}/"
    return response


class QuestionAnswerSchema(Schema):
    answer: str


@api.post("/questions/{question_id}/answer")
def answer_question(
    request, question_id: int, payload: QuestionAnswerSchema = Form(...)
):
    question = get_object_or_404(Question, id=question_id)
    question.answer = payload.answer
    question.save()

    embed_question(question)

    response = HttpResponse()
    response["HX-Redirect"] = f"/questions/{question.id}/"
    return response


@api.post("/questions/{question_id}/resolve")
def resolve_question(request, question_id: int):
    question = get_object_or_404(Question, id=question_id)
    question.is_resolved = True
    question.save()

    embed_question(question)

    response = HttpResponse()
    response["HX-Redirect"] = f"/questions/{question.id}/"
    return response
