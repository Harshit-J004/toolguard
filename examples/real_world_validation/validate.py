"""
Real-world validation of ToolGuard.

This is NOT a mock. These tools do actual computation:
  - parse_csv_data: Parses real CSV text into structured records
  - compute_statistics: Calculates real mean/median/std deviation
  - generate_report: Builds an actual formatted report string

We run ToolGuard's chain tester against this real pipeline to prove
it catches REAL cascading failures (not simulated ones).
"""

import sys
import os
import math
import statistics

# Add parent to path so we can import toolguard
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from toolguard import create_tool, test_chain, score_chain
from toolguard.reporters.console import print_chain_report


# ──────────────────────────────────────────────────────────
#  Tool 1: Parse CSV data into structured records
# ──────────────────────────────────────────────────────────

@create_tool(schema="auto")
def parse_csv_data(raw_csv: str, delimiter: str = ",") -> dict:
    """Parse a CSV string into structured records.
    
    This does REAL parsing — splits lines, handles headers,
    converts numeric fields to floats.
    """
    lines = raw_csv.strip().split("\n")
    if len(lines) < 2:
        raise ValueError("CSV must have at least a header and one data row")
    
    headers = [h.strip() for h in lines[0].split(delimiter)]
    records = []
    
    for line in lines[1:]:
        values = [v.strip() for v in line.split(delimiter)]
        record = {}
        for i, header in enumerate(headers):
            val = values[i] if i < len(values) else ""
            # Try to convert to float
            try:
                record[header] = float(val)
            except (ValueError, TypeError):
                record[header] = val
        records.append(record)
    
    return {
        "headers": headers,
        "records": records,
        "row_count": len(records),
        "column_count": len(headers),
    }


# ──────────────────────────────────────────────────────────
#  Tool 2: Compute real statistics on the parsed data
# ──────────────────────────────────────────────────────────

@create_tool(schema="auto")
def compute_statistics(
    headers: list,
    records: list,
    row_count: int,
    column_count: int,
) -> dict:
    """Compute real statistical analysis on parsed CSV data.
    
    Calculates mean, median, std deviation, min, max for each
    numeric column. This is REAL math, not hardcoded values.
    """
    numeric_stats = {}
    
    for header in headers:
        values = []
        for record in records:
            val = record.get(header)
            if isinstance(val, (int, float)) and not math.isnan(val):
                values.append(val)
        
        if values:
            numeric_stats[header] = {
                "mean": round(statistics.mean(values), 2),
                "median": round(statistics.median(values), 2),
                "stdev": round(statistics.stdev(values), 2) if len(values) > 1 else 0.0,
                "min": min(values),
                "max": max(values),
                "count": len(values),
            }
    
    return {
        "total_rows": row_count,
        "numeric_columns": list(numeric_stats.keys()),
        "stats": numeric_stats,
    }


# ──────────────────────────────────────────────────────────
#  Tool 3: Generate a formatted analysis report
# ──────────────────────────────────────────────────────────

@create_tool(schema="auto")
def generate_report(
    total_rows: int,
    numeric_columns: list,
    stats: dict,
) -> dict:
    """Generate a human-readable analysis report.
    
    Builds actual formatted output with real data-driven insights.
    """
    lines = [
        f"📊 Data Analysis Report",
        f"{'=' * 50}",
        f"Total records analyzed: {total_rows}",
        f"Numeric columns found: {len(numeric_columns)}",
        "",
    ]
    
    alerts = []
    
    for col_name in numeric_columns:
        col_stats = stats[col_name]
        lines.append(f"  📈 {col_name}:")
        lines.append(f"     Mean: {col_stats['mean']}")
        lines.append(f"     Median: {col_stats['median']}")
        lines.append(f"     Std Dev: {col_stats['stdev']}")
        lines.append(f"     Range: [{col_stats['min']}, {col_stats['max']}]")
        lines.append("")
        
        # Real data-driven alerts
        if col_stats['stdev'] > col_stats['mean'] * 0.5:
            alerts.append(f"⚠️  High variance in '{col_name}' (stdev > 50% of mean)")
        if col_stats['max'] > col_stats['mean'] * 3:
            alerts.append(f"⚠️  Outlier detected in '{col_name}' (max > 3x mean)")
    
    return {
        "report": "\n".join(lines),
        "alert_count": len(alerts),
        "alerts": alerts,
        "columns_analyzed": len(numeric_columns),
    }


# ──────────────────────────────────────────────────────────
#  Run the REAL validation
# ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Real CSV data (not mock!)
    REAL_CSV = """name,age,salary,performance_score
Alice,29,75000,4.2
Bob,35,92000,3.8
Charlie,42,110000,4.7
Diana,28,68000,3.5
Eve,31,85000,4.9
Frank,55,145000,3.2
Grace,26,62000,4.1
Hank,38,98000,3.9
Iris,33,88000,4.4
Jack,45,125000,2.8"""

    print("=" * 60)
    print("  🛡️  ToolGuard: REAL-WORLD VALIDATION")
    print("  Testing against actual data processing pipeline")
    print("=" * 60)
    print()

    # ── Step 1: Show the chain works on real data ────────
    print("▶ Step 1: Running chain with REAL CSV data...")
    print()
    
    parsed = parse_csv_data(raw_csv=REAL_CSV)
    print(f"  ✓ Parsed {parsed['row_count']} rows, {parsed['column_count']} columns")
    
    stats_result = compute_statistics(**parsed)
    print(f"  ✓ Computed statistics for {len(stats_result['numeric_columns'])} numeric columns")
    for col in stats_result['numeric_columns']:
        s = stats_result['stats'][col]
        print(f"    → {col}: mean={s['mean']}, median={s['median']}, stdev={s['stdev']}")
    
    report_result = generate_report(**stats_result)
    print(f"  ✓ Generated report with {report_result['alert_count']} alerts")
    for alert in report_result['alerts']:
        print(f"    {alert}")
    
    print()
    print("-" * 60)
    print()

    # ── Step 2: Run ToolGuard chain tests ────────────────
    print("▶ Step 2: Running ToolGuard chain tests...")
    print("  Testing with: happy_path, null_handling, malformed_data, missing_fields")
    print()
    
    report = test_chain(
        [parse_csv_data, compute_statistics, generate_report],
        base_input={
            "raw_csv": REAL_CSV,
            "delimiter": ",",
        },
        test_cases=["happy_path", "null_handling", "malformed_data", "missing_fields"],
        iterations=5,
        assert_reliability=0.0,  # Don't assert, we want to see the report
    )
    
    print_chain_report(report)
    
    print()
    print("-" * 60)
    print()

    # ── Step 3: Score the chain ──────────────────────────
    print("▶ Step 3: Reliability scoring...")
    print()
    
    score = score_chain(report)
    print(score.summary())
    
    print()
    print("=" * 60)
    print("  \u2705 VALIDATION COMPLETE")
    print(f"  Real data \u2192 Real computation \u2192 Real ToolGuard analysis")
    print("=" * 60)
