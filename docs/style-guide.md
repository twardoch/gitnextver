---
title: Style Guide
nav_order: 2
---

# Style Guide

Conventions for contributors to `gitnextver`.

---

## Python version

Minimum supported: **Python 3.10**.  New syntax or stdlib features introduced
after 3.10 require a compatibility shim or a version guard.

---

## Code style

All Python is formatted and linted with [ruff](https://docs.astral.sh/ruff/).

```bash
uvx ruff format .        # auto-format
uvx ruff check --fix .   # lint + auto-fix
```

The ruff configuration lives in `pyproject.toml` under `[tool.ruff]`.  Rules
enabled: `E`, `F`, `W`, `I` (pycodestyle errors/warnings + pyflakes + isort).

---

## Type hints

- Every public function must have full type annotations (parameters and return
  type).
- Use `Optional[X]` from `typing` for nullable parameters (Python 3.10 does
  not support `X | None` syntax in all positions).
- Private helpers (names prefixed with `_`) should still be annotated.

---

## Logging

- Use [loguru](https://loguru.readthedocs.io/) for all structured logging.
- Use `logger.debug` / `logger.info` for diagnostic messages.
- Use `logger.warning` for recoverable anomalies (index version mismatch,
  no remote configured, etc.).
- Use `logger.error` before raising or calling `sys.exit`.
- Never call `print()` inside library functions; reserve it for the single
  `print(next_version)` line in `main()` that callers capture.

---

## Error handling

- User-facing errors are displayed via `rich.panel.Panel` with a red border,
  then the process exits via `sys.exit(1)`.
- Internal errors that a caller could recover from return `False` (e.g.
  `commit_and_tag`, `pull_with_conflict_check`).
- Do not swallow exceptions silently; either re-raise or convert to a
  descriptive `logger.error` + exit.

---

## Testing

- Tests live in `tests/` and use [pytest](https://docs.pytest.org/).
- Each test that needs a git repository creates one in `tmp_path` (the pytest
  fixture) — never in the project's own `.git`.
- Run with: `uv run python -m pytest tests/ -v`
