# Welcome to ToolGuard

**Reliability testing for AI agent tool chains.**

AI agents chain tools together. But what happens when the first tool returns null or the wrong data type? The chain breaks silently, and your agent fails in production.

ToolGuard is the open-source framework that catches cascading tool failures *before* they hit production. It makes agent tool calling as predictable as unit tests make software reliable.

<div class="grid cards" markdown>

-   :material-shield-check: **Schema Validation**

    ---

    Automatic Pydantic input/output validation from type hints. No manual JSON schemas needed.

-   :material-link: **Chain Testing**

    ---

    Test multi-tool chains against 8 edge-case categories: nulls, type mismatches, malformed data, etc.

-   :material-chart-pie: **Reliability Scoring**

    ---

    Quantified trust with risk levels (CRITICAL to SAFE) and deployment gates (BLOCK or PASS).

-   :material-console: **Beautiful CLI**

    ---

    Run `toolguard test --chain my_chain.yaml` in your CI/CD pipeline to catch regression errors instantly.

</div>
