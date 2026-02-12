"""Tests for git subrepo push --squash"""

import subprocess
from conftest import (
    assert_exists,
    assert_commit_count,
    git_subrepo,
    assert_output_matches,
)


def test_push_squash(env):
    """Test subrepo push with --squash flag"""
    env.clone_foo_and_bar()

    # Clone the subrepo into a subdir
    git_subrepo(f'clone {env.upstream}/bar', cwd=env.owner / 'foo')

    # Make a series of commits
    env.add_new_files('bar/FooBar1', cwd=env.owner / 'foo')
    env.add_new_files('bar/FooBar2', cwd=env.owner / 'foo')
    env.modify_files('bar/FooBar1', cwd=env.owner / 'foo')
    env.add_new_files('./FooBar', cwd=env.owner / 'foo')
    env.modify_files('./FooBar', 'bar/FooBar2', cwd=env.owner / 'foo')

    # Do the subrepo push with --squash
    result = git_subrepo('push bar --squash', cwd=env.owner / 'foo')

    assert_output_matches(
        result.stdout.strip(),
        f"Subrepo 'bar' pushed to '{env.upstream}/bar' (master).",
        'push message is correct',
    )

    # Pull in bar
    subprocess.run(
        ['git', 'pull'], cwd=env.owner / 'bar', check=True, capture_output=True
    )

    # Check that all commits arrived in subrepo (squashed to 1 commit + initial 2)
    assert_commit_count(env.owner / 'bar', 'HEAD', 3)

    # Check files exist
    assert_exists(env.owner / 'bar' / 'Bar', should_exist=True)
    assert_exists(env.owner / 'bar' / 'FooBar1', should_exist=True)
    assert_exists(env.owner / 'bar' / 'FooBar2', should_exist=True)
    assert_exists(env.owner / 'bar' / '.gitrepo', should_exist=False)
