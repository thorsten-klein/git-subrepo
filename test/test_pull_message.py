"""Tests for git subrepo pull with custom messages"""

import subprocess
import os
from conftest import git_subrepo, assert_output_matches, assert_output_like


def test_pull_message(env):
    """Test subrepo pull with -m and -e options"""
    env.clone_foo_and_bar()
    env.subrepo_clone_bar_into_foo()

    # Add new file to bar and push
    env.add_new_files('Bar2', cwd=env.owner / 'bar')
    subprocess.run(
        ['git', 'push'], cwd=env.owner / 'bar', check=True, capture_output=True
    )

    # Do the pull with -m option
    result = git_subrepo("pull -m 'Hello World' bar", cwd=env.owner / 'foo')

    assert_output_matches(
        result.stdout.strip(),
        f"Subrepo 'bar' pulled from '{env.upstream}/bar' (master).",
        'subrepo pull command output is correct',
    )

    # Check commit message
    foo_new_commit_message = subprocess.run(
        ['git', 'log', '--format=%B', '-n', '1'],
        cwd=env.owner / 'foo',
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    assert_output_like(
        foo_new_commit_message, 'Hello World', "subrepo pull commit message"
    )

    # Add another file to bar and push
    env.add_new_files('Bar3', cwd=env.owner / 'bar')
    subprocess.run(
        ['git', 'push'], cwd=env.owner / 'bar', check=True, capture_output=True
    )

    # Do the pull with -e option
    my_env = os.environ.copy()
    my_env['GIT_EDITOR'] = 'echo cowabunga >'

    result = subprocess.run(
        ['git', 'subrepo', 'pull', '-e', 'bar'],
        cwd=env.owner / 'foo',
        env=my_env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert_output_matches(
        result.stdout.strip(),
        f"Subrepo 'bar' pulled from '{env.upstream}/bar' (master).",
        'subrepo pull command output is correct',
    )

    # Check commit message
    foo_new_commit_message = subprocess.run(
        ['git', 'log', '--format=%B', '-n', '1'],
        cwd=env.owner / 'foo',
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    assert_output_like(
        foo_new_commit_message, 'cowabunga', "subrepo pull edit commit message"
    )

    # Add another file to bar and push
    env.add_new_files('Bar4', cwd=env.owner / 'bar')
    subprocess.run(
        ['git', 'push'], cwd=env.owner / 'bar', check=True, capture_output=True
    )

    # Do the pull with -e and -m options
    my_env = os.environ.copy()
    my_env['GIT_EDITOR'] = 'true'

    result = subprocess.run(
        ['git', 'subrepo', 'pull', '-e', '-m', 'original', 'bar'],
        cwd=env.owner / 'foo',
        env=my_env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert_output_matches(
        result.stdout.strip(),
        f"Subrepo 'bar' pulled from '{env.upstream}/bar' (master).",
        'subrepo pull command output is correct',
    )

    # Check commit message
    foo_new_commit_message = subprocess.run(
        ['git', 'log', '--format=%B', '-n', '1'],
        cwd=env.owner / 'foo',
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    assert_output_like(
        foo_new_commit_message,
        'original',
        "subrepo pull edit and message commit message",
    )
