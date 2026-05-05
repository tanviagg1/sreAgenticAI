"""
Tests for Phase 5 — Orchestrator.

LEARNING — Testing a multi-agent graph:

Testing the full orchestrator is the hardest testing challenge in this project.
The graph involves 5+ LLM calls, conditional routing, and human-in-the-loop.

Strategy:
1. Unit tests: test each node function in isolation (mock the agent calls)
2. Unit tests: test routing functions (conditional edge logic — no LLM needed)
3. Integration tests: test graph structure (nodes, edges, entry point)
4. E2E tests: run the full graph with require_human_approval=False

LEARNING — Mocking in AI tests:
For unit tests of graph nodes, we don't want to call real LLMs.
We mock the agent functions to return predetermined outputs.
This makes tests fast, deterministic, and focused on the graph logic.

LEARNING — Testing conditional edges:
Routing functions are pure Python — they read state and return a string.
These are easy to test: set the state, call the function, assert the return value.
"""

import pytest
from unittest.mock import patch, MagicMock


# =============================================================================
# UNIT TESTS — Routing logic (no LLM)
# =============================================================================

class TestConditionalRouting:
    """
    LEARNING: Routing functions are deterministic Python — test them directly.
    These are the most important unit tests in Phase 5 because
    wrong routing means the wrong agents run.
    """

    def test_route_healthy_system_goes_to_summary(self):
        """HEALTHY system should skip to summary without running other agents."""
        from agents.orchestrator import route_after_health
        state = {"overall_status": "HEALTHY", "unhealthy_services": []}
        assert route_after_health(state) == "summary"

    def test_route_critical_system_goes_to_retrieval(self):
        """CRITICAL system should trigger the full pipeline."""
        from agents.orchestrator import route_after_health
        state = {"overall_status": "CRITICAL", "unhealthy_services": ["nginx", "worker"]}
        assert route_after_health(state) == "log_retrieval"

    def test_route_degraded_system_goes_to_retrieval(self):
        """DEGRADED system should also trigger investigation."""
        from agents.orchestrator import route_after_health
        state = {"overall_status": "DEGRADED", "unhealthy_services": ["app-server"]}
        assert route_after_health(state) == "log_retrieval"

    def test_route_fixable_service_goes_to_coding(self):
        """Unhealthy nginx (fixable) should route to coding agent."""
        from agents.orchestrator import route_after_citation
        state = {
            "unhealthy_services": ["nginx"],
            "runbook_recommendations": "increase memory limit",
        }
        assert route_after_citation(state) == "coding"

    def test_route_unfixable_service_skips_coding(self):
        """Service not in fixable set should skip coding and go to summary."""
        from agents.orchestrator import route_after_citation
        state = {
            "unhealthy_services": ["external-api"],   # not in fixable set
            "runbook_recommendations": "contact vendor",
        }
        assert route_after_citation(state) == "summary"

    def test_route_no_unhealthy_services_skips_coding(self):
        """Empty unhealthy list should skip coding."""
        from agents.orchestrator import route_after_citation
        state = {"unhealthy_services": []}
        assert route_after_citation(state) == "summary"


# =============================================================================
# UNIT TESTS — Graph structure (no LLM)
# =============================================================================

class TestGraphStructure:
    """Test that the graph is wired correctly."""

    def test_graph_builds_without_error(self):
        """Graph compilation should succeed."""
        from agents.orchestrator import build_sre_graph
        graph = build_sre_graph(require_human_approval=False)
        assert graph is not None

    def test_graph_has_all_nodes(self):
        """Graph should contain all 6 expected nodes."""
        from agents.orchestrator import build_sre_graph
        graph = build_sre_graph(require_human_approval=False)
        node_names = set(graph.get_graph().nodes.keys())
        expected = {"health_check", "log_retrieval", "citation", "coding", "summary", "__start__"}
        assert expected.issubset(node_names)

    def test_graph_with_approval_has_human_node(self):
        """Graph with require_human_approval=True should include human_approval node."""
        from agents.orchestrator import build_sre_graph
        graph = build_sre_graph(require_human_approval=True)
        node_names = set(graph.get_graph().nodes.keys())
        assert "human_approval" in node_names


# =============================================================================
# UNIT TESTS — Individual nodes with mocked agents
# =============================================================================

class TestGraphNodes:
    """
    LEARNING — Mocking agent calls in node tests:
    We patch the actual agent functions so nodes run without LLM calls.
    This tests that each node correctly reads from and writes to state.
    """

    def test_health_check_node_updates_state(self):
        """Health node should populate health_report, overall_status, unhealthy_services."""
        from agents.orchestrator import health_check_node

        mock_result = {"output": "## System Status: CRITICAL\n- nginx: OOMKilled\n- worker: stopped"}

        with patch("agents.orchestrator.run_health_check", return_value=mock_result):
            state = {"steps_taken": [], "incident_description": "test"}
            updates = health_check_node(state)

        assert "health_report" in updates
        assert "overall_status" in updates
        assert "unhealthy_services" in updates
        assert "health_check" in updates["steps_taken"]

    def test_log_retrieval_node_updates_state(self):
        """Retrieval node should populate log_analysis."""
        from agents.orchestrator import log_retrieval_node

        mock_result = {"output": "nginx OOM at 09:22 due to memory limit"}

        with patch("agents.orchestrator.run_log_analysis", return_value=mock_result):
            state = {
                "unhealthy_services": ["nginx"],
                "incident_description": "nginx OOMKilled",
                "steps_taken": [],
            }
            updates = log_retrieval_node(state)

        assert "log_analysis" in updates
        assert updates["log_analysis"] == mock_result["output"]
        assert "log_retrieval" in updates["steps_taken"]

    def test_citation_node_extracts_actions(self):
        """Citation node should populate runbook_recommendations and recommended_actions."""
        from agents.orchestrator import citation_node

        mock_result = {
            "output": "Recommendations:\n1. Increase memory to 1Gi\n2. Add alerting at 80%\n3. Restart nginx"
        }

        with patch("agents.orchestrator.run_citation_query", return_value=mock_result):
            state = {
                "incident_description": "nginx OOM",
                "overall_status": "CRITICAL",
                "unhealthy_services": ["nginx"],
                "log_analysis": "OOM at 09:22",
                "steps_taken": [],
            }
            updates = citation_node(state)

        assert "runbook_recommendations" in updates
        assert "recommended_actions" in updates
        assert isinstance(updates["recommended_actions"], list)

    def test_coding_node_skips_if_no_unhealthy_services(self):
        """Coding node should skip gracefully if unhealthy_services is empty."""
        from agents.orchestrator import coding_node

        state = {
            "unhealthy_services": [],
            "incident_description": "test",
            "steps_taken": [],
        }
        updates = coding_node(state)

        assert updates["proposed_fix"] == {}
        assert updates["fix_approved"] is False
        assert "coding_skipped" in updates["steps_taken"]

    def test_summary_node_produces_text(self):
        """Summary node should produce a non-empty final_summary string."""
        from agents.orchestrator import summary_node

        mock_response = MagicMock()
        mock_response.content = "The SRE pipeline detected critical issues in nginx and worker."

        with patch("agents.orchestrator.ChatOllama") as MockLLM:
            MockLLM.return_value.invoke.return_value = mock_response
            state = {
                "overall_status": "CRITICAL",
                "unhealthy_services": ["nginx"],
                "log_analysis": "OOM logs found",
                "runbook_recommendations": "Increase memory",
                "proposed_fix": {"problem_summary": "memory too low"},
                "fix_approved": True,
                "steps_taken": ["health_check", "log_retrieval", "citation", "coding"],
            }
            updates = summary_node(state)

        assert "final_summary" in updates
        assert len(updates["final_summary"]) > 0


# =============================================================================
# INTEGRATION TESTS — LLM Evaluator
# =============================================================================

class TestLLMEvaluator:
    """Test the LLM-as-judge evaluation system."""

    @pytest.mark.e2e
    def test_evaluate_pipeline_returns_scores(self):
        """Evaluator should return numeric scores for all dimensions."""
        from skills.evaluator import evaluate_pipeline_output

        mock_state = {
            "final_summary": "nginx OOMKilled due to 512Mi memory limit. Increased to 1Gi per RB-001.",
            "steps_taken": ["health_check", "log_retrieval", "citation", "coding"],
            "overall_status": "CRITICAL",
            "unhealthy_services": ["nginx"],
            "fix_approved": True,
        }
        scores = evaluate_pipeline_output(mock_state)

        assert "overall" in scores
        assert "faithfulness" in scores
        assert "completeness" in scores

    @pytest.mark.e2e
    def test_evaluate_rag_returns_ragas_metrics(self):
        """RAG evaluator should return context_precision, faithfulness, relevancy."""
        from skills.evaluator import evaluate_rag_retrieval

        scores = evaluate_rag_retrieval(
            query="Why did nginx OOMKill?",
            retrieved_chunks=[
                {"service": "nginx", "content": "OOMKilled at 09:22, memory at 512MB limit"},
            ],
            answer="nginx was killed because memory usage reached 512MB which equals the limit.",
        )

        assert "context_precision" in scores or "error" in scores


# =============================================================================
# END-TO-END TESTS — Full pipeline without human approval
# =============================================================================

class TestOrchestratorE2E:
    """
    LEARNING: E2E tests run the full graph with require_human_approval=False.
    This skips the terminal prompt so tests run automatically.
    We verify the state contains outputs from all expected nodes.
    """

    @pytest.mark.e2e
    def test_full_pipeline_critical_incident(self):
        """
        E2E: Full graph run for a critical incident.
        State should be populated by all nodes in the pipeline.
        """
        from agents.orchestrator import run_sre_pipeline

        final_state = run_sre_pipeline(
            incident_description="nginx OOMKilled 3 times, worker stopped",
            require_human_approval=False,
        )

        # Verify key state fields are populated
        assert final_state["overall_status"] in ("CRITICAL", "DEGRADED")
        assert len(final_state["steps_taken"]) >= 3
        assert final_state["health_report"]
        assert final_state["final_summary"]

    @pytest.mark.e2e
    def test_pipeline_skips_to_summary_if_healthy(self):
        """
        E2E: A healthy system should only run health_check and summary.
        LEARNING: Tests conditional routing in a real graph run.
        """
        from agents.orchestrator import build_sre_graph

        graph = build_sre_graph(require_human_approval=False)

        # Inject a state that says system is healthy to test the short path
        # We patch health_check_node to return HEALTHY status
        from agents.orchestrator import SREState

        with patch("agents.orchestrator.health_check_node") as mock_health:
            mock_health.return_value = {
                "health_report": "All systems healthy",
                "overall_status": "HEALTHY",
                "unhealthy_services": [],
                "current_step": "health_check",
                "steps_taken": ["health_check"],
            }

            initial_state: SREState = {
                "trigger": "test",
                "incident_description": "routine check",
                "health_report": "", "overall_status": "", "unhealthy_services": [],
                "log_analysis": "", "log_evidence": [],
                "runbook_recommendations": "", "recommended_actions": [],
                "proposed_fix": {}, "fix_reflection": {}, "fix_approved": False,
                "current_step": "start", "steps_taken": [], "final_summary": "",
            }

            config = {"configurable": {"thread_id": "test-healthy"}}
            final_state = graph.invoke(initial_state, config=config)

        # log_retrieval and citation should NOT have run
        assert "log_retrieval" not in final_state["steps_taken"]
        assert final_state["overall_status"] == "HEALTHY"

    @pytest.mark.e2e
    def test_api_orchestrator_endpoint(self):
        """E2E: Test POST /run-pipeline via FastAPI TestClient."""
        from fastapi.testclient import TestClient
        from api.main import app
        client = TestClient(app)

        response = client.post(
            "/run-pipeline",
            json={
                "incident_description": "nginx OOMKilled",
                "require_human_approval": False,
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "final_summary" in data
        assert "steps_taken" in data
        assert len(data["steps_taken"]) > 0
