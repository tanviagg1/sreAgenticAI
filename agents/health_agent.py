"""
Health Agent — Phase 1.

LEARNING — What is happening here end to end:

1. We create a local LLM connection via Ollama (no internet, no API key)
2. We give the LLM a set of tools (skills) it can call
3. We use the ReAct pattern: the agent loops through Thought -> Action -> Observation
   until it has enough information to produce a Final Answer
4. LangGraph's create_react_agent (v1.x) wires all of this together

LEARNING — LangChain 1.x vs older versions:
  In LangChain 0.x: create_react_agent lived in langchain.agents
  In LangChain 1.x: it moved to langgraph.prebuilt and returns a compiled graph
  The compiled graph handles the ReAct loop internally — no AgentExecutor needed.
  Result comes back in result["messages"][-1].content instead of result["output"].

ReAct loop example for this agent:
  Human:       "Check all containers and report issues"
  AI (thinks): calls get_system_summary()
  Tool:        {"overall_status": "CRITICAL", "healthy": 2, "unhealthy": 3}
  AI (thinks): calls get_unhealthy_containers()
  Tool:        [{"name": "worker", "status": "stopped"}, ...]
  AI (final):  "## System Status: CRITICAL ..."

LEARNING — temperature=0:
  Temperature controls randomness. 0 = fully deterministic.
  For SRE tasks we want consistent, reproducible analysis — always use 0.
  Use higher temperature (0.7-1.0) only for creative tasks.
"""

import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

# LEARNING — LangGraph 1.x: create_react_agent moved here from langchain.agents
# It returns a compiled StateGraph that runs the full ReAct loop automatically
# LEARNING — LangChain 1.x renamed create_react_agent to create_agent
# and moved it back to langchain.agents. system_prompt replaces state_modifier/prompt.
from langchain.agents import create_agent

from prompts.health_prompts import HEALTH_AGENT_SYSTEM_PROMPT, HEALTH_REPORT_INSTRUCTIONS
from skills.container_health import (
    list_all_containers,
    check_container_health,
    get_unhealthy_containers,
    get_system_summary,
)

load_dotenv()

# All tools the health agent is allowed to use
# LEARNING: Limiting tools to only what the agent needs prevents it from
# doing things outside its scope (principle of least privilege for agents)
HEALTH_AGENT_TOOLS = [
    list_all_containers,
    check_container_health,
    get_unhealthy_containers,
    get_system_summary,
]


def create_health_agent():
    """
    Build and return a ReAct health agent backed by a local Llama model.

    LEARNING — LangGraph create_react_agent:
      Takes: llm + tools + optional system prompt
      Returns: a compiled graph (CompiledStateGraph) — not an AgentExecutor
      The graph runs the Thought/Action/Observation loop until the LLM stops calling tools.
    """
    model_name = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

    # LEARNING — ChatOllama:
    # Connects to Ollama running on localhost:11434 (no API key needed)
    # temperature=0 = deterministic output, same input always gives same output
    llm = ChatOllama(
        model=model_name,
        temperature=0,
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )

    # LEARNING — create_react_agent (LangGraph 1.x):
    # state_modifier injects a system prompt into every run
    # This is how we give the agent its persona and rules
    agent = create_agent(
        model=llm,
        tools=HEALTH_AGENT_TOOLS,
        system_prompt=HEALTH_AGENT_SYSTEM_PROMPT,
    )
    return agent


def run_health_check() -> dict:
    """
    Run a full container health check using the ReAct agent.
    Returns a dict with 'output' (the final report string) for API/test compatibility.
    """
    agent = create_health_agent()

    query = f"""Check the health of all containers in the system. Use the available tools to:
1. Get an overall system summary
2. Find all unhealthy containers
3. Check details on each unhealthy container

Then produce a health report using this format:
{HEALTH_REPORT_INSTRUCTIONS}
"""

    # LEARNING — LangGraph agent input/output format:
    # Input:  {"messages": [HumanMessage(...)]}
    # Output: {"messages": [..., AIMessage(content="final report")]}
    # The last message is always the agent's final answer.
    result = agent.invoke({"messages": [HumanMessage(content=query)]})

    # Extract the final text response from the last message
    final_output = result["messages"][-1].content

    # Return in a consistent shape so API and tests stay unchanged
    return {"output": final_output, "messages": result["messages"]}


if __name__ == "__main__":
    # LEARNING: Run directly to watch the agent work step by step
    # python -m agents.health_agent
    print("Running Health Agent...\n")
    output = run_health_check()
    print("\n" + "=" * 60)
    print("FINAL REPORT:")
    print("=" * 60)
    print(output["output"])
