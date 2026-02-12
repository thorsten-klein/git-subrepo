"""Tests for git subrepo pull twice"""

import subprocess
from conftest import assert_file_exists


def test_pull_twice(env):
    """Test pulling subrepo twice in succession"""
    env.clone_foo_and_bar()
    env.subrepo_clone_bar_into_foo()

    # Add new file to bar and push
    env.add_new_files('Bar2', cwd=env.owner / 'bar')
    subprocess.run(
        ['git', 'push'], cwd=env.owner / 'bar', check=True, capture_output=True
    )

    # Make changes in foo and pull
    env.add_new_files('bar/Foo2', cwd=env.owner / 'foo')
    subprocess.run(
        ['git', 'push'], cwd=env.owner / 'foo', check=True, capture_output=True
    )
    subprocess.run(
        ['git', 'subrepo', 'pull', 'bar'],
        cwd=env.owner / 'foo',
        check=True,
        capture_output=True,
    )

    # Add another file to bar and push
    env.add_new_files('Bar3', cwd=env.owner / 'bar')
    subprocess.run(
        ['git', 'push'], cwd=env.owner / 'bar', check=True, capture_output=True
    )

    # Pull again
    subprocess.run(
        ['git', 'subrepo', 'pull', 'bar'],
        cwd=env.owner / 'foo',
        check=True,
        capture_output=True,
    )

    # Check all files exist
    assert_file_exists(env.owner / 'foo' / 'bar' / 'Bar2')
    assert_file_exists(env.owner / 'foo' / 'bar' / 'Bar3')
    assert_file_exists(env.owner / 'foo' / 'bar' / 'Foo2')
