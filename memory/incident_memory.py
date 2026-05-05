"""
Incident memory — long-term memory for the Citation Agent.

LEARNING — Types of Agent Memory:

SHORT-TERM MEMORY (in-context):
  The list of messages in the current conversation.
  Built into LangGraph automatically — every tool call and response is stored
  in the messages list and passed to the LLM each turn.
  Limitation: lost when the session ends. Limited by context window size.

LONG-TERM MEMORY (vector store):
  Past incidents stored as embeddings in ChromaDB.
  Persists across sessions. Searched semantically to find similar past cases.
  This is what we build here — an "incident history" the agent can query.

WHY LONG-TERM MEMORY MATTERS FOR SRE:
  "Has this happened before?"
  "What did we do last time nginx OOMKilled?"
  Without memory: agent re-diagnoses from scratch every time.
  With memory: agent retrieves past resolution and applies it faster.

ANALOGY:
  Short-term memory = your working memory right now
  Long-term memory  = your notebook of past incidents you can look up
"""

import os
import json
from datetime import datetime
from pathlib import Path
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from dotenv import load_dotenv

load_dotenv()

INCIDENT_COLLECTION = "past_incidents"
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")


def get_embeddings():
    return OllamaEmbeddings(
        model=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )


def get_incident_store() -> Chroma:
    """
    Get or create the incident memory vector store.

    LEARNING — Multiple ChromaDB collections:
    ChromaDB supports multiple collections in the same persist directory.
    Phase 2 uses 'sre_logs' collection for log chunks.
    Phase 3 adds 'past_incidents' collection for incident history.
    Each collection has its own embedding space — they don't interfere.
    """
    return Chroma(
        collection_name=INCIDENT_COLLECTION,
        embedding_function=get_embeddings(),
        persist_directory=CHROMA_PERSIST_DIR,
    )


def store_incident(service: str, symptom: str, root_cause: str, resolution: str) -> str:
    """
    Store a resolved incident in long-term memory.

    LEARNING — What to store:
    We embed a natural language description of the incident so it can be
    retrieved semantically later. The full details go in metadata.

    The text we embed is a summary (what happened + how it was fixed).
    The metadata holds the structured fields for display.
    """
    store = get_incident_store()

    incident_id = f"INC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    timestamp = datetime.now().isoformat()

    # LEARNING: The text we embed is what drives retrieval.
    # Write it to be semantically rich — include symptom + cause + resolution.
    embed_text = f"{service} incident: {symptom}. Root cause: {root_cause}. Resolution: {resolution}"

    doc = Document(
        page_content=embed_text,
        metadata={
            "incident_id": incident_id,
            "service": service,
            "symptom": symptom,
            "root_cause": root_cause,
            "resolution": resolution,
            "timestamp": timestamp,
        }
    )

    store.add_documents([doc])
    return incident_id


def search_similar_incidents(query: str, k: int = 3) -> list[dict]:
    """
    Search past incidents for cases similar to the current query.

    LEARNING — Semantic incident search:
    "nginx keeps dying" will find the OOMKilled incident even though
    those exact words weren't used in the stored incident — because
    the embeddings capture meaning, not keywords.
    """
    store = get_incident_store()
    results = store.similarity_search_with_score(query, k=k)

    return [
        {
            "incident_id": doc.metadata.get("incident_id"),
            "service": doc.metadata.get("service"),
            "symptom": doc.metadata.get("symptom"),
            "root_cause": doc.metadata.get("root_cause"),
            "resolution": doc.metadata.get("resolution"),
            "timestamp": doc.metadata.get("timestamp"),
            "similarity_score": round(float(score), 3),
        }
        for doc, score in results
    ]


def seed_past_incidents():
    """
    Seed the incident store with historical incidents for demo purposes.

    LEARNING — Seeding:
    In a real system, incidents would accumulate naturally over time.
    For learning, we pre-populate a few so the agent has something to retrieve.
    """
    store = get_incident_store()

    # Check if already seeded
    if store._collection.count() > 0:
        return

    historical_incidents = [
        {
            "service": "nginx",
            "symptom": "OOMKilled repeatedly, memory at 512MB limit",
            "root_cause": "Memory limit too low for traffic volume, no memory leak detected",
            "resolution": "Increased memory limit to 1Gi, added memory alerting at 80%",
        },
        {
            "service": "worker",
            "symptom": "Crash loop, exit code 1, cannot connect to database",
            "root_cause": "Postgres max_connections (100) exhausted by idle connections from app-server",
            "resolution": "Killed idle postgres connections, restarted worker, added PgBouncer",
        },
        {
            "service": "app-server",
            "symptom": "CPU at 95%, p99 latency 8000ms, SLO breach",
            "root_cause": "Inefficient SQL query in /api/reports endpoint causing full table scan",
            "resolution": "Added index on reports.created_at, latency dropped to 120ms",
        },
    ]

    for incident in historical_incidents:
        store_incident(**incident)

    print(f"Seeded {len(historical_incidents)} historical incidents into memory")
