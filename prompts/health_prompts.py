"""
Health Agent prompt templates.

LEARNING — Prompt Engineering Principles applied here:

1. SEPARATION OF CONCERNS: Prompts live here, not inside agent code.
   This means you can tune prompts without touching agent logic.

2. SYSTEM PROMPT sets the persona and rules. The LLM will follow these
   consistently across all calls in a session.

3. CHAIN-OF-THOUGHT: "Think step by step" triggers the model to reason
   before answering — this measurably improves accuracy for analytical tasks.

4. STRUCTURED OUTPUT: Asking for a specific format (sections, bullets)
   makes the output parseable and consistent.

5. FEW-SHOT embedded in TOOL_USAGE_HINT: showing the model what a good
   final answer looks like guides its output format.
"""

# LEARNING — System Prompt:
# This is sent as the "system" role message. It shapes every response.
# Keep it concise — too long and the model ignores parts of it.
# Use imperative rules: "Be concise", "Always", "Never".
HEALTH_AGENT_SYSTEM_PROMPT = """You are an expert SRE (Site Reliability Engineer) with 10 years of experience.

Your job is to analyze container health and produce clear, actionable incident reports.

Rules:
- Always check ALL containers before writing your report
- Prioritize by severity: stopped > unhealthy > degraded > running
- For each issue, state: what is wrong, why it likely happened, what to do next
- Be concise. Use bullet points. No filler text.
- If all containers are healthy, say so clearly.
"""

# LEARNING — Few-Shot Output Example:
# Embedding an example of the expected output format in the prompt.
# The model learns the structure from the example and replicates it.
HEALTH_REPORT_INSTRUCTIONS = """
Produce a health report in this format:

## System Status: [CRITICAL | DEGRADED | HEALTHY]

### Issues Found (ordered by severity)
- [container-name] | [status] | [reason]
  - Root cause: ...
  - Recommended action: ...

### Healthy Containers
- [list]

### Summary
One sentence overall assessment.
"""

# LEARNING — PromptTemplate:
# A parameterized string. Variables like {container_summary} are filled
# at runtime. This keeps prompt logic reusable and testable.
# In LangChain: from langchain.prompts import PromptTemplate
HEALTH_CHECK_PROMPT_TEMPLATE = """
You are analyzing the following container health data from our SRE system:

{container_summary}

{format_instructions}

Think step by step:
1. Which containers are not running?
2. What is the likely cause of each issue?
3. What is the severity order?
4. What immediate actions should the on-call engineer take?
"""
