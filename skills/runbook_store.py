"""
Runbook vector store — RAG pipeline over SRE runbooks.

LEARNING — Multi-collection RAG:

Phase 2 built a vector store over LOG files (sre_logs collection).
Phase 3 adds a second vector store over RUNBOOK files (sre_runbooks collection).

Why separate collections?
- Logs and runbooks have different content types and retrieval purposes
- You might want to search logs WITHOUT runbooks and vice versa
- Separate collections = separate embedding spaces = no cross-contamination

The Citation Agent uses BOTH collections:
  1. Search runbooks -> get the authoritative procedure
  2. Search past incidents -> get what worked before
  3. Synthesize -> grounded recommendation with citations

LEARNING — Source Attribution:
Each runbook chunk carries metadata: runbook_id, title, section.
When retrieved, this metadata becomes the citation in the agent's response.
"According to RB-001 (OOMKilled Runbook), Section: Immediate Remediation..."
"""

import os
from pathlib import Path
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from dotenv import load_dotenv

load_dotenv()

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")
RUNBOOKS_DIR = Path("mocks/runbooks")
RUNBOOK_COLLECTION = "sre_runbooks"


def get_embeddings():
    return OllamaEmbeddings(
        model=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )


def load_and_chunk_runbooks() -> list[Document]:
    """
    Load runbooks and chunk them by markdown headers.

    LEARNING — MarkdownHeaderTextSplitter:
    This is a smarter chunking strategy than fixed-size splitting.
    It splits on markdown headers (##, ###) so each chunk is a complete section.

    Why this matters:
    A fixed-size splitter might cut "Step 1: Confirm OOM" in half.
    A header splitter keeps "## Diagnosis Steps" as one complete chunk.
    Result: each retrieved chunk is a coherent, usable procedure.

    LEARNING — Chunking strategy choice:
    - Plain text logs: RecursiveCharacterTextSplitter (Phase 2)
    - Structured markdown runbooks: MarkdownHeaderTextSplitter (Phase 3)
    - Code: split on functions/classes
    - PDFs: split on pages, then recursively
    Match your splitter to your content type.
    """
    # Split on these header levels — each section becomes its own chunk
    headers_to_split_on = [
        ("##", "section"),
        ("###", "subsection"),
    ]
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        strip_headers=False,  # Keep the header in the chunk for context
    )

    # Secondary splitter for sections that are still too large
    fallback_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=80,
    )

    documents = []
    for runbook_file in RUNBOOKS_DIR.glob("*.md"):
        content = runbook_file.read_text()

        # Extract runbook ID and title from first lines
        first_line = content.split("\n")[0]  # e.g. "# Runbook: OOMKilled"
        runbook_title = first_line.replace("# ", "").strip()

        # Extract ID from content (e.g. "**ID:** RB-001")
        runbook_id = runbook_file.stem.upper().replace("_", "-")
        for line in content.split("\n"):
            if "**ID:**" in line:
                runbook_id = line.replace("**ID:**", "").strip()
                break

        # Split by markdown headers first
        section_chunks = header_splitter.split_text(content)

        for chunk in section_chunks:
            # LEARNING — metadata on runbook chunks enables source citation
            # The agent can say "According to RB-001, Section: Diagnosis Steps"
            base_metadata = {
                "runbook_id": runbook_id,
                "runbook_title": runbook_title,
                "source_file": runbook_file.name,
                "section": chunk.metadata.get("section", "Overview"),
                "subsection": chunk.metadata.get("subsection", ""),
            }

            # If a section is still large, split it further
            if len(chunk.page_content) > 800:
                sub_chunks = fallback_splitter.split_text(chunk.page_content)
                for i, sub in enumerate(sub_chunks):
                    documents.append(Document(
                        page_content=sub,
                        metadata={**base_metadata, "sub_chunk": i}
                    ))
            else:
                documents.append(Document(
                    page_content=chunk.page_content,
                    metadata=base_metadata,
                ))

    return documents


def build_runbook_store(force_rebuild: bool = False) -> Chroma:
    """
    Build or load the runbook vector store.
    Separate from the log vector store — different collection name.
    """
    persist_path = Path(CHROMA_PERSIST_DIR)

    existing_store = Chroma(
        collection_name=RUNBOOK_COLLECTION,
        embedding_function=get_embeddings(),
        persist_directory=CHROMA_PERSIST_DIR,
    )

    if existing_store._collection.count() > 0 and not force_rebuild:
        print(f"Loading existing runbook store ({existing_store._collection.count()} chunks)")
        return existing_store

    print("Building runbook vector store...")
    documents = load_and_chunk_runbooks()
    print(f"Loaded {len(documents)} chunks from {len(list(RUNBOOKS_DIR.glob('*.md')))} runbooks")

    store = Chroma.from_documents(
        documents=documents,
        embedding=get_embeddings(),
        collection_name=RUNBOOK_COLLECTION,
        persist_directory=CHROMA_PERSIST_DIR,
    )
    print("Runbook store built.")
    return store


def search_runbooks(query: str, k: int = 4) -> list[Document]:
    """
    Semantically search runbook sections relevant to a query.
    Returns chunks with full citation metadata (runbook_id, section).
    """
    store = build_runbook_store()
    return store.similarity_search_with_score(query, k=k)
