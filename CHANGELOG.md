# Changelog

All notable changes to ToolGuard are documented here. This project follows [Semantic Versioning](https://semver.org/).

---

## [4.0.0] — 2026-03-26 — "The Cloudflare for AI Agents"

### 🛡️ MCP Security Proxy (Runtime Firewall)
- **New module:** `toolguard/mcp/` — transparent JSON-RPC 2.0 proxy for the Model Context Protocol
- **New CLI command:** `toolguard proxy --upstream "python server.py" --policy policy.yaml`
- Intercepts all `tools/call` requests between any MCP client and any MCP server in real-time
- Operates at the raw transport layer — zero SDK coupling, works with Python/TypeScript/Go/Rust servers

### The 5-Layer Interceptor Pipeline
1. **Policy Enforcement:** YAML-based per-tool rules to permanently block dangerous tools
2. **Risk-Tier Gating:** Tier-2 tools pause for human terminal approval (bypassed via `TOOLGUARD_AUTO_APPROVE=1`)
3. **Prompt Injection Scanning:** Recursive DFS memory scanner detects prompt smuggling in nested JSON
4. **Rate Limiting:** Sliding-window per-tool frequency caps prevent cyclic agent loops
5. **Trace Logging:** Full execution DAG recorded to `.toolguard/mcp_traces/` as JSON

### New Files
- `toolguard/mcp/__init__.py` — Package exports
- `toolguard/mcp/policy.py` — YAML policy engine with per-tool `ToolPolicy` dataclasses
- `toolguard/mcp/interceptor.py` — 5-layer `MCPInterceptor` with `InterceptResult` API
- `toolguard/mcp/proxy.py` — `MCPProxy` subprocess-based JSON-RPC relay engine
- `toolguard/cli/commands/proxy_cmd.py` — Click CLI with `--upstream`, `--policy`, `--log`, `--verbose`
- `fuzz_targets/test_mcp_proxy.py` — 8-test end-to-end proof script (all passed)

---

## [3.2.0] — 2026-03-26 — "The 10 Integrations Milestone"

### New Framework Adapters
- **OpenAI Agents SDK:** `guard_openai_agents_tool()` — natively wraps `@function_tool` decorators
- **Google Agent Development Kit (ADK):** `guard_google_adk_tool()` — wraps `FunctionTool` from `google.adk.tools`
- CLI auto-discovery updated to detect both new SDKs via duck-typing
- Fuzz-tested with 14 adversarial payloads across both frameworks (all intercepted)

### Badge Update
- Integration badge updated from "8 frameworks" → "10 frameworks"

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
