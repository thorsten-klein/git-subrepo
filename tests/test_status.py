"""Tests for git subrepo status command"""
import subprocess
from conftest import (
    assert_output_like, assert_output_unlike
)


def test_status(env):
    """Test subrepo status command with nested subrepos"""
    env.clone_foo_and_bar()

    # Clone multiple subrepos, including nested ones
    subprocess.run(
        ['git', 'subrepo', 'clone', str(env.upstream / 'bar')],
        cwd=env.owner / 'foo',
        check=True,
        capture_output=True
    )
    subprocess.run(
        ['git', 'subrepo', 'clone', str(env.upstream / 'foo'), 'bar/foo'],
        cwd=env.owner / 'foo',
        check=True,
        capture_output=True
    )
    (env.owner / 'foo' / 'lib').mkdir()
    subprocess.run(
        ['git', 'subrepo', 'clone', str(env.upstream / 'bar'), 'lib/bar'],
        cwd=env.owner / 'foo',
        check=True,
        capture_output=True
    )
    subprocess.run(
        ['git', 'subrepo', 'clone', str(env.upstream / 'foo'), 'lib/bar/foo'],
        cwd=env.owner / 'foo',
        check=True,
        capture_output=True
    )

    # Test status --all (non-recursive)
    result = subprocess.run(
        ['git', 'subrepo', 'status', '--all'],
        cwd=env.owner / 'foo',
        capture_output=True,
        text=True,
        check=True
    )
    output = result.stdout

    assert_output_like(output, '2 subrepos:', "'status' intro ok")
    assert_output_like(output, "Git subrepo 'bar':", "bar is in 'status'")
    assert_output_like(output, "Git subrepo 'lib/bar':", "lib/bar is in 'status'")
    assert_output_unlike(output, "Git subrepo 'bar/foo':", "bar/foo is not in 'status'")
    assert_output_unlike(output, "Git subrepo 'lib/bar/foo':", "lib/bar/foo is not in 'status'")

    # Test status --ALL (recursive)
    result = subprocess.run(
        ['git', 'subrepo', 'status', '--ALL'],
        cwd=env.owner / 'foo',
        capture_output=True,
        text=True,
        check=True
    )
    output = result.stdout

    assert_output_like(output, '4 subrepos:', "'status --ALL' intro ok")
    assert_output_like(output, "Git subrepo 'bar':", "bar is in 'status --ALL'")
    assert_output_like(output, "Git subrepo 'lib/bar':", "lib/bar is in 'status --ALL'")
    assert_output_like(output, "Git subrepo 'bar/foo':", "bar/foo is in 'status --ALL'")
    assert_output_like(output, "Git subrepo 'lib/bar/foo':", "lib/bar/foo is in 'status --ALL'")

    # Test status --all again (should be same as first test)
    result = subprocess.run(
        ['git', 'subrepo', 'status', '--all'],
        cwd=env.owner / 'foo',
        capture_output=True,
        text=True,
        check=True
    )
    output = result.stdout

    assert_output_like(output, '2 subrepos:', "'status --all' intro ok")
    assert_output_like(output, "Git subrepo 'bar':", "bar is in 'status --all'")
    assert_output_like(output, "Git subrepo 'lib/bar':", "lib/bar is in 'status --all'")
    assert_output_unlike(output, "Git subrepo 'bar/foo':", "bar/foo is not in 'status --all'")
    assert_output_unlike(output, "Git subrepo 'lib/bar/foo':", "lib/bar/foo is not in 'status --all'")
