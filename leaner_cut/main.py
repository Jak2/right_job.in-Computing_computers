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
_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

MAX_RETRIES = 2


def _call_ollama(system_prompt: str, user_prompt: str) -> str:
    res = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": os.environ.get("OLLAMA_MODEL", "phi3:mini"),
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
            res = _client.models.generate_content(
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


# 3. Agent 1: Extractor
def agent_extractor(query: str) -> str:
    system_prompt = (
        "You are an expert research agent. Given a technical query, identify the top 3 "
        "core advancements or breakthrough developments in this field. Output them as a numbered list."
    )
    print(f"[Extractor] Processing query: '{query}'...")
    output = call_gemini(system_prompt, query)
    log_run("Extractor", query, output)
    print("[Extractor] Finished and logged to blackboard.")
    return output


# 4. Agent 2: Risk Analyst
def agent_risk_analyst(query: str, advancements: str) -> str:
    system_prompt = (
        "You are a technical risk analyst. Given a list of advancements in a technology field, "
        "identify key engineering risks, bottlenecks, or challenges associated with each advancement. "
        "Respond with a corresponding numbered list matching the advancements."
    )
    user_prompt = f"Field: {query}\nAdvancements:\n{advancements}"
    print("[Risk Analyst] Analyzing advancements...")
    output = call_gemini(system_prompt, user_prompt)
    log_run("Risk Analyst", user_prompt, output)
    print("[Risk Analyst] Finished and logged to blackboard.")
    return output


# 5. Agent 3: Synthesizer
def agent_synthesizer(query: str, advancements: str, risks: str) -> str:
    system_prompt = (
        "You are a principal technical editor. Synthesize the given advancements and risks "
        "into a structured executive summary report in Markdown. Highlight key findings, recommendations, "
        "and a final technical readiness verdict."
    )
    user_prompt = f"Topic: {query}\nAdvancements:\n{advancements}\n\nRisks & Bottlenecks:\n{risks}"
    print("[Synthesizer] Synthesizing final report...")
    output = call_gemini(system_prompt, user_prompt)
    log_run("Synthesizer", user_prompt, output)
    print("[Synthesizer] Finished and logged to blackboard.")
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
    test_query = "how much does a pen costs"
    run_pipeline(test_query)
