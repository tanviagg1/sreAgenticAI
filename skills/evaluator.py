"""
LLM Evaluator — assesses the quality of pipeline outputs.

LEARNING — LLM-as-judge (LLM Evaluation):

Testing deterministic code is easy: assert output == expected.
Testing LLM outputs is hard: the output varies, and "correctness" is subjective.

LLM evaluation (also called "LLM-as-judge") solves this by using
a second LLM call to score the first LLM's output.

Metrics we evaluate:
  FAITHFULNESS:   Is the answer grounded in retrieved data? (RAG quality)
  COMPLETENESS:   Did it address all parts of the question?
  ACTIONABILITY:  Are recommendations specific enough to act on?
  CITATION:       Are sources cited for every claim?

LEARNING — Why this matters:
In production, you run LLM eval continuously to catch regressions.
If faithfulness score drops after a model update, you know something broke.
Tools like deepeval, RAGAS, and LangSmith automate this at scale.

LEARNING — Limitations of LLM-as-judge:
- The judge LLM can also hallucinate or be inconsistent
- Scores are not perfectly reproducible (temperature matters)
- Best used as a relative signal (did quality improve?) not absolute truth
- Use temperature=0 for the judge to maximise consistency
"""

import json
import os
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv

load_dotenv()


def evaluate_pipeline_output(final_state: dict) -> dict:
    """
    Use an LLM to evaluate the quality of the orchestrator's final output.

    LEARNING — Evaluating a RAG pipeline:
    We check four dimensions that matter for SRE AI systems:
      1. Faithfulness — did it make things up?
      2. Completeness — did it miss any issues?
      3. Actionability — can an engineer act on this right now?
      4. Citation quality — is every recommendation cited?

    The judge receives the full pipeline output and scores each dimension.
    """
    from prompts.orchestrator_prompts import LLM_EVAL_PROMPT

    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        temperature=0,          # LEARNING: always use temp=0 for evaluation — need consistency
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )

    eval_prompt = LLM_EVAL_PROMPT.format(
        final_summary=final_state.get("final_summary", ""),
        steps_taken=" -> ".join(final_state.get("steps_taken", [])),
    )

    response = llm.invoke([
        SystemMessage(content="You are an objective evaluator of AI system outputs. Be critical and honest."),
        HumanMessage(content=eval_prompt),
    ])

    raw = response.content.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])

    try:
        scores = json.loads(raw)
    except json.JSONDecodeError:
        scores = {
            "faithfulness": 0,
            "completeness": 0,
            "actionability": 0,
            "citation_quality": 0,
            "overall": 0,
            "reasoning": "Evaluation output could not be parsed",
            "improvement_suggestions": [],
        }

    return scores


def evaluate_rag_retrieval(query: str, retrieved_chunks: list[dict], answer: str) -> dict:
    """
    Evaluate RAG retrieval quality for a specific query.

    LEARNING — RAG-specific evaluation:
    For RAG systems, you evaluate two things separately:
      1. RETRIEVAL quality: did we get the right chunks?
      2. GENERATION quality: did the LLM use the chunks correctly?

    This function evaluates retrieval + grounding together.

    RAGAS metrics (industry standard for RAG eval):
      - Context Precision: were retrieved chunks relevant?
      - Context Recall: did we retrieve all needed information?
      - Answer Faithfulness: is the answer supported by the chunks?
      - Answer Relevancy: does the answer address the question?
    """
    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        temperature=0,
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )

    chunks_text = "\n---\n".join([
        f"[{c.get('service', 'unknown')}]: {c.get('content', '')[:200]}"
        for c in retrieved_chunks[:3]
    ])

    prompt = f"""Evaluate this RAG retrieval result:

QUERY: {query}

RETRIEVED CHUNKS:
{chunks_text}

GENERATED ANSWER:
{answer[:500]}

Score 1-5:
1. CONTEXT_PRECISION: Are these chunks relevant to the query?
2. ANSWER_FAITHFULNESS: Is the answer supported by the chunks (not hallucinated)?
3. ANSWER_RELEVANCY: Does the answer actually address the query?

Respond in JSON:
{{
  "context_precision": <1-5>,
  "answer_faithfulness": <1-5>,
  "answer_relevancy": <1-5>,
  "hallucination_detected": true/false,
  "reasoning": "<brief explanation>"
}}
"""
    response = llm.invoke([HumanMessage(content=prompt)])
    raw = response.content.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "Evaluation parsing failed", "raw": response.content}
