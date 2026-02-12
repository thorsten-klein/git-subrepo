"""Tests for git subrepo branch --all command"""
import subprocess
from conftest import (
    assert_exists
)


def test_branch_all(env):
    """Test commands work using --all flag"""
    env.clone_foo_and_bar()

    # Clone two subrepos
    subprocess.run(
        ['git', 'subrepo', 'clone', '--quiet', str(env.upstream / 'bar'), 'one'],
        cwd=env.owner / 'foo',
        check=True,
        capture_output=True
    )
    subprocess.run(
        ['git', 'subrepo', 'clone', '--quiet', str(env.upstream / 'bar'), 'two'],
        cwd=env.owner / 'foo',
        check=True,
        capture_output=True
    )
    env.add_new_files('two/file', cwd=env.owner / 'foo')

    # Branch all (should work even when a subrepo has no new commits)
    result = subprocess.run(
        ['git', 'subrepo', 'branch', '--all'],
        cwd=env.owner / 'foo',
        capture_output=True,
        text=True,
        check=True
    )

    assert result.returncode == 0, "branch command works with --all even when a subrepo has no new commits"

    # Check that subrepo/two branch exists
    result = subprocess.run(
        ['git', 'branch', '--list', 'subrepo/two'],
        cwd=env.owner / 'foo',
        capture_output=True,
        text=True,
        check=True
    )
    assert result.stdout.strip() != '', "The 'subrepo/two' branch exists"

    # Check worktree exists
    assert_exists(env.owner / 'foo' / '.git' / 'tmp' / 'subrepo' / 'two', should_exist=True)

    # Check that subrepo/one branch exists
    result = subprocess.run(
        ['git', 'branch', '--list', 'subrepo/one'],
        cwd=env.owner / 'foo',
        capture_output=True,
        text=True,
        check=True
    )
    assert result.stdout.strip() != '', "The 'subrepo/one' branch exists"

    # Check worktree exists
    assert_exists(env.owner / 'foo' / '.git' / 'tmp' / 'subrepo' / 'one', should_exist=True)
