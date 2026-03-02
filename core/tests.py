from django.test import TestCase, Client
from django.urls import reverse
from .models import Project, Node
from ninja.testing import TestClient
from core.api import api


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

    def test_cross_project_wikilinks_processing(self):
        project2 = Project.objects.create(
            name="Project 2", description="Test Description 2"
        )
        node3 = Node.objects.create(
            project=project2, title="Node 3", content="Link to [[Node 1]]"
        )
        from .services import process_links

        process_links(node3)
        self.assertTrue(node3.links.filter(pk=self.node1.pk).exists())

    def test_search_nodes_cross_project(self):
        project2 = Project.objects.create(
            name="Project 2", description="Test Description 2"
        )
        Node.objects.create(project=project2, title="Node 3", content="Content 3")

        import os

        os.environ["NINJA_SKIP_REGISTRY"] = "yes"
        test_client = TestClient(api)
        response = test_client.get(
            f"/project/{self.project.id}/nodes/search", {"q": "Node 3"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Node 3", response.content.decode())
        self.assertIn("[Project 2]", response.content.decode())

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

        node = create_node_with_embedding(
            self.project, "Embedding Test Node", "Hello world ChromaDB"
        )
        self.assertEqual(node.title, "Embedding Test Node")

        # Verify it went into the real ChromaDB collection
        collection = get_nodes_collection()
        results = collection.get(ids=[str(node.id)])
        self.assertTrue(len(results["ids"]) > 0)
        self.assertIn(str(node.id), results["ids"])

        # Also clean it up so we don't bloat the real DB with test records
        collection.delete(ids=[str(node.id)])

    def test_node_move_api(self):
        project2 = Project.objects.create(
            name="Project 2", description="Test Description 2"
        )
        import os

        os.environ["NINJA_SKIP_REGISTRY"] = "yes"
        test_client = TestClient(api)
        response = test_client.post(
            f"/nodes/{self.node1.id}/move",
            {"project_id": project2.id},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["HX-Redirect"], f"/nodes/{self.node1.id}/")

        self.node1.refresh_from_db()
        self.assertEqual(self.node1.project.id, project2.id)

    def test_process_questions(self):
        from .services import process_questions
        from .models import Question

        self.node1.content = "Here is a question [? How to test this? ?] and another [? Why does it work? ?]"
        self.node1.save()
        process_questions(self.node1)

        self.assertEqual(Question.objects.filter(node=self.node1).count(), 2)
        self.assertTrue(Question.objects.filter(text="How to test this?").exists())
        self.assertTrue(Question.objects.filter(text="Why does it work?").exists())

    def test_wikilinks_question_rendering(self):
        from .templatetags.core_tags import wikilinks
        from .models import Question

        self.node1.content = "Answer this: [? What is life? ?]"
        self.node1.save()

        # Test without question created in DB
        rendered = wikilinks(self.node1)
        self.assertIn("[? What is life? ?]", rendered)
        self.assertNotIn("<a href=", rendered)

        # Test with question created
        q = Question.objects.create(node=self.node1, text="What is life?")
        rendered = wikilinks(self.node1)
        expected_url = reverse("question_detail", args=[q.pk])
        self.assertIn(expected_url, rendered)
        self.assertIn(
            f'<a href="{expected_url}" class="question-link">[? What is life? ?]</a>',
            rendered,
        )

    def test_answer_question_endpoint(self):
        from .models import Question

        q = Question.objects.create(node=self.node1, text="What is life?")

        import os

        os.environ["NINJA_SKIP_REGISTRY"] = "yes"
        test_client = TestClient(api)
        response = test_client.post(
            f"/questions/{q.id}/answer",
            {"answer": "42"},
        )
        self.assertEqual(response.status_code, 200)
        q.refresh_from_db()
        self.assertEqual(q.answer, "42")
        self.assertEqual(response["HX-Redirect"], f"/questions/{q.id}/")

    def test_resolve_question_endpoint(self):
        from .models import Question

        q = Question.objects.create(node=self.node1, text="What is life?")

        import os

        os.environ["NINJA_SKIP_REGISTRY"] = "yes"
        test_client = TestClient(api)
        response = test_client.post(f"/questions/{q.id}/resolve")
        self.assertEqual(response.status_code, 200)
        q.refresh_from_db()
        self.assertTrue(q.is_resolved)
        self.assertEqual(response["HX-Redirect"], f"/questions/{q.id}/")

    def test_project_open_questions_view(self):
        from .models import Question

        Question.objects.create(node=self.node1, text="Open Q")
        Question.objects.create(node=self.node1, text="Resolved Q", is_resolved=True)

        response = self.client.get(reverse("project_detail", args=[self.project.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("Open Q", response.content.decode())
        self.assertNotIn("Resolved Q", response.content.decode())
