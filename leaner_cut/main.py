import argparse
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load .env next to this file, not from the caller's cwd — load_dotenv()
# with no path searches cwd upward, which silently misses it if this
# script is invoked from outside its own directory.
load_dotenv(Path(__file__).parent / ".env")

DB_PATH = str(Path(__file__).parent / "blackboard.db")

# 1. Base LLM caller — always the local Ollama model (OLLAMA_MODEL, default
# qwen2.5:1.5b). No API key or network provider involved.
def call_llm(system_prompt: str, user_prompt: str) -> str:
    res = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b"),
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
        },
        timeout=600,  # CPU-only local inference is slow, especially on longer prompts
    )
    res.raise_for_status()
    return res.json()["response"]


# 2. SQLite blackboard — shared state every pattern below logs to. In the
# "blackboard" pattern specifically, agents also *read* from it instead of
# being handed a value directly, so they're decoupled from each other.
def log_run(agent_name: str, inputs: str, outputs: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            agent_name TEXT,
            input TEXT,
            output TEXT
        )
    """)
    cursor.execute(
        "INSERT INTO runs (agent_name, input, output) VALUES (?, ?, ?)",
        (agent_name, inputs, outputs),
    )
    conn.commit()
    conn.close()


def get_latest_output(agent_name: str) -> str:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT output FROM runs WHERE agent_name = ? ORDER BY id DESC LIMIT 1",
            (agent_name,),
        )
        row = cursor.fetchone()
    except sqlite3.OperationalError:
        row = None
    conn.close()
    if row is None:
        raise RuntimeError(f"No prior '{agent_name}' entry found on the blackboard.")
    return row[0]


# 3. Agent prompts — single source of truth, used by every pattern below.
AGENT_PROMPTS = {
    "extractor": (
        "Extractor",
        "You are an expert research agent. Given a technical query, identify the top 3 "
        "core advancements or breakthrough developments in this field. Output them as a numbered list.",
    ),
    "risk": (
        "Risk Analyst",
        "You are a technical risk analyst. Given a list of advancements in a technology field, "
        "identify key engineering risks, bottlenecks, or challenges associated with each advancement. "
        "Respond with a corresponding numbered list matching the advancements.",
    ),
    "synthesizer": (
        "Synthesizer",
        "You are a principal technical editor. Synthesize the given advancements and risks "
        "into a structured executive summary report in Markdown. Highlight key findings, recommendations, "
        "and a final technical readiness verdict.",
    ),
}


# Runs exactly one agent, independently — no other agent's output is involved.
# Whatever text is supplied on the command line is fed to that agent directly.
def run_single_agent(agent_key: str, query: str) -> str:
    name, system_prompt = AGENT_PROMPTS[agent_key]
    print(f"=== Running {name} independently ===")
    print(f"[{name}] Processing input: '{query}'...")
    output = call_llm(system_prompt, query)
    log_run(name, query, output)
    print(f"[{name}] Finished and logged to blackboard.")
    print(f"\n--- {name} Output ---\n{output}\n")
    return output


# 4a. Pipeline pattern — A -> B -> C, each agent's output is handed directly
# to the next as a function argument. Simple, but a bad step early poisons
# everything downstream.
def run_pipeline(query: str):
    print(f"=== Pattern: pipeline (sequential) — query: {query} ===")

    extractor_name, extractor_prompt = AGENT_PROMPTS["extractor"]
    print(f"[{extractor_name}] Processing query...")
    advancements = call_llm(extractor_prompt, query)
    log_run(extractor_name, query, advancements)
    print(f"\n--- {extractor_name} Output ---\n{advancements}\n")

    risk_name, risk_prompt = AGENT_PROMPTS["risk"]
    risk_input = f"Field: {query}\nAdvancements:\n{advancements}"
    print(f"[{risk_name}] Analyzing advancements...")
    risks = call_llm(risk_prompt, risk_input)
    log_run(risk_name, risk_input, risks)
    print(f"\n--- {risk_name} Output ---\n{risks}\n")

    synth_name, synth_prompt = AGENT_PROMPTS["synthesizer"]
    synth_input = f"Topic: {query}\nAdvancements:\n{advancements}\n\nRisks & Bottlenecks:\n{risks}"
    print(f"[{synth_name}] Synthesizing final report...")
    report = call_llm(synth_prompt, synth_input)
    log_run(synth_name, synth_input, report)
    print(f"\n--- Final Synthesized Report ---\n{report}\n")

    print("=== Pipeline Complete ===")


# 4b. Parallel / independent pattern — all 3 agents run on the same raw query
# at the same time. Fast, but no agent can use another's result.
def run_parallel(query: str):
    print(f"=== Pattern: parallel (independent) — query: {query} ===")

    def run_one(agent_key: str) -> tuple[str, str]:
        name, system_prompt = AGENT_PROMPTS[agent_key]
        print(f"[{name}] Started (independent)...")
        output = call_llm(system_prompt, query)
        log_run(name, query, output)
        print(f"[{name}] Finished and logged to blackboard.")
        return name, output

    with ThreadPoolExecutor(max_workers=len(AGENT_PROMPTS)) as pool:
        results = list(pool.map(run_one, AGENT_PROMPTS))

    for name, output in results:
        print(f"\n--- {name} Output ---\n{output}\n")

    print("=== Parallel Run Complete ===")


# 4c. Orchestrator-worker / supervisor pattern — a central controller decides
# which agent(s) to run, in what order, given the query. Here the controller
# is a lightweight router call: it decides whether the query is a simple
# lookup the Extractor can fully answer, or whether it needs the full chain.
SUPERVISOR_PROMPT = (
    "You are a routing controller in front of a 3-agent system:\n"
    "- Extractor: identifies the top advancements/facts for a topic.\n"
    "- Risk Analyst: analyzes engineering risks — needs Extractor's output first.\n"
    "- Synthesizer: writes a final executive report — needs both prior outputs.\n"
    "Given the user's query, decide: does it need the Risk Analyst and Synthesizer too "
    "(a request for risks, bottlenecks, or a full report/analysis), or is it a simple "
    "factual/lookup question the Extractor alone can fully answer?\n"
    "Respond with exactly one word, nothing else: 'extractor' or 'pipeline'."
)


def run_supervisor(query: str):
    print(f"=== Pattern: supervisor (orchestrator-worker) — query: {query} ===")
    decision = call_llm(SUPERVISOR_PROMPT, query).strip().lower()
    decision = "extractor" if "extractor" in decision and "pipeline" not in decision else "pipeline"
    print(f"[Supervisor] Classified query as '{decision}'.")

    if decision == "extractor":
        run_single_agent("extractor", query)
    else:
        run_pipeline(query)


# 4d. Blackboard pattern — agents never call each other directly. Each agent
# reads whatever it needs from the shared blackboard (the SQLite table),
# rather than being handed a value by the caller. Same execution order as
# pipeline, but fully decoupled: swap or rerun any agent without touching
# the others, since they only ever talk through shared state.
def run_blackboard(query: str):
    print(f"=== Pattern: blackboard — query: {query} ===")

    extractor_name, extractor_prompt = AGENT_PROMPTS["extractor"]
    print(f"[{extractor_name}] Processing query...")
    advancements = call_llm(extractor_prompt, query)
    log_run(extractor_name, query, advancements)
    print(f"[{extractor_name}] Wrote result to blackboard.")

    risk_name, risk_prompt = AGENT_PROMPTS["risk"]
    print(f"[{risk_name}] Reading '{extractor_name}' result from blackboard...")
    advancements_from_board = get_latest_output(extractor_name)
    risk_input = f"Field: {query}\nAdvancements:\n{advancements_from_board}"
    risks = call_llm(risk_prompt, risk_input)
    log_run(risk_name, risk_input, risks)
    print(f"[{risk_name}] Wrote result to blackboard.")

    synth_name, synth_prompt = AGENT_PROMPTS["synthesizer"]
    print(f"[{synth_name}] Reading prior results from blackboard...")
    advancements_from_board = get_latest_output(extractor_name)
    risks_from_board = get_latest_output(risk_name)
    synth_input = (
        f"Topic: {query}\nAdvancements:\n{advancements_from_board}"
        f"\n\nRisks & Bottlenecks:\n{risks_from_board}"
    )
    report = call_llm(synth_prompt, synth_input)
    log_run(synth_name, synth_input, report)
    print(f"[{synth_name}] Wrote result to blackboard.")

    print(f"\n--- Final Synthesized Report ---\n{report}\n")
    print("=== Blackboard Run Complete ===")


PATTERNS = {
    "pipeline": run_pipeline,
    "parallel": run_parallel,
    "supervisor": run_supervisor,
    "blackboard": run_blackboard,
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="3-agent demo: choose a multi-agent pattern, or run any one agent independently."
    )
    parser.add_argument(
        "query", nargs="?", default="how much does a pen costs",
        help="Task/topic text to feed the agent(s)",
    )
    parser.add_argument(
        "--agent", choices=list(AGENT_PROMPTS), default=None,
        help="Run only this agent, independently — overrides --pattern",
    )
    parser.add_argument(
        "--pattern", choices=list(PATTERNS), default="supervisor",
        help="Multi-agent pattern to run (default: supervisor)",
    )
    args = parser.parse_args()

    if args.agent:
        run_single_agent(args.agent, args.query)
    else:
        PATTERNS[args.pattern](args.query)
