"""
Tests for Phase 3 — Citation Agent.

LEARNING — Testing memory and citation:

New challenges in Phase 3 compared to Phase 2:
1. We need to test that citations are present (not just any output)
2. We need to test long-term memory (store + retrieve across calls)
3. We need to test multi-turn conversation (context is preserved)
4. We need to test that runbook chunking produces citable sections

Testing strategy:
- Unit: test runbook loading/chunking, incident memory store/retrieve (no LLM)
- Integration: test runbook semantic search with embeddings (no LLM)
- E2E: test full citation agent output — check for citation markers, runbook references
"""

import pytest
from pathlib import Path


# =============================================================================
# UNIT TESTS — No LLM, no ChromaDB
# =============================================================================

class TestRunbookLoading:
    """Test that runbooks are loaded and chunked correctly."""

    def test_all_runbooks_exist(self):
        """5 runbook files should be present."""
        runbook_dir = Path("mocks/runbooks")
        runbooks = list(runbook_dir.glob("*.md"))
        assert len(runbooks) == 5

    def test_runbook_chunking_produces_documents(self):
        """Chunking runbooks by headers should produce multiple documents."""
        from skills.runbook_store import load_and_chunk_runbooks
        docs = load_and_chunk_runbooks()
        assert len(docs) > 0

    def test_runbook_chunks_have_citation_metadata(self):
        """
        Every chunk must have runbook_id, runbook_title, section metadata.
        LEARNING: This ensures the agent can always cite its sources.
        A chunk without citation metadata = unverifiable recommendation.
        """
        from skills.runbook_store import load_and_chunk_runbooks
        docs = load_and_chunk_runbooks()
        for doc in docs:
            assert "runbook_id" in doc.metadata, f"Missing runbook_id in chunk: {doc.page_content[:50]}"
            assert "runbook_title" in doc.metadata
            assert "section" in doc.metadata

    def test_oom_runbook_chunks_contain_remediation(self):
        """OOM runbook should have chunks covering remediation steps."""
        from skills.runbook_store import load_and_chunk_runbooks
        docs = load_and_chunk_runbooks()
        oom_chunks = [d for d in docs if "RB-001" in d.metadata.get("runbook_id", "")]
        assert len(oom_chunks) > 0
        combined = " ".join(d.page_content for d in oom_chunks)
        assert "memory" in combined.lower()
        assert "limit" in combined.lower()

    def test_all_runbook_ids_present(self):
        """Each runbook should have a unique ID extracted into metadata."""
        from skills.runbook_store import load_and_chunk_runbooks
        docs = load_and_chunk_runbooks()
        ids = {d.metadata.get("runbook_id") for d in docs}
        # At least one chunk per runbook should have a recognisable ID
        assert len(ids) >= 5


class TestIncidentMemory:
    """Test long-term incident memory store and retrieve (no LLM)."""

    def test_store_and_retrieve_incident(self):
        """
        LEARNING: Test that long-term memory persists within a test run.
        Store an incident, then search for it — it should come back.
        """
        from memory.incident_memory import store_incident, search_similar_incidents

        incident_id = store_incident(
            service="test-service",
            symptom="test-service OOM in unit test",
            root_cause="memory limit too low in test",
            resolution="increased limit to 512Mi in test",
        )

        assert incident_id.startswith("INC-")

        # Search for the incident we just stored
        results = search_similar_incidents("test-service out of memory")
        assert len(results) > 0
        services = [r["service"] for r in results]
        assert "test-service" in services

    def test_incident_result_has_required_fields(self):
        """Every retrieved incident must have all fields for citation."""
        from memory.incident_memory import store_incident, search_similar_incidents

        store_incident(
            service="field-test-svc",
            symptom="field test symptom",
            root_cause="field test cause",
            resolution="field test resolution",
        )

        results = search_similar_incidents("field test")
        assert len(results) > 0

        required_fields = ["incident_id", "service", "symptom", "root_cause", "resolution", "timestamp", "similarity_score"]
        for field in required_fields:
            assert field in results[0], f"Missing field: {field}"

    def test_seed_past_incidents(self):
        """Seeding should populate the store with historical incidents."""
        from memory.incident_memory import seed_past_incidents, search_similar_incidents
        seed_past_incidents()

        results = search_similar_incidents("nginx OOMKilled memory")
        assert len(results) > 0

    def test_list_available_runbooks_tool(self):
        """list_available_runbooks tool should return all 5 runbooks."""
        from skills.citation_tools import list_available_runbooks
        result = list_available_runbooks.invoke({})
        assert len(result) == 5
        ids = {r["id"] for r in result}
        # All runbooks should have an ID
        assert all(id_ for id_ in ids)


# =============================================================================
# INTEGRATION TESTS — Runbook semantic search with embeddings (no LLM)
# =============================================================================

class TestRunbookSemanticSearch:
    """
    LEARNING: Test that semantic search retrieves the RIGHT runbook for each symptom.
    This validates the embedding quality and chunking strategy.
    """

    @pytest.mark.e2e
    def test_oom_query_retrieves_oom_runbook(self):
        """'container killed memory' should return RB-001 (OOM Runbook)."""
        from skills.citation_tools import search_runbooks_for_symptom
        results = search_runbooks_for_symptom.invoke({"symptom": "container killed out of memory"})

        assert len(results) > 0
        runbook_ids = [r["citation"]["runbook_id"] for r in results]
        assert any("RB-001" in rid for rid in runbook_ids), (
            f"OOM runbook not found. Got: {runbook_ids}"
        )

    @pytest.mark.e2e
    def test_cpu_query_retrieves_cpu_runbook(self):
        """'high CPU usage service degraded' should return RB-002."""
        from skills.citation_tools import search_runbooks_for_symptom
        results = search_runbooks_for_symptom.invoke({"symptom": "high CPU usage service degraded"})

        runbook_ids = [r["citation"]["runbook_id"] for r in results]
        assert any("RB-002" in rid for rid in runbook_ids)

    @pytest.mark.e2e
    def test_database_query_retrieves_db_runbook(self):
        """'connection refused database' should return RB-003."""
        from skills.citation_tools import search_runbooks_for_symptom
        results = search_runbooks_for_symptom.invoke({"symptom": "database connection refused"})

        runbook_ids = [r["citation"]["runbook_id"] for r in results]
        assert any("RB-003" in rid for rid in runbook_ids)

    @pytest.mark.e2e
    def test_results_have_citation_fields(self):
        """All results must have complete citation metadata."""
        from skills.citation_tools import search_runbooks_for_symptom
        results = search_runbooks_for_symptom.invoke({"symptom": "service crash"})

        for result in results:
            assert "citation" in result
            assert result["citation"]["runbook_id"]
            assert result["citation"]["runbook_title"]


# =============================================================================
# END-TO-END TESTS — Full Citation Agent (ChromaDB + LLM)
# =============================================================================

class TestCitationAgentE2E:
    """
    LEARNING: E2E tests for the Citation Agent.
    Key assertions:
    - Citations are present (source references in output)
    - Runbook IDs appear (RB-001, RB-002, etc.)
    - Past incidents are surfaced when relevant
    """

    @pytest.mark.e2e
    def test_oom_query_includes_runbook_citation(self):
        """
        E2E: Agent must cite a runbook when answering about OOMKilled.
        LEARNING: We check for citation markers (RB-, Source:) not exact text.
        """
        from agents.citation_agent import run_citation_query
        result = run_citation_query("nginx container is OOMKilled, restart count is 3")
        output = result["output"]

        # Agent must reference a runbook — either by ID or "Source:"
        has_citation = any(marker in output for marker in ["RB-", "Source:", "Runbook", "runbook"])
        assert has_citation, f"No citation found in output:\n{output}"

    @pytest.mark.e2e
    def test_worker_crash_surfaces_past_incident(self):
        """E2E: Agent should find the seeded past incident about worker DB crash."""
        from agents.citation_agent import run_citation_query
        from memory.incident_memory import seed_past_incidents
        seed_past_incidents()

        result = run_citation_query("worker container crashing with database connection errors")
        output = result["output"].lower()

        # Should mention database, connection, or past incident
        assert any(w in output for w in ["database", "connection", "postgres", "past incident", "similar"])

    @pytest.mark.e2e
    def test_multi_turn_conversation(self):
        """
        E2E: Agent should maintain context across conversation turns.
        LEARNING: Multi-turn test — second question refers to context from first answer.
        """
        from agents.citation_agent import run_citation_query

        result1 = run_citation_query("nginx is OOMKilled")
        history = [
            {"role": "user", "content": "nginx is OOMKilled"},
            {"role": "assistant", "content": result1["output"]},
        ]

        result2 = run_citation_query(
            "What is the long-term prevention for this?",
            conversation_history=history,
        )
        output2 = result2["output"].lower()

        # Should reference memory/profiling/alerting as long-term fixes
        assert any(w in output2 for w in ["long", "term", "alert", "monitor", "profil", "prevent"])

    @pytest.mark.e2e
    def test_citation_api_endpoint(self):
        """E2E: Test POST /citation via FastAPI TestClient."""
        from fastapi.testclient import TestClient
        from api.main import app
        client = TestClient(app)

        response = client.post(
            "/citation",
            json={"symptom": "nginx OOMKilled, memory at limit"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "report" in data
        assert len(data["report"]) > 0

    @pytest.mark.e2e
    def test_record_incident_tool(self):
        """E2E: Recording an incident should make it retrievable immediately."""
        from skills.citation_tools import record_incident, search_past_incidents

        record_incident.invoke({
            "service": "e2e-test-svc",
            "symptom": "e2e test OOM spike",
            "root_cause": "memory limit at 256Mi too low",
            "resolution": "raised to 512Mi, added alerting",
        })

        results = search_past_incidents.invoke({"query": "e2e test memory spike"})
        services = [r["service"] for r in results]
        assert "e2e-test-svc" in services
