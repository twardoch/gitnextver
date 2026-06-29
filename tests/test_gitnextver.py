# this_file: tests/test_gitnextver.py

"""Tests for gitnextver CLI.

These tests create throwaway git repositories in pytest's tmp_path fixture
so they never touch or modify the real repository.
"""

from pathlib import Path

import git
import pytest

from gitnextver.cli import (
    _read_index_version,
    calculate_next_version,
    get_last_version_tag,
    main,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_repo(tmp_path: Path) -> git.Repo:
    """Initialise a git repo with a single committed file.

    The repo has no remotes configured, so gitnextver's pull/push steps are
    silently skipped during tests.
    """
    repo = git.Repo.init(tmp_path)
    with repo.config_writer() as cw:
        cw.set_value("user", "name", "Test User")
        cw.set_value("user", "email", "test@example.com")
    (tmp_path / "README.md").write_text("# Test repo\n")
    repo.index.add(["README.md"])
    repo.index.commit("initial commit")
    return repo


# ---------------------------------------------------------------------------
# Unit tests: calculate_next_version
# ---------------------------------------------------------------------------


class TestCalculateNextVersion:
    def test_returns_v1_0_0_when_no_last_tag(self):
        assert calculate_next_version(None) == "v1.0.0"

    def test_increments_patch_component(self):
        assert calculate_next_version("v1.2.3") == "v1.2.4"

    def test_increments_patch_zero(self):
        assert calculate_next_version("v0.0.0") == "v0.0.1"

    def test_does_not_change_major_or_minor(self):
        result = calculate_next_version("v3.7.99")
        assert result == "v3.7.100"

    def test_invalid_tag_falls_back_to_v1_0_0(self):
        assert calculate_next_version("not-a-version") == "v1.0.0"

    def test_non_vprefix_tag_falls_back(self):
        assert calculate_next_version("1.2.3") == "v1.0.0"


# ---------------------------------------------------------------------------
# Unit tests: get_last_version_tag
# ---------------------------------------------------------------------------


class TestGetLastVersionTag:
    def test_returns_none_when_no_tags(self, tmp_path):
        repo = make_repo(tmp_path)
        assert get_last_version_tag(repo) is None

    def test_returns_single_tag(self, tmp_path):
        repo = make_repo(tmp_path)
        repo.create_tag("v1.0.0")
        assert get_last_version_tag(repo) == "v1.0.0"

    def test_returns_highest_tag_when_multiple_exist(self, tmp_path):
        repo = make_repo(tmp_path)
        for tag in ("v1.0.0", "v1.0.2", "v1.0.1"):
            repo.create_tag(tag)
        assert get_last_version_tag(repo) == "v1.0.2"

    def test_ignores_non_semver_tags(self, tmp_path):
        repo = make_repo(tmp_path)
        repo.create_tag("release")
        repo.create_tag("1.0.0")  # missing v prefix
        assert get_last_version_tag(repo) is None

    def test_handles_mixed_tags(self, tmp_path):
        repo = make_repo(tmp_path)
        repo.create_tag("latest")
        repo.create_tag("v2.0.0")
        assert get_last_version_tag(repo) == "v2.0.0"


# ---------------------------------------------------------------------------
# Unit tests: _read_index_version
# ---------------------------------------------------------------------------


class TestReadIndexVersion:
    def test_returns_2_when_index_missing(self, tmp_path):
        # tmp_path has no .git/index — safe fallback is 2
        assert _read_index_version(str(tmp_path)) == 2

    def test_returns_valid_version_for_real_repo(self, tmp_path):
        repo = make_repo(tmp_path)  # creates a commit → index file exists
        version = _read_index_version(str(repo.git_dir))
        # Standard git writes version 2; some configurations may write 3 or 4
        assert version in (1, 2, 3, 4)


# ---------------------------------------------------------------------------
# Integration tests: main()
# ---------------------------------------------------------------------------


class TestMain:
    """Integration tests that exercise the full main() workflow.

    Each test uses an isolated throwaway repository (no remote) so gitnextver's
    pull and push steps are skipped gracefully.
    """

    def test_creates_v1_0_0_from_untagged_repo(self, tmp_path):
        """main() creates tag v1.0.0 when no version tags exist."""
        make_repo(tmp_path)
        # An untracked file gives main() something to stage and commit
        (tmp_path / "feature.txt").write_text("new content\n")

        main(directory=str(tmp_path))

        fresh = git.Repo(tmp_path)
        assert "v1.0.0" in [t.name for t in fresh.tags]

    def test_bumps_patch_when_tag_exists(self, tmp_path):
        """main() increments the patch component of the latest vX.Y.Z tag."""
        repo = make_repo(tmp_path)
        repo.create_tag("v2.3.4")
        (tmp_path / "update.txt").write_text("update\n")

        main(directory=str(tmp_path))

        fresh = git.Repo(tmp_path)
        assert "v2.3.5" in [t.name for t in fresh.tags]

    def test_picks_highest_existing_tag(self, tmp_path):
        """main() uses the numerically highest tag, not the most recent."""
        repo = make_repo(tmp_path)
        repo.create_tag("v1.0.9")
        repo.create_tag("v1.0.3")
        (tmp_path / "change.txt").write_text("change\n")

        main(directory=str(tmp_path))

        fresh = git.Repo(tmp_path)
        assert "v1.0.10" in [t.name for t in fresh.tags]

    def test_exits_when_directory_is_not_a_repo(self, tmp_path):
        """main() calls sys.exit(1) for a non-repository directory."""
        non_repo = tmp_path / "not_a_repo"
        non_repo.mkdir()
        with pytest.raises(SystemExit) as exc_info:
            main(directory=str(non_repo))
        assert exc_info.value.code == 1
