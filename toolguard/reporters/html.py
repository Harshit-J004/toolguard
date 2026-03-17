"""
toolguard.reporters.html
~~~~~~~~~~~~~~~~~~~~~~~~

HTML report generator using Jinja2 templates.
Produces standalone, shareable HTML files with embedded CSS.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Template

if TYPE_CHECKING:
    from toolguard.core.report import ChainTestReport


# ──────────────────────────────────────────────────────────
#  HTML Template (embedded for zero-config)
# ──────────────────────────────────────────────────────────

_HTML_TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ToolGuard Report — {{ report.chain_name }}</title>
    <style>
        :root {
            --bg: #0f172a; --surface: #1e293b; --border: #334155;
            --text: #e2e8f0; --muted: #94a3b8;
            --green: #22c55e; --red: #ef4444; --yellow: #eab308;
            --blue: #3b82f6; --cyan: #06b6d4;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg); color: var(--text);
            line-height: 1.6; padding: 2rem;
        }
        .container { max-width: 900px; margin: 0 auto; }
        h1 {
            font-size: 1.75rem; font-weight: 700; margin-bottom: 0.5rem;
            background: linear-gradient(135deg, var(--cyan), var(--blue));
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .subtitle { color: var(--muted); margin-bottom: 2rem; }
        .card {
            background: var(--surface); border: 1px solid var(--border);
            border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem;
        }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 1rem; }
        .stat { text-align: center; }
        .stat-value { font-size: 2rem; font-weight: 700; }
        .stat-label { font-size: 0.85rem; color: var(--muted); text-transform: uppercase; }
        .stat-green { color: var(--green); }
        .stat-red { color: var(--red); }
        .stat-blue { color: var(--blue); }
        .badge {
            display: inline-block; padding: 0.25rem 0.75rem; border-radius: 999px;
            font-weight: 600; font-size: 0.875rem;
        }
        .badge-pass { background: rgba(34,197,94,0.15); color: var(--green); }
        .badge-fail { background: rgba(239,68,68,0.15); color: var(--red); }
        .failure { border-left: 3px solid var(--red); padding-left: 1rem; margin-bottom: 1rem; }
        .failure-title { font-weight: 600; color: var(--yellow); }
        .suggestion { color: var(--green); font-style: italic; }
        .cascade { font-family: monospace; color: var(--cyan); margin: 0.5rem 0; }
        table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
        th { text-align: left; color: var(--muted); font-size: 0.8rem; text-transform: uppercase; padding: 0.5rem; border-bottom: 1px solid var(--border); }
        td { padding: 0.5rem; border-bottom: 1px solid var(--border); }
        .footer { text-align: center; color: var(--muted); font-size: 0.8rem; margin-top: 2rem; }
    </style>
</head>
<body>
<div class="container">
    <h1>🧪 ToolGuard Report</h1>
    <p class="subtitle">{{ report.chain_name }}</p>

    <div class="card">
        <div class="stats">
            <div class="stat">
                <div class="stat-value stat-blue">{{ report.total_tests }}</div>
                <div class="stat-label">Total Tests</div>
            </div>
            <div class="stat">
                <div class="stat-value stat-green">{{ report.passed }}</div>
                <div class="stat-label">Passed</div>
            </div>
            <div class="stat">
                <div class="stat-value stat-red">{{ report.failed }}</div>
                <div class="stat-label">Failed</div>
            </div>
            <div class="stat">
                <div class="stat-value {% if report.passed_threshold %}stat-green{% else %}stat-red{% endif %}">
                    {{ "%.1f"|format(report.reliability * 100) }}%
                </div>
                <div class="stat-label">Reliability</div>
            </div>
        </div>
    </div>

    <div class="card">
        <h2 style="margin-bottom: 1rem;">
            <span class="badge {% if report.passed_threshold %}badge-pass{% else %}badge-fail{% endif %}">
                {% if report.passed_threshold %}✅ PASSED{% else %}❌ BELOW THRESHOLD{% endif %}
            </span>
            <span style="color: var(--muted); font-size: 0.85rem; margin-left: 0.5rem;">
                Threshold: {{ "%.0f"|format(report.reliability_threshold * 100) }}%
            </span>
        </h2>
    </div>

    {% if report.top_failures %}
    <div class="card">
        <h2 style="margin-bottom: 1rem; color: var(--red);">Top Failures</h2>
        {% for f in report.top_failures[:5] %}
        <div class="failure">
            <div class="failure-title">[{{ f.count }}x] {{ f.tool_name }} → {{ f.error_type }}</div>
            <p>🔍 {{ f.root_cause }}</p>
            <p class="suggestion">💡 {{ f.suggestion }}</p>
        </div>
        {% endfor %}
    </div>
    {% endif %}

    {% if failed_runs %}
    <div class="card">
        <h2 style="margin-bottom: 1rem; color: var(--yellow);">Cascade Paths</h2>
        {% for run in failed_runs %}
        <div class="cascade">{{ run.cascade_path | join(' → ') }}</div>
        {% endfor %}
    </div>
    {% endif %}

    <div class="footer">
        Generated by ToolGuard v0.1.0 — Reliability testing for AI agent tool chains
    </div>
</div>
</body>
</html>
""")


# ──────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────

def generate_html_report(report: ChainTestReport, output_path: str | Path = "toolguard_report.html") -> Path:
    """Generate a standalone HTML report file.

    Args:
        report:      ChainTestReport to render.
        output_path: Where to write the HTML file.

    Returns:
        Path to the generated HTML file.
    """
    failed_runs = [r for r in report.runs if not r.success][:10]

    html = _HTML_TEMPLATE.render(
        report=report,
        failed_runs=failed_runs,
    )

    path = Path(output_path)
    path.write_text(html, encoding="utf-8")
    return path
