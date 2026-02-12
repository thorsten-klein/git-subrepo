"""Tests for git subrepo pull with worktree"""

import subprocess
from conftest import assert_output_matches


def test_pull_worktree(env):
    """Test subrepo pull with git worktree"""
    env.clone_foo_and_bar()

    # Clone bar subrepo and create worktree
    subprocess.run(
        ['git', 'subrepo', 'clone', '../bar', 'bar'],
        cwd=env.owner / 'foo',
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'worktree', 'add', '-b', 'test', '../wt'],
        cwd=env.owner / 'foo',
        check=True,
        capture_output=True,
    )

    # Modify bar
    env.modify_files('Bar', cwd=env.owner / 'bar')

    # Pull from worktree
    subprocess.run(
        ['git', 'subrepo', 'pull', '--all'],
        cwd=env.owner / 'wt',
        check=True,
        capture_output=True,
    )

    # Merge into foo
    subprocess.run(
        ['git', 'merge', 'test'], cwd=env.owner / 'foo', check=True, capture_output=True
    )

    # Check that bar was updated
    bar_content = (env.owner / 'foo' / 'bar' / 'Bar').read_text()
    assert_output_matches(bar_content.strip(), 'a new line', 'bar/Bar content correct')
