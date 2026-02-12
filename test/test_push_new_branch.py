"""Tests for git subrepo push to new branch"""
import subprocess
from conftest import (
    assert_file_exists, git_subrepo, assert_output_matches
)


def test_push_new_branch(env):
    """Test subrepo push to a new branch"""
    env.clone_foo_and_bar()

    # Clone the subrepo into a subdir
    git_subrepo(f'clone {env.upstream}/bar', cwd=env.owner / 'foo')

    # Make a commit
    env.add_new_files('bar/FooBar', cwd=env.owner / 'foo')

    # Do the subrepo push to another branch
    result = git_subrepo('push bar --branch newbar', cwd=env.owner / 'foo')

    assert_output_matches(
        result.stdout.strip(),
        f"Subrepo 'bar' pushed to '{env.upstream}/bar' (newbar).",
        'First push message is correct'
    )

    # Do the subrepo push to another branch again
    result = git_subrepo('push bar --branch newbar', cwd=env.owner / 'foo')

    assert_output_matches(
        result.stdout.strip(),
        "Subrepo 'bar' has no new commits to push.",
        'Second push message is correct'
    )

    # Pull the changes from UPSTREAM/bar in OWNER/bar
    subprocess.run(['git', 'fetch'], cwd=env.owner / 'bar', check=True, capture_output=True)
    subprocess.run(
        ['git', 'checkout', 'newbar'],
        cwd=env.owner / 'bar',
        check=True,
        capture_output=True
    )

    assert_file_exists(env.owner / 'bar' / 'FooBar')
