# Contributing

## Setup

```bash
pip install -e ".[dev]"
```

## Run tests

```bash
pytest
```

## Lint

```bash
ruff check src tests
```

## Scope

This project is intentionally small. Before sending a PR that adds a feature, please open an issue describing the use case — the design bias is toward fewer knobs, not more.

Things this project is **not** going to grow into:
- An auto-launcher for terminals (operator must be in the loop per thread).
- An auto-merger for PRs (you decide landing order).
- A general task-decomposition engine (the operator writes the `plan.toml`).

Bug fixes, doc improvements, and new examples are always welcome.
