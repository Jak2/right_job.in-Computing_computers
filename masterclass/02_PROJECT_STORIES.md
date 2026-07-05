# 02 — Project Stories (Tell, Then Go Deep)

> Each project as you'd actually *tell* it: a 90-second story arc to open, the one clever
> decision that lands the "this person gets it" moment, then the depth to survive follow-ups.
> Same project, re-angled per question — the 5G pipeline is a RAG story, a caching story,
> or an LLM-reliability story depending on what they ask. Lead with the arc, stop, let them pull.
>
> **Priority for this agent role:** #1 (5G) is your lead — it's a full agent loop.
> #2 (Eval) is your "how do you make agents trustworthy" answer. #3 (RF Gen) is HITL.
> #4 (NFTRACE) is memory/lifecycle. #5 (Bias) is regulated-domain/HIPAA. #6 (Parser) is privacy.

---

## #1 — 5G Failure Detection & Remediation Pipeline  ★ LEAD STORY

*Pyshark · Qdrant · LangChain RetrievalQA · Claude · Redis*

**Why it's your lead:** it hits five JD bullets in one story — autonomy, RAG, HITL, escalation, self-improvement. It IS an agent loop.

**The 90-second arc:**
> "Picture a 5G core test lab where every signaling failure — an authentication timeout, a dropped handover — meant an engineer hand-scrolling gigabytes of packet captures for hours to find the cause. And the frustrating part: the *same* failures kept recurring, and we kept diagnosing them from scratch, because there was no institutional memory.
>
> So I built a pipeline that does the whole loop autonomously. Pyshark extracts the signaling error from the capture, Qdrant retrieves the closest known patterns, and Claude, grounded on those patterns, synthesizes a contextual fix.
>
> The key decision was *how* it recognizes errors. Keyword rules are brittle — the same fault shows up with slightly different wording every time. So I matched errors *semantically* against a vector database — and I pre-filtered by vendor and network layer at the database level, so a Nokia error never pulls an Ericsson fix, which would have the wrong CLI syntax and could make a live outage worse.
>
> The part I'm proudest of is what happens when the agent *doesn't* know. Below a 0.65 similarity score, a confident answer would be hallucinated advice — dangerous on a live network. So it refuses: 'unknown pattern, manual review required,' escalates to a human, and logs the error to a collection that ops engineers curate into new patterns. The agent's failures literally become its training data.
>
> Result: 70% of routine errors auto-resolved with no human, 55% MTTR reduction, cited in three internal audits."

**The one analogy:** semantic search = "a librarian who finds the right book even when you misremember the title."

**Go-deep answers (when they probe):**
- *Why Qdrant over FAISS?* Metadata pre-filtering at the DB level — Ericsson patterns never enter the similarity computation for a Nokia error. FAISS searches the whole corpus then filters in Python: slower and pollutes the ranking. (See tech deep-dive §3.)
- *Why cosine?* Angle not magnitude — concept over verbosity.
- *Why temperature 0.1?* Same pcap must give the same fix. Determinism is a feature for ops tooling.
- *Why not just return the closest document?* The document is generic ("check T3560 timer"). Claude contextualizes to *this* instance, synthesizes across multiple partial matches, and gives the engineer language they can act on: "this happened during a traffic spike — raise T3560 from 1s to 3s in the AMF config and monitor."
- *Redis?* Caches frequent error lookups so recurring failures resolve near-instantly instead of re-hitting retrieval + LLM.
- *Scale to 1000 pcaps/day?* Async FastAPI (I/O-bound), Celery (return job ID, poll), Qdrant sharding to keep search latency flat.

**Re-angle by question:**
- Asked about **RAG** → this is the metadata-prefilter story.
- Asked about **HITL / agent safety** → this is the 0.65-refusal story.
- Asked about **cost/caching** → this is the Redis + model-routing story.
- Asked about **"an agent"** → this is your perceive→retrieve→reason→act→escalate loop.

---

## #2 — LLM Evaluation Framework  ★ "how do you make agents trustworthy"

*FastAPI · Celery · Redis · PostgreSQL · Streamlit · Docker Compose*

**They WILL ask how you QA an AI system. This is the answer.**

**The 90-second arc:**
> "As the owner of an LLM-powered product, your worst failure is silent. A model provider ships an update with no changelog — the API contract doesn't change, but the answers quietly get worse. Shorter responses, shifted edge cases. Nobody notices for days; support tickets are your first signal, and by then users have felt the product get dumber.
>
> So I built an automated quality gate. Every prompt/response pair runs through four independent evaluators — an LLM-as-judge, a hallucination detector, a RAG faithfulness scorer, and a consistency checker. Results land in Postgres, failures fire a Slack alert, and a live dashboard shows the trend.
>
> The key design decision was AND-logic, not a weighted average. A response that's 95% faithful but hallucinates one claim still *fails* — because an average would hide exactly the failure that hurts a user. It's a quality gate, not a quality summary.
>
> The geeky part I love: the two RAG scores *diagnose* the failure. High faithfulness but a wrong answer means the retriever fed bad documents. Low faithfulness means the model ignored the retriever. Different failure, different fix.
>
> In a simulated provider update, it caught a 14-point faithfulness drop in under four minutes — versus two to three days of manual review."

**Go-deep answers:**
- *Faithfulness vs hallucination?* Hallucination = claims unverifiable against a reference (factual grounding). Faithfulness = did it stay inside the *retrieved context*. Faithfulness 1.0 ≠ correct — it means the model only used retrieved content. (Tech deep-dive §3/§4.)
- *Why Celery over FastAPI BackgroundTasks?* Background tasks are in-process — if the server restarts mid-eval (a deploy), the task vanishes silently, and a PR that should've been blocked passes. Celery persists in Redis and retries. Non-negotiable for a CI/CD gate.
- *Why async stack (FastAPI + async SQLAlchemy + asyncpg)?* API stays responsive while evals run 5–30s in the background.
- *Cost at scale?* Local-model fallbacks (80MB sentence-transformer instead of an API call), and evaluators are selectable per test case — a unit test runs only the judge, a RAG regression runs faithfulness + hallucination.
- *Extensibility?* Registry/factory pattern + a JSON `eval_scores` column — add an evaluator by writing a class and registering a name, no schema migration.
- *Consistency checker?* Re-runs the prompt N times at temp 0.7, measures mean pairwise cosine similarity — surfaces prompts that are a coin-flip in production.

**Re-angle:** this is your answer to "how do you evaluate agent quality before release," "how do you catch model drift," and "how do you make AI trustworthy." Connect it to their release process: "this is exactly how I'd QA a UWM agent before it ships — a golden suite as a blocking gate."

---

## #3 — Robot Framework Keyword Generator  ★ HITL / "when NOT to be autonomous"

*Streamlit · FastAPI · Claude Haiku · RF Parser*

**The 90-second arc:**
> "A test engineer describes a test in plain English and gets a ready-to-use Robot Framework keyword in under two seconds instead of an hour of boilerplate. But here's the trap: an LLM will happily generate syntactically beautiful, semantically *wrong* test code — and a wrong test that passes is worse than no test, because now you trust something broken.
>
> So I split the job by what each part is good at. The LLM does *only* entity extraction — understanding that 'mobile identity' means IMSI — and deterministic templates generate the actual RF structure, which is syntactically correct by construction. Then Robot Framework's own parser validates the output before it's ever returned, so the engineer never receives a broken file. And a human reviews every keyword before it enters the suite — human-in-the-loop by design.
>
> The fallback chain — LLM to regex to defaults — means it never crashes and always returns something reviewable. It went zero to 50-plus generations a week on pure word of mouth."

**Go-deep answers:**
- *Why templates, not full LLM generation?* Reliability (LLMs botch RF's indentation-sensitive, `${var}` syntax) + cost/latency at 50+/week. "LLM for understanding, templates for structure" — the production hybrid pattern.
- *Why Haiku specifically?* Entity extraction is narrow — no reasoning needed. Haiku is 3–5× cheaper at ~500ms. Cheapest model that reliably does the task.
- *Bad JSON from the LLM?* `json.loads` raises → automatic regex fallback → tester sees no error. LLM path is an enhancement, not a dependency. That's the 100%-uptime claim.
- *Why FastAPI + Streamlit split?* Testable endpoints (pytest+httpx, no browser automation), reusable `/generate` (CLI, CI, IDE plugin), UI redesign doesn't touch the engine.

**Re-angle:** this is your headline answer to "when should an agent NOT be autonomous?" — a senior-signal question. Also your fallback-chain / graceful-degradation story.

---

## #4 — NFTRACE  ★ memory / lifecycle / state management

*FastAPI · Redis · SQLite · XML-RPC · multiprocessing · Robot Framework*

**The 90-second arc:**
> "Our CI/CD pipelines for validating 5G network functions were slow and fragile, and the test scenarios were tangled with the validation logic — changing one risked breaking the other. And parallel test runs stepped on each other's state.
>
> So I architected NFTRACE, a distributed platform that cleanly separates *what* you test from *how* you validate it, exposed as four REST calls — start, stop, merge, validate.
>
> Two decisions made it work. First, lifecycle endpoints turned test scenarios into composable building blocks instead of monoliths. Second — the hard part — running tests in parallel without corrupting each other's state. I gave each run a UUID-keyed session so a worker can only ever touch its own trace, and I split persistence by *temperature*: Redis for hot active-session state that transitions rapidly and needs TTL-based cleanup if a worker crashes, and SQLite for cold completed history that has to survive restarts. An in-memory dict couldn't share safely across parallel workers; a full database server was overkill — Redis hit exactly the right point.
>
> It cut pipeline validation time in half. And the integration into Nokia's CD pipeline caught a whole class of bugs that were invisible before: tests that *passed* while the network behavior underneath was actually wrong."

**Go-deep answers:**
- *Redis + SQLite, why both?* Different access patterns. Redis: sub-ms, concurrent-safe, TTL auto-expires orphaned sessions from crashed workers. SQLite: persistent history, read infrequently. SQLite for hot state under 20 workers would bottleneck on write serialization; Redis-only loses history on eviction.
- *Session isolation?* UUID Redis key `session:{uuid4()}`; every op requires the session ID, so Worker 2 can't stop Worker 1's trace. TTL prevents orphan lockups.
- *Why multiprocessing not asyncio?* Traces on N nodes must start *simultaneously* or you miss initial messages; `xmlrpc.client` is synchronous, so multiprocessing.Pool used the stdlib without an async XML-RPC dependency. At 50+ nodes, asyncio would be the migration.
- *Why SQLite not Postgres?* Single-server test lab, sequential writes, low concurrent reads — Postgres adds a server, pooling, credentials, a DBA, for zero benefit here. "I documented exactly when to migrate: multi-server, failover, or hundreds of concurrent writes."
- *Why XML-RPC?* Telecom industry constraint (nodes expose it), but the REST API *shields* workers from it — when nodes move to gRPC, only the NodeManager changes. An abstraction win.

**Re-angle:** this is your **agent memory / state-management / lifecycle** story — "working memory in Redis, episodic history in SQLite, right store per access pattern." Also your "right tool for the job / knowing when NOT to add complexity" story.

---

## #5 — Bias & Fairness Auditor  ★ regulated domains / HIPAA / healthcare

*FastAPI · Claude · VADER · sentence-transformers · SciPy · Streamlit*

**Use when the JD's healthcare/insurance/fintech or HIPAA comes up.**

**The 90-second arc:**
> "As a compliance officer, when the EU AI Act requires you to prove your AI system isn't biased, you can't hand regulators a shrug — you need documented, reproducible evidence. Manual spot-checking isn't statistically credible; a single run can't separate a real bias signal from random variance.
>
> So I built an auditor that does counterfactual fairness testing — it takes a prompt, changes *only* the demographic signal (names, age, religion), runs each variant many times, and measures whether outputs differ in tone, content, or quality. Any difference can only be explained by the demographic, because everything else is held constant.
>
> The design decision that matters: the LLM-as-judge never sees the demographics — they're stripped before it judges. Otherwise you'd import the judge's *own* training-time bias into the audit. Two-layer scoring, VADER then DistilBERT only when VADER is ambiguous, ANOVA plus Cohen's d for statistical *and* practical significance. And the output is EU AI Act Article 13-compliant documentation, generated automatically as a by-product of every run.
>
> That's the same discipline healthcare and insurance need: audit trails, blind evaluation, data minimization. HIPAA changes *what* data is sensitive, not *how* you engineer for it."

**Go-deep answers:**
- *Why multiple runs per variant?* LLMs are non-deterministic — one run can't distinguish bias from noise. ANOVA separates significant differences from variance.
- *Cohen's d on top of p-value?* P-value = is it real; Cohen's d = does it matter. With enough samples a trivial difference is "significant" but meaningless. Both = the full picture.
- *Blind judge?* Strip demographics so the judge rates content, not the person — prevents bias import.
- *Async + semaphore?* 100 variants × 5 runs = 500 calls; `asyncio.gather` with a semaphore capping in-flight at 10 avoids instant rate-limiting.

**Re-angle:** regulated-AI / compliance / governance story, and a second strong "AI evaluation" story alongside the eval framework.

---

## #6 — Financial Statement Parser  ★ privacy-first architecture

*React · Tesseract.js (WASM) · Gemini · SheetJS*

**Shortest story — use for privacy/data-governance or a frontend question.**

**The 60-second arc:**
> "I built a privacy-first browser app that turns messy bank-statement PDFs into categorized Excel in about ten seconds — and the defining constraint is that the original file *never leaves the browser*. I run OCR entirely in-browser with Tesseract compiled to WebAssembly, extract only the text, and send just that text — never the file — to Gemini for categorization. No server, no subscription, no data liability. The whole architecture is one decision: send the OCR *text* to the AI, not the raw document. Privacy over simplicity."

**Go-deep answers:**
- *WASM?* Binary format running in-browser at near-native speed; lets a C++ OCR engine run locally with no server.
- *BYOK tradeoff?* First-run friction (user brings a Gemini key) buys zero backend — nothing to breach, no hosting cost, no data liability.
- *Truncated LLM output?* Three-method JSON salvage — strip code fences, index-based `{...}` boundary, repair to the last complete transaction. Partial results beat an error mid-session.
- *A real debug story (shows you ship):* the "Add More Files" bug — closure staleness in an async loop reset the state machine and wiped prior results. Fix: an `updateStatus=false` flag + snapshotting `const currentTransactions = [...transactions]` at function entry so the async loop didn't read a stale closure.

**Re-angle:** privacy/data-governance story; your frontend/React proof; graceful-degradation (JSON salvage) story.

---

## The portfolio one-liner (asked "what have you been building?")

> "My recent work sits where AI engineering meets production reliability. The through-line is that I treat the LLM as a brilliant but unreliable component and build the system that stays correct when it's wrong — retrieval that filters before it ranks, quality gates that fail on any single miss, agents that refuse to act when they're unsure, and a fallback under everything. On the telecom side I automated 5G failure diagnosis and network-function tracing; on the AI side I built the evaluation, bias-auditing, and privacy-first tooling that regulated AI actually needs to ship."

---

## Numbers table (glance before you walk in)

| Project | Impact | The one non-obvious decision |
|---|---|---|
| 5G Pipeline | 70% auto-resolution, 55% MTTR ↓ | Metadata pre-filter at DB level (Nokia never pulls Ericsson) |
| LLM Eval | 14-pt drop caught in 4 min vs 2–3 days | AND-logic gate, not weighted average |
| RF Generator | 50+/week, organic adoption | LLM for understanding, templates for structure |
| NFTRACE | 50% validation time ↓ | Redis (hot) + SQLite (cold) — right store per access pattern |
| Bias Auditor | EU AI Act Article 13 docs auto-generated | Blind judge — demographics stripped before judging |
| Financial Parser | Zero server, zero data liability | Send OCR text to AI, not the raw file |
