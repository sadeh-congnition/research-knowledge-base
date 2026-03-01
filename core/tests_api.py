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
