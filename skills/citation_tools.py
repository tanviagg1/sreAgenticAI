"""
Citation tools — @tool functions for the Citation Agent.

LEARNING — Citation Pattern:
The goal is not just to answer "what should I do?" but to answer
"what should I do, and WHERE does that recommendation come from?"

Every tool here returns structured data that includes:
  - The content (what to do)
  - The citation (which runbook, which section, which ID)

This makes the agent's output verifiable — an SRE can open the runbook
and confirm the recommendation is correct.

LEARNING — Grounding vs Citation:
Grounding:  answer is based on real data (not hallucinated)
Citation:   answer explicitly references where the data came from

Both together = trustworthy agent output.
"""

from langchain.tools import tool
from skills.runbook_store import search_runbooks
from memory.incident_memory import search_similar_incidents, store_incident, seed_past_incidents


@tool
def search_runbooks_for_symptom(symptom: str) -> list[dict]:
    """
    Search SRE runbooks for procedures relevant to a given symptom or error.
    Returns matching runbook sections with full citation information (runbook ID, title, section).
    Use this to find the official remediation procedure for any SRE issue.
    Example symptoms: 'OOMKilled', 'high CPU', 'database connection refused', 'SLO breach'.
    """
    results = search_runbooks(symptom, k=4)

    return [
        {
            "content": doc.page_content,
            # LEARNING — Citation fields: these are what the agent uses to cite sources
            "citation": {
                "runbook_id": doc.metadata.get("runbook_id"),
                "runbook_title": doc.metadata.get("runbook_title"),
                "section": doc.metadata.get("section", ""),
                "subsection": doc.metadata.get("subsection", ""),
                "source_file": doc.metadata.get("source_file"),
            },
            "relevance_score": round(float(score), 3),
        }
        for doc, score in results
    ]


@tool
def search_past_incidents(query: str) -> list[dict]:
    """
    Search the incident history for past cases similar to the current issue.
    Returns similar incidents with their root causes and resolutions.
    Use this to check if this issue has occurred before and what fixed it.
    Example queries: 'nginx memory', 'worker crash database', 'high CPU app-server'.
    """
    # Seed demo incidents on first call so there is history to search
    seed_past_incidents()
    return search_similar_incidents(query, k=3)


@tool
def record_incident(service: str, symptom: str, root_cause: str, resolution: str) -> str:
    """
    Record a resolved incident into long-term memory for future reference.
    Call this AFTER an incident is resolved to save the resolution for future similar incidents.
    Returns the incident ID assigned to this record.
    Args:
        service: name of the affected service (e.g. 'nginx', 'worker')
        symptom: what was observed (e.g. 'OOMKilled 3 times in one hour')
        root_cause: what caused it (e.g. 'memory limit too low at 512MB')
        resolution: what fixed it (e.g. 'increased memory limit to 1Gi')
    """
    # LEARNING — Writing to long-term memory:
    # This is how the agent "learns" from resolved incidents.
    # Future agents can retrieve this entry when they see similar symptoms.
    incident_id = store_incident(service, symptom, root_cause, resolution)
    return f"Incident recorded with ID: {incident_id}. It will be retrievable in future sessions."


@tool
def list_available_runbooks() -> list[dict]:
    """
    List all available SRE runbooks with their IDs and descriptions.
    Call this first to understand what runbooks exist before searching them.
    """
    from pathlib import Path
    runbook_dir = Path("mocks/runbooks")

    runbooks = []
    for f in sorted(runbook_dir.glob("*.md")):
        content = f.read_text()
        lines = content.split("\n")

        title = lines[0].replace("# ", "").strip() if lines else f.stem
        runbook_id = ""
        severity = ""
        applies_to = ""

        for line in lines[:20]:
            if "**ID:**" in line:
                runbook_id = line.replace("**ID:**", "").strip()
            if "**Severity:**" in line:
                severity = line.replace("**Severity:**", "").strip()
            if "**Applies to:**" in line:
                applies_to = line.replace("**Applies to:**", "").strip()

        runbooks.append({
            "id": runbook_id,
            "title": title,
            "severity": severity,
            "applies_to": applies_to,
            "file": f.name,
        })

    return runbooks
