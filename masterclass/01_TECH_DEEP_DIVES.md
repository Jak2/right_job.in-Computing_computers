# 01 — JD Technology Deep-Dives (Discussion Mode)

> How to *discuss* each technology the JD demands — not recite. Each section gives you:
> the senior mental model, the failure modes you'd bring up unprompted, the questions they'll
> ask with answers phrased as a conversation between peers, and the line from your own work
> that proves it. Talk *with* the interviewer, not *at* them.
>
> **Order = JD priority for an agent role.** Sections 1–8 are the meat. 9–14 are backend/infra
> you must be solid on but that get lighter probing in a theory round.

---

## 1. AI Agent Architecture & the Agent Loop

**The mental model to lead with:** An agent is a *loop with a decision at runtime*. A workflow is a fixed sequence *you* designed; an agent decides its own next step based on current state. The canonical loop: **perceive → retrieve context → reason → act (call a tool) → observe the result → decide whether to loop, finish, or escalate.** The tight academic version is **ReAct** (Reason-Act-Observe), where the model alternates thinking and tool calls, feeding each observation back into the context window.

**What separates senior from junior here:** juniors describe the happy path. You talk about *control*: how do you stop an infinite loop, cap the number of steps, detect when the agent is stuck, and — most importantly — when does it refuse to act. "Every agent I've shipped has an explicit 'I don't know' path. An agent that always acts is a liability."

**Failure modes you raise unprompted:**
- **Runaway loops** — cap max iterations; detect repeated identical tool calls (the model is stuck).
- **Context bloat** — each observation gets appended; the window fills, cost climbs, quality drops. You manage what enters the prompt (see §7).
- **Confidently wrong actions** — the model will call a tool with plausible-but-wrong arguments. Validate tool inputs/outputs; keep a human gate on anything irreversible.

**Questions and how you'd discuss them:**

*Q: "What's the difference between an agent and a workflow?"*
> "A workflow is a fixed sequence — I decide the steps at design time. An agent decides its next step at runtime based on state. My 5G pipeline is actually a hybrid, which I think is the honest production answer: it's agentic at the decision points — the match-confidence score chooses between auto-fixing, deeper reasoning, or human escalation — and a deterministic workflow everywhere determinism is safer. Pure autonomy everywhere is usually a liability; you make things agentic exactly where judgment adds value and keep them deterministic where correctness matters more than flexibility."

*Q: "How do you keep an agent from looping forever or going off the rails?"*
> "Three guards. A hard iteration cap. A loop-detector that catches the model making the same tool call twice — that's the signature of a stuck agent. And a confidence gate that escalates to a human instead of grinding. The philosophy is that the agent should fail *loudly and safely*, not silently and confidently."

**Your proof:** Brane's agent runtime — you worked on the agent loop, tool registry context, and the verifier-with-retry correction loop. The 5G pipeline is a full perceive→retrieve→reason→act→escalate loop in production.

---

## 2. Multi-Agent Systems, A2A & Orchestration

**The mental model:** multi-agent = decomposing a hard job into specialized agents that coordinate. Two shapes: **coordinator/orchestrator** (one agent delegates to sub-agents and aggregates their results — a hub-and-spoke) and **peer-to-peer A2A** (agents talk directly, negotiate, hand off). The hard problems are the *same as distributed systems*: shared state, failure isolation (one agent dying can't wedge the rest), and decision authority (who is allowed to decide what, and how do you aggregate conflicting verdicts).

**The honest, strong framing (use this — don't bluff):**
> "I've built coordinator-pattern systems in production. My eval framework runs four independent evaluator agents whose verdicts get aggregated by AND-logic — that's a coordinator with strict verdict combination. My 5G pipeline is a pipeline of specialized stages with a human-escalation authority. I haven't shipped peer-to-peer A2A protocols yet, but the genuinely hard parts of multi-agent — shared state, failure isolation, verdict aggregation — are the ones I already solve. I'd want to hear how UWM structures A2A messaging and whether it's a message bus or direct calls."

**Failure modes to raise:** cascading failure (one slow agent blocks the pipeline → timeouts + isolation), conflicting outputs (two agents disagree → you need an explicit resolution rule, not a silent last-writer-wins), and cost explosion (N agents × M calls — this is why routing and caching matter even more in multi-agent).

*Q: "How would you aggregate outputs from multiple agents that disagree?"*
> "Depends on the risk. For a quality gate, AND-logic — any agent's failure blocks the result, because I'd rather a false alarm than a missed defect. For a best-answer scenario, you can do weighted voting or a judge agent that adjudicates. The anti-pattern is averaging, which hides the one dissenting signal that mattered."

**Your proof:** eval framework = 4-agent coordinator with AND aggregation; 5G pipeline = staged pipeline with escalation authority.

---

## 3. RAG Pipelines & Vector Databases

**The mental model — RAG in one breath:** chunk your knowledge → embed each chunk into a vector → store in a vector DB → at query time, embed the query, retrieve the top-k nearest chunks, stuff them into the prompt as grounding, and have the LLM answer *from that context*. The whole point is to give the model *fresh, private, citable* knowledge it wasn't trained on — and to make answers traceable.

**The two insights that make you sound expert:**

1. **Metadata pre-filtering beats post-filtering.** Retrieval is a filtering problem *before* it's a similarity problem. In your 5G pipeline, a Nokia error must only ever match Nokia patterns — an Ericsson fix has different CLI syntax and could worsen a live outage. Qdrant's `must` filter runs *at the database level, before* similarity is computed. FAISS has no metadata filtering — you'd search the entire corpus and discard wrong-vendor matches afterward, which is slower *and* pollutes the ranking. "Pre-filter, then rank."

2. **Faithfulness ≠ accuracy** (your signature move — see §4 of the geek core). This is what you say when RAG quality comes up.

**Design decisions you can defend:**
- **Cosine similarity, not Euclidean** — cosine measures *angle/direction* (concept), not magnitude (verbosity). "T3560 timeout" and "NAS 5GMM authentication failed due to T3560 timer expiry" point the same direction; cosine scores them close, Euclidean would be misled by length.
- **Similarity threshold (0.65)** — below it, the match is too weak; returning a low-confidence answer is *hallucinated advice, worse than nothing*. You return "unknown — human review" and log to a growing `unknown_errors` collection. **The refusal path.**
- **`return_source_documents=True`** — trust. An ops engineer about to restart a live service needs to see "based on pattern AUTH_TIMEOUT_T3560, matched 0.94." Without citations it's a black box no one acts on.

**Chunking — have an opinion:** too-large chunks dilute the embedding (one vector for many ideas → poor recall); too-small chunks lose context. You chunk on semantic boundaries and often overlap slightly so a fact split across a boundary still retrieves. "Bad chunking is the silent killer of RAG — people blame the model when the real problem is that retrieval never surfaced the right passage."

**Vector DB landscape (know the tradeoffs, don't just name-drop):**
- **Qdrant** — DB-level metadata pre-filtering, production-grade, what you used.
- **FAISS** — a library, blazing fast, in-memory, *no metadata filtering, no persistence layer* — great for a static index, wrong for multi-tenant.
- **pgvector** — vector similarity *inside PostgreSQL*. Embeddings live next to relational data. "For a team already on RDS Postgres — which this JD is — pgvector removes an entire piece of infrastructure. I chose Qdrant when I needed DB-level pre-filtering at scale, but I'd genuinely put pgvector on the table here since the role pairs Postgres with RAG."
- **Pinecone / Weaviate** — managed, scale-out; you trade cost/lock-in for not running it yourself.

*Q: "How would you debug a RAG system giving wrong answers?"*
> "I don't start at the model — I start at retrieval, because that's where most RAG bugs live. First I log the retrieved chunks and read them: did the right passage even come back? If not, it's a retrieval problem — bad chunking, wrong embedding model, or a missing metadata filter. If the right chunk *did* come back and the answer's still wrong, now it's a generation problem, and my faithfulness score tells me whether the model ignored the context. The mistake juniors make is blaming the LLM first; nine times out of ten it's retrieval."

**Your proof:** the 5G pipeline is a full production RAG system — Qdrant pre-filtering, cosine, threshold + refusal path, source docs, LangChain RetrievalQA.

---

## 4. LLM Integration & Model Routing

**The mental model:** you don't integrate "an LLM," you integrate a *fleet* and route between them. Cheap/fast models for narrow well-defined tasks, expensive/deep models for ambiguous or high-stakes reasoning. Provider-agnostic where you can be, so one vendor's outage or price hike doesn't sink you.

**The routing philosophy (your senior signal):** "Model selection is a design decision, not a default." Your 5G router: `top_score > 0.92 AND score_gap > 0.15 AND severity != critical` → Haiku (fast, cheap); else → Sonnet (deep reasoning). ~60% cost cut, no accuracy loss on hard cases. In the keyword generator, Haiku *only* — entity extraction is narrow, doesn't need Sonnet's reasoning, runs 3–5× cheaper at ~500ms.

**Temperature is a correctness knob, not a vibe:** `temperature=0.1` (or 0) for operational tooling — same input must give same output. High temperature is *actively harmful* when an engineer running the same pcap twice must get the same fix. You raise temperature deliberately only when you *want* variance — e.g., your consistency checker re-runs at 0.7 to measure output stability.

**The reliability layer (this is where you shine):**
- **Structured output validation** — the model returns JSON; you validate with Pydantic *before* trusting it. Malformed output is a *when*, not an *if*.
- **Fallback chains** — LLM → regex → sane defaults. "The LLM path is an enhancement, not a dependency." That's how the keyword generator claimed 100% uptime.
- **Response parser hardening** — at Brane you hardened the parser for malformed LLM outputs and built a verifier-with-retry loop that feeds the error back for correction.
- **Rate limiting** — concurrent LLM calls hit provider limits fast; you cap in-flight calls with an `asyncio.Semaphore` (the bias auditor caps at 10; without it, a 500-call audit dies instantly).

*Q: "How do you handle the cost of LLMs at scale?"*
> "Three levers. Route to the cheapest model that reliably does each task — most of my traffic is well-defined enough for Haiku. Cache aggressively — identical inputs shouldn't pay twice; I cache frequent lookups in Redis. And for high-volume evaluation, swap in local models — my consistency checker uses an 80MB sentence-transformer instead of an API call when it's installed. Cost is an architecture problem, not a billing problem."

*Q: "How do you deal with hallucinations?"*
> "You can't make the model stop hallucinating — you build a system that catches it. Grounding via RAG so it answers from retrieved facts, faithfulness scoring to detect when it strayed from the context, structured-output validation, confidence thresholds with a refusal path, and human-in-the-loop on anything irreversible. I treat the model as an unreliable dependency and wrap it in the same discipline I'd wrap any flaky external service."

**Your proof:** 5G model routing, Brane multi-provider gRPC gateway (instruct/thinking/vision routing, stateless horizontal scaling), keyword-generator fallback chain.

---

## 5. Prompt Engineering

**The mental model:** a production prompt has *structure* — system persona (who the model is and its constraints), grounded context (retrieved facts, injected input), the tool registry (what it can call), the task, and the output contract (exact JSON schema). You're assembling a prompt, not writing a sentence.

**Senior techniques you can name and justify:**
- **Grounding / context injection** — put retrieved facts in the prompt so the model answers from them, not from memory. This is the anti-hallucination workhorse.
- **Few-shot examples** — show 2–3 input→output pairs when the task shape is unusual; the model pattern-matches.
- **Output contracts** — "return exactly this JSON" + Pydantic validation. Never parse prose you could have gotten as structured data.
- **Retry-with-feedback** — when output fails validation, feed the *specific error* back into the next prompt: "your JSON was missing field X, fix it." You built exactly this at Brane (the verifier correction loop).
- **Prompt caching** — put stable content (system prompt, persona) *first* so the provider can cache the prefix; variable content last. Cuts cost and latency on repeated calls.

**Prompt assembly for an agent (Brane, verbatim capability):** system prompt + grounded input injection + tool registry context + retry-with-feedback construction for the verifier loop. That sentence *is* senior prompt engineering — you assembled the full agent prompt, not a chat message.

*Q: "How do you make an LLM reliably return structured data?"*
> "Ask for JSON with an explicit schema, set temperature to zero, and — critically — validate the result with Pydantic instead of trusting it. When validation fails, I don't just retry blindly; I feed the validation error back into the prompt so the model corrects the specific mistake. And I always keep a deterministic fallback — a regex extractor — so a malformed response degrades gracefully instead of crashing."

**Your proof:** Brane prompt assembly + verifier retry loop; keyword generator temperature=0 JSON extraction with regex fallback.

---

## 6. LangChain / LangGraph

**The honest positioning:** you've used **LangChain RetrievalQA in production** (the 5G pipeline). You know **LangGraph** conceptually and can reason about it — be straight about the line between them.

**LangChain — what it actually gives you:** composable building blocks — chains (pipe steps together), retrievers (the RAG interface), memory, output parsers, and a tool-calling agent abstraction. The value is swappability: `RetrievalQA` lets you swap the LLM or the retriever in one line, and `return_source_documents=True` gives you citations for free. The critique you can voice (senior signal): "LangChain is great for getting a RAG pipeline standing fast, but its abstractions can get leaky at scale — sometimes you want to drop to raw API calls for control over exactly what enters the context window. I use it where it accelerates me and reach past it when I need precision."

**LangGraph — the concept, owned:**
> "LangGraph is LangChain's answer to stateful, cyclic agent orchestration. Instead of a linear chain, you model the agent as a graph — nodes are steps, edges are control flow, and it supports cycles, which is what you need for a real agent loop. The two features that matter: explicit shared state passed between nodes, and checkpointing — you can pause the graph, get a human decision, and resume. That checkpoint *is* human-in-the-loop built into the framework. My Celery task pipelines follow the same DAG thinking; LangGraph makes the loops and the HITL checkpoints first-class."

*Q: "Why LangGraph over a plain LangChain agent?"*
> "A plain LangChain agent is fine for a simple ReAct loop, but once you need branching logic, cycles, persistent state across steps, or a human approval gate mid-run, you want LangGraph's explicit graph — you can see and control the flow instead of hoping the agent's reasoning takes the right path. It's the difference between 'trust the model to orchestrate' and 'I orchestrate, the model reasons within nodes.'"

**Your proof:** LangChain RetrievalQA in the 5G pipeline with source documents.

---

## 7. Memory, Context Handling & Agent Lifecycle

**The mental model (your best one-liner):** "Agent memory is a data-access-pattern problem." Three kinds:
- **Working memory** — the current session/task state, changes fast → **Redis with TTL** (auto-expires if the agent crashes, so orphaned state doesn't pile up).
- **Episodic memory** — history of past runs, must survive restarts, read infrequently → **SQLite / PostgreSQL**.
- **Semantic memory** — knowledge that grows over time → **vector DB**.

You've built all three: NFTRACE's Redis (hot active sessions) + SQLite (cold completed history) is working + episodic memory; the 5G pipeline's `unknown_errors` Qdrant collection is semantic memory that *grows from the agent's own failures* — "the agent's failures literally become its training data."

**Context-window management (the constraint everyone hits):** the window is finite and every token costs money and dilutes attention. You prioritize what enters the prompt: system persona + top-k retrieved chunks (not the whole corpus — top-5 above threshold) + recent turns; summarize or evict old history; put stable content first for caching. "My RetrievalQA prompts already do this — five patterns above threshold, never the entire knowledge base."

**Agent lifecycle:** an agent run has states — created → running → waiting-on-human → completed/failed. You persist state per run (Brane's `agent_run_scratch`, `agent_episodes` tables), you make it restart-safe (Redis persists where an in-memory dict wouldn't), and you TTL orphaned sessions so a crashed agent doesn't hold resources forever.

*Q: "How do you manage context when a conversation gets too long?"*
> "You can't just keep appending — you'll blow the window and quality drops as it fills. I keep the system prompt and the top-k retrieved facts, keep the most recent turns verbatim, and summarize or drop older history. The skill is deciding what's load-bearing: stable instructions and freshly-retrieved facts stay; stale back-and-forth gets compressed. It's memory management, same as any system with a fixed cache."

**Your proof:** NFTRACE Redis+SQLite temperature split; Brane `agent_run_scratch`/`agent_episodes`; 5G growing `unknown_errors` semantic memory.

---

## 8. Human-in-the-Loop (HITL)

**The mental model:** HITL is not a fallback you bolt on — it's a *design decision about where the agent is allowed to be autonomous*. The senior question is "when should this agent NOT act on its own?" Answer: when confidence is low, when the action is irreversible, or when it's operating in a regulated/high-stakes domain.

**Three HITL patterns you've shipped:**
1. **Confidence-gated escalation** — 5G pipeline below 0.65 → "manual review required," logged for a human to curate. The human's correction becomes new training data.
2. **Review-before-commit** — keyword generator: an engineer reviews *every* generated keyword before it enters the test suite. "A wrong test that passes is worse than no test," so the human gate is by design, not afterthought.
3. **Verifier-with-retry** — Brane's correction loop: the system checks its own output and retries with feedback before ever surfacing to a human, so humans only see what automated verification couldn't fix.

*Q: "When should an agent be fully autonomous vs. human-supervised?"*
> "Map it on two axes: reversibility and confidence. High confidence + reversible action → let it run. Low confidence *or* irreversible action → human gate. My 5G pipeline auto-resolves the 70% it's confident about and escalates the rest, because applying a wrong fix to a live network is irreversible and dangerous. The goal isn't maximum autonomy — it's autonomy exactly where it's safe, and a human exactly where it isn't."

**Your proof:** 0.65 escalation, keyword-generator review gate, Brane verifier loop.

---

## 9. Python (Advanced) — Async & Concurrency

**The mental model:** pick the concurrency model that matches the bottleneck. **I/O-bound** (LLM calls, DB queries, network) → `asyncio` — one thread juggling many waits. **CPU-bound** (parsing, math) → `multiprocessing` — true parallelism across cores, because the GIL serializes threads. Threads are for I/O-bound work where you're stuck with sync libraries.

**Decisions you can defend:**
- **asyncio + Semaphore** for rate-limited concurrent LLM calls (bias auditor: `asyncio.gather` with a semaphore capping in-flight at 10).
- **multiprocessing.Pool** for parallel node ops in NFTRACE — because `xmlrpc.client` is synchronous, and traces on N nodes must start *simultaneously* or you miss the first messages. "asyncio would've meant adding an async XML-RPC dependency; multiprocessing used the standard library and the overhead is negligible for 5–10 nodes."
- **Celery + Redis** for durable background tasks — survives a server restart mid-job, unlike FastAPI's in-process BackgroundTasks. Non-negotiable for a CI/CD quality gate: a lost eval would silently pass a PR that should've been blocked.

*Q: "asyncio vs multiprocessing vs threading — when each?"*
> "It comes down to what you're waiting on. I/O-bound — LLM APIs, database, network — asyncio, because the work is mostly waiting and one event loop can juggle thousands of waits cheaply. CPU-bound — heavy parsing, numerical work — multiprocessing, because the GIL means threads won't actually run Python bytecode in parallel. Threading I reserve for I/O-bound work trapped behind a synchronous library. Most AI backend work is I/O-bound, so I default to async and reach for multiprocessing only when there's real CPU work or a sync dependency like XML-RPC."

**Your proof:** async semaphore (bias auditor), multiprocessing (NFTRACE), Celery (eval framework).

---

## 10. PostgreSQL — Indexing, Query Optimization, Schema for AI Workloads

**The mental model — indexes:** an index is a sorted lookup structure (a B-tree by default) that turns a full-table scan — O(n), read every row — into a logarithmic seek. The tradeoff you *always* mention unprompted: indexes speed reads but *slow writes* (every insert/update maintains the index) and cost storage. So you index the columns you filter and join on, not everything.

**The senior depth they're screening for:**
- **`EXPLAIN ANALYZE` is your first move.** "I don't guess why a query is slow — I read the plan. `EXPLAIN ANALYZE` tells me if it's doing a Seq Scan where it should do an Index Scan, where the time actually goes, and whether the planner's row estimates are off — which usually means stale statistics, fixed with `ANALYZE`."
- **Composite index column order matters** — a `(vendor, layer)` index serves queries filtering on `vendor` or `vendor AND layer`, but *not* `layer` alone. Order by selectivity and by your actual query patterns. This is the kind of detail that says "I've tuned real queries."
- **Index types beyond B-tree:** B-tree for equality/range; **GIN** for JSONB and full-text; **partial indexes** for "only the rows I query" (e.g., `WHERE status = 'active'`); and for AI workloads, **pgvector's HNSW/IVFFlat** for approximate nearest-neighbor over embeddings.
- **When an index does NOT help:** low-cardinality columns (a boolean — the planner will scan anyway), tables small enough that a seq scan is cheaper, or a query returning most of the table.

**Schema for AI workloads (your Brane work):** you designed agent identity tables, multi-agent **junction tables** for many-to-many agent↔LO relationships, **attribute-level RBAC** permission rows, and agent execution sibling tables (`lo_input_execution_agent`, `agent_run_scratch`, `agent_episodes`). Junction tables are the correct normalization for many-to-many; attribute-level RBAC means permissions down to individual attributes, not coarse roles — and because permission checks sit on a hot path, you *cached* them.

*Q: "A query got slow in production — walk me through fixing it."*
> "First, `EXPLAIN ANALYZE` — I want the actual plan, not a theory. Nine times out of ten it's a Seq Scan on a column that should be indexed, or a join without an index on the join key. I check whether an index exists and whether the planner is even using it — if the estimates look wrong I run `ANALYZE` to refresh statistics. If it's a filtered query I reach for a composite or partial index matching the exact predicate. Then I re-run `EXPLAIN ANALYZE` to confirm the plan changed and the time actually dropped — I verify the fix, I don't assume it. And I weigh the write cost, because every index I add taxes inserts."

*Q: "How do you handle many-to-many relationships?"* → junction/join table with foreign keys to both sides; index both FK columns. "That's exactly the multi-agent LO junction tables I built at Brane."

**Your proof:** Brane PSQL schema (junction tables, attribute-level RBAC with caching, execution tables); Redis caching of hot permission checks.

---

## 11. REST API Design, FastAPI & Microservices

**The mental model:** REST = resources (nouns) + HTTP verbs (GET read, POST create, PUT/PATCH update, DELETE), stateless requests, meaningful status codes. FastAPI's edge: async-native, Pydantic validation at the boundary (bad input rejected before it reaches your logic), and auto-generated OpenAPI docs.

**The pattern that matters for agents — long-running work:** an agent task takes 5–30s; you don't block the HTTP request. **Return a job ID immediately (202/201), process in the background (Celery), let the client poll or push results over WebSocket/SSE.** You built exactly this in the eval framework (POST returns 201 immediately, Celery runs the eval, dashboard polls) and the 5G scale answer.

**Microservices judgment (senior = knowing when NOT to):** "Microservices buy independent scaling and deployment at the cost of network latency, distributed-system complexity, and harder debugging. I split into services when parts have genuinely different scaling profiles — a stateless model gateway that scales horizontally separate from a stateful orchestrator — not because microservices are fashionable. NFTRACE stayed a well-structured monolith with clean internal boundaries because its deployment profile didn't justify the overhead."

**Your proof:** FastAPI across every project; Brane stateless gRPC model gateway (horizontal scaling); NFTRACE REST lifecycle API; job-ID + poll pattern in the eval framework.

---

## 12. Auth — OAuth2, JWT & API Security

**The mental model:** **authentication** = who are you; **authorization** = what are you allowed to do. **JWT** is a signed, self-contained token — the server verifies the signature and trusts the claims without a DB lookup (stateless, scales horizontally, but you can't easily revoke before expiry, so keep them short-lived + use refresh tokens). **OAuth2** is the delegation framework — "let this app act on my behalf without giving it my password" (authorization-code flow for users, client-credentials for service-to-service).

**Security practices you name:** validate every input at the boundary (Pydantic), least-privilege on resource access (you managed **IAM roles** at Abjayon), secrets never in code, HTTPS everywhere, rate limiting, and — the agent-specific one — **attribute-level RBAC** so an agent can only touch the attributes its role permits. That's your Brane work and it maps directly to the JD's healthcare/HIPAA "who can touch what data" concern.

*Q: "JWT vs session tokens?"*
> "Session tokens are stateful — the server stores the session and looks it up each request, so revocation is instant but it doesn't scale as cleanly across many servers. JWTs are stateless and self-contained — great for horizontal scaling and microservices since any instance can verify the signature, but you trade away easy revocation, so I keep them short-lived and pair them with refresh tokens. For a multi-service agent platform, JWT's statelessness usually wins."

**Your proof:** Abjayon IAM roles + secure resource access; Brane attribute-level RBAC.

---

## 13. AWS, Docker & Kubernetes

**Be honest about depth, strong on mapping.** Your hands-on AWS is AppSync/AppFlow/IAM (Abjayon). The JD wants EC2/Lambda/ECS/EKS/S3/RDS/API Gateway/CloudWatch. Don't claim ops depth you don't have — *map your architecture onto AWS confidently*:

> "I've worked with AWS AppSync, AppFlow, and IAM directly. For deploying the AI systems I've built, the mapping is clean: FastAPI services run on ECS or Lambda behind API Gateway, PostgreSQL is RDS, Redis is ElastiCache, object storage and pcap files land in S3, and CloudWatch handles logs and metrics. Lambda for spiky event-driven work, ECS/EKS for long-running services that need more control. I'd frame my AWS as strong on the architecture and the managed-service mapping, and I'd ramp fast on the ops depth."

**Docker (solid):** you containerize everything — reproducible environments, "works on my machine" solved. Multi-stage builds to keep images small; Qdrant and your services run in Docker; Docker Compose for local multi-service stacks (eval framework: API + worker + Redis + Postgres + dashboard). You even chose fpdf2 over WeasyPrint in the bias auditor *specifically* to avoid OS-level binary deps so the Docker image stays minimal — a real containerization-aware decision.

**Kubernetes (conceptual + exposure):** you validated K8s pod health and real-time cluster dashboards in the 5G core testing. "I understand the model — pods, deployments, services, horizontal pod autoscaling — and I've operated against K8s clusters in the telecom testbed. For AI workloads, EKS gives you autoscaling for bursty inference and clean rollout/rollback. I'd lean on that model; I'm stronger as a builder than a cluster operator and I'd close that gap on the job."

*Q: "How would you deploy and scale one of your AI services on AWS?"*
> "Containerize it, push to ECR, run it on ECS or EKS behind API Gateway with an Application Load Balancer. Stateless services scale horizontally — my Brane model gateway was built stateless exactly for this. Long-running agent tasks go on a Celery worker pool with the queue in ElastiCache Redis, so I return a job ID immediately and the work survives a deploy. RDS Postgres for relational and agent state, S3 for artifacts, CloudWatch for metrics and alarms, autoscaling on queue depth or CPU. The design principle is stateless-where-possible so scaling is just adding instances."

**Your proof:** Abjayon AppSync/AppFlow/IAM; Docker Compose (eval framework); fpdf2 image-size decision; K8s pod-health validation (5G testing); Brane stateless gateway.

---

## 14. MCP (Model Context Protocol)

**The mental model:** MCP is an open standard for exposing tools and data to an LLM through typed servers — think "USB-C for AI tools." Before MCP, every app wired tool-calling its own way; MCP standardizes the interface so any MCP-compatible model can discover and call any MCP server's tools. "It's the natural next step from the LangChain tool integrations I've done — same idea (give the model typed tools), standardized so it's portable across models and apps."

Say you use Claude/MCP tooling day-to-day (Claude Code is on your resume). Frame it as *tool-use standardization*. The JD lists it as "familiarity" — conceptual fluency plus a clean definition is exactly the bar.

*Q: "What problem does MCP solve?"*
> "Fragmentation. Everyone was building bespoke tool-calling glue between their app and the model. MCP gives a standard protocol — a tool exposes itself as an MCP server with typed inputs and outputs, and any MCP-aware model can use it without custom integration. It's the same instinct behind good API design: standardize the interface so components compose instead of coupling."

---

## 15. Agent Framework Landscape — CrewAI / AutoGen / OpenAI Agents SDK

**The JD names these — have a one-line opinion on each so you sound current, even if your production tool was LangChain.** The honest frame: "I've shipped agents on LangChain and reasoned in LangGraph terms. I've evaluated the others and can speak to where each fits — the concepts transfer directly, the SDK is a detail."

- **CrewAI** — role-based multi-agent orchestration. You define agents as *roles* (researcher, writer, reviewer) with goals and tools, and they collaborate on a task, sequentially or hierarchically. "It's opinionated toward the coordinator pattern — exactly the shape of my 4-evaluator eval framework, just with a framework wrapping the delegation."
- **AutoGen** (Microsoft) — conversation-driven multi-agent. Agents *talk to each other* in a chat loop to solve a problem, with a `UserProxyAgent` as the human/HITL hook and code-execution built in. "This is the closest thing to peer-to-peer A2A in the mainstream frameworks — agents negotiating via messages. The hard parts it exposes — turn-taking, termination conditions, who has authority — are the coordination problems I already solve."
- **OpenAI Agents SDK** — OpenAI's lightweight production framework: agents, handoffs (one agent passes control to another), guardrails, and tracing as first-class primitives. "The 'handoff' concept is A2A in miniature, and 'guardrails as a primitive' matches how I already build — validation and refusal paths aren't bolted on."
- **LangGraph** — covered in §6; the graph-based, stateful, checkpointable option, strongest for explicit control flow + HITL.

*Q: "Which agent framework would you pick?"*
> "Depends on the shape of the problem, not fashion. A linear RAG-plus-tools agent — LangChain, it's fastest to stand up. Complex branching with human checkpoints — LangGraph, because I want explicit control flow and resumable state. Role-specialized collaboration — CrewAI. Agents that genuinely need to converse and negotiate — AutoGen. And for all of them the reliability layer is *mine*, not the framework's — the refusal path, the output validation, the eval gate. Frameworks orchestrate; they don't make an agent trustworthy. That's the engineering."

**Your proof:** coordinator pattern in the eval framework, verifier/tool-registry work at Brane — the *patterns* these frameworks encode, built by hand.

---

## 16. The quieter must-haves — Git, Linux, JSON/XML

Don't over-prepare these, but don't fumble a softball:
- **Git/GitHub** — feature branches, PRs with review, meaningful commits; you authored code-review checklists adopted as team standard at Nokia (thread safety, Docker best practices → 25% code-quality improvement) and mentored 3 engineers to senior readiness. *That's a lead/mentor signal — use it if they ask about collaboration or reviewing others' work.*
- **Linux** — you work in it daily; comfortable with the shell, processes, permissions, Docker on Linux, deploying services. State it plainly, move on.
- **JSON/XML processing** — JSON is the lingua franca of every LLM and REST boundary you've built (Pydantic models validate it); XML-RPC was the node-communication layer in NFTRACE. "I handle both routinely — Pydantic for JSON validation at API boundaries, and I built a whole XML-RPC abstraction layer in NFTRACE."

---

## Rapid-fire definitions (30-second answers screeners love)

- **Agent vs workflow** — workflow = fixed sequence you designed; agent = decides next step at runtime from state.
- **ReAct** — Reason→Act→Observe loop; model alternates thinking and tool calls, each observation fed back.
- **Function/tool calling** — model returns structured `{name, args}`, your code executes, result fed back. Foundation of every agent framework.
- **RAG** — retrieve relevant chunks from a vector DB, inject as grounding, generate from context. Fresh/private/citable knowledge.
- **Faithfulness vs accuracy** — faithful = stayed inside retrieved context; accurate = actually true. You can be one without the other; the gap diagnoses retriever-fault vs model-fault.
- **Embedding** — text → a vector of numbers positioned so similar meaning sits nearby; enables semantic search.
- **Cosine similarity** — angle between vectors (concept), ignores magnitude (verbosity). Right metric for semantic match.
- **Vector DB** — stores embeddings, does fast approximate nearest-neighbor search; the good ones (Qdrant) filter on metadata before ranking.
- **pgvector** — vector search inside Postgres; embeddings next to relational data; removes a separate vector-DB service.
- **Context window** — the model's finite input budget; managing it = deciding what earns a place in the prompt.
- **Temperature** — randomness knob; 0 for deterministic tooling, higher when you *want* variance.
- **Guardrails** — input validation + output schema validation + confidence thresholds + a refusal path.
- **HITL** — human gate where confidence is low or the action is irreversible.
- **MCP** — open standard for exposing typed tools/data to LLMs; "USB-C for AI tools."
- **JWT** — signed self-contained token; stateless auth; short-lived + refresh tokens.
- **Idempotency** — same request twice = same effect once; matters for retries in agent/task systems.
