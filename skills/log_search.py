"""
Log search tools — @tool decorated functions the Retrieval Agent can call.

LEARNING — Tool design principles:
1. Each tool does ONE thing well (single responsibility)
2. The docstring IS the tool description the LLM reads — make it clear
3. Return structured data (dicts/lists) the LLM can reason about
4. Handle errors gracefully — return error info, don't raise exceptions
5. Tools should be stateless — no side effects, same input = same output

These tools wrap skills/vector_store.py (the RAG logic) with the @tool
interface so the Retrieval Agent can call them in its ReAct loop.
"""

from langchain.tools import tool
from skills.vector_store import search_logs, build_vector_store, load_and_chunk_logs


@tool
def search_logs_semantic(query: str) -> list[dict]:
    """
    Search all service logs using semantic (meaning-based) search.
    Use this to find log entries related to a concept, error type, or symptom.
    Returns the most relevant log chunks with their source service and relevance score.
    Example queries: 'memory errors', 'database connection failures', 'high CPU usage'.
    """
    # LEARNING — This is the core RAG retrieval step
    # query -> embed -> vector search -> top-k chunks
    results = search_logs(query, k=6)

    return [
        {
            "content": doc.page_content,
            "service": doc.metadata.get("service"),
            "source_file": doc.metadata.get("source"),
            "relevance_score": round(float(score), 3),
            # Lower score = more relevant (cosine distance)
        }
        for doc, score in results
    ]


@tool
def search_logs_for_service(service_name: str, query: str) -> list[dict]:
    """
    Search logs for a specific service only.
    Use this when you already know which service to investigate.
    service_name must be one of: nginx, worker, app-server, postgres, redis.
    Returns relevant log chunks from that service only.
    """
    results = search_logs(query, k=6, service_filter=service_name)

    if not results:
        return [{"error": f"No logs found for service '{service_name}' matching '{query}'"}]

    return [
        {
            "content": doc.page_content,
            "service": doc.metadata.get("service"),
            "relevance_score": round(float(score), 3),
        }
        for doc, score in results
    ]


@tool
def get_error_summary() -> dict:
    """
    Get a summary of all ERROR and FATAL level log entries across all services.
    Use this to quickly understand what errors are occurring system-wide.
    Returns error counts per service and sample error messages.
    """
    # LEARNING — Sometimes keyword filtering is better than semantic search.
    # For counting ERRORs, we want exact matches not semantic similarity.
    # A real system would use both approaches together.
    documents = load_and_chunk_logs()

    error_summary = {}
    for doc in documents:
        service = doc.metadata.get("service", "unknown")
        lines = doc.page_content.split("\n")
        errors = [l for l in lines if "[ERROR]" in l or "[FATAL]" in l]

        if errors:
            if service not in error_summary:
                error_summary[service] = {"count": 0, "samples": []}
            error_summary[service]["count"] += len(errors)
            # Keep up to 3 sample errors per service
            error_summary[service]["samples"].extend(errors[:3])
            error_summary[service]["samples"] = error_summary[service]["samples"][:3]

    return {
        "total_services_with_errors": len(error_summary),
        "by_service": error_summary,
    }


@tool
def get_log_index() -> list[dict]:
    """
    List all available log files and their chunk counts in the vector store.
    Use this first to understand what logs are available before searching.
    """
    documents = load_and_chunk_logs()

    index = {}
    for doc in documents:
        service = doc.metadata.get("service", "unknown")
        if service not in index:
            index[service] = {
                "service": service,
                "file": doc.metadata.get("source"),
                "chunks": doc.metadata.get("total_chunks", 0),
            }

    return list(index.values())
