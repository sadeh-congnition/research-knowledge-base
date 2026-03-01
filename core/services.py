import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from .models import Node, Project
import re

# Initialize the ChromaDB client mapped to a local directory
chroma_client = chromadb.PersistentClient(path="./chroma_db")

# Use local LMStudio for embeddings via OpenAI-compatible API
embedding_gemma = OpenAIEmbeddingFunction(
    api_key="lm-studio",
    api_base="http://127.0.0.1:1234/v1",
    model_name="text-embedding-embeddinggemma-300m"
)

def get_nodes_collection():
    return chroma_client.get_or_create_collection(
        name="nodes",
        embedding_function=embedding_gemma
    )

def process_links(node):
    # Find all occurrences of [[Title]]
    titles = set(re.findall(r"\[\[(.*?)\]\]", node.content))
    # We'll just add new ones to avoid clearing manual links from dropdown
    for title in titles:
        linked_node = node.project.nodes.filter(title=title).first()
        if linked_node:
            node.links.add(linked_node)

def create_node_with_embedding(project: Project, title: str, content: str) -> Node:
    # Save to Django database
    node = Node.objects.create(project=project, title=title, content=content)
    
    # Process wiki links
    process_links(node)
    
    # Upsert to ChromaDB
    collection = get_nodes_collection()
    
    # Combine title and content for embedding text
    full_text = f"Title: {title}\n\nContent: {content}"
    
    collection.upsert(
        documents=[full_text],
        ids=[str(node.id)],
        metadatas=[{"project_id": project.id, "title": title}]
    )
    
    return node


def vector_search(query: str, project_id: int = None, n_results: int = 50) -> list[dict]:
    if not query.strip():
        return []
        
    collection = get_nodes_collection()
    
    kwargs = {
        "query_texts": [query],
        "n_results": n_results
    }
    
    if project_id is not None:
        kwargs["where"] = {"project_id": project_id}
        
    results = collection.query(**kwargs)
    
    if not results or not results["ids"] or not results["ids"][0]:
        return []
        
    nodes_result = []
    # results["ids"][0] is a list of node IDs
    # results["metadatas"][0] is a list of dicts: {"project_id": 1, "title": "Node title"}
    # results["distances"][0] is a list of float distances (lower usually means closer depending on distance metric)
    
    for idx, node_id_str in enumerate(results["ids"][0]):
        title = results["metadatas"][0][idx].get("title", "Unknown Title")
        distance = None
        if "distances" in results and results["distances"] and len(results["distances"][0]) > idx:
            distance = results["distances"][0][idx]
            
        nodes_result.append({
            "id": node_id_str, 
            "title": title,
            "score": distance
        })
        
    return nodes_result
