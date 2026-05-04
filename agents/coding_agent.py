"""
Coding Agent — Phase 4.

LEARNING — What is new in this phase:

Phase 3: Agent searches and recommends ("here is what the runbook says to do")
Phase 4: Agent generates the actual fix ("here is the exact config change")
         + critiques its own fix (self-reflection)
         + requires human approval before the fix is "applied"

LEARNING — Self-Reflection Pattern:
This is a two-LLM-call pattern:

  Call 1 — GENERATION:
    "Read the nginx config. Generate a fix for the OOM issue. Respond in JSON."
    -> returns a CodeFix JSON object

  Call 2 — REFLECTION:
    "Here is the proposed fix. Review it. Does it solve the problem?
     Any new risks? Confidence score 1-10."
    -> returns a Reflection JSON object

  Decision:
    confidence >= 7 AND approved=True -> present to human for approval
    otherwise -> revise and try again (up to max_revisions times)

LEARNING — Human-in-the-Loop:
Even after self-reflection approves a fix, we require human confirmation.
This implements Level 2 autonomy:
  - Agent CAN read service configs (autonomous)
  - Agent CAN generate and critique fixes (autonomous)
  - Agent CANNOT apply fixes without human saying "yes" (gate)

This is critical for SRE systems — a bad config change can cause an outage.
"""

import os
import json
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents import create_agent

from prompts.coding_prompts import (
    CODING_AGENT_SYSTEM_PROMPT,
    CODE_FIX_SCHEMA,
    REFLECTION_PROMPT,
)
from skills.code_tools import (
    list_fixable_services,
    read_service_config,
    get_known_issues,
    validate_fix_schema,
)

load_dotenv()

CODING_AGENT_TOOLS = [
    list_fixable_services,
    read_service_config,
    get_known_issues,
    validate_fix_schema,
]

# Minimum confidence score (1-10) for a fix to pass reflection without revision
CONFIDENCE_THRESHOLD = 7
MAX_REVISIONS = 2


def get_llm():
    return ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        temperature=0,
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )


def generate_fix(service_name: str, problem_description: str) -> dict | None:
    """
    Step 1: Generate a code fix using the Coding Agent.

    LEARNING — Structured output via prompt:
    We instruct the LLM to respond ONLY in JSON matching CODE_FIX_SCHEMA.
    The agent reads the service config via tools first (grounded generation),
    then produces a structured fix.
    """
    agent = create_agent(
        model=get_llm(),
        tools=CODING_AGENT_TOOLS,
        system_prompt=CODING_AGENT_SYSTEM_PROMPT,
    )

    query = f"""Fix the following SRE issue for the '{service_name}' service:

PROBLEM: {problem_description}

Steps:
1. Call list_fixable_services to confirm the service exists
2. Call read_service_config('{service_name}') to see the current config
3. Call get_known_issues('{service_name}') to see all detected problems
4. Generate a fix for the specific problem described above

{CODE_FIX_SCHEMA}
"""
    result = agent.invoke({"messages": [HumanMessage(content=query)]})
    raw_output = result["messages"][-1].content

    # LEARNING — Parsing structured output:
    # The LLM should return pure JSON but sometimes wraps it in markdown.
    # We strip markdown code fences if present.
    cleaned = raw_output.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1])  # strip first and last lines

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # If JSON parsing fails, return raw output for debugging
        return {"raw_output": raw_output, "parse_error": "LLM did not return valid JSON"}


def reflect_on_fix(problem: str, fix: dict) -> dict:
    """
    Step 2: Self-reflection — LLM critiques its own generated fix.

    LEARNING — Why a separate LLM call for reflection?
    If you ask "generate a fix AND check if it's good" in one call,
    the LLM tends to be overconfident about its own output.
    A separate call forces a fresh perspective — like having a second
    engineer review a PR after the first one wrote it.

    We use a direct LLM call here (not an agent with tools) because
    reflection is pure reasoning — no tool calls needed.
    """
    llm = get_llm()

    reflection_query = REFLECTION_PROMPT.format(
        problem=problem,
        fix=json.dumps(fix, indent=2),
    )

    response = llm.invoke([
        SystemMessage(content="You are a senior SRE reviewing a proposed fix. Be critical and honest."),
        HumanMessage(content=reflection_query),
    ])

    raw = response.content.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Reflection failed to parse — default to requiring revision
        return {
            "approved": False,
            "confidence_score": 0,
            "reasoning": "Reflection output could not be parsed",
            "revision_needed": "Re-generate the fix with clearer JSON output",
        }


def run_coding_agent(service_name: str, problem_description: str, auto_approve: bool = False) -> dict:
    """
    Full Coding Agent pipeline:
      1. Generate fix (Coding Agent with tools)
      2. Reflect on fix (self-critique LLM call)
      3. Revise if needed (up to MAX_REVISIONS times)
      4. Present to human for approval (Human-in-the-Loop gate)

    LEARNING — auto_approve=False by default:
    This enforces human-in-the-loop. Set to True only in tests where
    we want to verify the full pipeline without a human prompt.

    Returns a dict with:
      - fix: the generated CodeFix
      - reflection: the self-critique result
      - approved: whether human approved
      - revision_count: how many revisions were needed
    """
    print(f"\nGenerating fix for '{service_name}': {problem_description}")

    fix = None
    reflection = None
    revision_count = 0

    for attempt in range(MAX_REVISIONS + 1):
        print(f"\n--- Generation attempt {attempt + 1} ---")

        fix = generate_fix(service_name, problem_description)

        if "parse_error" in fix:
            print(f"Fix generation failed: {fix['parse_error']}")
            continue

        print(f"Fix generated. Risk level: {fix.get('risk_level', 'unknown')}")

        # LEARNING — Self-reflection loop
        print("\nRunning self-reflection...")
        reflection = reflect_on_fix(problem_description, fix)

        confidence = reflection.get("confidence_score", 0)
        approved = reflection.get("approved", False)
        print(f"Reflection: confidence={confidence}/10, approved={approved}")

        if approved and confidence >= CONFIDENCE_THRESHOLD:
            print("Fix passed self-reflection.")
            break
        else:
            revision_count += 1
            revision_note = reflection.get("revision_needed", "")
            print(f"Fix needs revision: {revision_note}")
            if attempt < MAX_REVISIONS:
                # Append revision instructions to problem description
                problem_description = f"{problem_description}\n\nPrevious fix was rejected. {revision_note}"

    # LEARNING — Human-in-the-Loop gate:
    # Even after reflection approves, a human must confirm before fix is "applied".
    # In a real system this would pause and wait for Slack/PagerDuty approval.
    human_approved = False
    if fix and "parse_error" not in fix:
        if auto_approve:
            # Test mode — skip human prompt
            human_approved = True
        else:
            print("\n" + "=" * 60)
            print("PROPOSED FIX (requires your approval)")
            print("=" * 60)
            print(f"File: {fix.get('file')}")
            print(f"Problem: {fix.get('problem_summary')}")
            print(f"Risk: {fix.get('risk_level')}")
            print(f"\nOriginal:\n{fix.get('original')}")
            print(f"\nFixed:\n{fix.get('fixed')}")
            print(f"\nExplanation: {fix.get('explanation')}")
            print(f"\nSide effects: {fix.get('side_effects', [])}")
            print(f"\nSelf-reflection confidence: {reflection.get('confidence_score')}/10")
            print("=" * 60)

            response = input("\nApply this fix? (yes/no): ").strip().lower()
            human_approved = response in ("yes", "y")

    return {
        "service": service_name,
        "fix": fix,
        "reflection": reflection,
        "human_approved": human_approved,
        "revision_count": revision_count,
        "status": "approved" if human_approved else "rejected",
    }


if __name__ == "__main__":
    # Demo: fix the nginx memory limit issue
    result = run_coding_agent(
        service_name="nginx",
        problem_description="nginx is OOMKilled because the memory limit of 512Mi is too low. "
                            "Memory usage reaches 100% of the limit before being killed. "
                            "Fix the memory limit and add a memory alert threshold.",
    )
    print(f"\nFinal status: {result['status']}")
    print(f"Revisions needed: {result['revision_count']}")
