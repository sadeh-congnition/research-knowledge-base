import pytest
from model_bakery import baker
from core.models import Project, Node
from ninja.testing import TestClient
from core.api import api

client = TestClient(api)


@pytest.mark.django_db
def test_search_nodes_endpoint():
    project = baker.make(Project)
    baker.make(Node, project=project, title="Alpha Node")
    baker.make(Node, project=project, title="Beta Node")
    baker.make(Node, project=project, title="Gamma Alpha")

    # Search for "Alpha"
    response = client.get(f"/project/{project.id}/nodes/search?q=Alpha")
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Alpha Node" in content
    assert "Gamma Alpha" in content
    assert "Beta Node" not in content

    # Search for "Beta"
    response = client.get(f"/project/{project.id}/nodes/search?q=Beta")
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Beta Node" in content
    assert "Alpha Node" not in content

    # Empty search should return all up to 10
    response = client.get(f"/project/{project.id}/nodes/search?q=")
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Alpha Node" in content
    assert "Beta Node" in content
    assert "Gamma Alpha" in content


@pytest.mark.django_db
def test_delete_node_endpoint():
    project = baker.make(Project)
    node = baker.make(Node, project=project, title="Node to delete")

    # Send DELETE request
    response = client.delete(f"/nodes/{node.id}")

    assert response.status_code == 200
    assert response.get("HX-Redirect") == f"/project/{project.id}/"
    assert not Node.objects.filter(id=node.id).exists()


@pytest.mark.django_db
def test_create_node_endpoint(monkeypatch):
    # Monkeypatch ChromaDB upsert so we don't need the embedding server running
    import core.services as services

    def fake_upsert(**kwargs):  # noqa: ARG001
        pass

    monkeypatch.setattr(
        services,
        "get_nodes_collection",
        lambda: type("C", (), {"upsert": staticmethod(fake_upsert)})(),
    )

    project = baker.make(Project)

    payload = {"title": "Test Video", "content": "Some description text"}
    response = client.post(
        f"/project/{project.id}/nodes",
        json=payload,
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Video"
    assert data["content"] == "Some description text"
    assert Node.objects.filter(id=data["id"]).exists()


@pytest.mark.django_db
def test_vector_search_global():
    # Use real Chromadb to test actual embedding and retrieval (as requested: no monkeypatch)
    from core.services import create_node_with_embedding, get_nodes_collection

    project = baker.make(Project)

    # Create two nodes with very distinct topics
    node1 = create_node_with_embedding(
        project,
        "Global Search Test 1",
        "This node is all about machine learning algorithms",
    )
    node2 = create_node_with_embedding(
        project,
        "Global Search Test 2",
        "This node is all about beautiful UI design principles",
    )

    try:
        # Search for algorithms
        response = client.get("/search?q=machine learning")
        assert response.status_code == 200

        data = response.json()
        assert len(data) >= 1

        # At least one result should be node1
        ids = [item["id"] for item in data]
        assert str(node1.id) in ids

        # Ensure score is returned
        score = [item.get("score") for item in data if item["id"] == str(node1.id)][0]
        assert score is not None
        assert isinstance(score, float)
    finally:
        # Cleanup ChromaDB so we don't bleed into other tests
        collection = get_nodes_collection()
        collection.delete(ids=[str(node1.id), str(node2.id)])


@pytest.mark.django_db
def test_vector_search_project_scoped():
    from core.services import create_node_with_embedding, get_nodes_collection

    project1 = baker.make(Project)
    project2 = baker.make(Project)

    # Same content, different projects
    node1 = create_node_with_embedding(
        project1, "Project 1 Node", "Quantum physics is fascinating"
    )
    node2 = create_node_with_embedding(
        project2, "Project 2 Node", "Quantum physics is fascinating"
    )

    try:
        # Search scoped to project 1
        response = client.get(f"/project/{project1.id}/vector-search?q=Quantum")
        assert response.status_code == 200

        data = response.json()
        ids = [item["id"] for item in data]

        # Should find node1 but NOT node2
        assert str(node1.id) in ids
        assert str(node2.id) not in ids

        # Ensure score is returned
        score = [item.get("score") for item in data if item["id"] == str(node1.id)][0]
        assert score is not None
        assert isinstance(score, float)
    finally:
        # Cleanup
        collection = get_nodes_collection()
        collection.delete(ids=[str(node1.id), str(node2.id)])


@pytest.mark.django_db
def test_vector_search_empty_query():
    # An empty query should return [] without querying ChromaDB at all
    response = client.get("/search?q=")
    assert response.status_code == 200
    assert response.json() == []

    project = baker.make(Project)
    response2 = client.get(f"/project/{project.id}/vector-search?q=   ")
    assert response2.status_code == 200
    assert response2.json() == []


@pytest.mark.django_db
def test_project_graph_with_questions():
    from core.models import Question

    project = baker.make(Project)
    node1 = baker.make(Node, project=project, title="Node 1")
    node2 = baker.make(Node, project=project, title="Node 2")

    # Link nodes
    node1.links.add(node2)

    # Add questions to node 1
    q1 = baker.make(Question, node=node1, text="What is this?")
    q2 = baker.make(Question, node=node1, text="Why is this?")

    response = client.get(f"/project/{project.id}/graph")
    assert response.status_code == 200
    elements = response.json()

    # Check that we have the 2 nodes, 2 questions, 1 node edge, 1 question edge
    assert len(elements) == 6

    # Verify nodes
    node_ids = [el["data"]["id"] for el in elements if el["data"].get("type") == "node"]
    assert str(node1.id) in node_ids
    assert str(node2.id) in node_ids

    # Verify questions
    question_ids = [
        el["data"]["id"] for el in elements if el["data"].get("type") == "question"
    ]
    assert f"q_{q1.id}" in question_ids
    assert f"q_{q2.id}" in question_ids

    # Verify question edge
    question_edges = [
        el for el in elements if el["data"].get("type") == "question_edge"
    ]
    assert len(question_edges) == 1
    edge = question_edges[0]["data"]

    # Combination could be q1->q2 or q2->q1
    sources_targets = {
        (edge["source"], edge["target"]),
        (edge["target"], edge["source"]),
    }
    assert (f"q_{q1.id}", f"q_{q2.id}") in sources_targets


@pytest.mark.django_db
def test_question_embedding():
    from core.services import (
        create_node_with_embedding,
        get_questions_collection,
        get_nodes_collection,
    )
    from core.models import Question

    project = baker.make(Project)
    node = create_node_with_embedding(
        project,
        "Question Node Test",
        "Some text with a [? What is the meaning of life? ?] question in it.",
    )

    # Get the created question
    question = Question.objects.get(node=node, text="What is the meaning of life?")

    collection = get_questions_collection()
    nodes_collection = get_nodes_collection()
    try:
        # 1. Verify embedding upon creation
        results = collection.get(ids=[str(question.id)])
        assert len(results["ids"]) == 1
        assert "Question: What is the meaning of life?" in results["documents"][0]
        assert "Answer:" not in results["documents"][0]

        # 2. Answer the question via API
        response = client.post(
            f"/questions/{question.id}/answer",
            data={"answer": "42"},
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code == 200

        # 3. Verify embedding updated with answer
        results_after = collection.get(ids=[str(question.id)])
        assert len(results_after["ids"]) == 1
        assert "Question: What is the meaning of life?" in results_after["documents"][0]
        assert "Answer: 42" in results_after["documents"][0]

    finally:
        # Cleanup
        collection.delete(ids=[str(question.id)])
        nodes_collection.delete(ids=[str(node.id)])


@pytest.mark.django_db
def test_vector_search_with_questions():
    from core.services import (
        create_node_with_embedding,
        get_nodes_collection,
        get_questions_collection,
    )

    project = baker.make(Project)

    # Create a node that doesn't mention the topic directly, but has a question that does
    node = create_node_with_embedding(
        project,
        "General Discussion",
        "We talked about many things today. [? How does quantum entanglement work? ?]",
    )

    try:
        # Search for quantum entanglement
        response = client.get("/search?q=quantum entanglement")
        assert response.status_code == 200

        data = response.json()
        assert len(data) >= 1

        # The node should be hit because of the embedded question
        ids = [item["id"] for item in data]
        assert str(node.id) in ids

        score = [item.get("score") for item in data if item["id"] == str(node.id)][0]
        assert score is not None
        assert isinstance(score, float)
    finally:
        nodes_collection = get_nodes_collection()
        questions_collection = get_questions_collection()

        # Cleanup ChromaDB
        nodes_collection.delete(ids=[str(node.id)])
        # Fetch the question to delete its embedding
        from core.models import Question

        questions = Question.objects.filter(node=node)
        if questions.exists():
            questions_collection.delete(ids=[str(q.id) for q in questions])
