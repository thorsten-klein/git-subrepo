"""Tests for git subrepo push --force"""

import subprocess
from conftest import assert_exists, git_subrepo


def test_push_force(env):
    """Test subrepo push with --force flag"""
    env.clone_foo_and_bar()
    env.subrepo_clone_bar_into_foo()

    # Add new file to bar and push
    env.add_new_files('Bar2', cwd=env.owner / 'bar')
    subprocess.run(
        ['git', 'push'], cwd=env.owner / 'bar', check=True, capture_output=True
    )

    # Add file in foo and force push
    env.add_new_files('bar/Foo1', cwd=env.owner / 'foo')
    git_subrepo('push bar --force', cwd=env.owner / 'foo')

    # Pull in foo
    git_subrepo('pull bar', cwd=env.owner / 'foo')

    # Check that Foo1 exists but Bar2 doesn't (because we force pushed)
    assert_exists(env.owner / 'foo' / 'bar' / 'Foo1', should_exist=True)
    assert_exists(env.owner / 'foo' / 'bar' / 'Bar2', should_exist=False)

    # Pull in bar (will actually merge the old master with the new one)
    subprocess.run(
        ['git', 'pull', '--rebase=false'],
        cwd=env.owner / 'bar',
        check=True,
        capture_output=True,
    )

    # After merge, both files should exist
    assert_exists(env.owner / 'bar' / 'Bar2', should_exist=True)
    assert_exists(env.owner / 'bar' / 'Foo1', should_exist=True)

    # Test that a fresh repo is not contaminated
    new_bar_dir = env.owner / 'newbar'
    subprocess.run(
        ['git', 'clone', str(env.upstream / 'bar'), str(new_bar_dir)],
        check=True,
        capture_output=True,
    )

    # Fresh clone should only have Foo1, not Bar2
    assert_exists(new_bar_dir / 'Foo1', should_exist=True)
    assert_exists(new_bar_dir / 'Bar2', should_exist=False)
