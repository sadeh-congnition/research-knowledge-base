import pytest
from model_bakery import baker
from core.models import Project, Node
from ninja.testing import TestClient
from core.api import api

@pytest.mark.django_db
def test_search_nodes_endpoint():
    client = TestClient(api)
    project = baker.make(Project)
    baker.make(Node, project=project, title="Alpha Node")
    baker.make(Node, project=project, title="Beta Node")
    baker.make(Node, project=project, title="Gamma Alpha")

    # Search for "Alpha"
    response = client.get(f"/project/{project.id}/nodes/search?q=Alpha")
    assert response.status_code == 200
    content = response.content.decode('utf-8')
    assert "Alpha Node" in content
    assert "Gamma Alpha" in content
    assert "Beta Node" not in content

    # Search for "Beta"
    response = client.get(f"/project/{project.id}/nodes/search?q=Beta")
    assert response.status_code == 200
    content = response.content.decode('utf-8')
    assert "Beta Node" in content
    assert "Alpha Node" not in content

    # Empty search should return all up to 10
    response = client.get(f"/project/{project.id}/nodes/search?q=")
    assert response.status_code == 200
    content = response.content.decode('utf-8')
    assert "Alpha Node" in content
    assert "Beta Node" in content
    assert "Gamma Alpha" in content
