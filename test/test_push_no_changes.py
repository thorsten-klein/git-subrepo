"""Tests for git subrepo push with no changes"""

from conftest import git_subrepo, assert_output_matches


def test_push_no_changes(env):
    """Test that push requires changes to push"""
    env.clone_foo_and_bar()

    # Clone foo into bar
    git_subrepo(f'--quiet clone {env.upstream}/foo', cwd=env.owner / 'bar')

    # Try to push with no changes
    output = env.catch('git subrepo push foo', cwd=env.owner / 'bar')

    assert_output_matches(
        output,
        "Subrepo 'foo' has no new commits to push.",
        "Output OK: Check that 'push' requires changes to push",
    )

    # Clean up
    git_subrepo('--quiet clean foo', cwd=env.owner / 'bar')
