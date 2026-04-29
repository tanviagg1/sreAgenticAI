"""
Retrieval Agent — Phase 2.

LEARNING — What is new in this phase vs Phase 1:

Phase 1: Agent called tools that returned mock in-memory data.
Phase 2: Agent calls tools that query ChromaDB — a real vector database
         built from actual (mock) log files. This is RAG in action.

The flow:
  1. On first run, log files are chunked, embedded, and stored in ChromaDB
  2. Agent receives a query ("what caused the worker to stop?")
  3. Agent calls search tools -> ChromaDB does semantic search -> returns chunks
  4. Agent reasons over the chunks and produces a grounded report

LEARNING — Why RAG beats "just put logs in the prompt":
  - Log files are huge — can't fit in context window
  - RAG retrieves only the RELEVANT parts
  - Semantic search finds related entries even without exact keyword match
  - Retrieved chunks are cited -> answers are verifiable
"""

import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent

from prompts.retrieval_prompts import RETRIEVAL_AGENT_SYSTEM_PROMPT, LOG_ANALYSIS_FORMAT
from skills.log_search import (
    search_logs_semantic,
    search_logs_for_service,
    get_error_summary,
    get_log_index,
)

load_dotenv()

RETRIEVAL_AGENT_TOOLS = [
    get_log_index,           # Always call this first — understand what's available
    get_error_summary,       # Quick error count across all services
    search_logs_semantic,    # Broad semantic search across all logs
    search_logs_for_service, # Narrow search for a specific service
]


def create_retrieval_agent():
    """
    Build the Retrieval Agent.

    LEARNING — Same pattern as Health Agent, but different tools.
    This shows how agents are composable: swap out tools, get different capabilities.
    The LLM (Llama) doesn't change — only the tools and prompts change per agent.
    """
    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        temperature=0,
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )

    agent = create_agent(
        model=llm,
        tools=RETRIEVAL_AGENT_TOOLS,
        system_prompt=RETRIEVAL_AGENT_SYSTEM_PROMPT,
    )
    return agent


def run_log_analysis(query: str) -> dict:
    """
    Run the retrieval agent with a specific investigation query.

    LEARNING — Unlike the Health Agent which always runs the same check,
    the Retrieval Agent is query-driven. Different queries trigger different
    retrieval paths through the logs. This is the foundation of conversational RAG.

    Example queries:
      "Why did the worker container stop?"
      "Find all out of memory errors"
      "What was happening to nginx between 9am and 10am?"
    """
    agent = create_retrieval_agent()

    full_query = f"""{query}

Use the available tools to search the logs. Start with get_log_index to see
what logs are available, then search for relevant evidence.

{LOG_ANALYSIS_FORMAT}
"""
    result = agent.invoke({"messages": [HumanMessage(content=full_query)]})
    final_output = result["messages"][-1].content
    return {"output": final_output, "messages": result["messages"]}


if __name__ == "__main__":
    # Try a few different queries to see semantic search in action
    queries = [
        "Why did the worker container stop? Find the root cause.",
        "Find all out of memory errors across all services.",
    ]

    for query in queries:
        print(f"\n{'='*60}")
        print(f"QUERY: {query}")
        print('='*60)
        result = run_log_analysis(query)
        print(result["output"])
