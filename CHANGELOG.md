# Changelog

All notable changes to ToolGuard are documented here. This project follows [Semantic Versioning](https://semver.org/).

---

## [5.0.1] - 2026-03-27

### Fixed
- Synchronized visual assets and high-res Obsidian hero image for README/PyPI.
- Updated "Operations vs. Engineering" workflow guide.

## [5.0.0] - 2026-03-27

### Added
- **Enterprise MCP Security Proxy**: A transparent, runtime security firewall for the Model Context Protocol (MCP).
- **6-Layer Interceptor Pipeline**: Policy, Risk-Tier, Injection, Rate-Limit, Semantic, and Trace layers.
- **Semantic Policy Engine**: Context-aware authorization beyond type-checking (e.g., path patterns, regex, session scope).
- **Terminal Elite Web Dashboard (Obsidian)**: A zero-dependency, mission-critical GUI featuring Server-Sent Events (SSE) trace streaming, a live 6-Layer Sentinel HUD (`[ L1:POL - L6:TRC ]`), and deep payload JSON inspection.
- **10-Framework Integration Milestone**: Added native support for **OpenAI Agents SDK** and **Google Agent Development Kit (ADK)**.
- **Official MCP SDK Support**: Verified interoperability with Anthropic's official `mcp` Python SDK.

### Verified (Live Gemini 2.0 Flash API)
- **L1 Policy**: Permanently blocked `delete_database` tool — instant deny.
- **L2 Risk-Tier**: Headless auto-deny on Tier-2 `shutdown_server` without human terminal.
- **L3 Injection**: Detected `[SYSTEM OVERRIDE]` prompt injection payload in nested arguments.
- **L4 Rate-Limit**: Burst 12 rapid calls correctly throttled at 10/min sliding window.
- **L5 Semantic**: Regex-denied `DROP TABLE users` from a live Gemini-generated function call.
- **L6 Trace**: Clean `read_file` call passed all 6 layers and logged to execution DAG.

---

## [3.1.0] — 2026-03-23 — "The Deep Audit Release"

### Real-World Tool Fuzzing
- Fuzzed actual LangChain `WikipediaQueryRun` and CrewAI `ScrapeWebsiteTool` from their official packages
- Validated native integration with all 7 framework adapters (AutoGen, LlamaIndex, Swarm, FastAPI, AutoGPT)
- All framework adapters confirmed working with real pip-installed libraries

### Bug Fixes (11 Critical Patches)
- **Fixed:** CrewAI extraction bug — `guard_crewai_tool` crashed on non-callable Pydantic subclasses from `crewai-tools`
- **Fixed:** Bare decorator crash — `@create_tool` without parentheses caused runtime error
- **Fixed:** Fuzzer base inference — `test_chain` now auto-infers inputs from tool signatures when `base_input` is empty
- **Fixed:** Raw traceback leaks from `self._sig.bind()` — now returns clean `SchemaValidationError`
- **Fixed:** LangChain/CrewAI `_run` method inspection — `NotImplementedError` bypass logic repaired
- **Fixed:** Console Reporter `KeyError` when tools dynamically mutated names during `__init__`
- **Fixed:** Type annotation `callable` → `typing.Callable`, removed dead variable paths

---

## [3.0.0] — 2026-03-21 — "The Layer-2 Security Firewall"

### Human-in-the-Loop Risk Tiers
- `@create_tool(risk_tier=2)` blocks destructive tool execution until a human approves via terminal prompt
- AsyncIO event loop protection — approval prompts run in isolated `asyncio.to_thread` workers
- Headless Docker/AWS safety — auto-denies on `EOFError` instead of crashing
- CI/CD bypass via `TOOLGUARD_AUTO_APPROVE=1` env variable

### Recursive Prompt Injection Fuzzing
- `test_cases=["prompt_injection"]` injects `[SYSTEM OVERRIDE]` payloads into every string field
- Recursive depth-first memory parser scans nested `__dict__` attributes, custom classes, and byte arrays
- Case-insensitive `.casefold()` matching catches all string mutations
- Circular reference protection via `id(obj)` tracking

### Golden Traces & DAG Instrumentation
- `with TraceTracker() as trace:` captures all tool executions via Python `contextvars`
- `trace.assert_golden_path()` enforces exact execution order
- `trace.assert_sequence()` for non-deterministic subsequence verification
- Span-state logging (ENTRY, not EXIT) for correct DAG ordering
- `ignore_retries=True` collapses consecutive duplicate calls
- `ThreadPoolExecutor` survival for multi-agent CrewAI swarms
- Per-tool latency metrics on every `TraceNode`

### Ecosystem Patches
- Async LangChain & CrewAI extraction for `.coroutine` / `._arun` methods
- `strip_traceback=True` flag for public webhook safety (Slack, Discord, Datadog)
- Coverage calculator overflow fix for prompt injection categories

---

## [1.2.0] — 2026-03-19 — "The Enterprise Runtime Update"

### Local Crash Replay
- `toolguard run my_agent.py --dump-failures` auto-saves crash payloads to `.toolguard/failures/`
- `toolguard replay <file.json>` re-injects the exact crashing payload for local debugging with full Rich tracebacks

### Edge-Case Test Coverage
- Console Reporter now shows PyTest-style coverage metrics across 8 hallucination categories
- Explicitly lists untested categories (e.g., `large_payload_overflow`, `type_mismatch`)

### Minimal API
- `toolguard.quick_check(my_function)` — 1-line Jupyter-friendly testing wrapper

---

## [1.0.0] — 2026-03-17 — "The Enterprise Production Update"

### Zero-Config Auto-Discovery
- `toolguard run my_agent.py` auto-discovers tools, fuzzes with 40+ attacks, prints reliability score
- Zero YAML configuration required

### Production Observability
- Slack & Discord alerts with rich block-kit messages showing exact LLM JSON diffs
- Datadog native HTTP emission of `toolguard.agent.tool_failure` counters
- Background thread alerts with 0ms latency impact on agent transactions

### Live Dashboard
- `toolguard run my_agent.py --dashboard` launches dark-mode Textual terminal UI
- Real-time streaming of fuzz results and metrics

### Native Framework Integrations
- LangChain (`@tool`), CrewAI (`BaseTool`), LlamaIndex (`FunctionTool`)
- Microsoft AutoGen (`FunctionTool`), OpenAI Swarm (`Agent`)
- FastAPI (Middleware), Vercel AI SDK (HTTP Backend Guide)

### CI/CD Integration
- GitHub PR auto-commenter with reliability scores
- JUnit XML output for Jenkins/GitLab CI/CircleCI
- Dynamic reliability badges for README

### 100% Authentic Testing
- Deleted all legacy mock tests — integration suite runs exclusively against real PyPI libraries
