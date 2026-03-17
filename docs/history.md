# History & Storage

ToolGuard persists test results in a local SQLite database so you can track your chain's reliability over time.

## Automatic Saving

### Via CLI (default)
Every time you run `toolguard test`, results are automatically saved:

```bash
toolguard test --chain my_chain.yaml
# 💾 Results saved to history. Run toolguard history to view trends.
```

To disable: `toolguard test --chain my_chain.yaml --no-save`

### Via Python API

```python
from toolguard import test_chain

# Option 1: Use save=True
report = test_chain([tool_a, tool_b], base_input={...}, save=True)

# Option 2: Manual save for more control
from toolguard import ResultStore

store = ResultStore()
store.save_report(report, metadata={"env": "staging", "git_hash": "abc123"})
store.close()
```

## Viewing History

### CLI

```bash
# See all chains
toolguard history

# Detailed trend for one chain
toolguard history --chain "parse_csv → compute_statistics → generate_report"

# Last 7 days only
toolguard history --days 7

# Clear history
toolguard history --clear my_chain
```

### Python API

```python
from toolguard import ResultStore

store = ResultStore()

# Get all chains that have been tested
chains = store.get_all_chains()
for c in chains:
    print(f"{c['chain_name']}: {c['latest_reliability']:.1%} ({c['run_count']} runs)")

# Get reliability trend
trend = store.get_reliability_trend("my_chain", days=30)
print(trend.summary())
# Chain: my_chain
# Runs:  12
# Avg:   87.5%
# Trend: ↑ improving (+8.3%)

# Check if reliability is improving
if trend.improving:
    print("Getting better!")

store.close()
```

## Storage Location

By default, ToolGuard creates a `.toolguard/` directory in your project root:

```
my_project/
├── .toolguard/
│   └── history.db    ← SQLite database (auto-created)
├── my_tools.py
└── chain_config.yaml
```

> [!TIP]
> Add `.toolguard/` to your `.gitignore` — this is a local database, not meant to be committed.

## Custom Database Path

```python
store = ResultStore(db_path="/path/to/custom.db")
```
