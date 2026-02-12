"""Tests for git subrepo push after push with no changes"""
from conftest import (
    git_subrepo, assert_output_matches
)


def test_push_after_push_no_changes(env):
    """Test that push after an empty push works"""
    env.clone_foo_and_bar()
    env.subrepo_clone_bar_into_foo()

    # Do an empty push
    git_subrepo('push bar', cwd=env.owner / 'foo')

    # Add a file and push again
    env.add_new_files('bar/Bar1', cwd=env.owner / 'foo')

    result = git_subrepo('push bar', cwd=env.owner / 'foo')

    assert_output_matches(
        result.stdout.strip(),
        f"Subrepo 'bar' pushed to '{env.upstream}/bar' (master).",
        "Output OK: Check that 'push' after an empty push works."
    )
