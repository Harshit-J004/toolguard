# Contributing to ToolGuard

Thank you for considering contributing to ToolGuard! We want to make agent tool chains reliable for everyone.

## Quick Start

```bash
# Fork and clone
git clone https://github.com/Harshit-J004/toolguard.git
cd toolguard

# Install in development mode
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v
# All 48 tests should pass
```

## Development Workflow

1. **Fork** the repository
2. **Create a branch** for your feature: `git checkout -b feature/my-feature`
3. **Write tests first** — we maintain high test coverage
4. **Implement** your changes
5. **Run tests**: `python -m pytest tests/ -v`
6. **Submit a PR** with a clear description

## What We Need Help With

### High Impact
- **New test case types** for `TestInputGenerator` (e.g., unicode, concurrent)
- **Framework integrations** (DSPy, Semantic Kernel, Haystack)
- **Real-world example chains** (Stripe, database, multi-API workflows)

### Medium Impact
- **Documentation improvements** — tutorials, guides, recipes
- **CLI enhancements** — new commands, better output formatting
- **Performance optimizations** — faster test generation, parallel chain runs

### Always Welcome
- Bug reports with reproduction steps
- Typo fixes in docs
- Test coverage improvements

## Code Style

- **Type hints** on all public functions
- **Docstrings** on all classes and public methods
- **Dataclasses** for structured data, **Pydantic** for validation
- Use `from __future__ import annotations` in all files

## Commit Messages

```
feat: add DSPy integration adapter
fix: handle None return values in chain runner
docs: add Stripe example chain walkthrough
test: add edge cases for large payload handling
```

## Need Help?

Open an issue with the `question` label. We're friendly.
