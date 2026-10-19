# Changelog

All notable changes to `gitnextver` are documented here.

## [Unreleased]

## [1.0.4] — 2026-10-19

### Controlled release operations
- Add the pure `gitnextver.versioning.next_version` API, configurable initial
  tag, and patch/minor/major increments with strict stable-tag selection.
- Add `--dry-run`, `--pull=False`, `--commit=False` and `--push=False` while
  preserving the original default workflow. Dry runs perform no Git mutations
  or network calls; tag-only mode requires a clean checkout.
- Push only the selected tag and current branch, atomically, and report push
  rejection as failure instead of silently accepting GitPython PushInfo errors.
- Exercise controls with real isolated Git repositories and bare remotes;
  add Windows to the existing CI matrix and the missing Ruff dev dependency.
- Limit source distributions to package sources, tests and package metadata,
  excluding local agent state and private work logs.

### Added
- `tests/test_gitnextver.py` — 17 pytest tests covering version calculation,
  tag lookup, index-version reading, and end-to-end `main()` integration tests
  using throwaway git repositories in `tmp_path`.
- `pytest` added as a dev dependency (`[dependency-groups] dev`).
- `.github/workflows/ci.yml` — matrix CI (Python 3.10/3.12/3.13, Linux and
  macOS) running lint, format check, and the full test suite on every push and
  pull request against `main`.
- `.github/workflows/publish.yml` — publishes to PyPI via OIDC trusted
  publishing whenever a `vX.Y.Z` tag is pushed (no API token required).
- `docs/` — Jekyll site with the JustTheDocs remote theme, containing a home
  page (`index.md`) with usage, "What it does NOT do", and troubleshooting
  sections, plus a contributor style guide (`style-guide.md`).
- `_read_index_version(git_dir)` helper in `cli.py` reads the raw binary
  index header to determine the format version before GitPython touches it.

### Changed
- `ensure_gitpython_compatibility()` now gates the index downgrade on the
  actual index format version read from the binary header rather than
  attempting to access `repo.index.entries` and catching an `AssertionError`.
  The downgrade (`git update-index --index-version 2`) is performed only when
  the on-disk version is > 2; the fast path (version ≤ 2) returns immediately
  with no side effects.
- `main()` docstring expanded to document parameters, return behaviour, and
  the full workflow.
- Inline comments in `ensure_gitpython_compatibility()` explain why the hack
  exists, which git versions trigger it, and why reading the header first is
  better than catching a post-facto `AssertionError`.
- `README.md` restructured: added "What it does NOT do" section and a
  Troubleshooting section covering index-lock and index-version issues.

## [1.0.1] — 2026-04-08

### Fixed
- Stash/restore logic wraps pull to prevent losing local work on conflict.
- Index-lock cleanup in `stash_uncommitted_changes` when git index is corrupt.

## [1.0.0] — 2025-xx-xx

### Added
- Initial release: patch-only version bumping with stash/pull/push workflow.
- GitPython index version compatibility handling.
- Rich-formatted console output and loguru-based logging.

[Unreleased]: https://github.com/twardoch/gitnextver/compare/v1.0.4...HEAD
[1.0.4]: https://github.com/twardoch/gitnextver/releases/tag/v1.0.4
[1.0.1]: https://github.com/twardoch/gitnextver/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/twardoch/gitnextver/releases/tag/v1.0.0
