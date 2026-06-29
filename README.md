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

- Bump **minor** or **major** version components — patch only.
- Generate a changelog or release notes.
- Write a version number into source files.
- Create GitHub/GitLab releases.
- Honour conventional commits or commit linting.

For minor/major bumps, create the tag manually (`git tag v2.0.0`) and then
use `gitnextver` for subsequent patch releases.

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
