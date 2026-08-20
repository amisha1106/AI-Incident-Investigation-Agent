"""
ChromaDB vectorstore for historical incident retrieval.
Uses all-MiniLM-L6-v2 embeddings (free, local, no API calls).
"""

import json
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
from loguru import logger
from config import CHROMA_DB_PATH, INCIDENTS_DIR, RAG_COLLECTION_NAME, RAG_TOP_K, EMBEDDING_MODEL


def _build_incident_document(incident: dict) -> str:
    """Convert incident dict to a rich text document for embedding."""
    return (
        f"Incident ID: {incident['id']}\n"
        f"Date: {incident['date']}\n"
        f"Title: {incident['title']}\n"
        f"Service: {incident['service']}\n"
        f"Root Cause: {incident['root_cause']}\n"
        f"Resolution: {incident['resolution']}\n"
        f"Impact: {incident['impact']}\n"
        f"Signals: {', '.join(incident.get('signals', []))}\n"
        f"Tags: {', '.join(incident.get('tags', []))}"
    )


def get_vectorstore() -> chromadb.Collection:
    """Get or create the ChromaDB collection."""
    CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DB_PATH))

    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )

    collection = client.get_or_create_collection(
        name=RAG_COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    return collection


def ingest_historical_incidents(force: bool = False) -> int:
    """
    Load historical incidents from JSON and ingest into ChromaDB.
    Skips if already populated unless force=True.
    Returns number of documents ingested.
    """
    collection = get_vectorstore()

    if collection.count() > 0 and not force:
        logger.info(f"Vectorstore already has {collection.count()} incidents, skipping ingest.")
        return collection.count()

    incidents_file = INCIDENTS_DIR / "historical_incidents.json"
    if not incidents_file.exists():
        logger.warning("No historical incidents file found. Run data seeder first.")
        return 0

    incidents = json.loads(incidents_file.read_text())

    docs = [_build_incident_document(inc) for inc in incidents]
    ids = [inc["id"] for inc in incidents]
    metadatas = [
        {
            "date": inc["date"],
            "service": inc["service"],
            "title": inc["title"],
            "duration_minutes": inc.get("duration_minutes", 0),
            "tags": ",".join(inc.get("tags", [])),
        }
        for inc in incidents
    ]

    # Upsert (handles re-runs gracefully)
    collection.upsert(documents=docs, ids=ids, metadatas=metadatas)
    logger.info(f"Ingested {len(docs)} historical incidents into ChromaDB.")
    return len(docs)


def retrieve_similar_incidents(query: str, top_k: int = RAG_TOP_K) -> list[dict]:
    """
    Semantic search over historical incidents.
    Returns top_k most similar incidents with metadata.
    """
    collection = get_vectorstore()

    if collection.count() == 0:
        logger.warning("Vectorstore empty. Ingesting incidents now...")
        ingest_historical_incidents()

    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    retrieved = []
    for i, doc in enumerate(results["documents"][0]):
        similarity = round(1 - results["distances"][0][i], 3)
        retrieved.append({
            "document": doc,
            "metadata": results["metadatas"][0][i],
            "similarity_score": similarity,
        })

    logger.info(f"RAG retrieved {len(retrieved)} similar incidents for query: '{query[:60]}...'")
    return retrieved
