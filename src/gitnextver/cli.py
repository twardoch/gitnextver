# this_file: src/gitnextver/cli.py

"""
Git Next Version Tool - Automatically bump version tags and commit changes.

This tool:
1. Checks if we're in a git repo
2. Pulls from remote repo
3. Handles conflicts gracefully
4. Determines next version tag based on existing tags
5. Commits all changes with version tag
6. Creates and pushes the new tag
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

console = Console()

# Pre-compiled regex to match semantic version tags like v1.2.3
VERSION_PATTERN = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")

# Friendly default remote name
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
    """Check if the given path is a git repository."""
    try:
        git.Repo(path)
        return True
    except InvalidGitRepositoryError:
        return False


def get_last_version_tag(repo: git.Repo) -> Optional[str]:
    """Get the last version tag in vA.B.C format."""
    tags = repo.tags
    version_tags = []

    for tag in tags:
        match = VERSION_PATTERN.match(tag.name)
        if match:
            major, minor, patch = map(int, match.groups())
            version_tags.append((major, minor, patch, tag.name))

    if not version_tags:
        return None

    # Pick the tag with the highest numerical value
    latest = max(version_tags, key=lambda x: (x[0], x[1], x[2]))
    return latest[3]


def calculate_next_version(last_tag: Optional[str]) -> str:
    """Calculate the next version tag."""
    if not last_tag:
        return "v1.0.0"

    match = VERSION_PATTERN.match(last_tag)

    if not match:
        return "v1.0.0"

    major, minor, patch = map(int, match.groups())
    return f"v{major}.{minor}.{patch + 1}"


def _select_remote(repo: git.Repo):
    """Return a remote to interact with, or *None* if no remotes exist."""
    remotes = {r.name: r for r in repo.remotes}
    if DEFAULT_REMOTE_NAME in remotes:
        return remotes[DEFAULT_REMOTE_NAME]
    # Fallback to any remote if 'origin' is missing
    return next(iter(remotes.values())) if remotes else None


def stash_uncommitted_changes(repo: git.Repo) -> bool:
    """Stash any uncommitted (including untracked) changes before a pull.

    Returns True if a stash was created, False otherwise.
    """
    if repo.is_dirty(untracked_files=True) or repo.untracked_files:
        logger.info("Stashing uncommitted changes before pull …")
        try:
            # Include untracked files to ensure a clean working tree
            repo.git.stash(
                "push",
                "--include-untracked",
                "-m",
                "gitnextver-auto-stash",
            )
            return True
        except GitCommandError as e:
            if "could not write index" in str(e):
                # Try to fix index corruption
                logger.warning("Git index appears corrupted, attempting to fix...")
                try:
                    # Remove index lock if it exists
                    index_lock = Path(repo.git_dir) / "index.lock"
                    if index_lock.exists():
                        index_lock.unlink()
                        logger.info("Removed stale index.lock file")

                    # Reset the index
                    repo.git.reset("--mixed")
                    logger.info("Reset git index")

                    # Try stash again
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
        # Nothing to apply
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


def ensure_gitpython_compatibility(repo: git.Repo) -> None:
    """Ensure git index is compatible with GitPython by downgrading if needed."""
    try:
        # Test if GitPython can read the index
        _ = repo.index.entries
    except AssertionError as e:
        # The AssertionError from GitPython index version incompatibility
        logger.warning(f"Git index version incompatible with GitPython: {e}")
        logger.warning("Attempting to downgrade git index to version 2...")
        try:
            # Downgrade index to version 2 (compatible with GitPython)
            repo.git.update_index("--index-version", "2")
            logger.info("Successfully downgraded git index to version 2")

            # Verify the fix worked by testing index access again
            _ = repo.index.entries
            logger.info("GitPython can now access the git index")
        except GitCommandError as downgrade_error:
            logger.error(f"Failed to downgrade git index: {downgrade_error}")
            raise
        except Exception as verify_error:
            logger.error(f"Git index still incompatible after downgrade: {verify_error}")
            raise


def commit_and_tag(
    repo: git.Repo,
    version: str,
    verbose: bool = False,
) -> bool:
    """Add all files, commit, create tag, and push."""
    try:
        # Add all untracked and modified files
        logger.info("Adding all untracked and modified files...")
        repo.git.add(A=True)

        # Check if there are any changes to commit
        if not repo.is_dirty() and not repo.untracked_files:
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

        # Ensure GitPython compatibility before committing
        ensure_gitpython_compatibility(repo)

        # Commit with version as message
        logger.info(f"Committing changes with message: {version}")
        repo.index.commit(version)

        # Create tag
        logger.info(f"Creating tag: {version}")
        repo.create_tag(version)

        # Push commits and tags
        logger.info("Pushing commits and tags to remote...")
        remote = _select_remote(repo)
        if remote is None:
            logger.warning("No remotes configured – skipping push step.")
        else:
            remote.push()
            remote.push(tags=True)

        if verbose:
            console.print(
                Panel(
                    Text(
                        f"✅ Successfully created and pushed version {version}",
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


def main(directory: Optional[str] = None, verbose: bool = False) -> None:
    """
    Main function to handle git version tagging.

    Args:
        directory: Directory to work in (defaults to current directory)
        verbose: Enable verbose logging
    """
    setup_logging(verbose)

    # Determine working directory
    work_dir = Path(directory) if directory else Path.cwd()
    work_dir = work_dir.resolve()

    logger.info(f"Working in directory: {work_dir}")

    # Check if it's a git repository
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

    # Initialize git repo object
    repo = git.Repo(work_dir)

    # Ensure git index is compatible with GitPython early on
    try:
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

    # If there are local changes, stash them so that pull can proceed safely
    had_stash = stash_uncommitted_changes(repo)

    # Pull from remote
    if not pull_with_conflict_check(repo):
        # If pull failed and we created a stash, attempt to restore it so the
        # user does not lose their work (even though they may need to resolve
        # issues manually afterwards).
        if had_stash:
            try:
                repo.git.stash("pop")
            except GitCommandError:
                # If even restoring fails we still proceed to exit – the user
                # has to handle the situation manually.
                pass
        sys.exit(1)

    # Re-apply stashed changes (if any)
    if had_stash and not apply_latest_stash(repo):
        sys.exit(1)

    # Get last version tag
    last_tag = get_last_version_tag(repo)
    logger.info(f"Last version tag: {last_tag if last_tag else 'None found'}")

    # Calculate next version
    next_version = calculate_next_version(last_tag)
    logger.info(f"Next version will be: {next_version}")

    if verbose:
        console.print(
            Panel(
                Text(
                    f"Current version: {last_tag if last_tag else 'None'}\n"
                    f"Next version: {next_version}",
                    style="bold blue",
                ),
                title="📋 Version Info",
                border_style="blue",
            )
        )

    # Commit and tag
    if commit_and_tag(repo, next_version, verbose):
        print(next_version)


def app() -> None:
    """CLI entry point for gitnextver."""
    fire.Fire(main)


if __name__ == "__main__":
    app()
