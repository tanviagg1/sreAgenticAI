"""
Vector store skill — builds and queries a ChromaDB index over log files.

LEARNING — RAG pipeline, step by step:

  Step 1: LOAD
    Read raw log files from disk.

  Step 2: CHUNK
    Split logs into smaller pieces. Why?
    - LLMs have context limits — can't fit entire log files
    - Smaller chunks = more precise retrieval
    - Each chunk gets its own embedding (vector)

  Step 3: EMBED
    Convert each chunk to a vector using nomic-embed-text.
    Vectors capture semantic meaning — similar text = similar vectors.

  Step 4: STORE
    Save vectors + original text in ChromaDB (local, on disk).
    This only needs to happen once — ChromaDB persists across runs.

  Step 5: RETRIEVE
    At query time: embed the query, find closest vectors in ChromaDB,
    return the matching log chunks.

This is the foundation of RAG. The retrieved chunks are then passed
to the LLM as context to ground its answer.
"""

import os
from pathlib import Path
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from dotenv import load_dotenv

load_dotenv()

# Where ChromaDB persists its data on disk
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")
LOGS_DIR = Path("mocks/logs")

# Collection name — like a table name in a regular DB
LOG_COLLECTION = "sre_logs"


def get_embeddings():
    """
    LEARNING — Embeddings:
    nomic-embed-text converts text to a 768-dimensional vector.
    It runs locally via Ollama — no external API needed.
    Pull it once with: ollama pull nomic-embed-text

    Why nomic-embed-text?
    - Free, open source, runs on your machine
    - Good quality for technical/code text
    - 768 dimensions = good balance of quality vs speed
    """
    return OllamaEmbeddings(
        model=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )


def load_and_chunk_logs() -> list[Document]:
    """
    Load all log files and split them into chunks for embedding.

    LEARNING — RecursiveCharacterTextSplitter:
    This is the most commonly used splitter. It tries to split on:
      1. Paragraph breaks (double newline)
      2. Single newlines
      3. Spaces
      4. Individual characters (last resort)

    chunk_size=500: each chunk is at most 500 characters
    chunk_overlap=50: chunks overlap by 50 chars to avoid cutting context at boundaries

    LEARNING — Why overlap?
    If an error message spans two chunks, overlap ensures it appears in at least one chunk fully.
    Without overlap, a split in the middle of a log entry would lose context.

    LEARNING — Document metadata:
    Each chunk gets metadata (source file, line range).
    This is how the Citation Agent (Phase 3) will cite which log file an answer came from.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", " "],   # try these in order
    )

    documents = []
    for log_file in LOGS_DIR.glob("*.log"):
        content = log_file.read_text()
        chunks = splitter.split_text(content)

        for i, chunk in enumerate(chunks):
            # LEARNING — metadata: stored alongside the vector in ChromaDB
            # Lets you filter by source, or cite where the answer came from
            doc = Document(
                page_content=chunk,
                metadata={
                    "source": log_file.name,
                    "service": log_file.stem,   # filename without .log
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                }
            )
            documents.append(doc)

    return documents


def build_vector_store(force_rebuild: bool = False) -> Chroma:
    """
    Build (or load) the ChromaDB vector store from log files.

    LEARNING — Persistence:
    ChromaDB saves its data to disk at CHROMA_PERSIST_DIR.
    On the first run, it embeds all chunks (slow — ~30 seconds).
    On subsequent runs, it loads from disk instantly.

    force_rebuild=True: wipes and rebuilds from scratch (use after new logs are added).

    LEARNING — Chroma.from_documents():
    This does Steps 3+4 in one call:
      - Calls embeddings.embed_documents() on all chunks
      - Stores vectors + text + metadata in ChromaDB
    """
    persist_path = Path(CHROMA_PERSIST_DIR)

    # Check if store already exists on disk
    if persist_path.exists() and any(persist_path.iterdir()) and not force_rebuild:
        print(f"Loading existing vector store from {CHROMA_PERSIST_DIR}")
        return Chroma(
            collection_name=LOG_COLLECTION,
            embedding_function=get_embeddings(),
            persist_directory=CHROMA_PERSIST_DIR,
        )

    print("Building vector store from log files (this takes ~30s first time)...")
    documents = load_and_chunk_logs()
    print(f"Loaded {len(documents)} chunks from {LOGS_DIR}")

    # Embed all chunks and store in ChromaDB
    store = Chroma.from_documents(
        documents=documents,
        embedding=get_embeddings(),
        collection_name=LOG_COLLECTION,
        persist_directory=CHROMA_PERSIST_DIR,
    )
    print(f"Vector store built and saved to {CHROMA_PERSIST_DIR}")
    return store


def search_logs(query: str, k: int = 5, service_filter: str = None) -> list[Document]:
    """
    Semantically search log chunks for a given query.

    LEARNING — Semantic search vs keyword search:
    Keyword:  "OOMKilled" only finds exact string "OOMKilled"
    Semantic: "out of memory" finds OOMKilled, memory pressure, kill process, etc.
              because they have similar embedding vectors.

    k=5: return the top 5 most relevant chunks
    service_filter: optionally limit search to one service's logs

    LEARNING — similarity_search_with_score():
    Returns (Document, score) pairs.
    Score is cosine distance: 0.0 = identical, 2.0 = opposite meaning.
    Lower score = more relevant.
    """
    store = build_vector_store()

    # LEARNING — metadata filtering in ChromaDB:
    # You can filter by any metadata field before doing vector search.
    # This is more efficient than post-filtering all results.
    where_filter = {"service": service_filter} if service_filter else None

    if where_filter:
        results = store.similarity_search_with_score(
            query, k=k, filter=where_filter
        )
    else:
        results = store.similarity_search_with_score(query, k=k)

    return results
