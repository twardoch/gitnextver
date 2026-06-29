---
title: Home
nav_order: 1
---

# gitnextver

**One command, one tag, done.**

`gitnextver` bumps the patch component of the highest `vX.Y.Z` git tag in
your repository, stages all pending changes, commits them with the new version
string as the commit message, creates the tag, and pushes both to the remote.

```bash
pip install gitnextver   # or: uvx gitnextver
gitnextver               # in your repo → v1.0.1 (or whatever comes next)
```

---

## What it does

1. Validates that the working directory is a git repository.
2. Checks the git index format version and rewrites it to version 2 if needed
   so that GitPython can parse it (see [Troubleshooting](#troubleshooting)).
3. Stashes any uncommitted / untracked changes so the pull step can proceed
   cleanly.
4. Pulls from the configured remote (skipped when no remote is configured).
5. Re-applies the stash.
6. Finds the highest `vMAJOR.MINOR.PATCH` tag and increments `PATCH` by one.
   Defaults to `v1.0.0` when no version tags exist.
7. Stages all changes (`git add -A`), commits with the version string as the
   entire commit message (e.g. `v1.2.4`), creates the tag, and pushes.

---

## What it does NOT do

| Feature | Supported? |
|---|---|
| Bump **minor** version (v1.1.0 → v1.2.0) | No |
| Bump **major** version (v1.0.0 → v2.0.0) | No |
| Generate a **changelog** or release notes | No |
| Write a version number into source files | No |
| Create GitHub / GitLab releases | No |
| Honour conventional commits or commit linting | No |

`gitnextver` is intentionally a patch-only tool.  For minor/major bumps,
create the tag manually (`git tag v2.0.0`) and then use `gitnextver` to
manage patch releases going forward.

---

## Usage

```bash
# Bump patch version in the current directory
gitnextver

# Specify a repository path
gitnextver --directory /path/to/repo

# Verbose output (Rich panels + detailed logs)
gitnextver --verbose

# Capture the new version in a script
NEW_VER=$(gitnextver)
echo "Released $NEW_VER"
```

---

## Troubleshooting

### `AssertionError` or `Git index compatibility issue`

**Symptom:** `gitnextver` exits with a message like
*"Git index is format version 3 (GitPython requires ≤ 2)"* or a bare
`AssertionError` from GitPython.

**Cause:** Git 2.20+ and the Xcode Command-Line Tools on macOS can write index
files in format version 3 or 4, which GitPython does not support.  `gitnextver`
detects this automatically and rewrites the index to version 2 before any
GitPython operation.  If the automatic rewrite fails, run:

```bash
git update-index --index-version=2
```

### `index.lock` / "could not write index"

**Symptom:** A stash or reset operation fails with *"could not write index"*.

**Cause:** A stale `index.lock` file was left behind by a previous interrupted
git operation (crash, force-quit, etc.).

**Fix:**

```bash
rm -f .git/index.lock
git reset --mixed
```

Then re-run `gitnextver`.

### No changes to commit

If `gitnextver` prints *"No changes found to commit"*, there is nothing new to
stage.  Add or modify at least one file before running `gitnextver`.

### Merge conflicts after pull

`gitnextver` aborts if the pull results in merge conflicts.  Resolve the
conflicts manually (`git mergetool` or your editor), commit the resolution,
and then re-run `gitnextver`.
