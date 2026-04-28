"""
Health Agent — Phase 1.

LEARNING — What is happening here end to end:

1. We create a local LLM connection via Ollama (no internet, no API key)
2. We give the LLM a set of tools (skills) it can call
3. We use the ReAct pattern: the agent loops through Thought -> Action -> Observation
   until it has enough information to produce a Final Answer
4. LangChain's create_react_agent wires all of this together with a standard prompt
   from the LangChain Hub

ReAct loop example for this agent:
  Thought: "I should first get a system summary to understand the overall situation"
  Action: get_system_summary()
  Observation: {"overall_status": "CRITICAL", "healthy": 2, "unhealthy": 3}
  Thought: "System is critical. I need details on unhealthy containers."
  Action: get_unhealthy_containers()
  Observation: [{"name": "worker", "status": "stopped"}, ...]
  Thought: "I now have all I need to write a report."
  Final Answer: "## System Status: CRITICAL ..."

LEARNING — temperature=0:
  Temperature controls randomness. 0 = fully deterministic.
  For SRE tasks we want consistent, reproducible analysis — always use 0.
  Use higher temperature (0.7-1.0) only for creative tasks.
"""

import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain.agents import create_react_agent, AgentExecutor
from langchain import hub

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


def create_health_agent() -> AgentExecutor:
    """
    Build and return a ReAct health agent backed by a local Llama model.

    LEARNING — AgentExecutor settings:
      verbose=True:      prints every Thought/Action/Observation step — great for learning
      max_iterations=10: safety limit — prevents infinite loops if the LLM gets confused
      handle_parsing_errors=True: if the LLM returns malformed output, retry instead of crash
    """
    model_name = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

    # LEARNING — ChatOllama:
    # This connects to the Ollama server running on localhost:11434
    # The model must be pulled first: `ollama pull llama3.1:8b`
    # temperature=0 means the same input always produces the same output
    llm = ChatOllama(
        model=model_name,
        temperature=0,
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )

    # LEARNING — ReAct prompt from LangChain Hub:
    # hub.pull("hwchase17/react") downloads a standard ReAct prompt template.
    # It includes placeholders for: tools, tool_names, input, agent_scratchpad
    # The scratchpad is where Thought/Action/Observation history accumulates
    react_prompt = hub.pull("hwchase17/react")

    # LEARNING — create_react_agent:
    # This wires: LLM + tools + prompt -> an agent that follows the ReAct loop
    # The agent itself just produces the next action. AgentExecutor runs the loop.
    agent = create_react_agent(llm=llm, tools=HEALTH_AGENT_TOOLS, prompt=react_prompt)

    executor = AgentExecutor(
        agent=agent,
        tools=HEALTH_AGENT_TOOLS,
        verbose=True,           # Set to False in production
        max_iterations=10,
        handle_parsing_errors=True,
    )
    return executor


def run_health_check() -> dict:
    """
    Run a full container health check using the ReAct agent.
    Returns the agent's full output including the final report.

    This is the main entry point used by the API and tests.
    """
    agent = create_health_agent()

    # LEARNING — The input prompt is what kicks off the ReAct loop.
    # We inject the system prompt and report format into the query itself
    # because the standard ReAct prompt template only has one input variable.
    query = f"""{HEALTH_AGENT_SYSTEM_PROMPT}

Check the health of all containers in the system. Use the available tools to:
1. Get an overall system summary
2. Find all unhealthy containers
3. Check details on each unhealthy container

Then produce a health report using this format:
{HEALTH_REPORT_INSTRUCTIONS}
"""
    result = agent.invoke({"input": query})
    return result


if __name__ == "__main__":
    # LEARNING: Running this file directly lets you test the agent from the CLI
    # python -m agents.health_agent
    print("Running Health Agent...\n")
    output = run_health_check()
    print("\n" + "=" * 60)
    print("FINAL REPORT:")
    print("=" * 60)
    print(output["output"])
