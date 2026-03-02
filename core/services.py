import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from .models import Node, Project, Question
import re

# Initialize the ChromaDB client mapped to a local directory
chroma_client = chromadb.PersistentClient(path="./chroma_db")

# Use local LMStudio for embeddings via OpenAI-compatible API
embedding_gemma = OpenAIEmbeddingFunction(
    api_key="lm-studio",
    api_base="http://127.0.0.1:1234/v1",
    model_name="text-embedding-embeddinggemma-300m",
)


def get_nodes_collection():
    return chroma_client.get_or_create_collection(
        name="nodes", embedding_function=embedding_gemma
    )


def get_questions_collection():
    return chroma_client.get_or_create_collection(
        name="questions", embedding_function=embedding_gemma
    )


def embed_question(question: Question):
    collection = get_questions_collection()

    full_text = f"Question: {question.text}"
    if question.answer:
        full_text += f"\n\nAnswer: {question.answer}"

    collection.upsert(
        documents=[full_text],
        ids=[str(question.id)],
        metadatas=[
            {
                "node_id": question.node.id,
                "project_id": question.node.project.id,
                "is_resolved": question.is_resolved,
            }
        ],
    )


def process_links(node):
    # Find all occurrences of [[Title]]
    titles = set(re.findall(r"\[\[(.*?)\]\]", node.content))
    # We'll just add new ones to avoid clearing manual links from dropdown
    for title in titles:
        linked_node = Node.objects.filter(title=title).first()
        if linked_node:
            node.links.add(linked_node)


def process_questions(node):
    # Find all occurrences of [? Question ?]
    questions_text = set(re.findall(r"\[\?(.*?)\?\]", node.content))
    for qt in questions_text:
        question_text = qt.strip()
        if question_text:
            question, created = Question.objects.get_or_create(
                node=node, text=question_text
            )
            if created:
                embed_question(question)


def create_node_with_embedding(project: Project, title: str, content: str) -> Node:
    # Save to Django database
    node = Node.objects.create(project=project, title=title, content=content)

    # Process wiki links
    process_links(node)

    # Process questions
    process_questions(node)

    # Upsert to ChromaDB
    collection = get_nodes_collection()

    # Combine title and content for embedding text
    full_text = f"Title: {title}\n\nContent: {content}"

    collection.upsert(
        documents=[full_text],
        ids=[str(node.id)],
        metadatas=[{"project_id": project.id, "title": title}],
    )

    return node


def vector_search(
    query: str, project_id: int = None, n_results: int = 50
) -> list[dict]:
    if not query.strip():
        return []

    node_collection = get_nodes_collection()
    question_collection = get_questions_collection()

    kwargs = {"query_texts": [query], "n_results": n_results}

    if project_id is not None:
        kwargs["where"] = {"project_id": project_id}

    node_results = node_collection.query(**kwargs)
    question_results = question_collection.query(**kwargs)

    unique_nodes = {}

    if node_results and node_results.get("ids") and node_results["ids"][0]:
        for idx, node_id_str in enumerate(node_results["ids"][0]):
            title = node_results["metadatas"][0][idx].get("title", "Unknown Title")
            distance = None
            if (
                "distances" in node_results
                and node_results["distances"]
                and len(node_results["distances"][0]) > idx
            ):
                distance = node_results["distances"][0][idx]
            unique_nodes[node_id_str] = {
                "id": node_id_str,
                "title": title,
                "score": distance,
            }

    if question_results and question_results.get("ids") and question_results["ids"][0]:
        # Collect node IDs from question metadata
        q_node_ids = []
        for metadata in question_results["metadatas"][0]:
            if "node_id" in metadata:
                q_node_ids.append(str(metadata["node_id"]))

        # Fetch titles for these node IDs
        nodes = Node.objects.filter(id__in=q_node_ids).values("id", "title")
        node_title_map = {str(n["id"]): n["title"] for n in nodes}

        for idx, metadata in enumerate(question_results["metadatas"][0]):
            if "node_id" not in metadata:
                continue

            node_id_str = str(metadata["node_id"])
            distance = None
            if (
                "distances" in question_results
                and question_results["distances"]
                and len(question_results["distances"][0]) > idx
            ):
                distance = question_results["distances"][0][idx]

            if node_id_str in unique_nodes:
                if (
                    distance is not None
                    and unique_nodes[node_id_str]["score"] is not None
                ):
                    if distance < unique_nodes[node_id_str]["score"]:
                        unique_nodes[node_id_str]["score"] = distance
            else:
                title = node_title_map.get(node_id_str, "Unknown Title")
                unique_nodes[node_id_str] = {
                    "id": node_id_str,
                    "title": title,
                    "score": distance,
                }

    nodes_result = list(unique_nodes.values())

    # Sort by score ascending (lower distance is better)
    def sort_key(n):
        return n["score"] if n["score"] is not None else float("inf")

    nodes_result.sort(key=sort_key)

    return nodes_result[:n_results]
