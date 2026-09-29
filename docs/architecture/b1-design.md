---
type: design
tags: [design, draft, b1]
---

# B1: the first working pipeline

> **Preliminary design, open to change.** B1 is the earliest form of the system. It has the same components as the full workflow, but every step is general except one: dispatch runs a single task-specific capsule, `count_spaces`. The task is deliberately trivial so that B1 proves the pipeline itself, from intake to delivery.

**What B1 is:**

- **One straight line.** Every node runs once, in a fixed order: no branching, no retries, no repair loops. The engine retries an `agent()` call when the backend raises, when a `timeout` option expires, or when the result fails the schema passed to `agent()`. So the CC backend never raises, sets no `timeout`, and returns an envelope that always matches that schema. The engine's retries then never fire.
- **The same components as the full workflow:** intake, intent compilation, requirement compilation, planner-binder, freeze, dispatch and delivery.
  - Planner-binder and freeze are **pass-throughs**: they make no choices. There is no library, no selector for binding and no planner. So there is also no admission gate: a person adds each capsule to a fixed capsule folder by hand (see [How capsules get into B1](#how-capsules-get-into-b1-by-hand)).
- **A capsule and a gate where work is done.**
  - A **capability capsule (CC)** makes one object and decides nothing. It is a model call with deterministic post-checks, or plain code for a pure task.
  - A **gate** is deterministic code. It checks that object and decides whether the run goes on.
- **A gate that does not pass stops the run.** The run ends with the failed gate named in the error. Where the person sees it is open (question 4).
- **An unclear request is not a failure.** If the accepted IntentIR has a blocking ambiguity, control code ends the run with a clarify message that quotes the question. The fault is the input's, not the system's.

**Only dispatch is task-specific.** To swap `count_spaces` for another capsule, you change the allowed-capsule list in the policy, the capsule folder and the step's checks. The stage code stays the same. The research stages (search, screening, hypothesis, POC, benchmark, report) come later as dispatch capsules; see [the M1 design](m1-design.md).

**What goes in and out is known; how each capsule works inside is not.** A capsule's job may grow. In the original workflow, intent compilation was several modules: normalise, compile, an independent fidelity review, then the acceptance gate. B1 starts it as one capsule and one gate, and the capsule's ports fix what goes in and out, so its inside can change later.

## The pipeline

```mermaid
flowchart TB
    H>"researcher: request text + one .txt or .md in the input folder"]:::ext --> IN["intake: record what came in"]:::ctrl
    IN -->|"RawIntent"| C1(["compile_intent"]):::cc
    C1 -->|"IntentIR"| G1{{"intent gate (decide_acceptance)"}}:::gate
    G1 -->|"accepted IntentIR"| C2(["compile_requirement"]):::cc
    C2 -->|"semantic contract"| G2{{"requirement gate (acceptance)"}}:::gate
    G2 -->|"accepted contract"| PB["planner-binder: pass-through"]:::thin
    PB -->|"plan: 1 step, bind, yields"| FR["freeze: writes the Bindings"]:::thin
    ST[("capsule folder: Declarations, added by hand")]:::rec -.->|"Declarations and hashes, by name"| FR
    FR ==>|"Binding: this node runs this capsule, pinned by hash"| DISPATCH
    subgraph DISPATCH["dispatch: the dynamic stage. Set at runtime by the plan. One capsule in B1"]
        C3(["count_spaces"]):::cc -->|"integer"| G3{{"dispatch gate (step gate)"}}:::gate
    end
    IN -.->|"document text, via bind"| C3
    G3 -->|"checked integer"| DL["delivery: format the answer"]:::ctrl
    G2 -.->|"contract, yields"| DL
    DL --> OUT>"researcher reads the answer"]:::ext
    G1 -.->|"pass, but a blocking ambiguity"| CL>"run ends: the question goes back"]:::ext
    G1 & G2 & G3 -.->|"fail or blocked"| STOP>"run ends: the error names the gate"]:::ext
    CODE[("capsule code: files kept by sha256")]:::code
    C1 & C2 & C3 -.->|"points to its code by hash"| CODE

    classDef cc fill:#F2A007,stroke:#8A4B00,stroke-width:3px,color:#1a1208,font-weight:bold
    classDef gate fill:#C9A8E0,stroke:#5B1F86,stroke-width:2.5px,stroke-dasharray:6 3,color:#1a1208,font-weight:bold
    classDef ctrl fill:#ffffff,stroke:#5B1F86,stroke-width:2.5px,color:#1a1208,font-weight:bold
    classDef thin fill:#FFFFFF,stroke:#B86E00,stroke-width:2px,stroke-dasharray:3 3,color:#555555,font-weight:bold
    classDef rec fill:#E6CFB6,stroke:#6E3F12,stroke-width:2px,color:#1a1208,font-weight:bold
    classDef ext fill:#ffffff,stroke:#3b3b3b,stroke-width:2px,color:#111111,font-weight:bold
    classDef tool fill:#CFE3F7,stroke:#1F5A96,stroke-width:2px,color:#1a1208,font-weight:bold
    classDef code fill:#FFF8E6,stroke:#8A4B00,stroke-width:1.5px,stroke-dasharray:2 2,color:#5a3a00
    style DISPATCH fill:#FFF4DC,stroke:#B86E00,stroke-width:3px
```

**Key** (as in the M1 map): amber stadium = a capability capsule. Purple dashed hexagon = a gate: deterministic code that decides. White box, purple border = control code. White box, dashed orange border = a pass-through that makes no choices. Brown = an object or the capsule folder. Pale dotted = the capsule code, kept by hash. Orange box = the dynamic dispatch stage. Thick arrow = binding. White flag = the researcher.

**Two kinds of stage.** Intake, intent compilation, requirement compilation, planner-binder, freeze and delivery are always in the pipeline. **Dispatch**, the boxed stage, is dynamic: which capsules run there, and in what order, is set at runtime by the plan. In B1 the plan is fixed at one step, so dispatch holds one capsule, `count_spaces`. A later planner changes what goes in the box, not the stages around it. Inside dispatch, every capsule is followed by its own gate.

**A capsule points to its code; a Binding makes it a node.** A capsule is its Declaration. It does not hold its code: it points to files kept elsewhere by their sha256. Freeze writes a Binding for each node, and the Binding is what makes "this node runs this capsule, at this exact hash". The runner re-hashes the code before every call.

The gates are drawn as separate nodes because they are separate modules. In the code they run inside the CC backend, right after the runner.

## Inside a capsule and its gate

```mermaid
flowchart LR
    IN["input object"]:::rec --> RN["runner: checks hashes and needs.when, then calls"]:::ctrl
    subgraph CAP["capability capsule: makes the object, decides nothing"]
        M["the work: a model call with the output schema, or plain code"]:::cc --> POST["post-checks: deterministic, only add issues"]:::cc
    end
    RN --> M
    POST --> OBJ["output object + Observation"]:::rec
    OBJ --> G{{"gate: Binding checks, then call checks"}}:::gate
    G -->|"pass"| NEXT["next node"]:::ctrl
    G -->|"fail or blocked"| STOP>"run ends"]:::ext

    classDef cc fill:#F2A007,stroke:#8A4B00,stroke-width:3px,color:#1a1208,font-weight:bold
    classDef gate fill:#C9A8E0,stroke:#5B1F86,stroke-width:2.5px,stroke-dasharray:6 3,color:#1a1208,font-weight:bold
    classDef ctrl fill:#ffffff,stroke:#5B1F86,stroke-width:2.5px,color:#1a1208,font-weight:bold
    classDef rec fill:#E6CFB6,stroke:#6E3F12,stroke-width:2px,color:#1a1208,font-weight:bold
    classDef ext fill:#ffffff,stroke:#3b3b3b,stroke-width:2px,color:#111111,font-weight:bold
```

- **The runner** checks the code against its hashes and the Declaration's preconditions (`needs.when`) before the call. The capsule does not.
- **The capsule** always returns an object that matches its output port. If the input is unclear, it says so inside the object (an ambiguity, an unknown) rather than failing. A failed post-check adds an entry to the output's `issues`; it never repairs and never stops the call. *(Proposed: INV-19 and `issues` are not yet checked.)*
- **The gate** runs the Binding's `checks`: the capsule's, the output type's and the step's, those that apply at `node`. Then it runs its fixed checks on the call (it ended ok, it stayed within budget). It folds them into `pass`, `fail` or `blocked`. Anything but `pass` stops the run. B1's gates are this deterministic tier only. The PRD's second tier, an LLM judge, comes after B1.

## How capsules get into B1: by hand

The full system has three loops, like three clocks running at different speeds:

- **The hot path** is the AI4Research pipeline: one request, intake to delivery. B1 builds this.
- **The RSI cold path** builds and improves capsules, away from any run.
- **The library cold path** admits capsules, keeps the library, and selects capsules for binding.

In the full system, the library is the middle where the three loops meet. **B1 has no middle.** There is no library, no admission gate, no selector and no planner. So nothing connects the loops: a person moves a finished capsule into B1 by hand. This is deliberate for the earliest form.

```mermaid
flowchart LR
    subgraph HOT["hot path: AI4Research pipeline. Built in B1"]
        RQ>"request"]:::ext --> PIPE["intake, intent, requirement, planner-binder and freeze, dispatch, delivery"]:::ctrl --> ANS>"answer"]:::ext
    end
    subgraph RSI["cold path: RSI. A separate tree"]
        BUILD["build a capsule from its Declaration"]:::agent --> DONE[("finished capsule: Declaration, code, tests, results")]:::rec
    end
    subgraph LIBP["cold path: library management. Not in B1"]
        ADM{{"admission gate"}}:::off --> LIB[("library")]:::off --> SEL["selector for binding"]:::off
    end
    DONE -.->|"a person reviews it and copies it in"| FOLDER[("capsule folder")]:::rec
    FOLDER -->|"read by freeze"| PIPE
    PIPE -.->|"Observations, kept for later"| RECS[("CC records")]:::rec
    classDef cc fill:#F2A007,stroke:#8A4B00,stroke-width:3px,color:#1a1208,font-weight:bold
    classDef gate fill:#C9A8E0,stroke:#5B1F86,stroke-width:2.5px,stroke-dasharray:6 3,color:#1a1208,font-weight:bold
    classDef ctrl fill:#ffffff,stroke:#5B1F86,stroke-width:2.5px,color:#1a1208,font-weight:bold
    classDef rec fill:#E6CFB6,stroke:#6E3F12,stroke-width:2px,color:#1a1208,font-weight:bold
    classDef ext fill:#ffffff,stroke:#3b3b3b,stroke-width:2px,color:#111111,font-weight:bold
    classDef agent fill:#CFE3F7,stroke:#1F5A96,stroke-width:2px,color:#1a1208,font-weight:bold
    classDef off fill:#F2F2F2,stroke:#A0A0A0,stroke-width:1.5px,stroke-dasharray:4 4,color:#8a8a8a
```

Grey dashed = not built in B1. Blue = an agent in the RSI tree.

### The RSI tree: from a Declaration to a capsule

This runs outside B1, in its own tree. One way it could work:

```mermaid
flowchart TB
    DEC[("Declaration: ports, checks, effects")]:::rec --> IMP["agent 1: writes the implementation"]:::agent
    DEC --> TW["agent 2: writes the tests. It never sees the implementation"]:::agent
    IMP --> CODE[("implementation")]:::rec
    TW --> TESTS[("test cases")]:::rec
    CODE --> RUNT["run the tests against the implementation: deterministic"]:::ctrl
    TESTS --> RUNT
    RUNT --> OK{{"good enough? every test and every declared check passes"}}:::gate
    OK -->|"no: the failures go back"| IMP
    OK -->|"yes"| CAP[("capsule: Declaration, code, tests, results")]:::rec
    OK -->|"after a set number of rounds"| PER>"a person looks at the tests and the code"]:::ext
    CAP --> HUM>"a person reviews it and adds it to B1 by hand"]:::ext
    classDef cc fill:#F2A007,stroke:#8A4B00,stroke-width:3px,color:#1a1208,font-weight:bold
    classDef gate fill:#C9A8E0,stroke:#5B1F86,stroke-width:2.5px,stroke-dasharray:6 3,color:#1a1208,font-weight:bold
    classDef ctrl fill:#ffffff,stroke:#5B1F86,stroke-width:2.5px,color:#1a1208,font-weight:bold
    classDef rec fill:#E6CFB6,stroke:#6E3F12,stroke-width:2px,color:#1a1208,font-weight:bold
    classDef ext fill:#ffffff,stroke:#3b3b3b,stroke-width:2px,color:#111111,font-weight:bold
    classDef agent fill:#CFE3F7,stroke:#1F5A96,stroke-width:2px,color:#1a1208,font-weight:bold
    classDef off fill:#F2F2F2,stroke:#A0A0A0,stroke-width:1.5px,stroke-dasharray:4 4,color:#8a8a8a
```

- **The Declaration comes first.** It fixes the ports, the checks and the effects, so both agents work to the same spec.
- **Two agents, kept apart.** One writes the code and one writes the tests. The test writer never sees the code, so the capsule is not its own judge.
- **The loop is deterministic.** Running the tests decides; no model judges the result. Failures go back to the implementer, and a set number of rounds stops the loop and hands it to a person. That person may find the tests themselves are wrong.
- **The output is what a Candidate will hold** (Declaration, files, tests), so the same capsule can later go through admission unchanged, once the library exists.

### What adding a capsule by hand means

- A person copies the capsule's Declaration, code and tests into the capsule folder, and runs its tests once.
- Freeze reads the Declaration and hashes from the folder by name, and pins them in the Binding. The runner still re-hashes the code before every call, so a file changed after it was added is refused.
- There is no Verdict, because nothing admits the capsule. The Binding schema requires one today; see question 1.
- **One policy file** holds the gates' fold, the time budget per call, the effect-class mappings, the registries and the allowed-capsule list.

## The nodes

| Node | Kind | In | Out | The gate passes when |
|---|---|---|---|---|
| intake | control code | the request text; one `.txt` or `.md` file from the workspace input directory | RawIntent (the request text), and the document as a `text` Artifact | (no gate: intake only records what came in) |
| `compile_intent` | CC, model | RawIntent | IntentIR: goals, outcomes, constraints, ambiguities, unknowns | the IR matches its schema; every goal, outcome, constraint and ambiguity has at least one source span, and each span is a non-empty range inside the RawIntent text (unknowns have no spans: nobody stated them) |
| `compile_requirement` | CC, model | accepted IntentIR; the allowed-capsule list from the policy | semantic contract: what is wanted (`count`: `integer`), what is given (`document`: `text`), the capsule allowed to produce it, and requirements, each with check ids and `source_refs` to IntentIR goals | the contract matches its schema; every IntentIR goal id appears in some requirement's `source_refs`; the capsule it names is on the list; the `want` and `given` types equal that capsule's output and input port types; every check id it names exists and applies at `node` or `both` |
| planner-binder | control code, pass-through | accepted contract | plan: one step naming the contract's capsule, with `bind: [{input: text, from: given.document}]` and `yields: [{want: count, from: step.count}]` | (no gate: it decides nothing) |
| freeze | control code, pass-through | plan | run contract (the Bindings): the capsule's `decl_hash` and `code_sha256` from the capsule folder, its checks, budget and policy | (no gate, but it refuses a capsule name that is not in the folder, or whose files do not match their hashes) |
| `count_spaces` | CC, pure code | the document text, through `bind` | integer: the number of U+0020 characters | the value is an integer, 0 or more and at most the text's length; it passes the checks the contract named |
| delivery | control code | the checked integer, found through the plan's `yields`; the contract | the answer shown to the researcher | (no gate) |

- **Control code fills the references.** After the requirement gate passes, control code sets each `given[].artifact_ref` from intake's Artifacts. The model names only `given[].name` and `type`.
- **Why `count_spaces` is a capsule.** It shows that a capsule need not use a model. It is pure code (`effect_class: pure`), with typed ports and a check, pinned and recorded like any other capsule.
- **Why intent and requirement compilation are general.** They turn any request into an IntentIR and a contract. Only the contract's content ("count the spaces in this document") is specific to the task.

## The CC runner: how capsules plug into jiuwenswarm

**The CC runner is system code, not a capsule.** It serves the capsules: it is the only way a capsule runs inside the jiuwenswarm codebase. It does not exist yet, and B1 needs it. Everything around it already exists.

It plugs in through one existing interface. agent-core's Swarmflow engine runs a script and hands every `agent()` call to a backend (`AgentBackend`). The CC runner is that backend. So the engine drives the pipeline, and the runner handles each capsule call.

**A run starts on the chat stream.** A new branch in the Codex chat adapter (`CodexSubscriptionAdapter`, in the agent server) starts a CC run when a `chat.send` request carries a CC-run flag. The existing stream already carries deltas, the final answer, history and interrupt. The run must live in the agent server: that process holds the only signed-in Codex child for the profile, behind a file lock.

```mermaid
flowchart LR
    subgraph JS["jiuwenswarm and agent-core: exists"]
        CXA[Codex chat adapter in the agent server: chat.send stream]:::js
        ENG[Swarmflow engine: run_workflow, one agent call per node]:::js
        CX[Codex subscription runtime: text turns]:::js
    end
    LN[CC-run branch and launcher: new]:::ctrl
    subgraph RUN["CC runner: new system code"]
        PIN[1. load the Binding, re-hash the code, check needs.when]:::ctrl
        CALL[2. call the capsule by its kind]:::ctrl
        REC[3. write the Artifact and the Observation]:::ctrl
        GT{{4. gate: run the checks, fold to pass, fail or blocked}}:::gate
    end
    STORE[(capsule folder)]:::rec
    CAP([capsule code]):::cc
    RECS[(CC records under the profile folder)]:::rec
    CXA -->|chat.send with the CC-run flag| LN
    LN -->|start a run| ENG
    LN -.->|answer as chat.final| CXA
    ENG -->|each agent call| PIN
    STORE --> PIN
    PIN --> CALL
    CALL -->|skill: one text turn, JSON parsed| CX
    CALL -->|tool: Python call| CAP
    CALL --> REC
    REC --> RECS
    REC --> GT
    GT -->|envelope: value and decision, always valid| ENG
    classDef js fill:#EEEEEE,stroke:#777777,stroke-width:2px,color:#1a1208,font-weight:bold
    classDef ctrl fill:#ffffff,stroke:#5B1F86,stroke-width:2.5px,color:#1a1208,font-weight:bold
    classDef gate fill:#C9A8E0,stroke:#5B1F86,stroke-width:2.5px,stroke-dasharray:6 3,color:#1a1208,font-weight:bold
    classDef cc fill:#F2A007,stroke:#8A4B00,stroke-width:3px,color:#1a1208,font-weight:bold
    classDef rec fill:#E6CFB6,stroke:#6E3F12,stroke-width:2px,color:#1a1208,font-weight:bold
```

**Key:** grey = jiuwenswarm or agent-core, already built. White with purple = new CC code: the launcher and the runner. Purple dashed = the gate. Amber = capsule code. Brown = stored objects.

**What the runner does on every call:**

1. **Pin.** It loads the node's Binding from the run contract and re-hashes the capsule's code against `code_sha256`. A mismatch refuses the call. It checks the capsule's preconditions (`needs.when`).
2. **Call.** It calls the capsule through the handler for its `kind` (below).
3. **Record.** It stores the output as an Artifact and writes an Observation: outcome, model, time.
4. **Gate.** It runs the gate, which checks the output against the capsule's port. It returns an envelope, such as `{value, decision, obs_id}`, to the engine. The schema `agent()` passes is this envelope, not the port, so the engine's schema check always passes. The backend never raises and no call sets `timeout`, so the engine never retries on its own. The time budget per call is the runner's to enforce. The script ends the run on anything but `pass`.

**One handler per kind.** What the runner can do for a capsule depends on the capsule's `kind` field. Each kind has its own handler, and a handler gives the runner the capabilities that kind needs. B1 builds two.

| `kind` | The handler gives the runner | M1 |
|---|---|---|
| `skill` | a model turn: the capsule's files plus its inputs as the prompt, its output schema stated in the prompt as the reply format, JSON parsed from the reply | checked; built in B1 |
| `tool` | a Python call to the pinned code, with typed inputs and outputs | checked; built in B1 |
| `prompt_section` | text inserted into another capsule's model turn | checked; not needed in B1 |
| `mcp`, `a2a` | a call to a remote MCP tool or A2A agent, pinned by endpoint and version | unchecked |
| `subagent`, `agent_template` | starting an agent for one task | unchecked |
| `composite` | running member capsules as `structure` and `wiring` say | unchecked |

A new kind means a new handler in the runner. The capsules, the gate and the pipeline stay the same.

**The modules to build.** Each is one issue, with fixed inputs and outputs (see [What architecture covers](architecture.md)):

| Module | In | Out |
|---|---|---|
| launcher | a `chat.send` request with the CC-run flag, through a new branch in `CodexSubscriptionAdapter` in the agent server | a Swarmflow run of the fixed script, with a fresh `run_id`, `journal_path` and `resume` set to the same path, and a progress sink; the answer as one `chat.final` |
| runner backend | one `agent()` call: node name, inputs | an envelope with the value and the gate's decision, always valid against the `agent()` schema |
| kind handlers: `skill`, `tool` | a pinned capsule and its inputs | its output, or a declared failure |
| capsule folder loader | a capsule name | its Declaration and code, checked by hash |
| model adapter | a prompt, with the output schema stated as text | JSON parsed from one Codex text turn on a fresh synthetic session id |
| progress sink | engine progress events and each gate's decision | `workflow.updated` chunks on the chat stream, built with jiuwenswarm's `WorkflowRunState` |
| gate | the output Artifact, the Observation, the Binding's checks | a Verification: `pass`, `fail` or `blocked` |
| record writer | Artifacts, Observations, Verifications | files under the profile folder |

## Through jiuwenswarm: the deep view

The runner diagram above shows what CC adds. This one shows the whole path a B1 run takes through jiuwenswarm's processes, from the chat box to the answer. A Codex-mode launch runs a web process, a gateway and an agent server, and the agent server starts one `codex app-server` child.

```mermaid
flowchart TB
    subgraph BR["browser"]
        UI["chat input: chat.send"]:::js
        VIEW["chat view: chat.final and workflow tree"]:::js
    end
    subgraph WEB["web process"]
        PX["/ws proxy tunnel"]:::js
    end
    subgraph GW["gateway process"]
        WCH["WebChannel"]:::js
        MH["MessageHandler: forward filter, E2A stream"]:::js
    end
    subgraph AS["agent server process"]
        AWS["AgentWebSocketServer: dispatch"]:::js
        REG["AdapterRegistry: unary"]:::js
        RT["AgentRuntime.stream: history"]:::js
        CXA["CodexSubscriptionAdapter: new CC-run branch"]:::ctrl
        LN["CC launcher: run_id, journal, sink"]:::ctrl
        ENG["run_workflow: agent per node"]:::js
        VAL["agent: cache, schema check, 3 attempts"]:::js
        BK["CC backend: pin, call by kind"]:::ctrl
        C1(["compile_intent"]):::cc
        C2(["compile_requirement"]):::cc
        C3(["count_spaces"]):::cc
        G1{{"intent gate"}}:::gate
        G2{{"requirement gate"}}:::gate
        G3{{"dispatch gate"}}:::gate
        MA["model adapter: JSON from text"]:::ctrl
        SVC["SubscriptionService.stream and AppServerTransport"]:::js
        RW["record writer"]:::ctrl
        SNK["progress sink: WorkflowRunState"]:::ctrl
    end
    subgraph CX["codex app-server child"]
        APP["thread/start, turn/start, deltas"]:::js
    end
    subgraph DISK["files under the profile folder"]
        INP[("input folder: the document")]:::rec
        CAPF[("capsule folder")]:::rec
        CCR[("cc/ records")]:::rec
        JRN[("journal and .wal")]:::rec
        BND[("subscription/bindings.json")]:::rec
        HIS[("session history.jsonl")]:::rec
    end

    UI -->|"chat.send"| PX --> WCH --> MH -->|"E2A stream"| AWS
    AWS --> RT --> CXA
    AWS -.->|"option A: cc.run.start"| REG -.-> LN
    CXA -->|"CC-run flag"| LN -->|"run_workflow"| ENG
    INP --> LN
    ENG --> JRN
    ENG --> VAL -->|"backend.run"| BK
    CAPF -->|"Binding, re-hash"| BK
    BK --> C1 & C2 & C3
    C1 & C2 -->|"prompt"| MA
    MA --> SVC <-->|"JSON-RPC over stdio"| APP
    SVC --> BND
    C1 --> G1
    C2 --> G2
    C3 --> G3
    G1 & G2 & G3 --> RW --> CCR
    G1 & G2 & G3 -->|"envelope: value and decision"| VAL
    ENG -->|"progress events"| SNK
    SNK -->|"workflow.updated chunks"| CXA
    LN -->|"answer as chat.final"| CXA
    RT --> HIS
    RT -->|"chunks back the same way: E2A, WebChannel, /ws"| VIEW

    classDef js fill:#EEEEEE,stroke:#777777,stroke-width:2px,color:#1a1208,font-weight:bold
    classDef ctrl fill:#ffffff,stroke:#5B1F86,stroke-width:2.5px,color:#1a1208,font-weight:bold
    classDef gate fill:#C9A8E0,stroke:#5B1F86,stroke-width:2.5px,stroke-dasharray:6 3,color:#1a1208,font-weight:bold
    classDef cc fill:#F2A007,stroke:#8A4B00,stroke-width:3px,color:#1a1208,font-weight:bold
    classDef rec fill:#E6CFB6,stroke:#6E3F12,stroke-width:2px,color:#1a1208,font-weight:bold
```

**Key:** grey = jiuwenswarm or agent-core, already built. White with purple = new CC code. Amber = a capsule. Purple dashed = a gate. Brown = files on disk. Dashed edge = option A, a separate adapter entry, not used in B1.

**The hops.** Paths: `J/` is `jiuwenswarm/jiuwenswarm/` at `6d8c89e12`, `FE/` is `J/channels/web/frontend/src/`, and `A/` is agent-core `openjiuwen/`. **[pin]** `A/` lines are from `e23806c1`, not the pin `9e339019`.

| Hop | Process | Code (file:line) | Exists or new |
|---|---|---|---|
| The chat sends `chat.send`; the payload always carries `enable_swarmflow` | browser | `FE/hooks/useWebSocket.ts:2033-2054` | exists |
| `/ws` tunnel; WebChannel parses the frame; the forward filter passes `chat.send` | web, gateway | `J/channels/web/app_web.py:648`; `J/gateway/channel_manager/web/web_connect.py:1560-1700`; `J/gateway/app_gateway.py:2159-2191` | exists |
| MessageHandler sends an E2A stream request to the agent server | gateway | `J/gateway/message_handler/message_handler.py:4740-4866`; `J/gateway/routing/agent_client.py:585-640` | exists |
| Dispatch, then `AgentRuntime.stream`, then the Codex chat adapter | agent server | `J/server/agent_ws_server.py:2320-2855, 4058-4120`; `J/server/runtime/agent_adapter/interface_codex.py:33-49` | exists |
| CC-run branch on a request flag; the launcher calls `run_workflow` with `journal_path`, `resume` and `progress_sink` | agent server | `interface_codex.py:33-49`; `A/agent_teams/workflow/engine/runner.py:294-396` **[pin]** | branch and launcher new; engine exists |
| `agent()`: resume signature, cache, `backend.run`, schema check, up to 3 attempts | agent server | `A/agent_teams/workflow/engine/primitives.py:540-735`; `journal.py:81` **[pin]** | exists |
| CC backend: pin, call by kind, record, gate | agent server | new `AgentBackend` subclass (`A/agent_teams/workflow/engine/backends/base.py:101-119`) | new |
| Model adapter to `SubscriptionService.stream` to the `codex app-server` child | agent server, codex child | `J/server/runtime/codex_subscription/service.py:131-208`; `transport.py:30-189` | adapter new; service exists |
| Progress sink builds `workflow.updated` from `WorkflowRunState` | agent server | `J/agents/harness/team/handlers/workflow_state.py`; `workflow_monitor_handler.py:323-331` | sink new; state builder exists |
| Chunks go back over E2A to `WebChannel.send`; the wrapper writes history | all | `agent_ws_server.py:4091-4130`; `web_connect.py:1150-1178`; `J/server/runtime/agent_adapter/interface.py:3801-3822` | exists |

**How to read it:**

- **Only the agent server holds CC code.** The browser, web proxy and gateway stay as they are. Option A would change them too: a `ReqMethod` value, the gateway's forward sets and a frontend caller.
- **The flag can be the one the chat already sends.** Every `chat.send` carries `enable_swarmflow`, and Codex mode ignores it today. A new `cc_run` flag works the same way.
- **`count_spaces` is a Python call.** It has no edge to the model adapter.
- **Intake, planner-binder, freeze and delivery are plain code** in the script or the launcher. They make no `agent()` calls, so they are not engine nodes.
- **The gates return to the engine's schema check.** The envelope always passes it; the gate has already checked the port.
- **Traces are not drawn.** They are off in Codex mode; see [Observability and traces](#observability-and-traces).

## Observability and traces

**What we imagine.** There are two layers, joined by ids:

- **CC records: the source of truth.** Every capsule call writes an Observation, every gate a Verification, and every value an Artifact. Each Binding is kept. Records are never sampled and never expire. They answer "what ran, on which exact code, with what result", and they are what RSI, the librarian and benchmarking read later.
- **Traces: for debugging.** The runner opens one OpenTelemetry span per capsule call, using agent-core's span conventions. The span carries our `run_id` as `openjiuwen.run.id`, plus `cc.obs_id`, `cc.decl_hash`, `cc.caller` and `cc.outcome`. The Observation keeps the span's `trace_id` and `span_id` (unchecked at M1). Spans can be sampled and can expire. They link to records; they never replace them.

```mermaid
flowchart LR
    RUN[CC runner: one capsule call]:::ctrl
    subgraph CCR["CC records: kept, never sampled"]
        OBS[(Observation)]:::rec
        VER[(Verification)]:::rec
        ART[(Artifact)]:::rec
    end
    subgraph JSO["jiuwenswarm and agent-core: exists"]
        SPAN[OpenTelemetry span: openjiuwen.run.id and cc attributes]:::js
        TS[(trace store: SQLite per session)]:::js
        PROG[run view: workflow.updated from WorkflowRunState]:::js
        JRN[(Swarmflow journal)]:::js
        LOG[(logs)]:::js
    end
    RUN --> OBS
    RUN --> VER
    RUN --> ART
    RUN -.->|when tracing is on| SPAN --> TS
    OBS -.->|trace_id, span_id| SPAN
    RUN -.->|node started, finished, gate decision| PROG
    RUN -.->|call_key| JRN
    RUN -.-> LOG
    classDef js fill:#EEEEEE,stroke:#777777,stroke-width:2px,color:#1a1208,font-weight:bold
    classDef ctrl fill:#ffffff,stroke:#5B1F86,stroke-width:2.5px,color:#1a1208,font-weight:bold
    classDef rec fill:#E6CFB6,stroke:#6E3F12,stroke-width:2px,color:#1a1208,font-weight:bold
```

**The connectors, and where they plug in:**

| Connector | jiuwenswarm or agent-core side | What the CC side sends | B1 |
|---|---|---|---|
| Records | files under the profile folder (`JIUWENSWARM_DATA_DIR`), beside jiuwenswarm's sessions and logs | Observations, Verifications, Artifacts, Bindings, keyed by `run_id` | needed |
| Traces | agent-core span conventions (`extensions/observability/semconv.py`, `openjiuwen.run.id`); jiuwenswarm's trace store keeps OTLP spans in SQLite per session (`jiuwenswarm/observability/store.py:388`) | one span per capsule call, with `cc.*` attributes | optional, and off in Codex mode. The trace sink starts only on the harness, team and `/compact` paths (`agents/harness/agent_observability.py:125`), and `trajectory_ui.enabled` is `false` in the packaged config. To use it, the runner must start observability, set `gen_ai.conversation.id` to the chat session on each span, and the profile config must turn on `trajectory_ui` |
| Run view | the engine's `progress_sink` (`engine/runner.py`); jiuwenswarm's `WorkflowRunState` (`agents/harness/team/handlers/workflow_state.py`) has no team dependency, and the browser merges `workflow.updated` into its workflow tree | the CC sink reuses `WorkflowRunState` and emits `workflow.updated`. The engine emits no gate event, so the sink adds each gate's decision | needed. Whether the tree renders outside team mode is open |
| Journal | the Swarmflow journal, set per run with `journal_path` and `resume` at the same path; the WAL defaults to `<journal>.wal`. The journal file is written only when the run completes, and the WAL holds progress before that | the engine writes it; each Observation keeps the engine's `call_key` in `ext` so the two join | needed, for replay and resume |
| Model usage | the Codex service reads no token usage today. The engine's budget counts tokens only, so its budget gates never trip | Observation `cost.time_s`; `cost.tokens` stays empty. The time budget is the runner's own; engine budgets stay unbounded | time only, in the runner |

## How B1 fits jiuwenswarm

| B1 piece | In jiuwenswarm or agent-core | Status |
|---|---|---|
| Run entry | a CC-run branch in `CodexSubscriptionAdapter` (`interface_codex.py:33-49`), in the agent server, on the existing `chat.send` stream. The flag can be `enable_swarmflow`, which the chat already sends and Codex mode ignores, or a new one. Only the agent server can hold the run: the signed-in Codex child is locked to one process per profile | new branch in an existing adapter |
| The pipeline | a Swarmflow script run by agent-core `run_workflow(path, backend=...)`, one `agent()` call per capsule, a fresh `run_id` per launch. Nothing in jiuwenswarm calls `run_workflow` today; Swarmflow there is team-only | the engine exists; nothing calls it this way yet |
| Capsule calls | CC's runner as the engine's `AgentBackend`. The engine's resume signature covers only the prompt, `label`, `phase`, `model` and the schema, not `options`. So the capsule name, its `decl_hash` and the input hashes go in the prompt or `label`; otherwise a run is never resumed. `compile_intent` and `compile_requirement` are one model turn each; `count_spaces` is a Python call | new backend on an existing interface |
| Gates | inside the CC backend, right after the runner writes the Observation. The gate checks the output against its port. The backend returns an envelope with the value and the decision, which always matches the schema passed to `agent()`, and never raises. The script raises when `agent()` returns `None` or the decision is not `pass` | new |
| The model | one model through the Codex subscription runtime, which is text-only. Each call is a text turn through `SubscriptionService.stream` on a fresh synthetic session id, such as `cc:<run_id>:<call hash>`. Each id stays in `subscription/bindings.json` for good, and every turn gets the chat's fixed developer instructions. The backend parses JSON from the reply. The text/JSON port with an `outputSchema`, proposed in AI4R-001, is the clean version | works now as text turns; the port is proposed |
| Budget | the engine's `budget` counts tokens only, and Codex reports none. The time budget per call is enforced by the runner, not by an engine `timeout` | runner only |
| The document | read by intake from the workspace input directory. Chat attachments are refused on this runtime (`interface_codex.py:41`) | new |
| Stopping | the script raises and the run ends with the gate named in the error. `human_session` needs a backend with sessions; only the team backend has one, and this runtime does not start it. There is also no reply path: the browser can show a Swarmflow question, but the Codex adapter refuses the answer (`interface_codex.py:67-70`) | B1 stops and shows the failure |
| Capsule folder and records | files beside jiuwenswarm's own logs, under the profile folder | new |

The file-level details are in [A possible first design](first-design.md).

## What B1 uses from the schemas

| Schema | Used in B1 for |
|---|---|
| [Declaration](schemas/declaration.md) | the three capsules' ports, preconditions, effect class and checks |
| [Check](schemas/checks.md) | the checks the gates run; the test cases the RSI tree writes |
| [Policy](schemas/policy.md) | the one policy file every Binding pins |
| [Port types](schemas/port-types.md) | `raw_intent`, `intent_ir` and `semantic_contract` as domain types, and `text` and `integer`, each with its checks |
| [Binding](schemas/binding.md) | freeze's pin of `count_spaces` (and of the two compile capsules at run start), with no Verdict |
| [Observation](schemas/observation.md) | one per capsule call: outcome, model, time |
| [Artifact](schemas/artifact.md) | each object a node makes, and the request and document |
| [Verification](schemas/verification-record.md) | each gate's `pass`, `fail` or `blocked` |

**Not used in B1:** Candidate, Verdict and Standing, because there is no library or admission, and Finding. The RSI tree's output already has a Candidate's shape, ready for when admission exists.

## Open

1. **A Binding without a Verdict.** The Binding schema requires `verdict_ref`, and B1 has no admission. Proposed schema change: `verdict_ref` may be empty when a person added the capsule by hand, and the Binding then records that (for example `pinned_by: human`). The runner's hash check still applies.
2. **Is one capsule enough for intent compilation?** The original had a separate fidelity review before its gate. If `compile_intent` alone cannot pass its gate reliably, add the review as a second capsule on the same line.
3. **IntentIR and the semantic contract.** Their earlier drafts are parked. B1 needs a first version of each, as port types.
4. **Failed gates.** B1 stops the run. The failure goes back on the same chat stream, as `chat.final` text or as a `chat.error` with a code. How the UI shows it is open.
5. **"Good enough" in the RSI tree.** Every test passing is the floor. Whether RSI also needs a judged quality bar, and who writes the tests' own checks, is for the RSI tree to decide.
6. **Known risk: one Codex child for every session.** A failed, timed-out or cancelled turn closes the shared transport (`service.py:197-208`), which kills the Codex child. That breaks the user's own chat turn too, and the reverse. So the model adapter never cancels a turn mid-stream, and a CC call can still fail because of a chat turn.
7. **The workflow tree outside team mode.** The browser's run panel is mounted in the non-team view and reads `workflow.updated`. Whether it renders a CC run has not been run.
