"""Tests for git subrepo clean command"""
from conftest import (
    assert_exists, git_subrepo, assert_output_matches
)


def test_clean(env):
    """Test basic subrepo clean functionality"""
    env.clone_foo_and_bar()
    env.subrepo_clone_bar_into_foo()

    # Make changes and create branch
    env.add_new_files('bar/file', cwd=env.owner / 'foo')
    git_subrepo('--quiet branch bar', cwd=env.owner / 'foo')

    # Check refs exist
    assert_exists(env.owner / 'foo' / '.git' / 'refs' / 'heads' / 'subrepo' / 'bar', should_exist=True)
    assert_exists(env.owner / 'foo' / '.git' / 'refs' / 'subrepo' / 'bar' / 'fetch', should_exist=True)

    # Do the clean and check output
    result = git_subrepo('clean bar', cwd=env.owner / 'foo')
    assert_output_matches(
        result.stdout.strip(),
        "Removed branch 'subrepo/bar'.",
        "subrepo clean command output is correct"
    )

    # Check that branch ref was removed
    assert_exists(env.owner / 'foo' / '.git' / 'refs' / 'heads' / 'subrepo' / 'bar', should_exist=False)

    # Clean with --force
    git_subrepo('clean --force bar', cwd=env.owner / 'foo')

    # Check that fetch ref was also removed
    assert_exists(env.owner / 'foo' / '.git' / 'refs' / 'subrepo' / 'bar' / 'fetch', should_exist=False)
