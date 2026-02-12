"""Tests for git subrepo reclone"""
import subprocess
from conftest import (
    assert_exists, git_subrepo, assert_output_matches
)


def test_reclone(env):
    """Test subrepo reclone functionality"""
    env.clone_foo_and_bar()

    # Clone bar
    git_subrepo('--quiet clone ' + str(env.upstream / 'bar'), cwd=env.owner / 'foo')

    assert_exists(env.owner / 'foo' / 'bar' / 'bard', should_exist=True)

    # Test that reclone is not done if not needed
    result = git_subrepo('--force clone ' + str(env.upstream / 'bar'), cwd=env.owner / 'foo')

    assert_output_matches(
        result.stdout.strip(),
        "Subrepo 'bar' is up to date.",
        "No reclone if same commit"
    )

    # Test that reclone of a different ref works
    git_subrepo(
        '--quiet clone --force ' + str(env.upstream / 'bar') + ' --branch=refs/tags/A',
        cwd=env.owner / 'foo'
    )

    result = subprocess.run(
        ['git', 'subrepo', 'config', 'bar', 'branch'],
        cwd=env.owner / 'foo',
        capture_output=True,
        text=True,
        check=True
    )

    assert_output_matches(
        result.stdout.strip(),
        "Subrepo 'bar' option 'branch' has value 'refs/tags/A'.",
        "Branch config is correct"
    )

    assert_exists(env.owner / 'foo' / 'bar' / 'bard', should_exist=False)

    # Test that reclone back to (implicit) master works
    git_subrepo(
        '--quiet clone -f ' + str(env.upstream / 'bar'),
        cwd=env.owner / 'foo'
    )

    result = subprocess.run(
        ['git', 'subrepo', 'config', 'bar', 'branch'],
        cwd=env.owner / 'foo',
        capture_output=True,
        text=True,
        check=True
    )

    assert_output_matches(
        result.stdout.strip(),
        "Subrepo 'bar' option 'branch' has value 'master'.",
        "Branch config is master"
    )

    assert_exists(env.owner / 'foo' / 'bar' / 'bard', should_exist=True)
