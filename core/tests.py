from django.test import TestCase, Client
from django.urls import reverse
from .models import Project, Node


class KnowledgeBaseTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.project = Project.objects.create(
            name="Test Project", description="Test Description"
        )
        self.node1 = Node.objects.create(
            project=self.project, title="Node 1", content="Content 1"
        )
        self.node2 = Node.objects.create(
            project=self.project, title="Node 2", content="Content 2"
        )

    def test_project_list_view(self):
        response = self.client.get(reverse("project_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Project")

    def test_project_create_view(self):
        response = self.client.post(
            reverse("project_create"),
            {"name": "New Project", "description": "New Desc"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Project.objects.filter(name="New Project").exists())
        self.assertContains(response, "New Project")

    def test_project_detail_view(self):
        response = self.client.get(reverse("project_detail", args=[self.project.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Project")
        self.assertContains(response, "Node 1")

    def test_node_create_view(self):
        response = self.client.post(
            reverse("node_create", args=[self.project.pk]),
            {"title": "New Node", "content": "New Node Content"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Node.objects.filter(title="New Node").exists())
        self.assertContains(response, "New Node")

    def test_node_detail_view(self):
        response = self.client.get(reverse("node_detail", args=[self.node1.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Node 1")

    def test_node_update_view(self):
        response = self.client.post(
            reverse("node_update", args=[self.node1.pk]),
            {"title": "Updated Node 1", "content": "Updated Content 1"},
        )
        self.assertEqual(response.status_code, 200)
        self.node1.refresh_from_db()
        self.assertEqual(self.node1.title, "Updated Node 1")

    def test_node_add_link_view(self):
        response = self.client.post(
            reverse("node_add_link", args=[self.node1.pk]),
            {"target_node_id": self.node2.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.node1.links.filter(pk=self.node2.pk).exists())

    def test_wikilinks_processing(self):
        # Update node2 content to link to node1
        self.node2.content = "Link to [[Node 1]]"
        self.node2.save()
        # Trigger processing via update view (or call process_links directly)
        from .services import process_links

        process_links(self.node2)
        self.assertTrue(self.node2.links.filter(pk=self.node1.pk).exists())

    def test_graph_api_endpoint(self):
        # Link node1 to node2
        self.node1.links.add(self.node2)
        url = f"/api/project/{self.project.id}/graph"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Check if nodes and edges are in the response
        node_ids = [item["data"]["id"] for item in data if "source" not in item["data"]]
        edge_ids = [item["data"]["id"] for item in data if "source" in item["data"]]

        self.assertIn(str(self.node1.id), node_ids)
        self.assertIn(str(self.node2.id), node_ids)
        self.assertIn(f"e{self.node1.id}-{self.node2.id}", edge_ids)

    def test_node_creation_service(self):
        from .services import create_node_with_embedding, get_nodes_collection
        
        node = create_node_with_embedding(self.project, "Embedding Test Node", "Hello world ChromaDB")
        self.assertEqual(node.title, "Embedding Test Node")
        
        # Verify it went into the real ChromaDB collection
        collection = get_nodes_collection()
        results = collection.get(ids=[str(node.id)])
        self.assertTrue(len(results["ids"]) > 0)
        self.assertIn(str(node.id), results["ids"])
        
        # Also clean it up so we don't bloat the real DB with test records
        collection.delete(ids=[str(node.id)])
