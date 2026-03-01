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
