"""
Tests for Phase 1 — Health Agent.

LEARNING — Testing AI Systems:

There are three layers of tests here:

1. UNIT TESTS (class TestContainerHealthTools)
   - Test tools in complete isolation — NO LLM involved
   - These are fast, deterministic, always pass if code is correct
   - Test the Python logic, not the AI reasoning

2. INTEGRATION TESTS (class TestHealthAgentIntegration)
   - Test agent + tools together WITH the LLM
   - Marked @pytest.mark.e2e — require Ollama to be running
   - These are slower (LLM inference takes a few seconds)
   - Check that the LLM uses tools correctly and produces useful output

3. END-TO-END TESTS (class TestHealthAgentE2E)
   - Full pipeline: API endpoint -> agent -> tools -> report
   - Validates the entire system works together
   - Marked @pytest.mark.e2e

LEARNING — What NOT to test in AI:
   Don't assert on exact LLM output strings — they vary slightly each run.
   Instead, assert on:
     - Presence of key information (container names, severity words)
     - Structure (has sections, is non-empty)
     - Deterministic tool outputs (these are exact)
"""

import pytest
from fastapi.testclient import TestClient


# =============================================================================
# UNIT TESTS — No LLM, test tools in isolation
# =============================================================================

class TestContainerHealthTools:
    """
    LEARNING: Unit tests should be fast and not depend on external systems.
    We test the @tool functions by calling .invoke() on them directly.
    This is how LangChain tools are called programmatically.
    """

    def test_list_all_containers_returns_five(self):
        """Should return all 5 mock containers."""
        from skills.container_health import list_all_containers
        result = list_all_containers.invoke({})
        assert len(result) == 5
        assert "nginx" in result
        assert "postgres" in result
        assert "redis" in result
        assert "app-server" in result
        assert "worker" in result

    def test_check_known_container_nginx(self):
        """nginx is OOMKilled in mocks — verify tool returns correct data."""
        from skills.container_health import check_container_health
        result = check_container_health.invoke({"container_name": "nginx"})
        assert result["status"] == "unhealthy"
        assert result["reason"] == "OOMKilled"
        assert result["memory_mb"] == result["memory_limit_mb"]  # at 100% of limit

    def test_check_known_container_postgres(self):
        """postgres is healthy in mocks."""
        from skills.container_health import check_container_health
        result = check_container_health.invoke({"container_name": "postgres"})
        assert result["status"] == "running"
        assert result["reason"] is None

    def test_check_unknown_container_returns_error(self):
        """Unknown container name should return an error dict, not raise."""
        from skills.container_health import check_container_health
        result = check_container_health.invoke({"container_name": "doesnotexist"})
        assert "error" in result

    def test_get_unhealthy_containers_count(self, expected_unhealthy):
        """Should return exactly 3 unhealthy containers (nginx, app-server, worker)."""
        from skills.container_health import get_unhealthy_containers
        result = get_unhealthy_containers.invoke({})
        names = {c["name"] for c in result}
        assert names == expected_unhealthy

    def test_get_unhealthy_containers_excludes_healthy(self, expected_healthy):
        """postgres and redis should NOT appear in unhealthy list."""
        from skills.container_health import get_unhealthy_containers
        result = get_unhealthy_containers.invoke({})
        names = {c["name"] for c in result}
        assert names.isdisjoint(expected_healthy)

    def test_get_unhealthy_containers_sorted_by_severity(self):
        """
        Stopped containers should appear before unhealthy before degraded.
        LEARNING: Testing sort order ensures the agent gets prioritized info.
        """
        from skills.container_health import get_unhealthy_containers
        result = get_unhealthy_containers.invoke({})
        statuses = [c["status"] for c in result]
        # worker (stopped) should come before nginx (unhealthy) before app-server (degraded)
        assert statuses.index("stopped") < statuses.index("unhealthy")
        assert statuses.index("unhealthy") < statuses.index("degraded")

    def test_get_system_summary_overall_status_critical(self):
        """With nginx unhealthy and worker stopped, overall should be CRITICAL."""
        from skills.container_health import get_system_summary
        result = get_system_summary.invoke({})
        assert result["overall_status"] == "CRITICAL"
        assert result["total_containers"] == 5
        assert result["healthy"] == 2
        assert result["unhealthy"] == 3

    def test_get_system_summary_status_breakdown(self):
        """Verify breakdown counts match mock data."""
        from skills.container_health import get_system_summary
        result = get_system_summary.invoke({})
        breakdown = result["status_breakdown"]
        assert breakdown.get("running") == 2
        assert breakdown.get("unhealthy") == 1
        assert breakdown.get("degraded") == 1
        assert breakdown.get("stopped") == 1


# =============================================================================
# INTEGRATION TESTS — Agent + LLM (requires Ollama running)
# =============================================================================

class TestHealthAgentIntegration:
    """
    LEARNING: Integration tests verify the LLM uses tools correctly.
    We check the output contains expected information, not exact wording.
    """

    @pytest.mark.e2e
    def test_agent_mentions_unhealthy_containers(self):
        """Agent report should mention the known bad containers."""
        from agents.health_agent import run_health_check
        result = run_health_check()

        assert "output" in result
        output = result["output"].lower()

        # At least one unhealthy container should appear in the report
        assert any(name in output for name in ["nginx", "worker", "app-server"])

    @pytest.mark.e2e
    def test_agent_identifies_critical_severity(self):
        """Agent should recognize the system is in a critical state."""
        from agents.health_agent import run_health_check
        result = run_health_check()
        output = result["output"].lower()

        # Should mention critical/high severity or the stopped/oomkilled states
        severity_words = ["critical", "stopped", "oom", "unhealthy", "high", "down"]
        assert any(word in output for word in severity_words)

    @pytest.mark.e2e
    def test_agent_output_is_non_empty(self):
        """Agent should always produce a non-empty report."""
        from agents.health_agent import run_health_check
        result = run_health_check()
        assert result["output"]
        assert len(result["output"]) > 100  # More than a trivial response


# =============================================================================
# END-TO-END TESTS — Full API pipeline
# =============================================================================

class TestHealthAgentE2E:
    """
    LEARNING: E2E tests verify the whole system works — API, agent, tools, LLM.
    We use FastAPI's TestClient which simulates HTTP requests without starting a real server.
    """

    @pytest.fixture
    def client(self):
        """
        LEARNING: TestClient from FastAPI wraps the app for testing.
        No real HTTP server is started — requests are handled in-process.
        """
        from api.main import app
        return TestClient(app)

    def test_root_endpoint(self, client):
        """Root endpoint should return 200 and confirm the app is running."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["phase"] == 1

    @pytest.mark.e2e
    def test_health_check_endpoint_returns_200(self, client):
        """Full health check via API should succeed."""
        response = client.get("/health-check")
        assert response.status_code == 200

    @pytest.mark.e2e
    def test_health_check_endpoint_response_schema(self, client):
        """Response should match the HealthCheckResponse schema."""
        response = client.get("/health-check")
        data = response.json()

        # Verify all expected fields are present
        assert "status" in data
        assert "report" in data
        assert "containers_checked" in data

        # Verify types and values
        assert data["status"] == "ok"
        assert data["containers_checked"] == 5
        assert isinstance(data["report"], str)
        assert len(data["report"]) > 0

    @pytest.mark.e2e
    def test_health_check_report_covers_critical_issues(self, client):
        """
        Full E2E: API -> agent -> tools -> LLM -> report.
        The report must surface at least one of the known critical issues.
        """
        response = client.get("/health-check")
        report = response.json()["report"].lower()

        # At minimum, the most critical container (stopped worker) should be mentioned
        critical_signals = ["worker", "stopped", "nginx", "oom", "critical"]
        assert any(signal in report for signal in critical_signals), (
            f"Report did not mention any critical issues. Report was:\n{report}"
        )
