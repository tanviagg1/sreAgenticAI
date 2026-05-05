"""
Orchestrator prompt templates.

LEARNING — Why the orchestrator needs its own prompts:

The orchestrator is the only agent that needs to reason about
WHICH other agent to call and WHY. Its prompts are about:
  1. Understanding the incident holistically
  2. Deciding routing strategy
  3. Synthesising all agent outputs into a final report

This is different from specialist agent prompts which focus on
doing one thing well (check health, search logs, find runbook).

LEARNING — LLM Evaluation:
At the end of a run, we can evaluate the quality of the pipeline output.
This is called "LLM-as-judge" — using an LLM to score another LLM's output.
Metrics:
  - Faithfulness: is the report grounded in actual findings?
  - Completeness: did it cover all unhealthy services?
  - Actionability: are the recommendations specific and executable?
"""

ORCHESTRATOR_SYSTEM_PROMPT = """You are the SRE Incident Coordinator.

You oversee a team of specialist agents:
- Health Agent: checks container status
- Retrieval Agent: searches logs
- Citation Agent: looks up runbooks
- Coding Agent: generates configuration fixes

Your job is to coordinate them and produce a coherent incident response.
Always ground your coordination decisions in what the agents have found — not assumptions.
"""

INCIDENT_SUMMARY_PROMPT = """
Write an executive incident summary based on the following agent findings.

Be concise (3 short paragraphs):
1. WHAT HAPPENED: health status, affected services, log evidence
2. ROOT CAUSE & RUNBOOK: what the logs and runbooks say
3. ACTION TAKEN: was a fix generated and approved? What are next steps?

Findings:
Health Status: {overall_status}
Affected Services: {unhealthy_services}
Log Analysis: {log_analysis}
Runbook Recommendations: {runbook_recommendations}
Fix Proposed: {proposed_fix}
Fix Approved: {fix_approved}
"""

# LEARNING — LLM-as-judge evaluation prompt:
# We ask an LLM to score the quality of the pipeline's final output.
# This is a form of automated quality assurance for AI systems.
# Real-world tools: deepeval, ragas, LangSmith
LLM_EVAL_PROMPT = """
You are evaluating the quality of an SRE incident response pipeline output.

Score each dimension 1-5 (5 = excellent):

FINAL SUMMARY:
{final_summary}

PIPELINE STEPS TAKEN:
{steps_taken}

Score these dimensions:
1. FAITHFULNESS (1-5): Is the summary grounded in actual findings, or does it hallucinate?
2. COMPLETENESS (1-5): Did the pipeline address all detected issues?
3. ACTIONABILITY (1-5): Are the recommendations specific and immediately executable?
4. CITATION QUALITY (1-5): Are sources cited for recommendations?
5. OVERALL (1-5): Overall quality of the incident response

Respond in JSON:
{{
  "faithfulness": <1-5>,
  "completeness": <1-5>,
  "actionability": <1-5>,
  "citation_quality": <1-5>,
  "overall": <1-5>,
  "reasoning": "<brief explanation of scores>",
  "improvement_suggestions": ["<suggestion 1>", "<suggestion 2>"]
}}
"""
