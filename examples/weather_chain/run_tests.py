"""
Weather Chain — Run Tests
~~~~~~~~~~~~~~~~~~~~~~~~~

Demonstrates ToolGuard's chain testing capabilities:
  - Tests a 3-tool chain against edge cases
  - Shows beautiful console output
  - Generates an HTML report

Run: python run_tests.py
"""

import sys
from pathlib import Path

# Add parent dirs to path for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools import get_weather, process_forecast, send_alert
from toolguard import test_chain
from toolguard.core.compatibility import check_compatibility
from toolguard.reporters.console import print_chain_report, print_compatibility_report, print_tool_stats
from toolguard.reporters.html import generate_html_report


def main():
    print("=" * 60)
    print("  🛡️  ToolGuard — Weather Chain Example")
    print("=" * 60)
    print()

    # ── Step 1: Check compatibility ──
    print("Step 1: Checking tool compatibility...\n")
    compat_report = check_compatibility(
        [get_weather, process_forecast, send_alert],
        chain_name="Weather Alert Chain",
    )
    print_compatibility_report(compat_report)

    # ── Step 2: Run chain tests ──
    print("Step 2: Running chain tests...\n")
    try:
        report = test_chain(
            [get_weather, process_forecast, send_alert],
            base_input={"location": "NYC", "units": "metric"},
            test_cases=["happy_path", "null_handling", "malformed_data", "missing_fields"],
            assert_reliability=0.0,  # Don't assert, let the report show results
            chain_name="Weather Alert Chain",
        )
    except Exception as e:
        print(f"Error: {e}")
        return

    # ── Step 3: Display results ──
    print_chain_report(report)

    # ── Step 4: Show tool stats ──
    print("Tool Statistics after tests:\n")
    print_tool_stats([get_weather, process_forecast, send_alert])

    # ── Step 5: Generate HTML report ──
    html_path = generate_html_report(report, Path(__file__).parent / "report.html")
    print(f"\n📄 HTML report saved to: {html_path}")

    # ── Summary ──
    print(f"\n{'=' * 60}")
    print(f"  Reliability: {report.reliability:.1%}")
    print(f"  Passed: {report.passed}/{report.total_tests}")
    print(f"  {'✅ Chain is production-ready!' if report.reliability >= 0.90 else '⚠️ Chain needs improvement.'}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
