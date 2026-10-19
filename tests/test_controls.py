# this_file: tests/test_controls.py
"""Non-mutating selection and explicit release controls on owned repositories."""

from unittest.mock import Mock

import git
import pytest

from gitnextver.cli import main
from gitnextver.versioning import next_version
from tests.test_gitnextver import make_repo


@pytest.mark.parametrize(
    ("tags", "bump", "initial", "expected"),
    [
        ([], "patch", "v2.1.0", "v2.1.0"),
        (["v2.0.5-Py3.10"], "minor", "v2.1.0", "v2.1.0"),
        (["v1.9.9", "v1.10.1"], "patch", "v1.0.0", "v1.10.2"),
        (["v2.1.9"], "minor", "v1.0.0", "v2.2.0"),
        (["v2.1.9"], "major", "v1.0.0", "v3.0.0"),
        (["v0.0.0"], "patch", "v1.0.0", "v0.0.1"),
        (["v01.2.3", "v2.1.0rc1", "v9.8.7\n"], "patch", "v2.1.0", "v2.1.0"),
    ],
)
def test_next_version_selects_numeric_stable_tags(tags, bump, initial, expected):
    assert next_version(tags, bump=bump, initial=initial) == expected


@pytest.mark.parametrize(("bump", "initial"), [("oops", "v1.0.0"), ("patch", "bad")])
def test_invalid_options_fail_before_mutation(bump, initial):
    with pytest.raises(ValueError):
        next_version([], bump=bump, initial=initial)


def test_dry_run_preserves_dirty_index_stash_and_refs(tmp_path, monkeypatch, capsys):
    repo = make_repo(tmp_path)
    (tmp_path / "new.txt").write_text("pending")
    before = repo.git.status("--porcelain"), repo.head.commit.hexsha
    monkeypatch.setattr(
        "gitnextver.cli.ensure_gitpython_compatibility",
        Mock(side_effect=AssertionError),
    )
    monkeypatch.setattr(
        "gitnextver.cli.pull_with_conflict_check", Mock(side_effect=AssertionError)
    )
    main(str(tmp_path), dry_run=True, initial="v2.1.0")
    assert capsys.readouterr().out.strip() == "v2.1.0"
    assert before == (repo.git.status("--porcelain"), repo.head.commit.hexsha)
    assert not repo.tags and not repo.git.stash("list")


def test_tag_only_does_not_commit_pull_or_push(tmp_path, monkeypatch, capsys):
    repo = make_repo(tmp_path)
    before = repo.head.commit.hexsha
    monkeypatch.setattr(
        "gitnextver.cli.stash_uncommitted_changes", Mock(side_effect=AssertionError)
    )
    main(str(tmp_path), commit=False, pull=False, push=False, initial="v2.1.0")
    assert repo.head.commit.hexsha == before
    assert repo.tags["v2.1.0"].commit.hexsha == before
    assert capsys.readouterr().out.strip() == "v2.1.0"


def test_tag_only_refuses_dirty_tree_without_stashing(tmp_path):
    repo = make_repo(tmp_path)
    (tmp_path / "pending.txt").write_text("pending")
    with pytest.raises(SystemExit):
        main(str(tmp_path), commit=False, pull=False, push=False)
    assert not repo.tags and not repo.git.stash("list")
    assert (tmp_path / "pending.txt").read_text() == "pending"


def test_no_push_does_not_contact_remote(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    repo.create_remote("origin", str(tmp_path / "unreachable.git"))
    (tmp_path / "pending.txt").write_text("pending")
    main(str(tmp_path), pull=False, push=False)
    assert repo.tags["v1.0.0"].commit == repo.head.commit


def test_push_rejection_is_failure_and_does_not_push_other_tags(tmp_path):
    remote = git.Repo.init(tmp_path / "remote.git", bare=True)
    repo = make_repo(tmp_path / "repo")
    repo.create_remote("origin", str(remote.git_dir))
    branch = repo.active_branch.name
    repo.git.push("origin", f"HEAD:refs/heads/{branch}")
    # Another clone advances the remote, making our later push non-fast-forward.
    other = git.Repo.clone_from(str(remote.git_dir), tmp_path / "other")
    with other.config_writer() as config:
        config.set_value("user", "name", "Test")
        config.set_value("user", "email", "test@example.com")
    (tmp_path / "other/advance.txt").write_text("remote advance")
    other.git.add(A=True)
    other.git.commit("-m", "advance")
    other.git.push("origin", branch)
    repo.create_tag("unrelated-local-tag")
    (tmp_path / "repo/change.txt").write_text("local change")
    with pytest.raises(SystemExit):
        main(str(tmp_path / "repo"), pull=False)
    assert not remote.tags, "Rejected atomic push must not publish any tag"


def test_successful_push_sends_only_selected_tag(tmp_path):
    remote = git.Repo.init(tmp_path / "remote.git", bare=True)
    repo = make_repo(tmp_path / "repo")
    repo.create_remote("origin", str(remote.git_dir))
    repo.create_tag("unrelated-local-tag")
    (tmp_path / "repo/change.txt").write_text("local change")
    main(str(tmp_path / "repo"), pull=False, initial="v2.1.0")
    assert [tag.name for tag in remote.tags] == ["v2.1.0"]
    assert remote.tags["v2.1.0"].commit.hexsha == repo.head.commit.hexsha
