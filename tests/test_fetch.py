"""Tests for git subrepo fetch command"""
import subprocess
from conftest import (
    git_subrepo, assert_output_matches
)


def test_fetch(env):
    """Test basic subrepo fetch functionality"""
    env.clone_foo_and_bar()
    env.subrepo_clone_bar_into_foo()

    # Add new file with annotated tag to bar and push
    env.add_new_files('Bar2', cwd=env.owner / 'bar')
    subprocess.run(
        ['git', 'tag', '-a', 'CoolTag', '-m', 'Should stay in subrepo'],
        cwd=env.owner / 'bar',
        check=True,
        capture_output=True
    )
    subprocess.run(['git', 'push'], cwd=env.owner / 'bar', check=True, capture_output=True)

    # Fetch information
    result = git_subrepo('fetch bar', cwd=env.owner / 'foo')
    assert_output_matches(
        result.stdout.strip(),
        f"Fetched 'bar' from '{env.upstream}/bar' (master).",
        'subrepo fetch command output is correct'
    )

    # Check that there is no tags fetched
    result = subprocess.run(
        ['git', 'tag', '-l', 'CoolTag'],
        cwd=env.owner / 'foo',
        capture_output=True,
        text=True,
        check=True
    )

    assert_output_matches(
        result.stdout.strip(),
        '',
        'No tag is available'
    )
