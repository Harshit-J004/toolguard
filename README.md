<div align="center">

# 🛡️ ToolGuard

**Reliability testing for AI agent tool chains.**

Catch cascading failures before production. Make agent tool calling as predictable as unit tests made software reliable.

[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue?style=flat-square)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-43%20passed-brightgreen?style=flat-square)](#)

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

## The Solution

Test your agent's tools against edge-cases *before* you deploy them. ToolGuard acts like **unit tests for AI execution**.

```python
from toolguard import create_tool, test_chain, score_chain

@create_tool(schema="auto")
def parse_csv(raw_csv: str) -> dict:
    lines = raw_csv.strip().split("\n")
    headers = lines[0].split(",")
    records = [dict(zip(headers, line.split(","))) for line in lines[1:]]
    return {"headers": headers, "records": records, "row_count": len(records)}

@create_tool(schema="auto")
def compute_statistics(headers: list, records: list, row_count: int) -> dict:
    # Real computation — mean, median, std dev
    ...

@create_tool(schema="auto")
def generate_report(total_rows: int, stats: dict) -> dict:
    # Real report generation
    ...

# One line. Full visibility.
report = test_chain(
    [parse_csv, compute_statistics, generate_report],
    base_input={"raw_csv": "name,age,salary\nAlice,30,75000\nBob,35,92000"},
    test_cases=["happy_path", "null_handling", "malformed_data"],
)

score = score_chain(report)
print(score.summary())
```

**Real Output (not mocked):**

```
╔═══════════════════════════════════════════════════════════════════╗
║  Reliability Score: parse_csv → compute_statistics → generate_report
╠═══════════════════════════════════════════════════════════════════╣
║  Score:       50.0%                                               ║
║  Risk Level: 🟠 HIGH                                              ║
║  Deploy:     🚫 BLOCK                                             ║
║  Confidence:  45.1%                                               ║
╠═══════════════════════════════════════════════════════════════════╣
║  ⚠️  Top Risk: Schema validation failures                         ║
╠═══════════════════════════════════════════════════════════════════╣
║  Failure Distribution:                                            ║
║    schema_violation   █████████████░░░░░░░   4 (67%)              ║
║    type_mismatch      ██████░░░░░░░░░░░░░░   2 (33%)              ║
╠═══════════════════════════════════════════════════════════════════╣
║  ⚠️  Bottleneck Tools:                                            ║
║    → parse_csv       (50% success)                                ║
╚═══════════════════════════════════════════════════════════════════╝

💡 Suggestion: Check type compatibility between tools. The previous tool
may return str where parse_csv expects int.
```

---

## Quick Start

```bash
pip install toolguard
```

```python
from toolguard import create_tool, test_chain

@create_tool(schema="auto")
def my_tool(query: str) -> dict:
    return {"result": query.upper()}

report = test_chain(
    [my_tool],
    base_input={"query": "hello"},
    test_cases=["happy_path", "null_handling", "malformed_data"],
    assert_reliability=0.80,
)
```

Or scaffold a full project:

```bash
toolguard init --name my_agent
```

**Time to value: < 3 minutes.**

---

## Features

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

### 📊 Reliability Scoring
Quantified trust with risk levels and deployment gates.

```python
score = score_chain(report)
if score.deploy_recommendation.value == "BLOCK":
    sys.exit(1)  # CI/CD gate
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
toolguard test --chain my_chain.yaml           # Run chain tests
toolguard test --chain my_chain.yaml --html report.html  # HTML report
toolguard check --tools my_tools.py            # Check compatibility
toolguard observe --tools my_tools.py          # View tool stats
toolguard init --name my_project               # Scaffold project
```

### 🔌 Native Framework Integrations

If you are already using **LangChain** or **CrewAI**, you do **not** need to rewrite your tools to use ToolGuard. 

ToolGuard provides native adapters that instantly convert your existing framework tools into `GuardedTools` so you can stress-test them immediately.

```python
# 🦜🔗 LangChain
from toolguard.integrations.langchain import guard_langchain_tool
from my_app import my_langchain_tool

guarded_tool = guard_langchain_tool(my_langchain_tool)
report = test_chain([guarded_tool], ...)

# ⚙️ CrewAI
from toolguard.integrations.crewai import guard_crewai_tool
from my_app import my_crew_tool

guarded_tool = guard_crewai_tool(my_crew_tool)
report = test_chain([guarded_tool], ...)

# 🤖 OpenAI Function Calling
from toolguard.integrations.openai_func import to_openai_function
from my_app import my_python_tool

# Instantly export any ToolGuard tool to the strict OpenAI JSON schema format
openai_schema = to_openai_function(my_python_tool)
```

### 📡 Observability
OpenTelemetry tracing out of the box — works with Jaeger, Zipkin, Datadog, and more.

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
├── cli/
│   └── commands/         # init, test, check, observe
├── reporters/
│   ├── console.py        # Rich terminal output
│   └── html.py           # Standalone HTML reports
├── integrations/
│   ├── langchain.py      # LangChain adapter
│   ├── crewai.py         # CrewAI adapter
│   └── openai_func.py    # OpenAI function calling
├── tests/                # 43 tests (sync + async + storage)
└── examples/
    ├── weather_chain/              # Working 3-tool example
    ├── demo_failing_chain/         # Intentionally buggy (aha moment)
    └── real_world_validation/      # Real CSV pipeline validation
```

---

## Why ToolGuard?

| | Without ToolGuard | With ToolGuard |
|---|---|---|
| **Failure detection** | Stack trace at 3 AM | Caught before deploy |
| **Root cause** | "TypeError in line 47" | "Tool A returned null for 'price'" |
| **Fix guidance** | None | "Add default value OR validate response" |
| **Confidence** | "It works on my machine" | "92% reliability, LOW risk" |
| **CI/CD** | Manual testing | `toolguard test` in your pipeline |

---

## Tech Stack

| Component | Technology | Why |
|---|---|---|
| Core Language | Python 3.11 - 3.13 | Agent ecosystem standard |
| Schema Validation | Pydantic v2 | 3.5× faster than JSON Schema |
| Async | Native asyncio | Enterprise-grade concurrency |
| Testing | pytest (43 tests) | CI/CD native |
| Observability | OpenTelemetry | Vendor-neutral |
| CLI | Click + Rich | Beautiful terminal UX |
| Distribution | PyPI | `pip install toolguard` |

---

## License

MIT — use it, fork it, ship it.

---

<div align="center">

**Built to make AI agents actually work in production.**

[GitHub](https://github.com/Harshit-J004/toolguard)

</div>
