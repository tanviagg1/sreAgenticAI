"""
Coding Agent prompt templates.

LEARNING — Structured Output Prompting:

When an LLM generates code or config changes, you want the output in a
specific machine-readable format — not free text. Otherwise you can't
programmatically apply the fix or pass it to another agent.

Approach: instruct the LLM to respond ONLY in JSON with a fixed schema.
This is called "structured output" or "constrained generation".

Schema we enforce:
{
  "file": "which file/config to change",
  "change_type": "modify | add | delete",
  "original": "the current (broken) code",
  "fixed": "the corrected code",
  "explanation": "why this fixes the problem",
  "risk_level": "low | medium | high",
  "side_effects": ["list of possible side effects"]
}

LEARNING — Self-Reflection Prompt:
After generating a fix, we run a SECOND LLM call asking it to critique
the fix it just generated. This catches issues the first pass missed.

The reflection prompt asks:
  1. Does the fix actually solve the stated problem?
  2. Does it introduce any new risks?
  3. Is it the minimal change needed?
  4. Confidence score 1-10

If confidence < 7: the agent revises the fix.
If confidence >= 7: the fix is returned for human approval.

This "generate -> critique -> revise" loop dramatically improves code quality.
"""

CODING_AGENT_SYSTEM_PROMPT = """You are an expert SRE engineer specializing in container configuration and infrastructure fixes.

Your job is to generate precise, minimal configuration fixes for SRE issues.

Rules:
- Only fix what is broken — do not refactor or improve unrelated code
- Always generate the MINIMAL change that solves the problem
- Always explain WHY the change fixes the issue
- Assess the risk level of your change honestly
- If unsure about a fix, say so — do not guess

Output format: always respond in valid JSON matching the CodeFix schema.
"""

# LEARNING — Structured output schema embedded in the prompt.
# The LLM reads this and knows exactly what fields to populate.
# Tip: include an example for complex schemas — LLMs follow examples well.
CODE_FIX_SCHEMA = """
Respond ONLY with valid JSON in this exact schema:

{
  "file": "<name of the file or config being changed>",
  "change_type": "<modify | add | delete>",
  "problem_summary": "<one sentence: what is broken and why>",
  "original": "<the current broken config/code as a string>",
  "fixed": "<the corrected config/code as a string>",
  "explanation": "<why this specific change fixes the problem>",
  "risk_level": "<low | medium | high>",
  "side_effects": ["<possible side effect 1>", "<possible side effect 2>"]
}

Do not include any text outside the JSON. No markdown. No explanation. Just the JSON object.
"""

# LEARNING — Self-Reflection Prompt:
# This is sent as a second LLM call after the fix is generated.
# The LLM acts as a "reviewer" of its own previous output.
# Separating generation and critique into two calls produces better results
# than asking for generation + critique in one call.
REFLECTION_PROMPT = """You are a senior SRE reviewing a proposed configuration fix.

Evaluate this fix critically:

ORIGINAL PROBLEM:
{problem}

PROPOSED FIX:
{fix}

Assess:
1. Does this fix actually solve the stated problem? (yes/no + reason)
2. Does it introduce any new risks or regressions? (list them)
3. Is this the minimal change needed, or is it over-engineered?
4. Are the stated side effects complete?

Respond ONLY in JSON:
{{
  "solves_problem": true/false,
  "reasoning": "<why it does or does not solve the problem>",
  "new_risks": ["<risk 1>", "<risk 2>"],
  "is_minimal": true/false,
  "missing_side_effects": ["<any side effects not listed>"],
  "confidence_score": <1-10>,
  "approved": true/false,
  "revision_needed": "<if approved=false, what specifically needs to change>"
}}
"""
