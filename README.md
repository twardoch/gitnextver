# gitnextver

Automatically bump the patch component of a `vX.Y.Z` git tag, commit all
staged changes, and push — one command to cut a release.

## Installation

```bash
pip install gitnextver
```

Or run without installing:

```bash
uvx gitnextver
```

## Usage

```bash
# Bump patch version in the current directory
gitnextver

# Specify a repository path
gitnextver --directory /path/to/repo

# Verbose output
gitnextver --verbose

# Capture the new version in a script
NEW_VER=$(gitnextver)
echo "Released $NEW_VER"
```

## What it does

### Controlled workflows

The original defaults are preserved. Each step can also be controlled:

```sh
# Read-only: no fetch/pull, stash, index rewrite, commit, tag or push
gitnextver --dry-run --initial=v2.1.0

# Tag the existing clean HEAD locally, without pulling or committing
gitnextver --commit=False --pull=False --push=False --initial=v2.1.0

# Choose which component to increment
gitnextver --bump=minor
gitnextver --bump=major
```

`--initial` applies only when there are no canonical `vX.Y.Z` tags. Minor and
major bumps reset smaller components to zero. Host suffixes, prereleases and
leading-zero tags are ignored. Options are validated before any mutations.
Pushes send only the current branch and selected tag, atomically; a rejected
push exits nonzero and retains the local commit/tag for manual recovery.
An atomic push requires a server that supports it. Existing tags are never moved.

For automation that owns Git itself, use the pure API (no Git/network calls):

```python
from gitnextver.versioning import next_version

assert next_version([], initial="v2.1.0") == "v2.1.0"
assert next_version(["v2.1.9"], bump="minor") == "v2.2.0"
```

### Default workflow

1. Validates that the working directory is a git repository.
2. Checks the git index format and rewrites to version 2 if GitPython requires
   it (see [Troubleshooting](#troubleshooting)).
3. Stashes uncommitted/untracked changes so the pull step can proceed.
4. Pulls from the configured remote (skipped when no remote exists).
5. Re-applies the stash.
6. Finds the highest `vMAJOR.MINOR.PATCH` tag, increments `PATCH` by one.
   Defaults to `v1.0.0` when no version tags exist.
7. Stages all changes, commits with the version string as the commit message,
   creates the tag, and pushes.

## What it does NOT do

- Generate a changelog or release notes.
- Write a version number into source files.
- Create GitHub/GitLab releases.
- Honour conventional commits or commit linting.

Use `--bump=minor` or `--bump=major` for larger version changes.

## Troubleshooting

### Git index lock (`could not write index`)

A stale `.git/index.lock` file from a previous interrupted git operation can
block stashing or committing. Fix:

```bash
rm -f .git/index.lock
git reset --mixed
```

### GitPython index version error

Git 2.20+ and the Xcode CLI tools on macOS can write index format version 3
or 4, which GitPython does not support. `gitnextver` detects and rewrites the
index automatically. If the automatic rewrite fails, run:

```bash
git update-index --index-version=2
```

## License

Apache-2.0
