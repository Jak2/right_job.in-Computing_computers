# leaner_cut — walkthrough & talking points

This is the "lean," procedural build of the 3-agent system: one file, no classes,
everything runs locally against Ollama. Use this README to explain the code out
loud while you're screen-sharing — every section below has a **spoken version**
(in quotes, say it like you mean it) and a **why**, so you're never just reading
code at the interviewer.

---

## 1. What this actually is, in one breath

> "Three agents — Extractor, Risk Analyst, Synthesizer — that can either run
> completely independently, or hand work to each other collaboratively. Every
> run is logged to SQLite, and I picked four different ways to wire them
> together, because the JD explicitly said the agents need to work
> independently *or* collaboratively depending on the task — so I wanted to
> actually have both, not fake one with the other."

The three agents themselves never change. What changes is **how they're
wired together** — that's the whole design idea in this file. Four wiring
patterns, one shared set of agents.

---

## 2. Agent flow — the four patterns

```
Pipeline (sequential):
   query -> [Extractor] -> advancements -> [Risk Analyst] -> risks -> [Synthesizer] -> report
             (each arrow is a direct function call, output passed as an argument)

Parallel (independent):
   query -> [Extractor]   \
   query -> [Risk Analyst] |-- all three fire at once, same raw query, no cross-talk
   query -> [Synthesizer] /

Supervisor (orchestrator-worker):
   query -> [Supervisor classifies] -> "extractor"  -> [Extractor] only
                                     -> "pipeline"   -> full Pipeline above

Blackboard:
   query -> [Extractor] -> writes to DB
                            [Risk Analyst] -> reads Extractor's row from DB -> writes to DB
                                              [Synthesizer] -> reads both rows from DB -> writes to DB
   (agents never call each other directly — they only ever read/write the shared table)
```

Every pattern ends the same way: whatever ran gets logged into the `runs`
table, and `dashboard.py` renders that table regardless of which pattern
produced it. That's deliberate — the persistence and presentation layer
don't care how the agents were wired, only that they logged their work.

---

## 3. Section-by-section

### `call_llm()` — the one place that talks to the model

```python
def call_llm(system_prompt: str, user_prompt: str) -> str:
    res = requests.post("http://localhost:11434/api/generate", json={...})
```

> "Every agent is really just a system prompt plus a call to this one
> function. I didn't want three different places in the code that know how
> to talk to Ollama — if I ever swap the model, or point this at a real API
> instead, there's exactly one function to change."

**Why it looks like this:** it's a raw `requests.post` to Ollama's local
`/api/generate` endpoint, not a heavyweight SDK — because the only thing this
function needs to do is send a system prompt and a user prompt and get text
back. `timeout=600` is generous on purpose: this is CPU-only local inference
on a 1.5B model, and a long synthesis prompt can genuinely take a while — I'd
rather wait than have the demo throw a timeout mid-sentence.

### `log_run()` / `get_latest_output()` — the shared blackboard

```python
def log_run(agent_name, inputs, outputs): ...
def get_latest_output(agent_name) -> str: ...
```

> "This SQLite table is the single source of truth for what every agent did.
> `log_run` is the write side — every agent calls it after it finishes, no
> exceptions. `get_latest_output` is the read side, and it's *only* used by
> the blackboard pattern — that's what makes blackboard actually different
> from pipeline: agents pull their input from this table instead of getting
> it handed to them directly."

**Why the table is created inline (`CREATE TABLE IF NOT EXISTS`) instead of a
`schema.sql` file:** for a file this small, a separate schema file is one
more thing to keep in sync and one more thing that can go missing. The
table only has one shape, ever, so it lives right next to the function that
writes to it.

### `AGENT_PROMPTS` — one dictionary, not three functions

```python
AGENT_PROMPTS = {
    "extractor": ("Extractor", "You are an expert research agent..."),
    "risk": ("Risk Analyst", "You are a technical risk analyst..."),
    "synthesizer": ("Synthesizer", "You are a principal technical editor..."),
}
```

> "Every pattern below needs to look up 'what's Extractor's system prompt'
> or 'what's Extractor's display name' — so I made that one dictionary
> instead of three separate hardcoded prompts scattered across four
> functions. If I need to tune what the Risk Analyst does, I change it in
> exactly one place, and every pattern picks it up automatically."

This is also what makes `--agent extractor` (single-agent mode) and
`--pattern parallel` share code cleanly — they both just index into this
dict rather than duplicating the prompt text.

### `run_single_agent()` — the "just run one" case

```python
def run_single_agent(agent_key: str, query: str) -> str:
```

> "This is the direct answer to 'run it with just one of the agents' — no
> chaining, no other agent involved. Whatever text you give it goes straight
> to that one agent's system prompt, gets logged, done."

This is also what backs the `extractor` branch of the supervisor pattern —
the supervisor doesn't reimplement "run one agent," it just calls this.

### `run_pipeline()` — sequential handoff

```python
def run_pipeline(query: str):
    advancements = call_llm(extractor_prompt, query)
    ...
    risks = call_llm(risk_prompt, f"Field: {query}\nAdvancements:\n{advancements}")
    ...
    report = call_llm(synth_prompt, f"...\n{advancements}\n\n...\n{risks}")
```

> "This is the classic version — Extractor's output literally becomes part
> of the Risk Analyst's prompt, and both of theirs become part of the
> Synthesizer's prompt. It's the simplest way to make three agents
> collaborate, and it's also the most fragile: if Extractor hallucinates
> something wrong in step one, that mistake is now baked into the input for
> steps two and three. I still start here because it's the easiest one to
> reason about out loud, and it's genuinely the right tool when a task truly
> has three dependent steps."

### `run_parallel()` — independent execution

```python
with ThreadPoolExecutor(max_workers=len(AGENT_PROMPTS)) as pool:
    results = list(pool.map(run_one, AGENT_PROMPTS))
```

> "This is the other half of the requirement — agents running
> *independently*. All three get the same raw query at the same time, none
> of them waits on or reads another's output. I used a thread pool instead
> of just calling them one after another, because if I'm claiming
> 'independent,' I want them actually running concurrently, not just
> independently-in-sequence — the wall-clock time should look different, not
> just the wiring."

**Honest caveat, worth saying out loud if asked:** on a single local Ollama
instance, the model itself may still serialize requests under the hood — the
concurrency is real at the code level (three threads, three in-flight HTTP
calls), even if the GPU/CPU underneath processes them one at a time. That
distinction — "my code is parallel, the backend may not be" — is exactly the
kind of nuance that shows you're not just running code, you understand what
it's actually doing.

### `run_supervisor()` — orchestrator-worker

```python
SUPERVISOR_PROMPT = "...decide: does it need the Risk Analyst and Synthesizer too..."

def run_supervisor(query: str):
    decision = call_llm(SUPERVISOR_PROMPT, query)...
    if decision == "extractor":
        run_single_agent("extractor", query)
    else:
        run_pipeline(query)
```

> "This is the pattern I actually think is the most 'real' one, and it maps
> straight onto what I said in my UWM answer — a central controller decides
> which agent runs, instead of a human deciding in advance. Concretely: I
> make one cheap classification call first — 'does this query need risk
> analysis and a synthesized report, or is it just a factual lookup the
> Extractor can fully answer' — and only then do I call the agent(s) that
> decision actually requires. That's the difference between a workflow that
> always burns three LLM calls no matter what you ask, and one that reasons
> about what the task actually needs first."

**Why this is the default (`--pattern` defaults to `supervisor`):** it's the
one pattern that self-selects between independent and collaborative
depending on the task, which is *exactly* the literal requirement in the
brief — "capable of working independently or communicating with one another
... depending on the tasks." The other three patterns are fixed shapes; this
one is the shape that decides.

### `run_blackboard()` — decoupled via shared state

```python
def run_blackboard(query: str):
    advancements = call_llm(extractor_prompt, query)
    log_run("Extractor", query, advancements)

    advancements_from_board = get_latest_output("Extractor")   # <- reads DB, not the variable above
    risks = call_llm(risk_prompt, f"...{advancements_from_board}")
```

> "This one looks almost identical to pipeline if you just read the output,
> but the mechanism underneath is different on purpose. In pipeline, Risk
> Analyst's input is the Python variable `advancements` — direct function
> call, direct handoff. In blackboard, Risk Analyst doesn't receive anything
> from the caller at all — it goes and reads the Extractor's row back out of
> the database itself. The agents are fully decoupled: I could kill the
> process after Extractor finishes, restart it, and Risk Analyst would still
> find its input sitting on the blackboard. That's the trade-off — more
> moving parts, but agents that don't need to know about each other's
> function signatures, only about the shared table."

Notice `advancements_from_board` is fetched *again*, deliberately, inside the
Synthesizer's block too — not reused from the Risk Analyst's fetch. That's
not a bug, it's the pattern: every agent reads the blackboard fresh, it
never trusts a value handed to it in-memory by another step.

### `PATTERNS` + `argparse` — the actual switch

```python
PATTERNS = {"pipeline": run_pipeline, "parallel": run_parallel,
            "supervisor": run_supervisor, "blackboard": run_blackboard}
...
if args.agent:
    run_single_agent(args.agent, args.query)
else:
    PATTERNS[args.pattern](args.query)
```

> "This is the part that ties it together for a live demo. If you tell me
> to run just one agent, `--agent` skips all the pattern logic entirely and
> goes straight to `run_single_agent`. Otherwise, `--pattern` picks which of
> the four wiring styles handles the query. Same three agents underneath,
> every time — only the orchestration around them changes. That's the
> point I want to land: 'multi-agent design' is really a question of *how
> you wire the handoffs*, not how many different agents you write."

---

## 4. If asked "why four patterns, isn't that overkill for three small agents?"

> "Fair pushback. The three agents themselves stayed small on purpose — one
> prompt, one call, one log line each. What I spent the extra time on was
> the wiring, because that's actually where the interesting design decisions
> live, and where I could show I understand the trade-offs instead of just
> shipping the first thing that worked. In an actual live task, I'd default
> to whichever one pattern the task obviously calls for — usually pipeline
> or supervisor — and only reach for parallel or blackboard if the task
> specifically needed 'these must run independently' or 'these must not know
> about each other directly.'"

---

## 5. Running it

No API key, no `REHEARSAL_MODE`, no provider switch needed — this file only
ever talks to your local Ollama model (`OLLAMA_MODEL`, default
`qwen2.5:1.5b`). Every run appends to `blackboard.db`; run
`python dashboard.py` afterward to see it rendered.

### From inside `leaner_cut/`

```powershell
cd leaner_cut

# --help — see every flag
python main.py --help

# Default run — no args at all, uses the built-in sample query and the
# default pattern (supervisor)
python main.py

# Each of the four multi-agent patterns, explicit topic
python main.py --pattern pipeline   "quantum computing"
python main.py --pattern parallel   "quantum computing"
python main.py --pattern supervisor "quantum computing"   # same as omitting --pattern
python main.py --pattern blackboard "quantum computing"

# Force exactly one agent, independently — bypasses pattern selection entirely
python main.py --agent extractor    "what color is a tomato"
python main.py --agent risk         "what color is a tomato"
python main.py --agent synthesizer  "what color is a tomato"

# Swap the local model for a run, without touching code
$env:OLLAMA_MODEL = "qwen2.5:3b"
python main.py --pattern pipeline "quantum computing"
Remove-Item Env:\OLLAMA_MODEL   # back to the qwen2.5:1.5b default

# Render the dashboard after any run above
python dashboard.py
```

### From the repo root

```powershell
python leaner_cut\main.py --agent extractor "your topic"
python leaner_cut\main.py --pattern blackboard "your topic"
python leaner_cut\dashboard.py
```

### Via the venv directly (no activation), from the repo root

Useful when you haven't run `.\venv\Scripts\Activate.ps1` yet in the current
shell — this is exactly how every example in this README was actually tested:

```powershell
.\venv\Scripts\python.exe leaner_cut\main.py --pattern parallel "quantum computing"
.\venv\Scripts\python.exe leaner_cut\main.py --agent extractor "what color is a banana"
```

### Bash / Git Bash equivalents

Same script, just POSIX path separators and `python3`:

```bash
cd leaner_cut
python3 main.py --pattern supervisor "quantum computing"
python3 main.py --agent extractor "what color is a tomato"
python3 dashboard.py
```

### Via `run_rehearsal.ps1` (repo root)

The wrapper script that also auto-generates the dashboard on success:

```powershell
.\run_rehearsal.ps1                                                       # defaults: leaner_cut, supervisor pattern is not wired here — runs full pipeline
.\run_rehearsal.ps1 -Query "your topic"
.\run_rehearsal.ps1 -Query "your topic" -Agent extractor                  # single-agent mode
.\run_rehearsal.ps1 -Query "your topic" -Model qwen2.5:3b                 # different local model
.\run_rehearsal.ps1 -Query "your topic" -Project original_shape           # run the OOP version instead
```

Note: `run_rehearsal.ps1` predates the `--pattern` flag and only knows about
`--agent` vs the full pipeline — for `parallel`/`blackboard`, call
`main.py` directly as shown above rather than through the script.

---

## 6. Full source, annotated line-by-line

This is the actual, current content of `main.py` and `requirements.txt`, with
a comment on every line explaining what it does and — where it matters —
what the alternative would have been and why it lost. This is the copy to
have open if you want to narrate the code top-to-bottom without having to
improvise a reason for every choice on the spot. Nothing here changes the
real files; it's a reference copy.

### `main.py`

```python
import argparse                                    # stdlib CLI parser — chosen over hand-rolled sys.argv
                                                     # indexing so --agent/--pattern get free validation,
                                                     # --help text, and clear errors on bad input for free.
import os                                           # only used to read env vars (OLLAMA_MODEL) — no need
                                                     # for anything heavier like python-dotenv's os wrapper.
import sqlite3                                      # stdlib DB driver — no server process to run, no extra
                                                     # dependency; a file-based DB is exactly right for a
                                                     # single-process demo that just needs to persist rows.
from concurrent.futures import ThreadPoolExecutor   # used only by the parallel pattern, to fire all three
                                                     # Ollama calls concurrently instead of one after another.
                                                     # Chose threads over asyncio/aiohttp: these calls are
                                                     # blocking `requests.post`s, and threads parallelize
                                                     # blocking I/O without rewriting call_llm as async.
from pathlib import Path                            # used for __file__-relative paths — chosen over plain
                                                     # string concatenation so path joins are OS-correct on
                                                     # both Windows and POSIX without extra code.

import requests                                     # simple synchronous HTTP client — chosen over the
                                                     # heavier `httpx` or writing raw `urllib` calls, since
                                                     # this script only ever does a single POST per call.
from dotenv import load_dotenv                      # loads a .env file into os.environ — chosen over asking
                                                     # the user to export env vars by hand every session.

# Load .env next to this file, not from the caller's cwd — load_dotenv()
# with no path searches cwd upward, which silently misses it if this
# script is invoked from outside its own directory.
load_dotenv(Path(__file__).parent / ".env")         # explicit path, not load_dotenv() with no args — the
                                                     # no-args version searches upward from the *current
                                                     # working directory*, which breaks the moment this
                                                     # script is run from anywhere but its own folder.

DB_PATH = str(Path(__file__).parent / "blackboard.db")  # DB always lives next to this script, not in
                                                          # whatever directory you happened to run it from —
                                                          # same reasoning as the .env path above.

# 1. Base LLM caller — always the local Ollama model (OLLAMA_MODEL, default
# qwen2.5:1.5b). No API key or network provider involved.
def call_llm(system_prompt: str, user_prompt: str) -> str:   # one shared function every agent calls —
                                                               # chosen over each agent making its own HTTP
                                                               # call, so there's exactly one place to change
                                                               # if the model or endpoint ever changes.
    res = requests.post(
        "http://localhost:11434/api/generate",         # Ollama's local generation endpoint — hardcoded
                                                         # since this is always local, never a remote host;
                                                         # a remote LLM would need auth/TLS this doesn't have.
        json={
            "model": os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b"),  # env var with a default, not a
                                                                        # hardcoded model name — lets you
                                                                        # swap models (e.g. qwen2.5:3b)
                                                                        # without touching code.
            "system": system_prompt,                   # the agent's role/instructions, kept separate from
                                                         # the user prompt — mirrors how every real LLM API
                                                         # (Gemini, OpenAI, Anthropic) splits system vs user.
            "prompt": user_prompt,                      # the actual task input for this specific call.
            "stream": False,                            # get one complete response back, not a token
                                                         # stream — simpler to log and print for a CLI demo
                                                         # that doesn't need live token-by-token output.
        },
        timeout=600,  # CPU-only local inference is slow, especially on longer prompts
                      # 600s, not the requests default (no timeout at all) — long enough that a slow
                      # synthesis prompt on CPU doesn't get killed mid-generation, but still finite so a
                      # genuinely hung request doesn't block forever.
    )
    res.raise_for_status()                              # fail loudly on a non-2xx response (e.g. model not
                                                         # pulled, Ollama not running) instead of silently
                                                         # returning a JSON error body as if it were a reply.
    return res.json()["response"]                       # Ollama's non-streaming response body puts the
                                                         # generated text under "response" — pull just that.


# 2. SQLite blackboard — shared state every pattern below logs to. In the
# "blackboard" pattern specifically, agents also *read* from it instead of
# being handed a value directly, so they're decoupled from each other.
def log_run(agent_name: str, inputs: str, outputs: str):     # one write function, called by every agent
                                                               # after every call — no agent skips logging.
    conn = sqlite3.connect(DB_PATH)                     # open a fresh connection per call rather than a
                                                         # long-lived global one — this is a low-frequency,
                                                         # single-process script, so connection reuse would
                                                         # save microseconds at the cost of more state to
                                                         # manage (e.g. across the parallel pattern's threads).
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,       # simple auto-incrementing id — enough to order
                                                         # rows and to fetch "latest" reliably.
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,  # DB-assigned timestamp, not Python's
                                                             # datetime.now() — keeps clock authority in one
                                                             # place (the DB) rather than trusting the caller.
            agent_name TEXT,                            # which agent produced this row — the key every
                                                         # pattern filters/joins on.
            input TEXT,                                 # exactly what was sent to the model, logged
                                                         # verbatim — needed to reconstruct what happened.
            output TEXT                                 # exactly what the model returned.
        )
    """)                                                 # created inline here, not via a schema.sql file —
                                                         # for one table this small, a separate schema file
                                                         # is one more file to keep in sync for no real
                                                         # benefit (see original_shape for the alternative).
    cursor.execute(
        "INSERT INTO runs (agent_name, input, output) VALUES (?, ?, ?)",  # parameterized query, not an
                                                                            # f-string building SQL — avoids
                                                                            # SQL injection even though the
                                                                            # input here is just LLM text,
                                                                            # not untrusted user input from
                                                                            # a web form; still the correct
                                                                            # default habit.
        (agent_name, inputs, outputs),
    )
    conn.commit()                                       # persist immediately after every single run — so
                                                         # a crash mid-pipeline still leaves prior agents'
                                                         # work durably on disk, not lost with an uncommitted
                                                         # transaction.
    conn.close()                                        # close rather than reuse — see note on connect().


def get_latest_output(agent_name: str) -> str:          # the "read" side of the blackboard — only used by
                                                         # run_blackboard(), nothing else calls this.
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT output FROM runs WHERE agent_name = ? ORDER BY id DESC LIMIT 1",  # newest row for
                                                                                         # this agent, not
                                                                                         # the oldest —
                                                                                         # "latest" means
                                                                                         # most recent run,
                                                                                         # so a rerun
                                                                                         # correctly
                                                                                         # supersedes an
                                                                                         # earlier one.
            (agent_name,),
        )
        row = cursor.fetchone()
    except sqlite3.OperationalError:                    # table might not exist yet if this is called
                                                         # before any agent has ever run — caught here
                                                         # rather than crashing, so the error message below
                                                         # can be specific instead of a raw traceback.
        row = None
    conn.close()
    if row is None:
        raise RuntimeError(f"No prior '{agent_name}' entry found on the blackboard.")  # fail loudly and
                                                                                          # specifically —
                                                                                          # not returning an
                                                                                          # empty string,
                                                                                          # which would
                                                                                          # silently feed a
                                                                                          # blank context
                                                                                          # into the next
                                                                                          # agent's prompt.
    return row[0]                                       # row is a 1-tuple (output,) — unwrap it.


# 3. Agent prompts — single source of truth, used by every pattern below.
AGENT_PROMPTS = {                                       # one dict, not three separate hardcoded prompt
                                                         # strings duplicated across every pattern function
                                                         # — every pattern below looks the agent's name and
                                                         # prompt up from here instead of repeating them.
    "extractor": (
        "Extractor",                                    # human-readable display name, used in prints and
                                                         # logged as agent_name in the DB.
        "You are an expert research agent. Given a technical query, identify the top 3 "
        "core advancements or breakthrough developments in this field. Output them as a numbered list.",
                                                         # system prompt asks for exactly 3, numbered — a
                                                         # constrained output shape is easier for the next
                                                         # agent (Risk Analyst) to match risk-to-advancement
                                                         # against, and easier to read on a dashboard card.
    ),
    "risk": (
        "Risk Analyst",
        "You are a technical risk analyst. Given a list of advancements in a technology field, "
        "identify key engineering risks, bottlenecks, or challenges associated with each advancement. "
        "Respond with a corresponding numbered list matching the advancements.",
                                                         # explicitly told to match Extractor's numbering —
                                                         # keeps the two lists aligned 1-to-1 so the
                                                         # Synthesizer isn't left guessing which risk maps
                                                         # to which advancement.
    ),
    "synthesizer": (
        "Synthesizer",
        "You are a principal technical editor. Synthesize the given advancements and risks "
        "into a structured executive summary report in Markdown. Highlight key findings, recommendations, "
        "and a final technical readiness verdict.",
                                                         # asks for Markdown specifically — dashboard.py
                                                         # renders this inside a <pre> block, and a
                                                         # structured report reads better there than an
                                                         # unstructured paragraph would.
    ),
}


# Runs exactly one agent, independently — no other agent's output is involved.
# Whatever text is supplied on the command line is fed to that agent directly.
def run_single_agent(agent_key: str, query: str) -> str:   # returns the output too (not just prints it) —
                                                             # so run_supervisor() can call this and still
                                                             # get the value back if it ever needs it.
    name, system_prompt = AGENT_PROMPTS[agent_key]      # unpack straight from the shared dict — this is
                                                         # exactly why AGENT_PROMPTS exists as a dict keyed
                                                         # by the same strings argparse's --agent accepts.
    print(f"=== Running {name} independently ===")      # printed banner — this is a live CLI demo, so
                                                         # stdout narration matters as much as the return
                                                         # value; the interviewer is watching this scroll by.
    print(f"[{name}] Processing input: '{query}'...")
    output = call_llm(system_prompt, query)             # query goes straight in as the user prompt, no
                                                         # reformatting — this agent needs no other agent's
                                                         # context by definition.
    log_run(name, query, output)                        # log immediately after the call, before printing
                                                         # the result — so a persisted row exists even if
                                                         # something after this line were to fail.
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
    advancements = call_llm(extractor_prompt, query)    # step 1 — raw query straight in, same as
                                                         # run_single_agent's extractor call.
    log_run(extractor_name, query, advancements)
    print(f"\n--- {extractor_name} Output ---\n{advancements}\n")

    risk_name, risk_prompt = AGENT_PROMPTS["risk"]
    risk_input = f"Field: {query}\nAdvancements:\n{advancements}"   # step 1's output is interpolated
                                                                     # directly into step 2's prompt string
                                                                     # — this is the "direct handoff" that
                                                                     # defines the pipeline pattern; no DB
                                                                     # round-trip needed to pass it along.
    print(f"[{risk_name}] Analyzing advancements...")
    risks = call_llm(risk_prompt, risk_input)
    log_run(risk_name, risk_input, risks)               # log the *combined* prompt as the input, not just
                                                         # the query — so the DB row shows exactly what this
                                                         # agent actually saw, not just the original topic.
    print(f"\n--- {risk_name} Output ---\n{risks}\n")

    synth_name, synth_prompt = AGENT_PROMPTS["synthesizer"]
    synth_input = f"Topic: {query}\nAdvancements:\n{advancements}\n\nRisks & Bottlenecks:\n{risks}"
                                                         # step 3 gets *both* prior outputs — this is why
                                                         # Synthesizer is last: it's the only agent whose
                                                         # prompt depends on two upstream results, not one.
    print(f"[{synth_name}] Synthesizing final report...")
    report = call_llm(synth_prompt, synth_input)
    log_run(synth_name, synth_input, report)
    print(f"\n--- Final Synthesized Report ---\n{report}\n")

    print("=== Pipeline Complete ===")


# 4b. Parallel / independent pattern — all 3 agents run on the same raw query
# at the same time. Fast, but no agent can use another's result.
def run_parallel(query: str):
    print(f"=== Pattern: parallel (independent) — query: {query} ===")

    def run_one(agent_key: str) -> tuple[str, str]:     # nested closure, not a module-level function —
                                                         # it only exists to be the unit of work handed to
                                                         # the thread pool, so it doesn't need to be visible
                                                         # or reusable outside this one pattern.
        name, system_prompt = AGENT_PROMPTS[agent_key]
        print(f"[{name}] Started (independent)...")
        output = call_llm(system_prompt, query)         # every agent gets the *same* raw query — the
                                                         # defining trait of "independent": nobody's prompt
                                                         # depends on anybody else's output.
        log_run(name, query, output)
        print(f"[{name}] Finished and logged to blackboard.")
        return name, output                             # returned as a tuple, not just printed — pool.map
                                                         # needs a return value to collect results in order.

    with ThreadPoolExecutor(max_workers=len(AGENT_PROMPTS)) as pool:   # exactly 3 workers, one per
                                                                         # agent — no point sizing the pool
                                                                         # larger since there are only ever
                                                                         # 3 units of work to hand out.
        results = list(pool.map(run_one, AGENT_PROMPTS))   # pool.map over the dict iterates its keys
                                                             # ("extractor", "risk", "synthesizer") — chosen
                                                             # over submit()+as_completed() because we don't
                                                             # need first-finished-first-handled ordering,
                                                             # just "all three, then show results in a
                                                             # stable order."

    for name, output in results:
        print(f"\n--- {name} Output ---\n{output}\n")   # printed after the pool block closes — so the
                                                         # per-agent "Started"/"Finished" lines interleave
                                                         # live as threads run, but the final full outputs
                                                         # print in one clean, deterministic block after.

    print("=== Parallel Run Complete ===")


# 4c. Orchestrator-worker / supervisor pattern — a central controller decides
# which agent(s) to run, in what order, given the query. Here the controller
# is a lightweight router call: it decides whether the query is a simple
# lookup the Extractor can fully answer, or whether it needs the full chain.
SUPERVISOR_PROMPT = (                                   # module-level constant, not built fresh inside the
                                                         # function — it never changes per call, so there's
                                                         # no reason to reconstruct the string every run.
    "You are a routing controller in front of a 3-agent system:\n"
    "- Extractor: identifies the top advancements/facts for a topic.\n"
    "- Risk Analyst: analyzes engineering risks — needs Extractor's output first.\n"
    "- Synthesizer: writes a final executive report — needs both prior outputs.\n"
    "Given the user's query, decide: does it need the Risk Analyst and Synthesizer too "
    "(a request for risks, bottlenecks, or a full report/analysis), or is it a simple "
    "factual/lookup question the Extractor alone can fully answer?\n"
    "Respond with exactly one word, nothing else: 'extractor' or 'pipeline'."
                                                         # forced to exactly one word — a small local model
                                                         # is unreliable at following complex output-format
                                                         # instructions, so the classification is kept to
                                                         # the simplest possible parseable output: one word.
)


def run_supervisor(query: str):
    print(f"=== Pattern: supervisor (orchestrator-worker) — query: {query} ===")
    decision = call_llm(SUPERVISOR_PROMPT, query).strip().lower()   # .strip().lower() to normalize —
                                                                       # small local models often pad
                                                                       # responses with whitespace or
                                                                       # inconsistent casing even when told
                                                                       # to answer in one word.
    decision = "extractor" if "extractor" in decision and "pipeline" not in decision else "pipeline"
                                                         # substring check, not exact `== "extractor"` —
                                                         # more forgiving of a model that answers
                                                         # "Extractor." or "extractor\n" instead of the bare
                                                         # word; and defaults to "pipeline" (the safer, more
                                                         # thorough option) on any ambiguous or unparseable
                                                         # response, rather than silently under-running.
    print(f"[Supervisor] Classified query as '{decision}'.")   # decision is printed before acting on it —
                                                                 # so the routing choice is visible and
                                                                 # explainable live, not a silent branch.

    if decision == "extractor":
        run_single_agent("extractor", query)            # reuses run_single_agent rather than duplicating
                                                         # its logic — the supervisor's job is only to
                                                         # decide, not to reimplement how a single agent runs.
    else:
        run_pipeline(query)                              # reuses run_pipeline rather than duplicating it —
                                                         # same reasoning: the supervisor composes the other
                                                         # patterns, it doesn't reinvent them.


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
    log_run(extractor_name, query, advancements)        # write to the blackboard — this row is what the
                                                         # next agent will read back, not receive directly.
    print(f"[{extractor_name}] Wrote result to blackboard.")

    risk_name, risk_prompt = AGENT_PROMPTS["risk"]
    print(f"[{risk_name}] Reading '{extractor_name}' result from blackboard...")
    advancements_from_board = get_latest_output(extractor_name)   # deliberately re-fetched from the DB
                                                                     # instead of reusing the `advancements`
                                                                     # variable already sitting in memory —
                                                                     # that in-memory reuse is exactly what
                                                                     # pipeline does; blackboard's whole
                                                                     # point is that this agent only trusts
                                                                     # the shared table, never a value handed
                                                                     # to it directly by the caller.
    risk_input = f"Field: {query}\nAdvancements:\n{advancements_from_board}"
    risks = call_llm(risk_prompt, risk_input)
    log_run(risk_name, risk_input, risks)
    print(f"[{risk_name}] Wrote result to blackboard.")

    synth_name, synth_prompt = AGENT_PROMPTS["synthesizer"]
    print(f"[{synth_name}] Reading prior results from blackboard...")
    advancements_from_board = get_latest_output(extractor_name)   # fetched *again* here, independently of
                                                                     # the Risk Analyst's fetch above — this
                                                                     # agent doesn't trust a variable handed
                                                                     # down through the function either; it
                                                                     # does its own read, same as every other
                                                                     # agent in this pattern.
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


PATTERNS = {                                            # maps the --pattern CLI string straight to the
                                                         # function that implements it — chosen over an
                                                         # if/elif chain in __main__ so adding a fifth
                                                         # pattern later means adding one dict entry, not
                                                         # another branch in the argument-handling code.
    "pipeline": run_pipeline,
    "parallel": run_parallel,
    "supervisor": run_supervisor,
    "blackboard": run_blackboard,
}


if __name__ == "__main__":                              # guards the CLI entry point — lets this file be
                                                         # imported (e.g. by dashboard.py or a test) without
                                                         # triggering a live LLM run as a side effect.
    parser = argparse.ArgumentParser(
        description="3-agent demo: choose a multi-agent pattern, or run any one agent independently."
    )
    parser.add_argument(
        "query", nargs="?", default="how much does a pen costs",   # positional and optional — so the
                                                                      # script is runnable with zero
                                                                      # arguments for a quick smoke test,
                                                                      # but takes a real topic when given one.
        help="Task/topic text to feed the agent(s)",
    )
    parser.add_argument(
        "--agent", choices=list(AGENT_PROMPTS), default=None,   # choices=... restricts input to the three
                                                                   # valid keys — argparse rejects a typo'd
                                                                   # agent name before any LLM call is made,
                                                                   # instead of failing deep inside call_llm.
        help="Run only this agent, independently — overrides --pattern",
    )
    parser.add_argument(
        "--pattern", choices=list(PATTERNS), default="supervisor",   # defaults to supervisor, not
                                                                        # pipeline — supervisor is the one
                                                                        # pattern that itself decides
                                                                        # independent-vs-collaborative per
                                                                        # query, which is the literal
                                                                        # requirement in the brief; the
                                                                        # other three are fixed shapes you
                                                                        # opt into deliberately.
        help="Multi-agent pattern to run (default: supervisor)",
    )
    args = parser.parse_args()

    if args.agent:
        run_single_agent(args.agent, args.query)        # --agent short-circuits pattern selection
                                                         # entirely — if you know exactly which one agent
                                                         # you want, there's no reason to run the supervisor
                                                         # classification call first.
    else:
        PATTERNS[args.pattern](args.query)               # dict lookup + call — same reasoning as PATTERNS
                                                         # itself: one line, no branching to maintain.
```

### `requirements.txt`

```
python-dotenv>=1.0.0   # loads .env into os.environ — only real alternative was asking the user to set
                       # OLLAMA_MODEL / etc. as real shell env vars every session, which is worse UX for a
                       # rehearsal script you'll run many times.
requests>=2.30.0       # synchronous HTTP client for the one POST call to Ollama — chosen over the stdlib's
                       # urllib (more boilerplate for the same result) or httpx (adds async support this
                       # script never uses, since call_llm is a simple blocking call by design).
```

Notice `google-genai` is **not** in this file — it was removed on purpose when
`leaner_cut` was cut over to Ollama-only. If you re-add a real Gemini path
later, that's the dependency that comes back.

---

## 7. Pattern comparison table

| Dimension | Pipeline | Parallel | Supervisor | Blackboard |
|---|---|---|---|---|
| **Execution order** | Sequential: A → B → C, one after another | Concurrent: A, B, C all fire at once (threads) | Decided at runtime: either just A, or the full A→B→C chain | Sequential: A → B → C, same order as pipeline |
| **How data moves between agents** | Direct handoff — prior output passed as a Python function argument | No handoff — each agent gets the same raw query, independently | Same as whichever it picks (single-agent = no handoff, pipeline = direct handoff) | Indirect — each agent writes to SQLite, the next agent re-reads it from SQLite, ignoring any in-memory value |
| **Coupling between agents** | Tightly coupled — B's call requires A's return value in scope | None — agents don't know about each other at all | Coupled only for the chain it picks; decoupled if it picks single-agent | Loosely coupled — agents only share a DB table, never call/reference each other directly |
| **Who decides what runs** | Fixed at code level — always all 3, in order | Fixed at code level — always all 3, no order | An LLM call (the router) decides live, based on the query | Fixed at code level — always all 3, in order |
| **LLM calls made** | Always 3 | Always 3 | 1 (simple query) or 4 (router call + 3 agents) | Always 3 |
| **Can one agent be rerun alone, safely?** | No — needs the caller to still have the prior variable | Trivially — no dependency exists in the first place | Depends which branch it took | Yes — it just re-reads the DB, doesn't need the original process/variables alive |
| **Survives a crash between steps?** | No — in-memory `advancements`/`risks` are lost, must restart from step 1 | N/A — no sequencing to resume | Same as whichever branch it's mid-way through | Yes — whatever was written to the DB before the crash is still there for the next agent to read |
| **Matches the JD's "independent OR collaborative depending on task"?** | Only demonstrates collaborative | Only demonstrates independent | Demonstrates both — decides per query, which is the literal requirement | Only demonstrates collaborative (different mechanism, same behavior) |
| **When you'd actually pick it** | Simple, auditable, everything genuinely depends on the last step | Truly unrelated sub-tasks on the same input, want speed | You don't know in advance which shape a given query needs | Agents might run in separate processes/restarts, or you want to swap/rerun one agent without touching the others |

The one-line version: **pipeline** and **blackboard** produce the same output in the same order — they only differ in *mechanism* (direct handoff vs. shared-state read). **Parallel** is the only one that's actually independent. **Supervisor** is the only one that *decides* between shapes rather than being a fixed shape itself.
