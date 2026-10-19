---
this_file: WORK.md
---

# Release controls, 2026-10-19

Add a pure semantic-tag selection API and explicit dry-run/pull/commit/push
controls without replacing the existing default workflow. First-release tags
are configurable; minor/major bumps reset smaller components. Rejected pushes
fail visibly and atomically, with only the chosen branch/tag sent.

Verification:

- Baseline: 17 tests pass.
- New controls tests first fail on the missing versioning module.
- Initial rejection fixture needed a native Git commit because this machine's
  clone used index v4; the product already has an index-compatibility path.
- `rtk proxy uv run python -m pytest -q`: 32 tests pass.
- `rtk proxy uv run --no-project --with pytest --with pytest-cov --with fire --with GitPython --with loguru --with rich env PYTHONPATH=src python -m pytest -q --cov=gitnextver.versioning --cov-report=term-missing --cov-fail-under=80`: 32 tests pass, pure API coverage 100%.
- `rtk proxy uv run python -m ruff check .`: exit 0.
- `rtk proxy uv run python -m ruff format --check .`: exit 0.
- `rtk proxy uv run gitnextver --dry-run --bump=patch`: v1.0.3, exit 0.

Release/publication verification follows after the reviewed commit and tag.

The local-only v1.0.3 candidate passed wheel/sdist imports and Twine, but its
source archive inherited existing .omc state from Hatch's default selection.
It was never pushed or published. Restricted sdist selection explicitly; the
next new tag is v1.0.4. Keep the failed candidate tag unchanged.

v1.0.4 published successfully to PyPI and GitHub. Public PyPI wheel/sdist hashes
match the audited files; a fresh public-index install exposes the new API.
Installed wheel runs all 32 tests; source archive installs independently.
The full nine-job Linux/macOS/Windows CI matrix passes.
Existing OIDC publishing was unconfigured (invalid-publisher). Added an optional
PYPI_TOKEN secret path, idempotent existing-file handling and manual dispatch of
an existing release tag; configured the authorized token without logging it.
