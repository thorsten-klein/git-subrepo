"""Tests for git subrepo with rebase"""

import subprocess
from conftest import git_subrepo, assert_output_like


def test_rebase(env):
    """Test subrepo operations after rebase"""
    # Setup foo with 2 branches, one before the subrepo
    # is added and one after so that we can rebase
    # thus destroying the parent in two ways
    env.clone_foo_and_bar()

    # Create branch1, add file, clone subrepo, create branch2, add file
    subprocess.run(
        ['git', 'switch', '-c', 'branch1'],
        cwd=env.owner / 'foo',
        check=True,
        capture_output=True,
    )
    env.add_new_files('foo1', cwd=env.owner / 'foo')
    env.subrepo_clone_bar_into_foo()

    subprocess.run(
        ['git', 'branch', 'branch2'],
        cwd=env.owner / 'foo',
        check=True,
        capture_output=True,
    )
    env.add_new_files('foo2', cwd=env.owner / 'foo')

    # Add new file in bar and push
    env.add_new_files('bar2', cwd=env.owner / 'bar')
    subprocess.run(
        ['git', 'push'], cwd=env.owner / 'bar', check=True, capture_output=True
    )

    # Pull subrepo
    git_subrepo('pull bar', cwd=env.owner / 'foo')

    # Rebase branch1 onto branch2
    subprocess.run(
        ['git', 'switch', 'branch2'],
        cwd=env.owner / 'foo',
        check=True,
        capture_output=True,
    )
    env.add_new_files('foo-branch2', cwd=env.owner / 'foo')

    subprocess.run(
        ['git', 'switch', 'branch1'],
        cwd=env.owner / 'foo',
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'rebase', 'branch2'],
        cwd=env.owner / 'foo',
        check=True,
        capture_output=True,
    )

    # Force subrepo to search for the parent SHA
    # Validate it found the previous merge point
    git_subrepo('clean --force --all', cwd=env.owner / 'foo')
    output = env.catch('git subrepo branch bar', cwd=env.owner / 'foo')

    assert_output_like(output, 'caused by a rebase', "subrepo detected merge point")
