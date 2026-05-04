# Changelog

All notable changes to ToolGuard are documented here. This project follows [Semantic Versioning](https://semver.org/).

---

## [6.1.2] - 2026-05-04

### Fixed — Security Patch: Null Byte DoS in Schema Drift Engine
- **`_looks_like_ipv4()` / `_looks_like_ipv6()` Crash**: `socket.inet_pton()` raises `ValueError` (not `socket.error`) when the input string contains embedded null bytes (`\x00`). This caused an **unhandled crash** in the drift detection engine, exploitable as a denial-of-service attack. Fixed by broadening the exception handler to catch `(socket.error, ValueError, OSError)`.
- **Discovery Method**: Found by **Hypothesis property-based testing** — not manual code review. The fuzzer generated a `'\x00'` string input that no human tester would think to try.

### Added — Adversarial Red-Team Test Suite (82 Attack Vectors)
- **`test_redteam_evasion.py`** (54 tests): Adversarial evasion attacks across all 7 security layers — Unicode homoglyphs, fragmented injections, Base64 encoding, path traversal, SQL comment evasion, and more.
- **`test_redteam_robustness.py`** (16 tests): Crash/DoS resistance — 500-level deep nesting, 1MB payloads, circular references, 200 concurrent threads, malformed UTF-8, NaN/Infinity floats.
- **`test_property_based.py`** (12 tests / 1,700+ generated cases): Hypothesis-powered invariant testing — randomly plants injections at random depths/widths/container types and verifies the scanner catches every single one.
- **Result**: 82/82 passed. Zero bypasses. Zero crashes.

---

## [6.1.1] - 2026-04-06

### Fixed — Server Freeze on Webhook Approvals (Starlette Offloading)
- **FastAPI Thread Offloading**: Changed webhook approval routes (`/approve`, `/deny`) from `async def` to standard `def`, mathematically forcing FastAPI to offload synchronous Redis polls to Starlette's background threadpool.
- **Zero-Blocking Concurrency**: The main event loop is now 100% shielded from hanging during Human-in-the-Loop Slack webhook proxy requests.

### Added — Enterprise Redis Resilience
- **Transient Network Recovery**: Wrapped the `RedisStorageBackend` in a zero-dependency `@_retry_on_transient` decorator. Network blips dynamically retry up to 3 times (with `0.1s -> 0.2s -> 0.4s` exponential backoff) before crashing an agent pipeline.
- **Fatal Error Fast-Fail**: Implemented strict exception whitelisting to guarantee configuration errors like `AuthenticationError` bypass the retry loop and instantly fail.

### Removed
- **Dead Code Cleanup**: Eliminated the legacy, unused `RateLimiter` class from `interceptor.py` as all sliding-window enforcement is now globally guaranteed by the `StorageBackend`.

---

## [6.1.0] - 2026-04-03

### Added — Enterprise HTTP Proxy Sidecar (Cross-Language Support)
- **Asymmetric Language Architecture**: ToolGuard can now be used by **TypeScript, Node.js, Go, Rust, Java**, and any other language ecosystem via a standalone HTTP Proxy.
- **REST Intercept Endpoint**: `POST /v1/intercept` allows any agent to execute the full 7-Layer security pipeline natively via JSON. Trace events bridge perfectly into the Obsidian Dashboard.
- **API Key Security**: Secure the proxy sidecar against unauthenticated internal network requests using standard `Bearer <token>` middleware. Includes configuration via `--api-key` or `TOOLGUARD_API_KEY` env var.
- **Docker & Kubernetes Integration**: Official `Dockerfile` and `docker-compose.yml` added. Run the proxy sidecar instantly with `docker-compose up -d`, completely abstracting Python away from Java/TypeScript DevOps teams.
- **New CLI Command**: `toolguard serve --policy security.yaml --port 8080` launches the ASGI server using FastAPI/Uvicorn.
- **Kubernetes Readiness**: Added `GET /v1/health` endpoint for native Kubernetes liveness probes.

### Added — Distributed State (Cluster-Safe ToolGuard)
- **Unified `StorageBackend` Interface**: Decoupled all ToolGuard memory (Rate Limits, Approval Cache, Schema Fingerprints, and Execution Grants) from local files.
- **Redis Enterprise Backend**: Implemented `RedisStorageBackend` enabling atomic `INCR`, `SETEX`, and `HSET` operations. Prevents rate-limit leakage across 50-pod Kubernetes swarms.
- **Zero-Config local Fallback**: Implemented `LocalStorageBackend` maintaining SQLite/JSON behavior for local development.

### Added — Asynchronous Webhook Approvals (Headless Agent Resumption)
- **Headless-First Approvals**: When a Risk Tier 2 or 3 tool fires in a cloud server without a terminal (`sys.stdin.isatty() == False`), ToolGuard now pauses execution instead of permanently "Failing Closed".
- **4 Native Webhook Providers**: 
  - **Discord**: Link-button embeds for open-source communities.
  - **Slack**: Block Kit interactive buttons for startups.
  - **Microsoft Teams**: Adaptive Cards for Fortune 500 enterprises.
  - **Generic**: Standard JSON payloads for Zapier/Make.com/n8n.
- **Cryptographic Execution Grants**: Generates an ephemeral `grant_id` UUID stored in Redis with `PENDING` state.
- **FastAPI Approval Server**: Pre-built HTTP endpoints (`/toolguard/approve` & `/toolguard/deny`) rendered with beautiful dark-mode HTML confirmation pages.
- **Polling Resumption Loop**: The interceptor safely waits up to the `approval_timeout`, polling the Redis cluster for a manager's remote authorization before unblocking the LLM chain.

---

## [6.0.0] - 2026-04-03

### Added — Production-grade 4-Tier Risk Architecture (Layer 2 Upgrade)
- **Refined Risk Tiers**: Upgraded from a simple 2-tier system to a comprehensive 4-tier risk architecture.
  - **Tier 1 (Standard)**: Auto-approve execution with full trace logging.
  - **Tier 2 (Restricted)**: Human approval via terminal (Y/N prompt). Supports configuration for approval timeout (prevents pipeline deadlocks from unattended terminals) and approval TTL caching to reduce friction in looping LLM executions.
  - **Tier 3 (Critical)**: "Double-confirm" constraint (the user must type the exact tool name, not just 'y', overriding muscle memory limits). Skips approval caching.
  - **Tier 4 (Forbidden)**: Always denied execution with full log trace availability, enhancing forensic auditing capabilities without removing the tool definition via `blocked: true`.
- **7-Defense Architecture**: Implemented 7 targeted architectural defenses:
  - Global `_stdin_lock` mutex to perfectly prevent input thread collision.
  - Isolated `TOOLGUARD_AUTO_APPROVE` bypass mapping (Tier 2 only, Tiers 3 & 4 ignore).
  - Configurable Tier clamping `_clamp_tier(1-4)` handling malformed values reliably.
  - Thread-atomic `_approval_cache_lock` checks.
  - Advanced headless failure validations targeting sub-tty layers like SSH-T and systemd pods using `os.fstat()`.
  - Case-folded Tier-3 string comparisons.
  - Dynamic `_approval_cache.clear()` methods available on Hot Policy Reloads.

### Added — Schema Drift Detection Engine (Layer 7 Upgrade)
- **7-Layer Interceptor Pipeline**: Upgraded from 6 to 7 layers. New Layer 6 (`L6:DRF`) intercepts live LLM tool payloads and compares them against frozen structural baselines in real-time.
- **Schema Drift Engine (`drift.py`)**: Recursive structural diffing algorithm that infers JSON Schema from raw Python dicts, freezes cryptographic fingerprints, and detects field additions, removals, type changes, and format changes.
- **Fingerprint Store (`drift_store.py`)**: SQLite-backed persistence with WAL mode for concurrency, v2 schema migration, and `default=str` serialization safety.
- **Pydantic Bridge**: `create_fingerprint_from_model()` generates baselines directly from Python classes. Includes recursive `$ref` resolver (depth-capped at 10) and `anyOf` union flattener for `Optional` types.
- **False-Positive Guard**: Missing optional fields (not in `required[]`) are silently allowed — only missing *required* fields trigger `CRITICAL` drift alerts.
- **`SchemaDriftError`**: First-class catchable exception in the error hierarchy for programmatic pipeline control.
- **CLI Commands**: `toolguard drift snapshot`, `toolguard drift check --fail-on-drift`, `toolguard drift list`, `toolguard drift clear`, `toolguard drift snapshot-pydantic`.
- **Dashboard HUD**: New `L6:DRF` and `L7:TRC` LEDs on the Obsidian Sentinel HUD with real-time SSE pulse integration.

### Added — "Absolute Zero" Security Hardening
- **L2-L6 Firewalls**: Injected the 5-layer "Absolute Zero" gauntlet (Docker-Deadlock prevention, Stack-Buster DoS depth-limits, Atomic JSON Rate Persistence, and recursive Obfuscation Unrolling).
- **Nano-Latency Forensics**: Dashboard now tracks per-tool latency with 0.001ms precision.
- **Identity Spoof Detection**: Automated monitoring for casing-based tool identity attacks.

### Verified (E2E Test Suite — 6 Phases)
- **Phase 1**: Baseline fingerprint creation with SHA-256 checksum.
- **Phase 2**: Identical output produces zero drift (checksum fast-path).
- **Phase 3**: Drifted output detects type changes, missing fields, added fields, format changes.
- **Phase 4**: Specific assertions on field-level drift severity classification.
- **Phase 5**: SQLite persistence round-trip with checksum integrity.
- **Phase 6**: Pydantic model footprinting with `anyOf` unrolling and metadata scrubbing.
- **Sentinel Swarm Phase**: Verified 100% interception success against concurrent triple-agent LangGraph attacks using live Google Gemini instances.

---

## [5.1.2] - 2026-03-30

### Documentation Sync
- **PyPI README Update**: Synchronized the PyPI package page with the latest README, including the 7-Layer Security Interceptor Waterfall, 0ms Latency proof, MCP Proxy commands, and the 10-framework integration catalog.
- **Edge-Case Accuracy**: Corrected hallucination category count from 8 to 9 across all documentation to match the source code (`TestCaseType` enum).

---

## [5.1.1] - 2026-03-28

### Security Audit (The "Obsidian" Verification)
- **Binary-Encoded Injection Defense**: Upgraded the recursive DFS memory scanner to natively decode and scan `bytes` and `bytearray` objects. This closes a critical evasion vector in both the core pipeline and the **MCP Interceptor**.
- **Public Webhook Privacy**: Verified `strip_traceback=True` implementation for Slack, Discord, and Datadog to prevent source code leakage. **Updated Slack/Discord formatters** to natively render the `traceback` (or "STRIPPED" notice) in the final UI notification.
- **Dynamic Dashboard Versioning**: Obsidian Dashboard now dynamically pulls the current ToolGuard version from `__init__.py` instead of hardcoding text fields.

### Fixed
- **Dashboard Live Telemetry**: Replaced `MCPInterceptor` stub logging with a High-Performance File-Watcher pipeline (`_emit_trace()`). The interceptor now writes JSON events directly to `.toolguard/mcp_traces/`, enabling pure real-time streaming to the dashboard HUD without blocking the upstream agent.
- **Framework Async Deadlock**: Patched a critical bug in **LangChain** and **CrewAI** adapters where synchronous `.func` shadowing was causing asynchronous `.coroutine` and `._arun` paths to be skipped.
- **Coverage Math**: Fixed a calculation overflow in the Console Reporter where coverage percentiles could structurally exceed 100% under aggressive prompt injection fuzzing.
- Synchronized visual assets and high-res Obsidian image for README/PyPI.
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
