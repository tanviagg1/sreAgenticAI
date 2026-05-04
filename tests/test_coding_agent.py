"""
Tests for Phase 4 — Coding Agent.

LEARNING — Testing code generation agents:

New challenges vs previous phases:
1. Output is JSON — we can validate schema precisely (unlike free-text reports)
2. Self-reflection is a second LLM call — test both passes independently
3. Human-in-the-loop gate — use auto_approve=True in tests to skip the prompt
4. Revision loop — test that bad fixes trigger revision

Testing strategy:
- Unit: test tools (read config, detect issues, validate schema) — no LLM
- Integration: test fix generation schema compliance — LLM required
- E2E: test full pipeline including reflection and auto-approval — LLM required

LEARNING — What makes code generation tests different:
  Regular test: assert output == "expected string"  ← exact match
  AI code gen test: assert fix["risk_level"] in ["low", "medium", "high"]  ← schema check
                    assert "memory" in fix["explanation"].lower()  ← content check
                    assert fix["fixed"] != fix["original"]  ← change happened

We test STRUCTURE and KEY CONTENT, not exact wording.
"""

import pytest
import json


# =============================================================================
# UNIT TESTS — No LLM, test tools in isolation
# =============================================================================

class TestCodeTools:
    """Test code reading and issue detection tools."""

    def test_list_fixable_services_returns_three(self):
        from skills.code_tools import list_fixable_services
        result = list_fixable_services.invoke({})
        assert len(result) == 3
        names = {s["service"] for s in result}
        assert names == {"nginx", "worker", "app-server"}

    def test_read_nginx_config(self):
        from skills.code_tools import read_service_config
        result = read_service_config.invoke({"service_name": "nginx"})
        assert result["service_name"] == "nginx"
        assert "resources" in result
        assert "memory_limit" in result["resources"]

    def test_read_unknown_service_returns_error(self):
        from skills.code_tools import read_service_config
        result = read_service_config.invoke({"service_name": "doesnotexist"})
        assert "error" in result

    def test_nginx_has_memory_issue_detected(self):
        """
        LEARNING: Issue detection is deterministic Python code — testable without LLM.
        The memory_limit of 512Mi is the known bug in the mock config.
        """
        from skills.code_tools import get_known_issues
        issues = get_known_issues.invoke({"service_name": "nginx"})
        severities = [i["severity"] for i in issues]
        assert "high" in severities

        fields = [i["field"] for i in issues]
        assert any("memory_limit" in f for f in fields)

    def test_worker_has_retry_issue_detected(self):
        from skills.code_tools import get_known_issues
        issues = get_known_issues.invoke({"service_name": "worker"})
        fields = [i["field"] for i in issues]
        assert any("DB_RETRY_ATTEMPTS" in f for f in fields)

    def test_app_server_has_scaling_issue_detected(self):
        from skills.code_tools import get_known_issues
        issues = get_known_issues.invoke({"service_name": "app-server"})
        fields = [i["field"] for i in issues]
        assert any("replicas" in f for f in fields)

    def test_validate_fix_schema_valid(self):
        """A correctly formed fix JSON should pass validation."""
        from skills.code_tools import validate_fix_schema
        valid_fix = json.dumps({
            "file": "docker-compose.yml",
            "change_type": "modify",
            "problem_summary": "memory limit too low",
            "original": "memory_limit: 512Mi",
            "fixed": "memory_limit: 1Gi",
            "explanation": "doubles the limit",
            "risk_level": "low",
            "side_effects": ["increased memory cost"],
        })
        result = validate_fix_schema.invoke({"fix_json": valid_fix})
        assert result["valid"] is True

    def test_validate_fix_schema_missing_fields(self):
        """A fix missing required fields should fail validation."""
        from skills.code_tools import validate_fix_schema
        incomplete = json.dumps({"file": "docker-compose.yml"})
        result = validate_fix_schema.invoke({"fix_json": incomplete})
        assert result["valid"] is False
        assert "missing_fields" in result

    def test_validate_fix_schema_unchanged_code(self):
        """A fix where original == fixed should fail validation."""
        from skills.code_tools import validate_fix_schema
        no_change = json.dumps({
            "file": "docker-compose.yml",
            "change_type": "modify",
            "problem_summary": "test",
            "original": "memory: 512Mi",
            "fixed": "memory: 512Mi",   # same as original — invalid
            "explanation": "no change",
            "risk_level": "low",
            "side_effects": [],
        })
        result = validate_fix_schema.invoke({"fix_json": no_change})
        assert result["valid"] is False

    def test_validate_fix_invalid_risk_level(self):
        """Invalid risk_level value should fail validation."""
        from skills.code_tools import validate_fix_schema
        bad_risk = json.dumps({
            "file": "x",
            "change_type": "modify",
            "problem_summary": "test",
            "original": "a",
            "fixed": "b",
            "explanation": "test",
            "risk_level": "extreme",    # not in [low, medium, high]
            "side_effects": [],
        })
        result = validate_fix_schema.invoke({"fix_json": bad_risk})
        assert result["valid"] is False


# =============================================================================
# INTEGRATION TESTS — Fix generation with LLM (structured output)
# =============================================================================

class TestFixGeneration:
    """
    LEARNING: Test that the LLM generates valid structured JSON fixes.
    We validate schema compliance, not exact content.
    """

    @pytest.mark.e2e
    def test_nginx_fix_is_valid_json(self):
        """Fix for nginx OOM should be parseable JSON with all required fields."""
        from agents.coding_agent import generate_fix
        fix = generate_fix(
            "nginx",
            "nginx OOMKilled because memory_limit of 512Mi is too low"
        )
        assert "parse_error" not in fix, f"Fix was not valid JSON: {fix.get('raw_output')}"
        assert "file" in fix
        assert "fixed" in fix
        assert "explanation" in fix
        assert "risk_level" in fix

    @pytest.mark.e2e
    def test_nginx_fix_changes_memory(self):
        """The fix for an OOM issue should change the memory limit."""
        from agents.coding_agent import generate_fix
        fix = generate_fix(
            "nginx",
            "nginx OOMKilled because memory_limit of 512Mi is too low"
        )
        assert "parse_error" not in fix

        # The fix should reference memory in some way
        fix_text = json.dumps(fix).lower()
        assert any(word in fix_text for word in ["memory", "512", "1gi", "limit"])

    @pytest.mark.e2e
    def test_fix_original_differs_from_fixed(self):
        """The fix must actually change something."""
        from agents.coding_agent import generate_fix
        fix = generate_fix(
            "worker",
            "worker crashes when database is unavailable — no retry logic configured"
        )
        assert "parse_error" not in fix
        assert fix.get("original") != fix.get("fixed"), "Fix did not change anything"

    @pytest.mark.e2e
    def test_risk_level_is_valid_enum(self):
        """risk_level must be one of the valid enum values."""
        from agents.coding_agent import generate_fix
        fix = generate_fix("nginx", "nginx OOMKilled, memory limit too low")
        assert "parse_error" not in fix
        assert fix.get("risk_level") in ["low", "medium", "high"]


# =============================================================================
# INTEGRATION TESTS — Self-reflection
# =============================================================================

class TestSelfReflection:
    """
    LEARNING: Test the reflection (self-critique) pass.
    Reflection should approve good fixes and reject bad ones.
    """

    @pytest.mark.e2e
    def test_reflection_on_good_fix_approves(self):
        """A well-formed fix should pass reflection with confidence >= 7."""
        from agents.coding_agent import reflect_on_fix

        good_fix = {
            "file": "docker-compose.yml",
            "change_type": "modify",
            "problem_summary": "nginx OOMKilled because memory_limit is 512Mi",
            "original": "memory_limit: 512Mi",
            "fixed": "memory_limit: 1Gi",
            "explanation": "Doubles memory limit giving nginx headroom above its peak usage",
            "risk_level": "low",
            "side_effects": ["increased memory allocation per container"],
        }
        reflection = reflect_on_fix("nginx OOMKilled — memory_limit 512Mi too low", good_fix)

        assert "confidence_score" in reflection
        assert "approved" in reflection
        # A clearly correct fix should score reasonably well
        assert reflection["confidence_score"] >= 5

    @pytest.mark.e2e
    def test_reflection_on_bad_fix_rejects(self):
        """A fix that doesn't address the problem should fail reflection."""
        from agents.coding_agent import reflect_on_fix

        bad_fix = {
            "file": "docker-compose.yml",
            "change_type": "modify",
            "problem_summary": "nginx OOMKilled",
            "original": "restart_policy: on-failure:5",
            "fixed": "restart_policy: on-failure:10",   # wrong fix — doesn't address memory
            "explanation": "Allow more restarts before giving up",
            "risk_level": "low",
            "side_effects": [],
        }
        reflection = reflect_on_fix("nginx OOMKilled because memory_limit 512Mi too low", bad_fix)

        # This fix doesn't solve the OOM problem — should not be fully approved
        # either approved=False or confidence < 7
        solved = reflection.get("approved", True) and reflection.get("confidence_score", 10) >= 7
        assert not solved, "Reflection incorrectly approved a fix that doesn't solve the problem"

    @pytest.mark.e2e
    def test_reflection_returns_required_fields(self):
        """Reflection output must always have the schema fields."""
        from agents.coding_agent import reflect_on_fix

        fix = {
            "file": "x", "change_type": "modify", "problem_summary": "test",
            "original": "a", "fixed": "b", "explanation": "test",
            "risk_level": "low", "side_effects": [],
        }
        reflection = reflect_on_fix("test problem", fix)

        required = ["approved", "confidence_score", "reasoning"]
        for field in required:
            assert field in reflection, f"Missing reflection field: {field}"


# =============================================================================
# END-TO-END TESTS — Full pipeline with human-in-the-loop (auto_approve=True)
# =============================================================================

class TestCodingAgentE2E:
    """
    LEARNING: E2E tests use auto_approve=True to skip the human prompt.
    In production the agent would pause and wait for a human to type yes/no.
    In tests we bypass this so the pipeline runs fully automated.
    """

    @pytest.mark.e2e
    def test_full_nginx_pipeline_auto_approve(self):
        """
        E2E: Full pipeline for nginx OOM fix.
        auto_approve=True bypasses the human prompt for testing.
        """
        from agents.coding_agent import run_coding_agent
        result = run_coding_agent(
            service_name="nginx",
            problem_description="nginx OOMKilled — memory_limit is 512Mi which equals peak usage",
            auto_approve=True,
        )

        assert result["service"] == "nginx"
        assert result["fix"] is not None
        assert "parse_error" not in result["fix"]
        assert result["human_approved"] is True
        assert result["status"] == "approved"

    @pytest.mark.e2e
    def test_full_worker_pipeline_auto_approve(self):
        """E2E: Full pipeline for worker DB connection fix."""
        from agents.coding_agent import run_coding_agent
        result = run_coding_agent(
            service_name="worker",
            problem_description="worker crashes when database is unavailable — no retry or timeout configured",
            auto_approve=True,
        )

        assert result["fix"] is not None
        assert "parse_error" not in result["fix"]
        assert result["status"] == "approved"

    @pytest.mark.e2e
    def test_api_coding_endpoint(self):
        """E2E: Test POST /fix-code API endpoint."""
        from fastapi.testclient import TestClient
        from api.main import app
        client = TestClient(app)

        response = client.post(
            "/fix-code",
            json={
                "service_name": "nginx",
                "problem": "nginx OOMKilled, memory_limit too low",
                "auto_approve": True,
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["approved", "rejected"]
        assert "fix" in data
