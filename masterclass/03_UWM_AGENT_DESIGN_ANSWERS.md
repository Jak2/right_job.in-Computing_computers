# 03 — Design & Lead: UWM Architecture + Autonomous Agent Build

> These two JD bullets are **design and leadership** questions, not "have you used X" questions:
> - *"Design and lead the development of AI Agents using the Universal Worker Model (UWM) architecture"*
> - *"Build fully autonomous and semi-autonomous agents capable of multi-step task planning, execution, and orchestration"*
>
> Everything in quotes below is written **to be spoken** — read it out loud, not as bullet points to translate in the room. Practice it until the sentences feel like yours, not like a script. The non-quoted lines are stage directions for you, not lines to say.

---

## Q1 — "How would you design and lead the development of AI Agents using UWM?"

**Say this. All of it, straight through, in your own cadence — pause where you naturally would when thinking out loud.**

> "UWM is your internal framework, so I won't pretend I know its exact internals — I'd rather be straight about that than bluff and get caught in round two. But 'design and lead the development of an agentic architecture' is a problem I can actually walk you through, because it's the same problem I worked on at Brane. And honestly, whatever UWM calls its pieces, I think every serious agent framework ends up needing the same handful of layers underneath. So let me just talk through how I'd design it, and then how I'd lead a team actually building it, and you can tell me where that maps onto what you've already got.

> "First layer is agent identity. Every agent needs an identity, a role, and a set of permissions, and that needs to live in a real relational schema — not a config file — because the moment someone asks 'which agents can touch patient records,' you need to be able to query that, not go searching through code. That's basically the RBAC schema I built at Brane, and in a healthcare or fintech context, which this JD names directly, that's not optional, that's day one.

> "Second, perception — how input gets in. Whether it's a structured API payload or something messy like a scanned document or a packet capture, I'd normalize it into one internal representation before anything downstream touches it. Otherwise your planner and every tool you write end up reimplementing 'what does this input actually mean,' each slightly differently, and that's where bugs hide.

> "Third is planning — turning a goal into steps. I'll go deep on this one separately because it's really its own question, but the short version: some of the plan you know in advance, some of it you don't, and the design has to handle both.

> "Fourth, execution — the tools the plan actually calls. I'd want every tool registered with a typed input, a typed output, and a declared risk level — is this reversible or not. That risk level is what later decides whether a step can run on its own or needs a human, so it has to be declared up front, not discovered at runtime.

> "Fifth, memory — and I think about this as three different things, not one box. Working memory for the current run, which is hot and can live in something like Redis. Episodic memory, the history of past runs, which needs to survive a restart, so that's more like Postgres. And semantic memory — knowledge that actually grows over time from the agent's own outcomes, which is where a vector store earns its keep.

> "Sixth, coordination — the moment you have more than one agent, you need a rule for what happens when they disagree. I'd rather design that rule on day one than discover it in production when two agents give conflicting answers and nobody knows which one wins.

> "Seventh, and this is the one I actually care most about — governance. Confidence thresholds and reversibility checks gate every single step. Anything below threshold, or anything irreversible, goes to a human, and whatever that human decides gets logged and fed back in. That's what makes 'autonomous' something you can actually sell into healthcare or insurance, instead of something compliance shuts down.

> "And eighth, observability. Every run gets logged and traced, and continuously scored — is it still faithful to what it retrieved, is it still consistent — so that if something starts drifting, you catch it in minutes, not from a user complaint three weeks later.

> "None of those eight are specific to UWM — I think they're just what any agent framework needs. So honestly, if I walked in on day one, my first move wouldn't be to guess at UWM's API. It'd be to map what UWM already has onto this model, and go find out which of these eight are already strong and which ones are thin — because that's usually where the actual pain is."

**Then, without a big pause, move into the leading half — this is the part most candidates skip entirely, so don't rush it:**

> "That's the design side. The 'lead' part of the question matters just as much, so let me say how I'd actually run a team building this.

> "First thing I'd do is get the contracts written and reviewed before anyone writes agent code against them — the tool interface and the agent identity schema, specifically, because every other engineer's work depends on those two things. That's basically what the PSQL schema was at Brane — get that frozen and agreed on first.

> "Second, I wouldn't try to make everything autonomous at once. I'd phase it — crawl, walk, run. Crawl means one agent, everything gated by a human, no exceptions. Walk means confidence thresholds start letting the routine, low-risk steps run on their own while the edge cases still escalate — which, honestly, is exactly where my 5G pipeline already lives, seventy percent auto-resolved, the rest escalated. Run means you only expand autonomy once the evaluation layer has enough real data to prove a given step type is actually safe to trust. Autonomy gets earned per step type, not switched on for the whole system at once.

> "Third, I'd build the evaluation and observability layer before I let the agent count grow. Adding more agents before you can measure how often they fail is how teams end up debugging blind in production — that's basically my LLM Eval Framework, just generalized to score any agent's output before it ships.

> "And fourth — the part that's maybe less obvious but matters just as much — I'd set an actual written standard for what a good agent looks like, and mentor people against it, not just review pull requests reactively. At Nokia I wrote the code review checklist that became the team standard — thread safety, Docker practices — and that alone was a twenty-five percent bump in code quality scores, and I mentored three engineers to senior level through that same review process. I'd do the same thing here: a written definition of what a 'good agent' is — idempotent tools, typed inputs and outputs, an explicit path for saying 'I don't know' — enforced through review, not left as tribal knowledge that only I have in my head."

**Your proof, if you need to remind yourself where each line comes from:** Brane (agent identity/RBAC schema, gRPC gateway, verifier loop) · 5G pipeline (the walk-phase autonomy dial, live) · LLM Eval Framework (the observability layer, live) · Nokia (the review-standard and mentoring precedent).

### If they push deeper: "What would the agent identity schema actually look like?"

> "Relationally, I'd have an agents table — id, role, model tier — and a junction table for the many-to-many between agents and workflows, because in practice one agent usually serves more than one workflow and vice versa. And I'd want permissions at the attribute level, not just a coarse role flag, because 'can read patient demographics' and 'can write prescription data' really need to be grantable independently. That's the exact shape of the RBAC schema I built at Brane, and because permission checks sit right on the hot path of every tool call, I cached them rather than hitting Postgres on every single invocation."

---

## Q2 — "How would you build fully autonomous and semi-autonomous agents capable of multi-step task planning, execution, and orchestration?"

**Open with this line — it's the one sentence that signals you actually think about this seriously, so don't bury it:**

> "The way I'd frame it first is that autonomous and semi-autonomous aren't really two different systems — they're the same agent runtime with a dial turned to different settings. And the dial is per step, not per agent. A step that's low-risk and the agent is confident about — it just runs. A step that's irreversible, or the agent isn't sure — that one escalates. Designing for that spectrum, instead of building two separate codepaths, is really the whole decision."

**Then keep going, straight through, into planning:**

> "So how does a goal actually become steps — that's the planner's job, decomposing a goal into an ordered, or sometimes partially ordered, set of steps. And there's really two ways to represent that, and honestly I'd use both, deliberately, for different parts of the same task.

> "For the parts of the task where I already know the shape — a known workflow type, like 'process an intake form' or 'diagnose a 5G signaling error' — I'd use a static plan, basically a DAG. It's deterministic, it's auditable, it's cheap to run, and it's easy to explain to a compliance reviewer if they ask 'what exactly did the agent do.'

> "But for the parts where the next step genuinely depends on what the last step just observed — you don't know in advance whether a retrieved pattern is actually going to match — that's where I'd let the plan branch dynamically, more of a reason-act-observe loop.

> "And honestly the hybrid is the real answer here, not picking one. My 5G pipeline is exactly this shape — a deterministic skeleton, extract, then retrieve, then reason, then decide, with exactly one dynamic decision point in the middle, the confidence gate, which determines whether the next step is 'return the fix' or 're-plan this as an escalation.' Pure dynamic planning everywhere gets expensive and hard to audit. Pure static plans can't handle the genuinely unpredictable parts. So you use dynamic planning exactly where judgment actually adds value, and you lock everything else down."

**Then execution:**

> "On execution — every tool the plan can call, I'd register with a typed input schema, a typed output schema, and a declared risk level, reversible or not. That's basically the same idea MCP standardizes at the protocol level, just applied to my own tool registry. The executor calls the tool, validates what comes back against the schema before trusting it — because a malformed tool response is a when, not an if — and feeds that result back to the planner as its next observation.

> "And when something fails, I don't think the right move is a blind retry. A failure should become new context that goes back into the planner — 'the AMF didn't respond the way we expected, try the fallback endpoint' — rather than mechanically hammering the same failed call again. That's basically the verifier-with-retry loop I built at Brane — a failure gets fed back into the reasoning, not just repeated."

**Then orchestration:**

> "For orchestration — every agent run, I'd model as a state machine that's actually persisted to a database, not just held in memory: created, planning, executing, waiting on a human, completed or failed. And I'd persist it per step, not just per run, so if the process crashes, it resumes from the last completed step instead of starting the whole plan over. That's the same shape as the agent run and episode tables I worked on at Brane.

> "That step-level checkpointing matters more than it sounds like it should — say you've got a twelve-step plan, and step seven needs a human and that human doesn't respond for twenty minutes. You don't want to hold a connection open, and you definitely don't want to re-run steps one through six when they finally do respond. It just resumes at step seven.

> "And the autonomy dial itself — I'd enforce that at the orchestrator level, not inside each tool. The tool itself shouldn't be deciding whether it's allowed to run unsupervised. The orchestrator checks the step's risk level and the plan's current confidence before it ever calls the tool. That way governance lives in one place, instead of being scattered as ad hoc logic across every single tool you write."

**If they ask for a concrete example, walk through this:**

> "Take a healthcare intake form, since that's a domain this JD calls out directly. Step one, perceive — classify what kind of document this even is. Step two, extract — pull structured fields, name, date of birth, policy number. Step three, validate — check those fields against policy rules, is this a plan we recognize, is the date of birth even a valid format. If every field comes back high-confidence, step four just auto-files the intake — that's reversible, it's low-risk, it doesn't need a human standing over it. But if something's ambiguous — say the policy number's illegible — the plan doesn't guess. It re-routes: flags that specific field, escalates to a human with the document and the ambiguous part highlighted, and waits. Whatever the human decides gets logged, and if that exact kind of ambiguity keeps showing up, that's a signal to go fix the extraction step itself, not just patch it one document at a time. Autonomous where it's safe, supervised exactly where it isn't — same principle as the whole design."

### Rapid-fire — say these as direct, short answers if asked

> **"How do you keep a multi-step agent from doing something wrong across five steps before anyone notices?"**
> "I validate at every step boundary, not just at the end. Each step's output gets schema-checked before it's allowed to become the next step's input, so a bad step two gets caught right there — it never gets the chance to cascade into three, four, and five."

> **"What's actually the difference between orchestration and a plain workflow engine?"**
> "A workflow engine runs a plan you already wrote. An orchestrator can also replan — when a step observes something that contradicts what the plan assumed, it goes back to the planner with that new information, instead of just grinding forward on a plan that doesn't fit reality anymore."

> **"How would you know a multi-step agent is actually ready for full autonomy?"**
> "Same AND-gate discipline as my eval framework — I wouldn't graduate a step type to autonomous until faithfulness, consistency, and the human-override rate are all above threshold, independently, across a real sample size. Not an average of the three. Every one of them has to clear the bar on its own."

**Your proof, if you need to remind yourself where each line comes from:** 5G pipeline (the hybrid static/dynamic plan, live, the 70 and 55 percent numbers) · Brane (agent run and episode state persistence, the verifier-retry replanning) · LLM Eval Framework (the graduation-to-autonomy gate) · NFTRACE (step-level lifecycle, session-scoped state, crash-safe via TTL).

---

## If time is short and they only let you answer once — say this

> "I'd design it as one runtime with an autonomy dial, not two separate systems. Every agent run is a planned, persisted state machine — part deterministic skeleton for the parts of the task I already understand, part dynamic replanning for the parts that genuinely depend on what just happened. Every step gets schema-validated and risk-classified, so the low-risk, reversible stuff just runs, and anything irreversible or low-confidence goes to a human, whose correction feeds straight back into the system. And I'd lead the build the same way I've led review standards before — get a written contract for what a 'good agent' looks like frozen early, enforce it through review, and get the evaluation layer built before we ever scale up how many agents are running, not after."
