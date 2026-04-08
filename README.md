# gitnextver

Automatically bump semantic version tags in Git repositories.

## Installation

```
pip install gitnextver
```

Or run directly:

```
uvx gitnextver
```

## Usage

```bash
# Bump patch version in current directory
gitnextver

# Specify directory
gitnextver --directory /path/to/repo

# Verbose output
gitnextver --verbose
```

## What it does

1. Validates you're in a git repository
2. Stashes uncommitted changes
3. Pulls from remote with conflict detection
4. Re-applies stashed changes
5. Finds the latest `vX.Y.Z` tag and increments the patch version
6. Commits all changes, creates the tag, and pushes

Defaults to `v1.0.0` if no version tags exist.

## License

Apache-2.0
