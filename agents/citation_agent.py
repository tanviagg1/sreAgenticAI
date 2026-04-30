"""
Citation Agent — Phase 3.

LEARNING — What is new in this phase:

Phase 2: Agent searches LOGS to find what happened.
Phase 3: Agent searches RUNBOOKS to find what to DO about it.
         Agent also searches PAST INCIDENTS to see if it happened before.

Together, Phases 2 + 3 give you:
  "Here is what the logs show" (Retrieval Agent)
  + "Here is what to do about it, per our runbooks" (Citation Agent)

LEARNING — Agent Memory in LangGraph:
Short-term memory is automatic — every message in the conversation is stored
in the `messages` list in LangGraph state and passed to the LLM each turn.
This means the agent "remembers" what tools it called and what they returned
throughout the current session.

Long-term memory (past incidents) lives in ChromaDB and persists across sessions.
The agent accesses it via the search_past_incidents tool.

LEARNING — Conversational agents:
Unlike Phase 1 (single health check) and Phase 2 (single log query),
the Citation Agent can support multi-turn conversations.
Each call to run_citation_query can carry conversation history forward,
letting the agent build on previous questions.
"""

import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage
from langchain.agents import create_agent

from prompts.citation_prompts import CITATION_AGENT_SYSTEM_PROMPT, CITATION_REPORT_FORMAT
from skills.citation_tools import (
    list_available_runbooks,
    search_runbooks_for_symptom,
    search_past_incidents,
    record_incident,
)

load_dotenv()

CITATION_AGENT_TOOLS = [
    list_available_runbooks,      # Always start here — know what runbooks exist
    search_runbooks_for_symptom,  # Core tool — find the right procedure
    search_past_incidents,        # Long-term memory — has this happened before?
    record_incident,              # Write to long-term memory after resolution
]


def create_citation_agent():
    """
    Build the Citation Agent.

    LEARNING — Same create_agent pattern, different tools + system prompt.
    The agent's behaviour is entirely shaped by:
      1. Which tools it has access to
      2. What the system prompt tells it to do with those tools
    The LLM itself (Llama) does not change across agents.
    """
    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        temperature=0,
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )

    agent = create_agent(
        model=llm,
        tools=CITATION_AGENT_TOOLS,
        system_prompt=CITATION_AGENT_SYSTEM_PROMPT,
    )
    return agent


def run_citation_query(symptom: str, conversation_history: list = None) -> dict:
    """
    Run the Citation Agent with a symptom description.

    LEARNING — Conversation history (short-term memory):
    The optional conversation_history lets callers pass previous turns.
    This enables multi-turn use: ask about nginx, then ask a follow-up,
    and the agent remembers the context from the first question.

    Format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]

    In LangGraph this translates to HumanMessage / AIMessage objects.
    """
    agent = create_citation_agent()

    # LEARNING — Building message history for multi-turn conversation:
    # LangGraph agents use a messages list. We prepend any prior conversation
    # turns so the agent has full context when answering the new question.
    messages = []

    if conversation_history:
        for turn in conversation_history:
            if turn["role"] == "user":
                messages.append(HumanMessage(content=turn["content"]))
            elif turn["role"] == "assistant":
                messages.append(AIMessage(content=turn["content"]))

    # Add the current query
    full_query = f"""I need runbook guidance for this SRE issue: {symptom}

Please:
1. List available runbooks to understand what guidance exists
2. Search runbooks for relevant procedures
3. Search past incidents for similar cases
4. Provide cited recommendations

{CITATION_REPORT_FORMAT}
"""
    messages.append(HumanMessage(content=full_query))

    result = agent.invoke({"messages": messages})
    final_output = result["messages"][-1].content

    return {
        "output": final_output,
        "messages": result["messages"],
    }


if __name__ == "__main__":
    # Demo: multi-turn conversation
    print("=" * 60)
    print("TURN 1: Ask about nginx OOM")
    print("=" * 60)
    result1 = run_citation_query("nginx container keeps getting OOMKilled, restart count is 3")
    print(result1["output"])

    # LEARNING — Multi-turn: pass previous messages as history
    print("\n" + "=" * 60)
    print("TURN 2: Follow-up using conversation history")
    print("=" * 60)
    history = [
        {"role": "user", "content": "nginx container keeps getting OOMKilled"},
        {"role": "assistant", "content": result1["output"]},
    ]
    result2 = run_citation_query(
        "What is the long-term fix to prevent this from recurring?",
        conversation_history=history,
    )
    print(result2["output"])
