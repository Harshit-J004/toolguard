# Scoring & Deployment Gates

ToolGuard's scoring engine quantifies how trustworthy your tool chain is and tells you whether it's safe to deploy.

## Quick Usage

```python
from toolguard import test_chain, score_chain

report = test_chain([tool_a, tool_b], base_input={...})
score = score_chain(report)

print(score.summary())
```

## Risk Levels

| Level | Score Range | Meaning |
|---|---|---|
| 🟢 **SAFE** | 95–100% | Production-ready |
| 🔵 **LOW** | 85–94% | Minor issues, likely safe |
| 🟡 **MEDIUM** | 70–84% | Needs attention before production |
| 🟠 **HIGH** | 50–69% | Significant risk, fix failures first |
| 🔴 **CRITICAL** | 0–49% | Do not deploy |

## Deploy Recommendations

| Recommendation | When | CI Exit Code |
|---|---|---|
| ✅ **PASS** | Reliability ≥ 90% | 0 |
| ⚠️ **WARN** | Reliability 70–89% | 0 (with warnings) |
| 🚫 **BLOCK** | Reliability < 70% | 1 |

## Failure Distribution

The score includes a breakdown of failure types:

```
Failure Distribution:
  null_propagation ██████████████░░░░░░  6 (75%)
  type_mismatch    ████░░░░░░░░░░░░░░░░  2 (25%)
```

## Using as a CI/CD Gate

```python
import sys
from toolguard import test_chain, score_chain

report = test_chain(chain, base_input=inputs, assert_reliability=0.0)
score = score_chain(report)

if score.deploy_recommendation.value == "BLOCK":
    print(score.summary())
    sys.exit(1)
```

## Confidence Score

ToolGuard also reports a confidence score (0.0–1.0) indicating how statistically reliable the reliability measurement is, based on the number of test runs executed.
