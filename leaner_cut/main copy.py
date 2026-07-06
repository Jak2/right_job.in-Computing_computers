import argparse
import os
import re
import sqlite3
import time
import requests
from pathlib import Path
from google import genai
from google.genai import errors as genai_errors
from dotenv import load_dotenv

# Load .env next to this file, not from the caller's cwd — load_dotenv()
# with no path searches cwd upward, which silently misses it if this
# script is invoked from outside its own directory.
load_dotenv(Path(__file__).parent / ".env")

DB_PATH = str(Path(__file__).parent / "blackboard.db")

# 1. Base LLM caller — Gemini is the locked provider (§7) for the actual interview.
# REHEARSAL_MODE=ollama is a rehearsal-only override (unlimited local calls, no
# quota) so practice runs don't burn the 20/day free-tier cap. Off by default —
# never enable this for the real interview run.
# Built lazily so Ollama-only rehearsal runs never require a GEMINI_API_KEY.
_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    return _client


MAX_RETRIES = 2


def _call_ollama(system_prompt: str, user_prompt: str) -> str:
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


def call_gemini(system_prompt: str, user_prompt: str) -> str:
    if os.environ.get("REHEARSAL_MODE") == "ollama":
        return _call_ollama(system_prompt, user_prompt)

    for attempt in range(MAX_RETRIES + 1):
        try:
            res = _get_client().models.generate_content(
                model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
                contents=user_prompt,
                config={"system_instruction": system_prompt},
            )
            return res.text
        except genai_errors.ClientError as e:
            if e.code != 429 or attempt == MAX_RETRIES:
                raise
            # Free-tier rate limit — Google tells us how long to wait in the
            # error message itself. Never retry silently: say why and how long.
            match = re.search(r"retry in ([\d.]+)s", str(e))
            delay = float(match.group(1)) + 1 if match else 30
            print(f"[call_gemini] Hit rate limit (429). Waiting {delay:.0f}s before retry "
                  f"{attempt + 1}/{MAX_RETRIES}...")
            time.sleep(delay)


# 2. SQLite blackboard logger — table created inline, no schema.sql file
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


# 3. Agent prompts — single source of truth, used both in the collaborative
# pipeline below and for running any one agent independently via --agent.
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


def agent_extractor(query: str) -> str:
    name, system_prompt = AGENT_PROMPTS["extractor"]
    print(f"[{name}] Processing query: '{query}'...")
    output = call_gemini(system_prompt, query)
    log_run(name, query, output)
    print(f"[{name}] Finished and logged to blackboard.")
    return output


def agent_risk_analyst(query: str, advancements: str) -> str:
    name, system_prompt = AGENT_PROMPTS["risk"]
    user_prompt = f"Field: {query}\nAdvancements:\n{advancements}"
    print(f"[{name}] Analyzing advancements...")
    output = call_gemini(system_prompt, user_prompt)
    log_run(name, user_prompt, output)
    print(f"[{name}] Finished and logged to blackboard.")
    return output


def agent_synthesizer(query: str, advancements: str, risks: str) -> str:
    name, system_prompt = AGENT_PROMPTS["synthesizer"]
    user_prompt = f"Topic: {query}\nAdvancements:\n{advancements}\n\nRisks & Bottlenecks:\n{risks}"
    print(f"[{name}] Synthesizing final report...")
    output = call_gemini(system_prompt, user_prompt)
    log_run(name, user_prompt, output)
    print(f"[{name}] Finished and logged to blackboard.")
    return output


# Runs exactly one agent, independently — no other agent's output is involved.
# Whatever text is supplied on the command line is fed to that agent directly.
def run_single_agent(agent_key: str, query: str) -> str:
    name, system_prompt = AGENT_PROMPTS[agent_key]
    print(f"=== Running {name} independently ===")
    print(f"[{name}] Processing input: '{query}'...")
    output = call_gemini(system_prompt, query)
    log_run(name, query, output)
    print(f"[{name}] Finished and logged to blackboard.")
    print(f"\n--- {name} Output ---\n{output}\n")
    return output


# 6. Pipeline orchestrator — collaborative wiring: each agent's output feeds the next
def run_pipeline(query: str):
    print(f"=== Starting Lean Agent Pipeline for query: {query} ===")

    advancements = agent_extractor(query)
    print(f"\n--- Agent 1 Output ---\n{advancements}\n")

    risks = agent_risk_analyst(query, advancements)
    print(f"\n--- Agent 2 Output ---\n{risks}\n")

    report = agent_synthesizer(query, advancements, risks)
    print(f"\n--- Final Synthesized Report ---\n{report}\n")

    print("=== Pipeline Complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="3-agent demo: run the full collaborative pipeline, or any one agent independently."
    )
    parser.add_argument(
        "query", nargs="?", default="how much does a pen costs",
        help="Task/topic text to feed the agent(s)",
    )
    parser.add_argument(
        "--agent", choices=list(AGENT_PROMPTS), default=None,
        help="Run only this agent, independently, instead of the full collaborative pipeline",
    )
    args = parser.parse_args()

    if args.agent:
        run_single_agent(args.agent, args.query)
    else:
        run_pipeline(args.query)
