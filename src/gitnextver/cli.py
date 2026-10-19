# this_file: src/gitnextver/cli.py

"""
Git Next Version Tool — bump the patch component of a vX.Y.Z tag and push.

Workflow
--------
1. Validate that the working directory is a git repository.
2. Gate GitPython index compatibility: read the raw binary index header and
   rewrite to version 2 only when the version is > 2 (git ≥ 2.20 or Xcode
   CLI tools can write v3/v4 which GitPython does not support).
3. Stash uncommitted / untracked changes so that the pull step can proceed.
4. Pull from the configured remote (skipped when no remote exists).
5. Re-apply the stash (if one was created in step 3).
6. Find the highest vX.Y.Z tag in the repository, increment the patch
   component, and default to v1.0.0 when no tags exist.
7. Stage all changes (git add -A), commit with the version string as the
   commit message, create an annotated tag, and push both commits and tags.
"""

import re
import sys
from pathlib import Path
from typing import Optional

import fire  # type: ignore
import git
from git.exc import GitCommandError, InvalidGitRepositoryError
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from gitnextver.versioning import next_version

console = Console()

# Pre-compiled regex matching semantic version tags of the form vMAJOR.MINOR.PATCH
VERSION_PATTERN = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")

# Preferred remote name; fall back to any available remote when absent
DEFAULT_REMOTE_NAME = "origin"


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    logger.remove()
    level = "DEBUG" if verbose else "WARNING"
    logger.add(
        sys.stderr,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | <level>{message}</level>"
        ),
        level=level,
    )


def is_git_repo(path: Path) -> bool:
    """Return True when *path* is (inside) a git repository."""
    try:
        git.Repo(path)
        return True
    except InvalidGitRepositoryError:
        return False


def get_last_version_tag(repo: git.Repo) -> Optional[str]:
    """Return the highest vA.B.C tag name, or None when no such tag exists."""
    tags = repo.tags
    version_tags = []

    for tag in tags:
        match = VERSION_PATTERN.match(tag.name)
        if match:
            major, minor, patch = map(int, match.groups())
            version_tags.append((major, minor, patch, tag.name))

    if not version_tags:
        return None

    # Pick the numerically largest (major, minor, patch) triple
    latest = max(version_tags, key=lambda x: (x[0], x[1], x[2]))
    return latest[3]


def calculate_next_version(last_tag: Optional[str]) -> str:
    """Return the next version string by incrementing the patch component.

    Falls back to ``v1.0.0`` when *last_tag* is None or does not match the
    expected ``vMAJOR.MINOR.PATCH`` pattern.
    """
    if not last_tag:
        return "v1.0.0"

    match = VERSION_PATTERN.match(last_tag)
    if not match:
        return "v1.0.0"

    major, minor, patch = map(int, match.groups())
    return f"v{major}.{minor}.{patch + 1}"


def _select_remote(repo: git.Repo) -> Optional[git.Remote]:
    """Return the preferred remote, or *None* if no remotes are configured."""
    remotes = {r.name: r for r in repo.remotes}
    if DEFAULT_REMOTE_NAME in remotes:
        return remotes[DEFAULT_REMOTE_NAME]
    # Fallback: any available remote when 'origin' is absent
    return next(iter(remotes.values())) if remotes else None


def stash_uncommitted_changes(repo: git.Repo) -> bool:
    """Stash any uncommitted (including untracked) changes before a pull.

    Returns True if a stash was created, False otherwise.
    """
    if repo.is_dirty(untracked_files=True) or repo.untracked_files:
        logger.info("Stashing uncommitted changes before pull …")
        try:
            # --include-untracked ensures the working tree is fully clean
            repo.git.stash(
                "push",
                "--include-untracked",
                "-m",
                "gitnextver-auto-stash",
            )
            return True
        except GitCommandError as e:
            if "could not write index" in str(e):
                # Index may be locked from a previous interrupted operation
                logger.warning("Git index appears corrupted, attempting to fix...")
                try:
                    index_lock = Path(repo.git_dir) / "index.lock"
                    if index_lock.exists():
                        index_lock.unlink()
                        logger.info("Removed stale index.lock file")

                    repo.git.reset("--mixed")
                    logger.info("Reset git index")

                    repo.git.stash(
                        "push",
                        "--include-untracked",
                        "-m",
                        "gitnextver-auto-stash",
                    )
                    return True
                except Exception as fix_error:
                    logger.error(f"Failed to fix git index: {fix_error}")
                    console.print(
                        Panel(
                            Text(
                                "Git index is corrupted. Try running:\n"
                                "rm -f .git/index.lock\n"
                                "git reset --mixed",
                                style="bold red",
                            ),
                            title="❌ Git Index Error",
                            border_style="red",
                        )
                    )
                    raise
            else:
                raise
    return False


def apply_latest_stash(repo: git.Repo) -> bool:
    """Apply (pop) the most recent stash if one exists.

    Returns True when the stash is successfully applied (or none existed).
    Returns False when applying the stash leads to merge conflicts or other
    errors that require manual user intervention.
    """
    stash_list = repo.git.stash("list").strip()
    if not stash_list:
        return True

    try:
        logger.info("Re-applying stashed changes …")
        repo.git.stash("pop")
        logger.info("Successfully re-applied stashed changes")
        return True
    except GitCommandError as exc:
        message = str(exc)
        if "CONFLICT" in message.upper():
            logger.error("Applying stash resulted in conflicts")
            console.print(
                Panel(
                    Text(
                        "Applying stashed changes resulted in "
                        "merge conflicts!\n\n"
                        "Please resolve conflicts manually and run the "
                        "command again.",
                        style="bold red",
                    ),
                    title="❌ Merge Conflict",
                    border_style="red",
                )
            )
            return False

        logger.error(f"Failed to apply stash: {exc}")
        console.print(
            Panel(
                Text(f"Failed to apply stash: {exc}", style="bold red"),
                title="❌ Stash Error",
                border_style="red",
            )
        )
        return False


def pull_with_conflict_check(repo: git.Repo) -> bool:
    """Pull from the selected remote and check for merge conflicts.

    Returns True on success, False if a conflict or pull failure occurred.
    If no remote is configured, the function logs a warning and returns
    True (nothing to pull).
    """
    remote = _select_remote(repo)

    if remote is None:
        logger.warning("No git remotes configured – skipping pull step.")
        return True

    try:
        logger.info(f"Pulling from remote '{remote.name}' …")
        remote.pull()
        logger.info("Successfully pulled from remote")
        return True
    except GitCommandError as exc:
        if "CONFLICT" in str(exc).upper():
            logger.error("Git pull resulted in conflicts")
            console.print(
                Panel(
                    Text(
                        "Git pull resulted in merge conflicts!\n\n"
                        "Please resolve conflicts manually and run the "
                        "command again.",
                        style="bold red",
                    ),
                    title="❌ Merge Conflict",
                    border_style="red",
                )
            )
            return False

        logger.error(f"Git pull failed: {exc}")
        console.print(
            Panel(
                Text(f"Git pull failed: {exc}", style="bold red"),
                title="❌ Pull Error",
                border_style="red",
            )
        )
        return False


def _read_index_version(git_dir: str) -> int:
    """Return the git index format version by reading the binary file header.

    Git's on-disk index starts with a 4-byte magic string (``DIRC``) followed
    by a 4-byte big-endian version number.  GitPython's ``IndexFile`` class
    supports only versions 1 and 2.  When it reads a version-3 or version-4
    index it raises an ``AssertionError`` instead of a descriptive exception.

    Version 3 / 4 indexes are written by:
    - git ≥ 2.20 when ``feature.manyFiles = true`` is set in the git config.
    - The Xcode Command-Line Tools on macOS (which may default to a newer
      index format regardless of the ``feature.manyFiles`` flag).

    Reading the raw header lets us gate the downgrade on the actual version
    number, avoiding any interaction with GitPython on the common case where
    the index is already version 2.

    Returns the version number, or 2 (the safe default) when the index file
    does not exist or cannot be parsed.
    """
    index_path = Path(git_dir) / "index"
    if not index_path.exists():
        return 2  # New / empty repository — version 2 is the implicit default
    try:
        with open(index_path, "rb") as fh:
            header = fh.read(8)
        if len(header) >= 8 and header[:4] == b"DIRC":
            return int.from_bytes(header[4:8], "big")
    except OSError:
        pass
    return 2  # Unreadable or unrecognised magic — assume compatible


def ensure_gitpython_compatibility(repo: git.Repo) -> None:
    """Rewrite the git index to version 2 if GitPython cannot parse it.

    Why this exists
    ~~~~~~~~~~~~~~~
    GitPython's ``IndexFile`` hard-codes support for index *format versions
    1 and 2* only (see ``git/index/base.py``).  When it encounters a version-3
    or version-4 index it raises an ``AssertionError`` — not a helpful
    ``UnsupportedOperation`` — which would crash gitnextver with a confusing
    traceback.

    The fix
    ~~~~~~~
    ``git update-index --index-version 2`` rewrites the index file using the
    older encoding.  This is *data-compatible*: all staged files and their
    metadata are preserved; only the on-disk representation changes.

    Why we read the header first
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    By inspecting the raw binary header we can determine the index version
    *before* GitPython touches the file.  When the version is already ≤ 2
    (the overwhelmingly common case) we return immediately with no side
    effects.  The downgrade is performed only when genuinely required.
    """
    index_version = _read_index_version(str(repo.git_dir))
    if index_version <= 2:
        # Already compatible with GitPython — nothing to do.
        return

    # Index version > 2: GitPython will raise AssertionError when it reads it.
    # Rewrite to version 2 (no data loss — only the encoding changes).
    logger.warning(
        f"Git index is format version {index_version} "
        "(GitPython requires version ≤ 2). "
        "Rewriting to version 2 — no staged data will be lost."
    )
    try:
        repo.git.update_index("--index-version", "2")
        logger.info("Git index rewritten to version 2.")
        # Sanity-check: confirm GitPython can now parse the rewritten index.
        _ = repo.index.entries
        logger.info("GitPython index access confirmed after rewrite.")
    except GitCommandError as exc:
        logger.error(f"Failed to rewrite git index: {exc}")
        raise
    except AssertionError as exc:
        # Should not happen after a successful rewrite, but guard defensively.
        logger.error(f"Git index still incompatible after rewrite: {exc}")
        raise


def commit_and_tag(
    repo: git.Repo,
    version: str,
    verbose: bool = False,
    commit: bool = True,
    push: bool = True,
) -> bool:
    """Optionally commit files, tag HEAD, and optionally push exactly that tag.

    Returns True when the commit and tag were created successfully,
    False when there were no changes to commit (nothing to release).
    Calls ``sys.exit(1)`` on unrecoverable git errors.
    """
    try:
        if push and _select_remote(repo) is not None and repo.head.is_detached:
            raise GitCommandError("push", 1, stderr="Cannot push a detached HEAD")
        if not commit and repo.git.status("--porcelain", "--untracked-files=all"):
            raise GitCommandError(
                "tag", 1, stderr="commit=False requires a clean checkout"
            )
        if commit:
            logger.info("Staging all untracked and modified files…")
            repo.git.add(A=True)

        # After staging, check whether the index actually has new content
        if commit and not repo.is_dirty() and not repo.untracked_files:
            logger.warning("No changes to commit")
            if verbose:
                console.print(
                    Panel(
                        Text("No changes found to commit", style="yellow"),
                        title="⚠️  Warning",
                        border_style="yellow",
                    )
                )
            return False

        # Re-check index compatibility after staging (add may update the index)
        if commit:
            ensure_gitpython_compatibility(repo)
            logger.info(f"Committing with message: {version}")
            repo.index.commit(version)

        logger.info(f"Creating tag: {version}")
        repo.create_tag(version)

        remote = _select_remote(repo)
        if not push:
            logger.info("Push disabled; tag retained locally.")
        elif remote is None:
            logger.warning("No remotes configured – skipping push step.")
        else:
            logger.info("Pushing commits and tags to remote…")
            # GitPython's Remote.push can return failed PushInfo without raising.
            # Native git checks its exit status; atomic prevents partial branch/tag
            # publication and the explicit refspec leaves unrelated tags alone.
            branch = repo.active_branch.name
            repo.git.push(
                "--atomic",
                remote.name,
                f"HEAD:refs/heads/{branch}",
                f"refs/tags/{version}:refs/tags/{version}",
            )

        if verbose:
            console.print(
                Panel(
                    Text(
                        f"✅ Successfully created version {version}",
                        style="bold green",
                    ),
                    title="🎉 Success",
                    border_style="green",
                )
            )
        return True

    except GitCommandError as e:
        logger.error(f"Git operation failed: {e}")
        console.print(
            Panel(
                Text(f"Git operation failed: {str(e)}", style="bold red"),
                title="❌ Git Error",
                border_style="red",
            )
        )
        sys.exit(1)


def main(
    directory: Optional[str] = None,
    verbose: bool = False,
    bump: str = "patch",
    initial: str = "v1.0.0",
    dry_run: bool = False,
    pull: bool = True,
    commit: bool = True,
    push: bool = True,
) -> None:
    """Select a semantic tag and optionally commit, tag and push.

    Reads the highest ``vMAJOR.MINOR.PATCH`` tag in *directory*, increments
    the patch component by one, stages all pending changes, commits them using
    the new version string as the commit message, creates the tag, and pushes
    both to the configured remote.  Defaults to ``v1.0.0`` when no version
    tags exist yet.

    When successful the new version string (e.g. ``v1.2.4``) is printed to
    stdout so that callers can capture it::

        NEW_VER=$(gitnextver)

    The function calls ``sys.exit(1)`` on unrecoverable errors (not a git
    repository, merge conflicts, git command failures).

    Args:
        directory: Path to the git repository root.  Defaults to the current
            working directory when *None* or omitted.
        verbose: When True, emit Rich-formatted progress panels to the console
            in addition to the loguru log stream.
        bump: Version component to increment: patch, minor or major.
        initial: First tag when no canonical stable tags exist.
        dry_run: Print the next tag without index, stash, network or ref changes.
        pull: Enable the legacy stash/pull/restore step. Disable for local use.
        commit: Stage/commit pending work. False requires a clean checkout and
            tags the existing HEAD without rewriting the index.
        push: Push the current branch and selected tag atomically. False keeps
            both local; it does not implicitly disable pull.

    Returns:
        None.  The new version string is printed to stdout on success.
    """
    # Validate options before any index, stash, network or ref mutations.
    next_version([], bump=bump, initial=initial)
    setup_logging(verbose)

    work_dir = Path(directory).resolve() if directory else Path.cwd().resolve()
    logger.info(f"Working in directory: {work_dir}")

    if not is_git_repo(work_dir):
        console.print(
            Panel(
                Text(
                    f"Directory {work_dir} is not a git repository!",
                    style="bold red",
                ),
                title="❌ Not a Git Repository",
                border_style="red",
            )
        )
        sys.exit(1)

    repo = git.Repo(work_dir)

    if dry_run:
        print(next_version((tag.name for tag in repo.tags), bump, initial))
        return
    if not commit and repo.git.status("--porcelain", "--untracked-files=all"):
        logger.error("commit=False requires a clean checkout; no files were stashed")
        sys.exit(1)

    # Check index compatibility before any GitPython index access.
    # This must run early; if the index version is > 2 and we let GitPython
    # read it first, it raises an AssertionError with no useful message.
    try:
        if commit:
            ensure_gitpython_compatibility(repo)
    except Exception as e:
        logger.error(f"Failed to ensure GitPython compatibility: {e}")
        console.print(
            Panel(
                Text(
                    f"Git index compatibility issue: {e}\n\n"
                    "This may be due to a newer git index version. "
                    "Try running: git update-index --index-version=2",
                    style="bold red",
                ),
                title="❌ Git Index Error",
                border_style="red",
            )
        )
        sys.exit(1)

    had_stash = stash_uncommitted_changes(repo) if pull else False

    if pull and not pull_with_conflict_check(repo):
        if had_stash:
            try:
                repo.git.stash("pop")
            except GitCommandError:
                pass
        sys.exit(1)

    if had_stash and not apply_latest_stash(repo):
        sys.exit(1)

    last_tag = get_last_version_tag(repo)
    logger.info(f"Last version tag: {last_tag if last_tag else 'None found'}")

    new_version = next_version((tag.name for tag in repo.tags), bump, initial)
    logger.info(f"Next version: {new_version}")

    if verbose:
        console.print(
            Panel(
                Text(
                    f"Current version: {last_tag if last_tag else 'None'}\n"
                    f"Next version: {new_version}",
                    style="bold blue",
                ),
                title="📋 Version Info",
                border_style="blue",
            )
        )

    if commit_and_tag(repo, new_version, verbose, commit=commit, push=push):
        print(new_version)


def app() -> None:
    """CLI entry point for gitnextver."""
    fire.Fire(main)


if __name__ == "__main__":
    app()
