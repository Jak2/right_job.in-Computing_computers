# Agentic AI Engineer — Interview Prep & Build-From-Scratch Guide
**For:** right_job.in — Senior AI Agent Developer (UWM), 2nd round live-build interview
**Written as:** a 20-year Python/AI practitioner would brief a candidate before this exact interview

---

## 0. How this guide is organized

1. §1–2: decode the two documents you were given (JD + 2nd round problem statement)
2. §3–5: theory — what an agent is, agent taxonomies, multi-agent architecture taxonomies
3. §6–12: hands-on tutorial — build a 3-agent system from zero, in layers
4. §13: practices — what a senior engineer keeps vs. cuts
5. §14–17: the JD's broader surface area (frameworks, RAG, security, AWS) for the general/technical round
6. §18: live-failure recovery playbook
7. §19: your resume mapped to this JD, line by line
8. §20: likely questions with answers
9. §21–23: rehearsal plan, checklist, and things to verify yourself

I've cross-checked this against your own `progress-tracker.html` and `agent-field-notes.html` — you've already made good decisions (Python, Gemini free tier, SQLite blackboard, orchestrator pattern, leaner-cut-first). I'm not re-deciding those; I'm filling in what those two documents don't cover — because the JD covers a much wider surface (RAG, vector DBs, A2A, MCP, HITL, AWS, security) than the live-build round alone tests. Assume the live-build round is a *filter*, and a broader technical conversation about the JD is still likely either before or after it.

---

## 1. Decoding the job description

Stripped to what's actually being tested:

| JD line | What they're really checking |
|---|---|
| "Universal Worker Model (UWM) architecture" | **I don't have a verified public reference for "UWM" as a named, standard agentic architecture.** It's very likely this company's internal name for their agent framework. Don't try to bluff a definition — ask them directly: *"Can you point me to your internal docs on UWM, or describe its core primitives?"* That question itself signals seniority (you don't pretend to know internal tooling). |
| "Fully autonomous and semi-autonomous agents... multi-step task planning" | Loop-based agents (see §4) vs. single-shot agents — know when each applies |
| "Agent-to-Agent (A2A) communication" | Multi-agent coordination patterns (see §5) — specifically whether you can name more than one |
| "RAG pipelines and knowledge-driven agent architectures" | Vector DB + retrieval + grounding basics (§15) |
| "Memory management, context handling, agent lifecycle" | Short-term (context window) vs. long-term (vector store / DB) memory distinction |
| "Human-in-the-loop (HITL)" | Can you describe an approval/interrupt point in an agent loop, not just automate everything |
| "PostgreSQL... stored procedures, indexing, query optimization" | Straight DB skill — your resume has real depth here (§19) |
| "AWS: EC2, Lambda, ECS/EKS, S3, RDS, API Gateway, CloudWatch, IAM" | Standard cloud deployment vocabulary (§17) |
| "OAuth2, JWT, API security" | Auth basics for agent-exposed endpoints |
| "LangChain / LangGraph (preferred), CrewAI / AutoGen / OpenAI Agents SDK" | They want you to at least know what these are and how they differ, not necessarily be deep in all of them (§14) |
| "MCP and emerging agentic standards" | Model Context Protocol — know the one-sentence version |
| "HIPAA / data governance" | Only relevant if the healthcare-domain work comes up — know the term, don't need deep compliance expertise |

**My read as an interviewer:** this JD is written broad (typical of a role meant to own agent architecture across multiple domains). The 2nd-round live-build is a *practical filter* — can you actually construct a working multi-agent system under time pressure, not just talk about one. The rest of the JD's surface (AWS, RAG, security, frameworks) is very likely probed in a separate technical/architecture conversation, not necessarily in this specific 1-hour session. Prepare for both.

---

## 2. Decoding the 2nd-round problem statement

Re-reading it literally:

- **1 hour, live, screen-share.** Scored on *process*, not polish.
- **Three small, lightweight agents.** "Lightweight" is doing real work in that sentence — it's telling you not to over-engineer.
- **Independent or collaborative, decided per task.** The task is revealed on the day — you can't pre-wire the collaboration pattern, only pre-build the *capability* to wire it either way.
- **Gather/process info via LLM and/or API calls.** Not every agent needs to call an LLM — one could just be a plain API-calling function. Don't assume all three must hit an LLM.
- **Database persists outputs and execution logs.** Two things, one table is fine: each row is both an output record and a log line.
- **Dashboard displays results.** No spec on *how* — a printed table, a static HTML file, or a running web app are all valid; the ask is "displays," not "is a web app."
- **AI tool use is allowed, blind copy-paste is not.** You must be able to explain every line, live.

This matches exactly what your own field notes already concluded in §4–§6. Good — that means the architecture decision is done. What's left is **rehearsal and the ability to justify it under questioning**, which is what the rest of this guide adds on top of what you already wrote.

---

## 3. What actually is an "agent"?

There's no single universally-agreed definition — be aware different interviewers use the word differently. The most useful working definition for this interview:

> **An agent is a system that observes some state, decides on an action using an LLM and/or rules, takes that action (which may include calling tools/APIs), and optionally repeats.**

The critical distinguishing feature vs. a plain script: **the decision of *what to do next* is at least partly made by the model, not hard-coded entirely in advance.**

A single LLM call that returns an answer is *not* usually called an agent — it's a completion. The word "agent" earns itself when there's a **decision + action** step, even if that loop only runs once (single-shot).

---

## 4. Taxonomy: types of agents

There are two taxonomies worth knowing, from two different eras. Interviewers with a classical-AI background (many senior architects) may ask about the first one; interviewers from the LLM-tooling world will ask about the second. Know both — I'm not aware of a single authority that unifies them, so I'll present them separately rather than force a merge.

### 4a. Classical AI taxonomy (pre-LLM, from foundational AI textbooks — this is standard university-course material, stable and uncontested)

| Type | How it decides | Example |
|---|---|---|
| **Simple reflex agent** | Fixed rule triggered by current perception only, no memory | Thermostat |
| **Model-based reflex agent** | Keeps an internal model of the world to handle partial observability | Robot vacuum tracking a map |
| **Goal-based agent** | Chooses actions that lead toward an explicit goal state | A* pathfinding agent |
| **Utility-based agent** | Chooses actions that maximize a utility/value function, not just "any path to goal" | An agent trading off speed vs. cost |
| **Learning agent** | Improves its decision policy over time from feedback | RL agent |

### 4b. Modern LLM-agent taxonomy (practitioner convention, not a single formal standard — different vendors/blogs draw these lines slightly differently, so treat this as the common vocabulary, not law)

| Type | Shape | When to use |
|---|---|---|
| **Single-shot / tool-calling agent** | One `input → LLM (with tool access) → output`, no re-planning loop | Task is well-scoped, one round of reasoning is enough — **this is almost certainly what your 3 interview agents should be**, per your own §3 boundary analysis |
| **ReAct agent** (Reason + Act, interleaved) | Loop: think → pick a tool → observe result → think again → ... → answer | Task needs iterative lookup where the number of steps isn't known upfront |
| **Plan-and-execute agent** | Produces a full plan upfront, then executes each step (optionally re-planning on failure) | Long multi-step tasks where planning cost is worth paying once |
| **Reflexion / self-critique agent** | Generates an output, critiques its own output, revises | Tasks where quality matters more than speed and there's a way to self-verify |
| **Multi-agent system** | Multiple single-shot or looped agents coordinating (see §5 for *how*) | Task naturally decomposes into specialist roles |

**Interview-ready one-liner if asked "how many types of agents are there":**
*"There isn't one official count — classical AI names five reflex/goal/utility/learning-style categories, and the LLM-agent world commonly talks about single-shot, ReAct, plan-and-execute, reflexion, and multi-agent — but that second list is convention, not a formal standard, and people draw the lines slightly differently."* That answer is more defensible than picking a number and being wrong.

---

## 5. Taxonomy: multi-agent coordination approaches

Again, not one canonical list — I'm giving you the patterns that actually show up in production systems and in frameworks like LangGraph/CrewAI/AutoGen, which is what "A2A" in the JD is gesturing at.

| Pattern | Shape | Trade-off |
|---|---|---|
| **Pipeline / sequential** | A → B → C, each agent's output feeds the next | Simple, but a bad step early poisons everything downstream |
| **Parallel / independent** | A, B, C all run on the same input simultaneously | Fast, but no agent can use another's result |
| **Orchestrator–worker (hub-and-spoke / "supervisor")** | A central controller decides which agent runs, in what order, with what input | Most flexible; matches your own §4 architecture; this is what LangGraph's "supervisor" pattern and most production multi-agent systems use |
| **Blackboard** | No agent talks to another directly — all read/write a shared state (a table, in your case) | Decouples agents completely; simplest to persist and debug; this is what you already chose |
| **Peer-to-peer / decentralized (A2A)** | Agents message each other directly, no central controller | More resilient to a single point of failure, harder to reason about and debug — this is the pattern the JD's "A2A" line is referencing |
| **Hierarchical (manager of managers)** | Orchestrators of orchestrators, for large agent counts | Only earns its complexity at real scale (10+ agents) — not for a 3-agent demo |
| **Market-based / auction** | Agents "bid" for tasks based on capability/cost | Classical multi-agent-systems literature; rare in current LLM practice, but worth knowing the name exists |

**Your architecture (orchestrator + blackboard) is a defensible combination of two of these** — orchestrator decides call order/wiring, blackboard (SQLite table) is the shared state. That's a legitimate, nameable pattern, not an ad hoc invention — good, because if asked "what pattern is this," you have a real answer.

---

## 6. Core building blocks of any agent system

Regardless of framework or no-framework, every agent system is assembled from the same six pieces:

1. **LLM/API call wrapper** — one function, one place to change providers/models
2. **Tool/action interface** — how the agent's decision turns into a real action (API call, DB write, function call)
3. **State/memory** — what the agent knows: short-term (this conversation/context) vs. long-term (DB, vector store)
4. **Control flow** — single-shot vs. loop vs. plan-and-execute (§4b)
5. **Stop condition** — max iterations, a model-emitted "done" signal, or a budget check — **mandatory**, not optional, for anything that loops
6. **Persistence + observability** — logging every input/output so failures are visible, not silent

Everything you build below is just these six pieces, assembled differently depending on the task.

---

## 7. Build from scratch — Part 1: the smallest possible agent

Start here even if it feels too simple — it's the unit everything else is made of.

```python
import os

def call_llm(system_prompt: str, user_input: str) -> str:
    """
    One function, one seam. Swap providers here without touching agent code.
    NOTE: exact SDK call shape below is illustrative — verify current method
    names/signatures against the SDK version you actually pip-install on the day.
    """
    import anthropic
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    response = client.messages.create(
        model="claude-sonnet-4-6",       # verify current model string before the call
        max_tokens=1000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_input}],
    )
    return response.content[0].text


def agent_1(task_input: dict) -> dict:
    system = "You extract the key entities from the input. Respond with plain text only."
    output_text = call_llm(system, str(task_input))
    return {"agent": "agent_1", "input": task_input, "output": output_text}


if __name__ == "__main__":
    result = agent_1({"text": "Acme Corp signed a deal with Beta Inc on July 4th."})
    print(result)
```

That's a complete, working single-shot agent: `run(input) → output`. No class, no loop, no framework. This is the unit you'll copy three times.

**A note on provider choice:** your own notes already worked through Claude → Gemini (free tier) for cost reasons, and already hit two live SDK-deprecation bugs doing it (`google.generativeai` → `google-genai`, model name retirement). That's a real, valuable story to tell in the interview (§20 has a question this answers directly) — don't hide it, it demonstrates exactly the debugging behavior they said they're scoring.

---

## 8. Build from scratch — Part 2: when (and how) to add a loop

Per your own §3 boundary analysis — most task-scoped agents do **not** need this. Add it only if one specific agent's job is open-ended (e.g., "keep querying until you find a match" or "retry until the output validates").

```python
def agent_with_loop(task_input: dict, max_iters: int = 5) -> dict:
    system = "You search for a specific fact. Reply DONE:<answer> when found, or CONTINUE:<next query> otherwise."
    state = task_input
    trace = []

    for i in range(max_iters):                       # stop condition #1: hard cap
        output_text = call_llm(system, str(state))
        trace.append(output_text)

        if output_text.startswith("DONE:"):           # stop condition #2: model signal
            return {"agent": "agent_with_loop", "result": output_text[5:], "trace": trace}

        state = {"previous": state, "note": output_text}

    return {"agent": "agent_with_loop", "result": None, "trace": trace, "status": "max_iters_hit"}
```

Two stop conditions stacked (max-iterations *and* a model-emitted done signal) — never ship a loop with only a model-emitted stop condition, because a model that never says "done" is an infinite bill.

---

## 9. Build from scratch — Part 3: multi-agent orchestration (orchestrator + blackboard)

This is the pattern from §5 that matches your own plan. Three single-shot agents, one orchestrator deciding the wiring, no direct agent-to-agent calls.

```python
def agent_extractor(task_input: dict) -> dict:
    system = "Extract key entities and facts. Respond with plain text."
    return {"agent": "extractor", "input": task_input, "output": call_llm(system, str(task_input))}

def agent_analyst(task_input: dict) -> dict:
    system = "Given these facts, identify the single biggest risk. Respond with plain text."
    return {"agent": "analyst", "input": task_input, "output": call_llm(system, str(task_input))}

def agent_synthesizer(task_input: dict) -> dict:
    system = "Summarize the analysis into one actionable recommendation. Respond with plain text."
    return {"agent": "synthesizer", "input": task_input, "output": call_llm(system, str(task_input))}


def run_pipeline(task_input: dict, mode: str = "collaborative") -> list:
    """
    The orchestrator. `mode` is decided per-task on the day, not hard-coded in advance.
    """
    results = []

    if mode == "collaborative":
        r1 = agent_extractor(task_input)
        results.append(r1)

        r2 = agent_analyst({"facts": r1["output"]})   # chained: B's input includes A's output
        results.append(r2)

        r3 = agent_synthesizer({"analysis": r2["output"]})
        results.append(r3)

    elif mode == "independent":
        for fn in (agent_extractor, agent_analyst, agent_synthesizer):
            results.append(fn(task_input))            # all three see the same raw input

    for r in results:
        log_run(r["agent"], r["input"], r["output"])  # every result hits the blackboard — see §10

    return results
```

Notice: the orchestrator is the *only* place that knows about wiring. Each agent function is unaware the others exist — that's what makes this a blackboard pattern rather than a peer-to-peer one.

---

## 10. Build from scratch — Part 4: persistence (SQLite blackboard)

```python
import sqlite3
import json
from datetime import datetime, timezone

DB_PATH = "blackboard.db"

def log_run(agent_name: str, input_data, output_data, error: str | None = None) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT NOT NULL,
            input_json TEXT,
            output_json TEXT,
            error TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute(
        "INSERT INTO runs (agent_name, input_json, output_json, error, created_at) VALUES (?, ?, ?, ?, ?)",
        (
            agent_name,
            json.dumps(input_data, default=str),
            json.dumps(output_data, default=str),
            error,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()
```

Notes worth saying out loud in the interview:
- `CREATE TABLE IF NOT EXISTS` inline means no separate schema file — one less thing to juggle live (matches your §6 leaner-cut reasoning).
- **Errors get logged too** — a failed call is still a row, not a silent gap. This directly answers "what exactly gets logged" (§20).
- `default=str` on `json.dumps` is a defensive habit — if an agent's output ever contains a non-JSON-serializable object, this doesn't crash the logger mid-demo.

---

## 11. Build from scratch — Part 5: the dashboard

Simplest version — zero server, zero port, matches the ask ("displays results") exactly:

```python
import sqlite3

def render_dashboard(db_path: str = "blackboard.db", out_path: str = "dashboard.html") -> None:
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT agent_name, input_json, output_json, error, created_at FROM runs ORDER BY id").fetchall()
    conn.close()

    html_rows = "".join(
        f"<tr><td>{r[0]}</td><td><pre>{r[1]}</pre></td><td><pre>{r[2]}</pre></td>"
        f"<td>{r[3] or ''}</td><td>{r[4]}</td></tr>"
        for r in rows
    )

    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Agent Run Log</title>
    <style>table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:6px;vertical-align:top}}</style>
    </head><body><h1>Agent Run Log</h1><table>
    <tr><th>Agent</th><th>Input</th><th>Output</th><th>Error</th><th>Timestamp</th></tr>
    {html_rows}
    </table></body></html>"""

    with open(out_path, "w") as f:
        f.write(html)

    print(f"Wrote {out_path} — open it directly in a browser (file:// URL, no server needed).")
```

If the interviewer signals they want a *live-refreshing* dashboard rather than "show me the result," that's your cue to upgrade to Streamlit or a small Flask route — but per your own §6 reasoning, don't pre-build that on a guess; it adds a server/port failure mode for no scored benefit.

---

## 12. Build from scratch — Part 6: the full assembly

```python
# main.py — the whole system in one file, per your leaner-cut decision
import sqlite3, json, os
from datetime import datetime, timezone

# --- call_llm, log_run, agent_extractor/analyst/synthesizer, run_pipeline, render_dashboard ---
# (as defined in §7, §10, §9, §11 above)

if __name__ == "__main__":
    task = {"text": "<the live task text goes here, decided on interview day>"}

    print("Expected: three rows in blackboard.db, one per agent, chained if collaborative.")
    results = run_pipeline(task, mode="collaborative")

    for r in results:
        print(r["agent"], "->", r["output"][:80], "...")

    render_dashboard()
```

Say the expected outcome out loud *before* running it (per your own §9) — that single habit is what turns a demo into a narrated, scored reasoning process.

---

## 13. Best & simplest practices (what a senior engineer keeps vs. cuts)

| Situation | Junior instinct | Senior instinct | Why |
|---|---|---|---|
| Need 3 agents | Build a `BaseAgent` class hierarchy | Plain functions, unless you're actually swapping implementations | Classes earn their cost with reuse/testing over time — a one-shot demo has neither |
| Need to loop | Add a ReAct loop "to be safe" | Default to single-shot; add a loop only to the one agent whose task is open-ended | Unearned complexity is exactly what a "why did you do this" question will expose |
| Need a DB | Reach for Postgres/Mongo | SQLite, unless concurrency or scale is a real requirement | Zero setup, one file, inspectable in one line, live |
| Need a dashboard | Spin up a server | Static HTML from a DB query, unless live-refresh is explicitly required | No port/network failure mode |
| LLM output malformed | Silently retry | Say what broke, tighten the prompt/schema, retry with a stated reason | Narrated debugging is the thing being scored, not the happy path |
| Framework available | Reach for LangChain/CrewAI by default | Hand-roll for small agent counts under time pressure; frameworks earn their cost at 10+ agents with complex routing | You can explain every line of your own code; you can't always explain library internals live |
| Asked "why not X" | Defend the choice you made | State the trade-off honestly, including what you'd change with more time | Shows judgment, not attachment |

The single unifying principle: **every piece of your system should map to a literal line in the problem statement.** If you can't point to which requirement a piece of code satisfies, it's ceremony, and ceremony is what gets cut when someone asks "why is this here."

---

## 14. Framework landscape (for the broader technical conversation)

Brief, factual, and deliberately not over-specified — these products iterate fast, so verify exact current capabilities/API shape against their docs before claiming specifics in the interview.

| Framework | One-line description | Fit |
|---|---|---|
| **LangChain** | General-purpose LLM app framework: chains, tool-calling, retrieval components | Broad tooling, sometimes more abstraction than a small agent needs |
| **LangGraph** | Graph-based orchestration for agents, built by the LangChain team, models agent flow as nodes/edges with explicit state | Closest fit to the JD's "supervisor"/A2A language — worth being able to describe its node-and-edge mental model even if you don't use it live |
| **CrewAI** | Higher-level abstraction: define agents by "role," let the framework handle delegation | Fast to prototype role-based multi-agent setups |
| **AutoGen** (Microsoft) | Multi-agent conversation framework — agents literally "talk" to each other in a loop | Closest fit to a true peer-to-peer/A2A pattern from §5 |
| **OpenAI Agents SDK** | OpenAI's own lightweight agent/tool-calling SDK | Newer; verify current maturity/API before claiming depth |
| **MCP (Model Context Protocol)** | An open protocol standardizing how an LLM application connects to external tools/data sources — one interface instead of a bespoke integration per tool | Know this one-sentence definition; it's explicitly named in the JD |

**Honest positioning if asked "which have you used":** answer with what you've actually used (be accurate to your resume — LangChain/RetrievalQA appears there) and be direct about the rest: *"I know LangGraph and CrewAI by their design philosophy, I haven't shipped with them — happy to get hands-on quickly given how similar the underlying loop is to what I've hand-rolled."*

---

## 15. RAG & vector DB basics

Since the JD explicitly requires this and your resume already has a real RAG pipeline (5G failure detection with LangChain RetrievalQA):

**RAG in one sentence:** instead of relying only on what's in the model's training data, you retrieve relevant text chunks from an external knowledge store at query time and inject them into the prompt, so the model reasons over grounded, current information.

Minimal pipeline shape:
1. **Chunk** source documents into passages
2. **Embed** each chunk into a vector (via an embedding model)
3. **Store** vectors in a vector database
4. **Retrieve** the top-k most similar chunks to the query at runtime (via cosine/dot-product similarity)
5. **Inject** retrieved chunks into the LLM prompt as context
6. **Generate** the grounded answer

Common vector DB options named in the JD: **Pinecone, Weaviate, Qdrant, pgvector** (a Postgres extension — relevant given your Postgres depth, worth mentioning you could keep everything in one Postgres instance via pgvector instead of adding a separate vector DB service).

Your resume's version of this (Pyshark → LangChain RetrievalQA → vector DB of known error patterns → Redis cache) is a genuinely strong, concrete answer if asked to describe a RAG system you've built — use the real numbers you already have (70% auto-resolution, 55% MTTR reduction) rather than a generic textbook description.

---

## 16. Security, RBAC, and enterprise concerns

- **OAuth2 / JWT**: standard token-based auth for API access — JWT is a signed token carrying claims (identity, scope) that a service verifies without a DB round-trip; OAuth2 is the broader authorization framework token issuance sits inside.
- **RBAC (Role-Based Access Control)**: permissions attached to roles, not individual users. Your resume's **attribute-level RBAC** work (Brane Enterprises) is a step beyond basic RBAC — attribute-based control checks specific attributes/conditions, not just a role label — this is a strong, specific talking point, more advanced than what most candidates will have shipped.
- **HIPAA**: US healthcare data privacy regulation. You don't need deep compliance expertise — know that it implies encryption at rest/in transit, access logging, and minimal necessary data exposure. If the domain comes up, it's fine to say plainly you'd defer detailed compliance work to their legal/compliance function while handling the technical controls (encryption, audit logs, access scoping).

---

## 17. AWS deployment concerns for agent systems

Map the JD's list to what an agent system actually needs from each:

| AWS service | Role in an agent system |
|---|---|
| **EC2 / ECS / EKS** | Where the orchestrator/agent processes actually run |
| **Lambda** | Good fit for single-shot, stateless agent invocations triggered by events |
| **RDS (Postgres)** | Production equivalent of your SQLite blackboard — same table concept, networked and concurrent-safe |
| **S3** | Document/artifact storage — e.g., source documents for a RAG pipeline |
| **API Gateway** | Exposes agent endpoints to external callers with auth/throttling |
| **CloudWatch** | Logs and metrics — production equivalent of your `runs` table's logging role, but for infrastructure-level observability |
| **IAM** | Least-privilege access control between services — you have direct experience here (Abjayon: IAM roles for AppSync/AppFlow) |

If asked "how would you productionize this," a credible answer chains these: agents on ECS/Lambda, blackboard becomes RDS Postgres, logs also go to CloudWatch, S3 for any document store feeding RAG, API Gateway + IAM in front of anything externally callable.

---

## 18. Handling failure live — the recovery playbook

Your own field notes (§9) already cover this well. Adding the generic pattern underneath it, since this is very likely to be the actual scoring moment:

**The loop for any live failure:**
1. **Name the failure class out loud** — malformed output, hallucinated API/method, traceback, or under-specified prompt (your own table already distinguishes these).
2. **Read the actual error, don't guess** — for a traceback, find the exact failing line before touching code.
3. **Make one targeted fix** — never regenerate the whole file blind.
4. **State why you expect this fix to work** before re-running.
5. **If it fails again, that's new information, not a reason to panic** — narrate the update to your hypothesis.

**Never do these live:** silently retry, silently swallow an exception, regenerate a whole file hoping it's different, defend a hallucinated detail because "the AI said so."

---

## 19. Your resume mapped to this JD

Concrete talking points, pulled directly from your resume against the JD's requirements — use these verbatim as anchors when a question invites you to give an example:

| JD requirement | Your matching experience |
|---|---|
| "AI Agent Architecture... multi-step task planning, orchestration" | Brane Enterprises: agent loop development, prompt assembly for the agent loop, retry-with-feedback for the verifier correction loop |
| "Multi-agent systems with A2A communication" | Brane Enterprises: multi-agent LO junction tables in Postgres schema design |
| "LLM Integration... multi-provider" | Brane Enterprises: gRPC model gateway with multi-provider model routing (instruct, thinking, vision) |
| "RAG pipelines" | Infinite Computer Solutions: LangChain RetrievalQA against a vector DB of known error patterns |
| "PostgreSQL schema design, indexing" | Brane Enterprises: agent identity tables, RBAC permission rows, execution sibling tables |
| "OAuth2/JWT... attribute-level access" | Brane Enterprises: attribute-level RBAC permission rows + caching |
| "AWS: AppSync, AppFlow, IAM" | Abjayon Pvt. Ltd.: direct hands-on with exactly these three services |
| "Workflow automation frameworks" | Nokia: NFTRACE distributed tracing platform, FastAPI lifecycle endpoints |
| "Frontend integration... dashboards" | Nokia: Streamlit + FastAPI dashboard for the RF keyword generator |
| "LLM Evaluation" (not explicit in JD but strengthens the AI-depth story) | Your own project: LLM Evaluation Framework, hallucination/regression detection |

This gives you a real example for nearly every bullet in the JD without inventing anything — worth rehearsing which resume line you'd reach for, for each JD bullet, so it's not a cold search during the interview.

---

## 20. Likely interview questions — beyond what your own notes already cover

Your `agent-field-notes.html` §10 already has strong answers for architecture/data/failure/meta questions specific to the live-build. These extend into the JD's *broader* surface, which a first/technical round is more likely to probe:

**"What's the difference between RAG and fine-tuning, and when would you choose one over the other?"**
> RAG injects external knowledge at query time without changing model weights — it's faster to update (just change the source documents) and keeps the model's reasoning general. Fine-tuning bakes behavior or domain knowledge into the weights themselves — better for changing *style* or *task format*, not for keeping facts current. If the underlying facts change often, I'd reach for RAG first.

**"How would you handle memory across a long-running agent conversation?"**
> Two tiers: short-term is just what fits in the context window for the current turn. Long-term is anything that needs to survive across sessions — I'd persist that outside the model, in a DB or vector store, and retrieve only the relevant slice back into context per turn, rather than trying to keep everything in-context indefinitely.

**"What is Model Context Protocol, and why does it matter?"**
> It's a protocol that standardizes how an LLM application connects to external tools and data sources, so you write one integration against the protocol instead of a bespoke one per tool per vendor. I haven't shipped against it directly — happy to verify the current spec details before claiming deeper familiarity.

**"Where would you put a human-in-the-loop checkpoint in an agent pipeline, and why there?"**
> Wherever an action is irreversible or high-cost if wrong — e.g., before an agent sends an external communication, commits a financial transaction, or modifies production data. Cheap, reversible, or purely informational steps don't need it; adding approval gates everywhere just kills the automation value.

**"How do you decide between a hand-rolled agent and using LangGraph/CrewAI/AutoGen in production, not in an interview?"**
> Scale and team size, mainly. A few agents with simple routing — hand-rolled is fine and gives full visibility. Once you're past roughly 10+ agents with complex conditional routing, retries, and multiple people maintaining it, a framework's shared vocabulary and tooling starts paying for its abstraction cost.

*(For remaining question types — architecture, data/persistence, failure handling, meta-reflection — use your own field notes §10 directly; they're already strong and don't need duplication here.)*

---

## 21. A realistic 1-hour rehearsal timeline

| Time | What you're doing |
|---|---|
| 0–5 min | Task is revealed. Say out loud: what are the 3 agents, are they collaborative or independent, what does each one's input/output look like |
| 5–15 min | Write `call_llm`, `log_run`, and one agent function. Run it once against a throwaway input to prove the wiring works before building the other two |
| 15–30 min | Write agents 2 and 3, wire the orchestrator per the decided mode |
| 30–40 min | Run the full pipeline end to end. Expect at least one bug — narrate it per §18, don't panic |
| 40–50 min | Write and run the dashboard script, confirm it reads real rows from the DB |
| 50–60 min | Open the DB directly in a terminal to show real persisted rows; answer questions; state what you'd add with more time |

This mirrors your own §11 checklist almost exactly — the only addition here is putting a clock against each phase so you know at minute 20 whether you're on pace.

---

## 22. Final pre-interview checklist

- [ ] `call_llm` tested against a real key, today, not assumed to still work from last week
- [ ] Confirm current model name/free-tier limits for whichever provider you're using (your own notes already caught one retired model — check again close to interview day)
- [ ] One full pipeline run completed today, not just "it worked before"
- [ ] Can state, without looking, why single-shot over a loop for this task shape
- [ ] Can name at least two multi-agent coordination patterns beyond the one you built (§5)
- [ ] Can name at least one classical-AI agent type and one LLM-agent type (§4) without conflating the two taxonomies
- [ ] Have 2–3 resume examples ready per major JD theme (§19), not just for the live-build
- [ ] Comfortable saying "I'd need to verify the current API for that" out loud, rather than guessing at syntax under pressure
- [ ] Have an honest, rehearsed answer for "what would you have done differently with more time"

---

## 23. Things to verify yourself before the interview (don't take these from memory — mine or anyone's)

- Current model names and free-tier limits for whichever LLM provider you commit to (changes frequently)
- Current SDK method names/call shape for that provider (your own notes already found one deprecated mid-prep — assume it can happen again)
- What "Universal Worker Model" specifically means at this company — ask them, don't guess
- Current LangGraph/CrewAI/AutoGen/OpenAI Agents SDK capabilities if the conversation goes deep on frameworks — these products move fast
- Current MCP spec details if asked to go beyond the one-sentence definition

Good luck — the architecture work is already done in your own notes; this guide's job was to fill in the wider JD surface and give you the taxonomy vocabulary to sound precise, not to redo decisions you'd already made correctly.
