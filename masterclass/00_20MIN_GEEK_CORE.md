# 00 — The 20-Minute Geek Core

> Read this out loud the morning of the interview. Nothing else if you're short on time.
> This is what an AI engineer who *loves the craft* carries in their head — not memorized lines,
> but a way of thinking that leaks into every answer and makes the interviewer think
> *"this person actually builds these things."*

---

## The one belief that runs through every answer

**An LLM is a brilliant, unreliable component. My job is not to trust it — my job is to build a system around it that stays correct even when the model is wrong.**

Say this in your own words when they ask anything open-ended. Every design decision you made — the 0.65 threshold, the AND-gate, the regex fallback, the blind judge, the verifier-retry loop — is the *same idea* pointed at a different failure. That single belief is your senior signal. A junior asks "what can the model do?" A senior asks "what happens when it fails, and who gets hurt?"

When you frame it this way, you're not an engineer who *uses* AI. You're an engineer who makes AI *safe to put in front of a paying customer*. That's the whole job.

---

## The 6 ideas that make you sound like a builder, not a reader

**1. Retrieval is a filtering problem before it's a similarity problem.**
Everyone knows RAG = embed + search. The insight that separates you: *you filter at the database level before you ever compute similarity.* In your 5G pipeline a Nokia error must never pull an Ericsson fix — wrong CLI syntax could make a live outage worse. Qdrant's `must` filter runs *before* ranking. FAISS can't do that; you'd search the whole corpus and throw away the wrong-vendor matches afterward — slower and lower quality. **Metadata pre-filter > post-filter.** This one sentence makes you sound like you've run RAG at scale.

**2. Faithfulness ≠ accuracy.** This is the geek flex that wins RAG conversations. Accuracy asks "is the answer true?" Faithfulness asks "did the model stay inside the documents I retrieved?" You can be 100% faithful and 100% wrong — that means your *retriever* fed bad docs. You can be accurate but unfaithful — the model ignored retrieval and used its own memory, which will bite you the moment the topic drifts. **High faithfulness + wrong answer = retriever's fault. Low faithfulness = model ignored the retriever.** Different failure, different fix. You built a scorer that separates these. Almost no candidate can articulate this cleanly.

**3. Quality gates use AND logic, never a weighted average.** A response that's 95% faithful but hallucinates one claim must *fail*. An average would let it through — because the average hides exactly the one number that hurts a user. Your eval framework fails a test case if *any single* evaluator drops below threshold. "It's a quality gate, not a quality summary." This is a mindset, not a trick — apply it to guardrails, CI checks, agent verifiers, everything.

**4. The right answer is usually "the cheapest model that reliably does the task."** Model selection is a *design decision, not a default.* Haiku for narrow, well-defined extraction; Sonnet for ambiguous reasoning. In your 5G pipeline you route: high-similarity + non-critical → Haiku; ambiguous or critical → Sonnet. ~60% cost cut, zero accuracy loss on the hard cases. Saying "I'd just use GPT-4 for everything" is a junior tell. Routing is the senior move.

**5. Every agent needs a refusal path.** The hardest part of shipping agents isn't making them act — it's making them *not* act when they shouldn't. Below 0.65 similarity your pipeline says "unknown — human review" instead of inventing advice. "An agent without an 'I don't know' path is a liability, not automation." When they ask "what's hard about production agents?", *this* is your answer.

**6. Memory is a data-access-pattern problem, not a magic feature.** Agent memory splits three ways: **working memory** (hot, changes fast → Redis with TTL), **episodic history** (cold, must survive restarts → SQLite/Postgres), **semantic memory** (knowledge that grows → vector DB). You've built all three: NFTRACE's Redis+SQLite split *is* working memory + episodic history, and the `unknown_errors` Qdrant collection *is* semantic memory that grows from the agent's own failures. Right store per access pattern.

---

## The agent loop — draw it in your head, describe it in one breath

Every agent, including their "UWM", is a loop:

**Perceive → Retrieve → Reason → Act → Observe → (escalate to human if unsure) → repeat.**

Your 5G pipeline maps onto it exactly: Pyshark perceives the error from the packet capture, Qdrant retrieves known patterns, Claude reasons a fix, the system acts (returns/applies the suggestion), and below-threshold confidence escalates to a human. **That IS an agent** — you don't need to have used their framework to have built the pattern. Lead with this whenever "agent" comes up.

The academic name for the tight version is **ReAct**: Reason → Act → Observe, looping, with the model alternating between thinking and calling tools, feeding each observation back into context. LangChain agents, tool-use loops, and most agent frameworks are ReAct underneath. Function/tool calling is the mechanism: the model returns a structured `{name, args}` instead of prose, your code runs it, you feed the result back. **MCP** standardizes how those tools are exposed to the model. That's the whole stack in four sentences.

---

## The UWM move (their framework — nobody outside knows it)

Don't pretend. Do this:

> "I haven't worked with UWM by name — it's your internal framework. But everything it's built for, I've built: the agent loop, a tool registry, a verifier-with-retry correction loop, execution episodes persisted per run. At Brane I worked on exactly that runtime. So rather than guess — how does UWM handle agent state and the human-in-the-loop checkpoints? I'd love to map what I built onto how you've structured it."

Asking one sharp question there scores higher than bluffing. It signals you think in *patterns*, not tool names — which is the actual senior skill.

---

## Your five numbers (say them slow, then stop talking)

- **70%** of routine 5G errors auto-resolved, no human needed
- **55%** MTTR reduction (Mean Time To Repair)
- **50%** pipeline validation time cut (NFTRACE)
- **14-point** faithfulness drop caught in **4 minutes** vs 2–3 days manual (Eval Framework)
- **60%** LLM API cost cut from Haiku/Sonnet routing

Never rush past your own metric. Say the number, pause one beat, let it land. "It was only about 70%" shrinks you — drop "only," drop "just," drop "kind of." Quiet confidence reads as senior; enthusiasm yes, theatrics no.

---

## The 60-second opener (they open with "tell me about yourself")

> "I'm a Python engineer who builds production AI agent systems. My most recent work is a pipeline that autonomously diagnoses 5G network failures — it perceives errors from packet captures, retrieves known patterns from a vector database, reasons with Claude to synthesize a fix, and escalates to a human when confidence is low. It auto-resolves about 70% of routine incidents. Around that I've built the systems agents need in production — an LLM evaluation framework that catches model regressions in minutes instead of days, and a bias auditor that generates regulatory compliance documentation automatically. Under all of it is five years of backend engineering — FastAPI, PostgreSQL, Celery, Redis — which is what makes the agents reliable enough for enterprise use. Agent architecture on a production-grade backend — that's exactly how this role reads, which is why I'm here."

Lead with agents, close with backend as the credibility layer. 55–65 seconds spoken. Practice it 5 times out loud before you join.

---

## Two questions you ask them (asking well = senior signal)

1. "How does UWM handle agent state and HITL checkpoints — is escalation built into the framework, or per-application?"
2. "How do you evaluate agent quality before release — golden suites, canary testing against a new model version?" *(then connect to your eval framework)*

---

## In the room — the delivery rules

- **Open with the story arc** (Hook → the enemy → what you built → the one clever decision → the number). Then *stop* and let them pull you deeper.
- **Every technical answer ends with a user or a number.** "Because otherwise the engineer at 3 AM gets hallucinated advice" beats any diagram.
- **Signpost:** "There were really two key decisions here…" tells them the shape so they can follow.
- **One analogy per project, max.** Semantic search = "a librarian who finds the right book even when you misremember the title." Don't overdo it.
- **Never claim more than you did**, especially Brane (2 months). Tell *your part* vividly and honestly. Getting caught inflating destroys every ounce of credibility the story built.
- **Calm beats loud.** You know this material. Act like it.
