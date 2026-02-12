"""Tests for git subrepo branch with rev-list"""

import subprocess
from conftest import assert_exists, git_subrepo, assert_output_matches


def test_branch_rev_list(env):
    """Test branch command with complex merge history"""
    env.clone_foo_and_bar()
    env.subrepo_clone_bar_into_foo()

    # Create a complex merge scenario
    branchpoint = subprocess.run(
        ['git', 'rev-parse', 'HEAD'],
        cwd=env.owner / 'foo',
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    env.add_new_files('bar/file1', cwd=env.owner / 'foo')
    # Push here to force subrepo to handle histories where it's not first parent
    git_subrepo('push bar', cwd=env.owner / 'foo')

    env.add_new_files('bar/file2', cwd=env.owner / 'foo')

    subprocess.run(
        ['git', 'checkout', '-b', 'other', branchpoint],
        cwd=env.owner / 'foo',
        check=True,
        capture_output=True,
    )
    env.add_new_files('bar/file3', cwd=env.owner / 'foo')
    env.add_new_files('bar/file4', cwd=env.owner / 'foo')
    env.add_new_files('bar/file5', cwd=env.owner / 'foo')

    subprocess.run(
        ['git', 'merge', 'master'],
        cwd=env.owner / 'foo',
        check=True,
        capture_output=True,
    )

    # Check files exist
    assert_exists(env.owner / 'foo' / 'bar' / 'file1', should_exist=True)
    assert_exists(env.owner / 'foo' / 'bar' / 'file2', should_exist=True)
    assert_exists(env.owner / 'foo' / 'bar' / 'file3', should_exist=True)
    assert_exists(env.owner / 'foo' / 'bar' / 'file4', should_exist=True)
    assert_exists(env.owner / 'foo' / 'bar' / 'file5', should_exist=True)

    # -F is needed for branch to fetch new information
    result = git_subrepo('-F branch bar', cwd=env.owner / 'foo')

    assert_output_matches(
        result.stdout.strip(),
        "Created branch 'subrepo/bar' and worktree '.git/tmp/subrepo/bar'.",
        "subrepo branch command output is correct",
    )

    # Count commits
    commit_count = (
        subprocess
        .run(
            ['git', 'rev-list', 'subrepo/bar'],
            cwd=env.owner / 'foo',
            capture_output=True,
            text=True,
            check=True,
        )
        .stdout.strip()
        .split('\n')
    )

    assert len(commit_count) == 5, "We have only created commits for one of the paths"
