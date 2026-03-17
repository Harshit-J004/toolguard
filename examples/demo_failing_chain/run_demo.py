"""
Demo Failing Chain — Run the "Aha Moment"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# This script is the FIRST thing a developer runs after `pip install py-toolguard`.
# It simulates a common AI failure (an agent sending a malformed object)null propagation bug
  2. ToolGuard catching the exact failure point
  3. Cascading failure visualization
  4. Actionable fix suggestions
  5. Reliability scoring with deploy gate

Run:
    cd examples/demo_failing_chain
    python run_demo.py
"""

import sys
from pathlib import Path

# Add parent dirs to path for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools import fetch_stock_price, calculate_position, generate_risk_alert
from toolguard import test_chain
from toolguard.core.scoring import score_chain
from toolguard.core.compatibility import check_compatibility
from toolguard.reporters.console import print_chain_report, print_compatibility_report


def main():
    print()
    print("=" * 60)
    print("  🛡️  ToolGuard — Demo: Catching Silent Failures")
    print("=" * 60)
    print()

    # ── FIRST: Show what happens WITHOUT ToolGuard ──
    print("━" * 60)
    print("  😱 WITHOUT ToolGuard (the silent killer):")
    print("━" * 60)
    print()

    # This runs fine for AAPL...
    result1 = fetch_stock_price.unwrap()(ticker="AAPL")
    result2 = calculate_position.unwrap()(
        ticker=result1["ticker"],
        price=result1["price"],
    )
    print(f"  AAPL → ${result2['position_value']:,.2f} ✓  (looks correct)")

    # But TSLA has a null price — and it SILENTLY produces wrong data
    result1_bad = fetch_stock_price.unwrap()(ticker="TSLA")
    try:
        result2_bad = calculate_position.unwrap()(
            ticker=result1_bad["ticker"],
            price=result1_bad["price"],  # ← None! Python treats None * 100 as error
        )
        print(f"  TSLA → ${result2_bad['position_value']:,.2f} ✓  (WRONG! No error raised!)")
    except TypeError:
        print(f"  TSLA → TypeError: can't multiply None × 100")
        print(f"         (No context. No suggestion. No idea where it came from.)")

    print()
    print("  👆 In production, this crashes your pipeline at 3am.")
    print("     You get a stack trace with ZERO context about which")
    print("     tool caused it or how to fix it.")
    print()

    # ── NOW: Show what ToolGuard catches ──
    print("━" * 60)
    print("  🛡️  WITH ToolGuard (full visibility):")
    print("━" * 60)
    print()

    # Step 1: Check compatibility BEFORE running
    print("  📋 Step 1: Compatibility Check")
    print()
    compat = check_compatibility(
        [fetch_stock_price, calculate_position, generate_risk_alert],
        chain_name="Stock Risk Pipeline",
    )
    print_compatibility_report(compat)

    # Step 2: Run chain tests with edge cases
    print("  🧪 Step 2: Chain Reliability Test")
    print()
    report = test_chain(
        [fetch_stock_price, calculate_position, generate_risk_alert],
        base_input={"ticker": "AAPL", "exchange": "NYSE"},
        test_cases=["happy_path", "null_handling", "malformed_data", "missing_fields", "type_mismatch"],
        assert_reliability=0.0,  # Don't assert, let report show results
        chain_name="Stock Risk Pipeline",
    )

    print_chain_report(report)

    # Step 3: Reliability Score
    print("  📊 Step 3: Reliability Score")
    print()
    score = score_chain(report)
    print(score.summary())
    print()

    # ── Final comparison ──
    print("━" * 60)
    print("  🎯 Summary")
    print("━" * 60)
    print()
    print(f"  Reliability:  {report.reliability:.1%}")
    print(f"  Risk Level:   {score.risk_level.value}")
    print(f"  Deploy:       {score.deploy_recommendation.value}")
    print(f"  Top Risk:     {score.top_risk}")
    print()

    if report.reliability < 0.90:
        print("  ⚠️  This chain is NOT production-ready.")
        print("     ToolGuard found the bugs BEFORE your users did.")
    else:
        print("  ✅ Chain is production-ready!")

    print()
    print("=" * 60)
    print("  💡 This is what ToolGuard does.")
    print("     Install: pip install py-toolguard")
    print("     Configure your OpenAI key: export OPENAI_API_KEY=...")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
