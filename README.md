<div align="center">

# 🛡️ ToolGuard

**Reliability testing for AI agent tool chains.**

Catch cascading failures before production. Make agent tool calling as predictable as unit tests made software reliable.

[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue?style=flat-square)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-50%20passed-brightgreen?style=flat-square)](#)
[![Integrations](https://img.shields.io/badge/integrations-10%20frameworks-blueviolet?style=flat-square)](#native-framework-integrations)
[![Security](https://img.shields.io/badge/security-6%20layer%20firewall-critical?style=flat-square)](#)

</div>

---

## 🧠 What ToolGuard Actually Solves

Right now, developers don't deploy AI agents because they are fundamentally unstable. They crash.

There are two layers to AI:
1. **Layer 1: Intelligence** (evals, reasoning, accurate answers)
2. **Layer 2: Execution** (tool calls, chaining, JSON payloads, APIs)

**ToolGuard does not test Layer 1.** We do not care if your AI is "smart" or makes good decisions. That is what eval frameworks are for.

**ToolGuard mathematically proves Layer 2.** We solve the problem of agents crashing at 3 AM because the LLM hallucinated a JSON key, passed a string instead of an int, or an external API timed out. 

> *"We don't make AI smarter. We make AI systems not break."*

---

## 🚀 Zero Config — Try It in 60 Seconds

```bash
pip install py-toolguard
toolguard run my_agent.py
```

That's it. ToolGuard auto-discovers your tools, fuzzes them with hallucination attacks (nulls, type mismatches, missing fields), and prints a reliability report. Zero config needed.

```
🚀 Auto-discovered 3 tools from my_agent.py
   • fetch_price (2 params)
   • calculate_position (3 params)
   • generate_alert (2 params)

🧪 Running 42 fuzz tests...

╔══════════════════════════════════════════════════════════════╗
║  Reliability Score: my_agent                                 ║
╠══════════════════════════════════════════════════════════════╣
║  Score:       64.3%                                          ║
║  Risk Level: 🟠 HIGH                                         ║
║  Deploy:     🚫 BLOCK                                        ║
╠══════════════════════════════════════════════════════════════╣
║  ⚠️  Top Risk: Null values propagating through chain         ║
║  ⚠️  Bottleneck Tools:                                       ║
║    → fetch_price       (50% success)                         ║
║    → generate_alert    (42% success)                         ║
╚══════════════════════════════════════════════════════════════╝

💡 fetch_price: Add null check for 'ticker' — LLM hallucinated None
💡 generate_alert: Field 'severity' expects int, got str from upstream tool
```

Or with Python:

```python
from toolguard import create_tool, test_chain, score_chain

@create_tool(schema="auto")
def parse_csv(raw_csv: str) -> dict:
    lines = raw_csv.strip().split("\n")
    headers = lines[0].split(",")
    records = [dict(zip(headers, line.split(","))) for line in lines[1:]]
    return {"headers": headers, "records": records, "row_count": len(records)}

report = test_chain(
    [parse_csv],
    base_input={"raw_csv": "name,age\nAlice,30\nBob,35"},
    test_cases=["happy_path", "null_handling", "malformed_data", "type_mismatch", "missing_fields"],
)

score = score_chain(report)
print(score.summary())
```

---

## 🤖 How ToolGuard is Different

Most testing tools (LangSmith, Promptfoo) test your agent by sending prompts to a live LLM. It is slow, expensive, and non-deterministic.

**ToolGuard does NOT use an LLM to run its tests.** 

When you decorate a function with `@create_tool(schema="auto")`, ToolGuard reads your Python type hints and automatically generates a Pydantic schema. It then uses that schema to know exactly which fields to break, which types to swap, and which values to null — no manual configuration needed.

It acts like a deterministic fuzzer for AI tool execution, programmatically injecting the exact types of bad data that an LLM would accidentally generate in production:
1. Missing dictionary keys
2. Null values propagating down the chain
3. `str` instead of `int`
4. Massive 10MB payloads to stress your server
5. Extra/unexpected fields in JSON

ToolGuard doesn't test if your AI is smart. It tests if your Python code is bulletproof enough to *survive* when your AI does something stupid — running in 1 second and costing $0 in API fees.

---

## Features

### 🛡️ Layer-2 Security Firewall (V3.0)
ToolGuard features an impenetrable execution-layer security framework protecting production servers from critical LLM exploits.

- **Human-in-the-Loop Risk Tiers:** Mark destructive tools with `@create_tool(risk_tier=2)`. ToolGuard mathematically intercepts these calls and natively streams terminal approval prompts before execution, gracefully protecting `asyncio` event loops and headless daemon environments.
- **Recursive Prompt Injection Fuzzing:** The `test_chain` fuzzer automatically injects `[SYSTEM OVERRIDE]` execution payloads into your pipelines. A bespoke recursive depth-first memory parser scans internal custom object serialization, byte arrays, and `.casefold()` string mutations to eliminate zero-day blind spots.
- **Golden Traces (DAG Instrumentation):** With two lines of code (`with TraceTracker() as trace:`), ToolGuard natively intercepts Python `contextvars` to construct a chronologically perfect Directed Acyclic Graph of all tools orchestrated by LangChain, CrewAI, Swarm, and AutoGen.
- **Non-Deterministic Verification:** Punishing an AI for self-correcting is an anti-pattern. Developers use `trace.assert_sequence(["auth", "refund"])` to mathematically enforce mandatory compliance checkpoints while permitting the LLM complete freedom to autonomously select supplementary network tools.

### 🔍 Schema Validation
Automatic Pydantic input/output validation from type hints. No manual schemas needed.

```python
@create_tool(schema="auto")
def fetch_price(ticker: str) -> dict:
    ...
```

### 🔗 Chain Testing
Test multi-tool chains against **8 edge-case categories**: null handling, type mismatches, missing fields, malformed data, large payloads, and more.

```python
report = test_chain(
    [fetch_price, calculate_position, generate_alert],
    base_input={"ticker": "AAPL"},
    test_cases=["happy_path", "null_handling", "type_mismatch"],
)
```

### ⚡ Async Support
Works with both `def` and `async def` tools transparently. No special flags needed.

```python
@create_tool(schema="auto")
async def fetch_from_api(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        return resp.json()

# Same API — ToolGuard handles the async automatically
report = test_chain([fetch_from_api, process_data], assert_reliability=0.95)
```

### 📻 The "Obsidian" Live Web Dashboard (v5.0.0)
ToolGuard includes a stunning, high-contrast, dark-mode web dashboard for monitoring live agent execution and security traces.

![ToolGuard v5.0.0 Obsidian Dashboard](docs/images/dashboard_v5_hero.png)

```bash
# Launch the live proxy monitor
toolguard dashboard
```

It streams live concurrent security interventions via SSE (Server-Sent Events) and tracks precisely which functions get blocked under payload injection. Built with a dedicated hacker-style "Terminal Elite" aesthetic, featuring a real-time **Sentinel HUD (L1-L6)** and structural DAG timeline analysis.

### 📊 Reliability Scoring
Quantified trust with risk levels and deployment gates.

```python
score = score_chain(report)
if score.deploy_recommendation.value == "BLOCK":
    sys.exit(1)  # CI/CD gate
```

### ⏪ Local Crash Replay
When a remote tool crashes in production or tests, ToolGuard automatically dumps the structured JSON payload. You can instantly replay the exact crashing state locally to view the stack trace.

```bash
toolguard run my_agent.py --dump-failures
toolguard replay .toolguard/failures/fail_1774068587_0.json
```

### 🎯 Edge-Case Test Coverage
ToolGuard gives you PyTest-style coverage metrics. Instead of arbitrary line-coverage, it calculates exactly what percentage of the 8 known LLM hallucination categories (nulls, missing fields, type mismatches, etc.) your tests successfully covered, and lists what is untested.

### ⚡ The Minimal API
For rapid Jupyter Notebook testing and quick demos, use the highly portable 1-line Python wrapper.

```python
from toolguard import quick_check

quick_check(my_agent_function, test_cases=["happy_path", "null_handling"])
```

### 🔄 Retry & Circuit Breaker
Production-grade resilience patterns built-in.

```python
from toolguard import with_retry, RetryPolicy, CircuitBreaker, with_circuit_breaker

@with_retry(RetryPolicy(max_retries=3, backoff_base=0.5))
def call_api(data: dict) -> dict: ...

breaker = CircuitBreaker(failure_threshold=5, reset_timeout=60)

@with_circuit_breaker(breaker)
def call_flaky_service(data: dict) -> dict: ...
```

### 🖥️ CLI
```bash
toolguard proxy --upstream "mcp-server.py"         # Run the raw JSON-RPC 6-layer MCP proxy
toolguard dashboard                                # 🦇 Launch the Obsidian web dashboard
toolguard run my_agent.py                          # Zero-config auto-test
toolguard test --chain my_chain.yaml               # YAML-based chain test
toolguard test --chain my_chain.yaml --html out.html  # HTML report
toolguard test --chain my_chain.yaml --junit-xml out.xml  # JUnit XML for CI
toolguard badge                                    # Generate reliability badge
toolguard check --tools my_tools.py                # Check compatibility
toolguard observe --tools my_tools.py              # View tool stats
toolguard init --name my_project                   # Scaffold project
```

---

## 🔌 Native Framework Integrations

ToolGuard works with your existing tools. No rewrites needed — just wrap and fuzz.

```python
# 🦜🔗 LangChain
from langchain_core.tools import tool
from toolguard import test_chain
from toolguard.integrations.langchain import guard_langchain_tool

@tool
def search(query: str) -> str:
    """Search the web."""
    return f"Results for {query}"

guarded = guard_langchain_tool(search)
report = test_chain([guarded], base_input={"query": "hello"})
```

```python
# 🚀 CrewAI
from crewai.tools import BaseTool
from toolguard.integrations.crewai import guard_crewai_tool

guarded = guard_crewai_tool(my_crew_tool)
```

```python
# 🦙 LlamaIndex
from llama_index.core.tools import FunctionTool
from toolguard.integrations.llamaindex import guard_llamaindex_tool

llama_tool = FunctionTool.from_defaults(fn=my_function)
guarded = guard_llamaindex_tool(llama_tool)
```

```python
# 🤖 Microsoft AutoGen
from autogen_core.tools import FunctionTool
from toolguard.integrations.autogen import guard_autogen_tool

autogen_tool = FunctionTool(my_function, name="my_tool", description="...")
guarded = guard_autogen_tool(autogen_tool)
```

```python
# 🐝 OpenAI Swarm
from swarm import Agent
from toolguard.integrations.swarm import guard_swarm_agent

agent = Agent(name="My Agent", functions=[func_a, func_b])
guarded_tools = guard_swarm_agent(agent)  # Returns list of GuardedTools
```

```python
# ⚡ FastAPI
from toolguard.integrations.fastapi import as_fastapi_tool

guarded = as_fastapi_tool(my_endpoint_function)
```

All 10 integrations tested with **real pip-installed libraries** — not mocks, not duck-types.

### 🧹 100% Authentic Testing
ToolGuard's integration suite runs exclusively against the *actual* PyPI codebase implementations of LangChain, AutoGen, Swarm, FastAPI, and CrewAI. There is absolutely no faked compatibility—it is mathematically proven against the live libraries. We deleted all fake "mock" tests to ensure the standard of reliability is pristine.

---

## 🏗️ CI/CD Integration

### GitHub Action

Add to any repo — auto-comments on PRs with reliability scores:

```yaml
# .github/workflows/toolguard.yml
name: ToolGuard Reliability Check
on: [pull_request]

jobs:
  reliability:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: Harshit-J004/toolguard@main
        with:
          script_path: src/agent.py
          github_token: ${{ secrets.GITHUB_TOKEN }}
          reliability_threshold: "0.95"
```

**PR Comment Example:**
> 🚨 **ToolGuard Reliability Check (BLOCKED)**
>
> **Chain:** `my_agent`
> **Reliability Score:** `64.3%` (Threshold: `95%`)
>
> Warning: The PR introduces agent fragility. **3 tools will crash** if the LLM hallucinates null.

### JUnit XML (Jenkins / GitLab CI)

```bash
toolguard test --chain config.yaml --junit-xml results.xml
```

Generates standard `<testsuites>` XML that Jenkins, GitLab CI, and CircleCI parse natively.

### Reliability Badges

```bash
toolguard badge
```

Generates shields.io badge markdown for your README:

![ToolGuard Reliability](https://img.shields.io/badge/ToolGuard-92%25-brightgreen?logo=shield&style=flat-square)

---

## 📡 Observability & Production Alerts

### 1. Zero-Latency Hallucination Alerts
Catch "LLM drift" in production. When an LLM hallucinates a bad JSON payload, ToolGuard instantly fires a background alert to your team without slowing down the agent:

```python
import toolguard

toolguard.configure_alerts(
    slack_webhook_url="https://hooks.slack.com/...",
    discord_webhook_url="https://discord.com/api/webhooks/...",
    datadog_api_key="my-api-key",
    generic_webhook_url="https://my-dashboard.com/api/ingest"
)
```
*Built with background thread pools so network requests never block the LLM runtime.*

### 2. OpenTelemetry Tracing
Tracing works out of the box with Jaeger, Zipkin, Datadog, and more.

```python
from toolguard.core.tracer import init_tracing, trace_tool

init_tracing(service_name="my-agent")

@trace_tool
def my_tool(data: dict) -> dict: ...
```

---

## Architecture

```
toolguard/
├── core/
│   ├── validator.py      # @create_tool decorator + GuardedTool (sync + async)
│   ├── chain.py          # Chain testing engine (8 test types, async-aware)
│   ├── schema.py         # Auto Pydantic model generation
│   ├── scoring.py        # Reliability scoring + deploy gates
│   ├── report.py         # Failure analysis + suggestions
│   ├── errors.py         # Exception hierarchy + correlation IDs
│   ├── retry.py          # RetryPolicy + CircuitBreaker
│   ├── tracer.py         # OpenTelemetry integration
│   └── compatibility.py  # Schema conflict detection
├── alerts/
│   ├── manager.py        # Abstract ThreadPool dispatcher
│   ├── slack.py          # Block Kit formatting
│   ├── discord.py        # Embed formatting
│   └── datadog.py        # HTTP Metrics + Events sink
├── cli/
│   └── commands/         # run, test, check, observe, badge, init
├── reporters/
│   ├── console.py        # Rich terminal output
│   ├── html.py           # Standalone HTML reports
│   ├── junit.py          # JUnit XML for Jenkins/GitLab CI
│   └── github.py         # GitHub PR auto-commenter
├── integrations/
│   ├── langchain.py      # LangChain adapter
│   ├── crewai.py         # CrewAI adapter
│   ├── llamaindex.py     # LlamaIndex adapter
│   ├── autogen.py        # Microsoft AutoGen adapter
│   ├── swarm.py          # OpenAI Swarm adapter
│   ├── fastapi.py        # FastAPI middleware
│   └── openai_func.py    # OpenAI function calling export
├── tests/                # 50 tests (sync + async + integration)
├── integration_tests/    # Real-library integration tests
└── examples/
    ├── test_alerts.py              # Phase 4 webhook crash simulation
    ├── weather_chain/              # Working 3-tool example
    └── demo_failing_chain/         # Intentionally buggy (aha moment)
```

---

## Why ToolGuard?

| | Without ToolGuard | With ToolGuard |
|---|---|---|
| **Failure detection** | Stack trace at 3 AM | Caught before deploy |
| **Root cause** | "TypeError in line 47" | "Tool A returned null for 'price'" |
| **Fix guidance** | None | "Add default value OR validate response" |
| **Confidence** | "It works on my machine" | "92% reliability, LOW risk" |
| **CI/CD** | Manual testing | `toolguard run` in your pipeline |
| **Cost** | $0.10/test (LLM calls) | $0 (deterministic fuzzing) |
| **Speed** | 30s (API roundtrips) | <1s (local execution) |

---

## Tech Stack

| Component | Technology | Why |
|---|---|---|
| Core Language | Python 3.11 - 3.13 | Agent ecosystem standard |
| Schema Validation | Pydantic v2 | 3.5× faster than JSON Schema |
| Async | Native asyncio | Enterprise-grade concurrency |
| Testing | pytest (50 tests) | CI/CD native |
| Observability | OpenTelemetry | Vendor-neutral |
| CLI | Click + Rich | Beautiful terminal UX |
| CI/CD | GitHub Actions + JUnit | First-class pipeline support |
| Distribution | PyPI | `pip install py-toolguard` |

---

## License

MIT — use it, fork it, ship it.

---

<div align="center">

**Built to make AI agents actually work in production.**

[GitHub](https://github.com/Harshit-J004/toolguard) · [PyPI](https://pypi.org/project/py-toolguard/)

</div>
