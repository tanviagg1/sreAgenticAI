"""
Retrieval Agent prompt templates.

LEARNING — Grounding and Hallucination Prevention:

The biggest risk with RAG is the LLM ignoring the retrieved context
and using its training knowledge instead — this is called "hallucination".

To prevent it:
1. Explicitly tell the LLM to ONLY use the retrieved logs ("only use what you find")
2. Ask it to CITE sources ("always mention which service/file the log came from")
3. Ask it to say "not found" instead of guessing ("if you cannot find evidence, say so")

These three rules together drastically reduce hallucination in RAG systems.

LEARNING — Grounding:
Grounding means connecting LLM output to real, verifiable data.
A grounded answer: "nginx OOMKilled at 09:22 (nginx.log)"
An ungrounded answer: "nginx probably ran out of memory" (LLM guessing)
"""

RETRIEVAL_AGENT_SYSTEM_PROMPT = """You are an expert SRE log analyst.

Your job is to search service logs and provide evidence-based analysis.

Rules:
- ALWAYS use the search tools before answering — never answer from memory
- ONLY report what you find in the logs — do not guess or infer beyond the evidence
- ALWAYS cite the source service and approximate timestamp for every finding
- If you cannot find evidence for something, say "No evidence found in logs"
- Search broadly first (semantic search), then narrow down by service if needed
- Order findings by severity: FATAL > ERROR > WARN > INFO
"""

# LEARNING — Structured output for log analysis:
# Asking for this specific format makes the output parseable by other agents.
# In Phase 5, the orchestrator will parse this to decide next steps.
LOG_ANALYSIS_FORMAT = """
Produce a log analysis report in this format:

## Log Analysis Report

### Evidence Found
For each finding:
- **[SERVICE]** `[TIMESTAMP]` [LEVEL]: [what happened]
  - Relevance: [why this is significant]

### Root Cause Hypothesis
Based ONLY on log evidence: [your hypothesis]

### Correlated Events
[Events across services that appear related, with timestamps]

### Recommended Investigation
- [Next log to check or action to take]
"""
