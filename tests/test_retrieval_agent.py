"""
Tests for Phase 2 — Retrieval Agent.

LEARNING — Testing RAG systems:

RAG introduces non-determinism at two levels:
  1. Retrieval: ChromaDB returns top-k chunks — usually stable, but order can vary
  2. Generation: LLM synthesizes an answer — varies slightly each run

Testing strategy:
  - Unit tests: test chunking logic, metadata, and error counting (no LLM, no ChromaDB)
  - Integration tests: test semantic search returns relevant chunks (ChromaDB, no LLM)
  - E2E tests: test full agent pipeline (ChromaDB + LLM)

LEARNING — What to assert in RAG tests:
  - Don't assert exact text — LLM output varies
  - Assert that KEY FACTS are present (service names, error types, timestamps)
  - Assert that retrieved chunks are RELEVANT (relevance score below threshold)
  - Assert that source citations are PRESENT
"""

import pytest
from pathlib import Path


# =============================================================================
# UNIT TESTS — No LLM, no ChromaDB, test log loading and chunking logic
# =============================================================================

class TestLogLoading:
    """Test that log files are correctly loaded and chunked."""

    def test_log_files_exist(self):
        """All 5 mock log files should be present."""
        log_dir = Path("mocks/logs")
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) == 5
        services = {f.stem for f in log_files}
        assert services == {"nginx", "worker", "app-server", "postgres", "redis"}

    def test_log_chunking_produces_documents(self):
        """Chunking should produce multiple Document objects with correct metadata."""
        from skills.vector_store import load_and_chunk_logs
        docs = load_and_chunk_logs()

        assert len(docs) > 0
        # Each document should have required metadata
        for doc in docs:
            assert "service" in doc.metadata
            assert "source" in doc.metadata
            assert "chunk_index" in doc.metadata
            assert len(doc.page_content) > 0

    def test_chunks_respect_size_limit(self):
        """No chunk should exceed the configured chunk_size of 500 chars."""
        from skills.vector_store import load_and_chunk_logs
        docs = load_and_chunk_logs()
        # Allow small overage due to overlap — check within reasonable bound
        for doc in docs:
            assert len(doc.page_content) <= 600, (
                f"Chunk too large: {len(doc.page_content)} chars in {doc.metadata['source']}"
            )

    def test_all_services_represented_in_chunks(self):
        """Every log file should contribute at least one chunk."""
        from skills.vector_store import load_and_chunk_logs
        docs = load_and_chunk_logs()
        services_in_chunks = {doc.metadata["service"] for doc in docs}
        assert "nginx" in services_in_chunks
        assert "worker" in services_in_chunks
        assert "app-server" in services_in_chunks
        assert "postgres" in services_in_chunks
        assert "redis" in services_in_chunks

    def test_nginx_log_contains_oom_events(self):
        """nginx.log should contain OOMKilled entries."""
        log_content = Path("mocks/logs/nginx.log").read_text()
        assert "OOMKilled" in log_content
        assert log_content.count("OOMKilled") >= 3  # 3 OOM events in the mock

    def test_worker_log_contains_exit_code(self):
        """worker.log should record the fatal exit."""
        log_content = Path("mocks/logs/worker.log").read_text()
        assert "exit_code=1" in log_content
        assert "FATAL" in log_content


class TestErrorSummaryTool:
    """Test the error summary tool (no LLM, no ChromaDB — uses raw log parsing)."""

    def test_error_summary_returns_dict(self):
        from skills.log_search import get_error_summary
        result = get_error_summary.invoke({})
        assert "total_services_with_errors" in result
        assert "by_service" in result

    def test_nginx_appears_in_error_summary(self):
        from skills.log_search import get_error_summary
        result = get_error_summary.invoke({})
        assert "nginx" in result["by_service"]
        assert result["by_service"]["nginx"]["count"] > 0

    def test_worker_appears_in_error_summary(self):
        from skills.log_search import get_error_summary
        result = get_error_summary.invoke({})
        assert "worker" in result["by_service"]

    def test_redis_has_no_errors(self):
        """redis.log has no ERROR lines — should not appear in error summary."""
        from skills.log_search import get_error_summary
        result = get_error_summary.invoke({})
        # redis should not appear or have 0 errors
        redis_errors = result["by_service"].get("redis", {}).get("count", 0)
        assert redis_errors == 0

    def test_get_log_index_lists_all_services(self):
        from skills.log_search import get_log_index
        result = get_log_index.invoke({})
        services = {entry["service"] for entry in result}
        assert len(services) == 5


# =============================================================================
# INTEGRATION TESTS — ChromaDB + embeddings (no LLM)
# =============================================================================

class TestSemanticSearch:
    """
    LEARNING: Integration tests for RAG retrieval.
    These require nomic-embed-text to be running via Ollama.
    We test that semantic search returns RELEVANT chunks.
    """

    @pytest.mark.e2e
    def test_oom_query_returns_nginx_chunks(self):
        """
        LEARNING: Semantic search test.
        'out of memory' should semantically match 'OOMKilled' in nginx logs.
        This would FAIL with keyword search — it passes with semantic search.
        """
        from skills.log_search import search_logs_semantic
        results = search_logs_semantic.invoke({"query": "out of memory errors"})

        assert len(results) > 0
        # At least one result should come from nginx (where OOM happened)
        services = [r["service"] for r in results]
        assert "nginx" in services

    @pytest.mark.e2e
    def test_database_query_returns_worker_or_postgres(self):
        """'database connection failure' should retrieve worker or postgres logs."""
        from skills.log_search import search_logs_semantic
        results = search_logs_semantic.invoke({"query": "database connection failure"})

        services = [r["service"] for r in results]
        assert "worker" in services or "postgres" in services

    @pytest.mark.e2e
    def test_service_filter_limits_results(self):
        """Searching with service_filter='nginx' should only return nginx chunks."""
        from skills.log_search import search_logs_for_service
        results = search_logs_for_service.invoke({
            "service_name": "nginx",
            "query": "memory"
        })
        for result in results:
            assert result["service"] == "nginx"

    @pytest.mark.e2e
    def test_relevance_scores_are_present(self):
        """All results should have a relevance_score."""
        from skills.log_search import search_logs_semantic
        results = search_logs_semantic.invoke({"query": "errors"})
        for result in results:
            assert "relevance_score" in result
            assert isinstance(result["relevance_score"], float)


# =============================================================================
# END-TO-END TESTS — Full agent pipeline (ChromaDB + LLM)
# =============================================================================

class TestRetrievalAgentE2E:
    """
    LEARNING: E2E tests for the full RAG pipeline.
    These are the hardest to write because LLM output varies.
    Strategy: check for KEY FACTS, not exact wording.
    """

    @pytest.mark.e2e
    def test_worker_root_cause_query(self):
        """
        E2E: Agent should identify database connection failure as worker root cause.
        LEARNING: We check for the key fact (database/connection) not exact wording.
        """
        from agents.retrieval_agent import run_log_analysis
        result = run_log_analysis("Why did the worker container stop?")
        output = result["output"].lower()

        # The root cause is database connection failure — agent should find this
        assert any(word in output for word in ["database", "connection", "postgres", "refused"])

    @pytest.mark.e2e
    def test_oom_query_finds_nginx(self):
        """E2E: Agent should find OOM events in nginx logs."""
        from agents.retrieval_agent import run_log_analysis
        result = run_log_analysis("Find all out of memory errors")
        output = result["output"].lower()

        assert any(word in output for word in ["nginx", "oom", "memory", "killed"])

    @pytest.mark.e2e
    def test_agent_output_is_grounded(self):
        """
        E2E: Agent output should cite a source service.
        LEARNING: This tests GROUNDING — the agent must reference log sources.
        Ungrounded answer: "The service crashed due to memory issues" (no citation)
        Grounded answer: "nginx.log shows OOMKilled at 09:22" (cited)
        """
        from agents.retrieval_agent import run_log_analysis
        result = run_log_analysis("Summarize all critical errors across services")
        output = result["output"].lower()

        # Should mention at least one concrete service name
        services = ["nginx", "worker", "app-server", "postgres", "redis"]
        assert any(s in output for s in services), (
            "Agent output is not grounded — no service names found in response"
        )

    @pytest.mark.e2e
    def test_api_retrieval_endpoint(self):
        """E2E: Test the retrieval endpoint via FastAPI TestClient."""
        from fastapi.testclient import TestClient
        from api.main import app
        client = TestClient(app)

        response = client.post(
            "/log-analysis",
            json={"query": "What errors occurred in nginx?"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "report" in data
        assert len(data["report"]) > 0
