"""Tests for git subrepo with submodules"""
import subprocess
from conftest import (
    git_subrepo, assert_output_matches
)


def test_submodule(env):
    """Test that a subrepo that contains a submodule retains the submodule reference"""
    env.clone_foo_and_bar()

    # Add submodule reference along with a new file to the bar repo
    subprocess.run(
        ['git', 'clone', '../foo', 'submodule'],
        cwd=env.owner / 'bar',
        check=True,
        capture_output=True
    )
    env.add_new_files('file', cwd=env.owner / 'bar')
    subprocess.run(['git', 'add', 'submodule', 'file'], cwd=env.owner / 'bar', check=True)
    subprocess.run(
        ['git', 'commit', '--amend', '-C', 'HEAD'],
        cwd=env.owner / 'bar',
        check=True,
        capture_output=True
    )

    # Clone bar into foo
    git_subrepo('clone ../bar', cwd=env.owner / 'foo')

    # Modify file in bar
    env.modify_files('file', cwd=env.owner / 'bar')

    # Pull and verify
    result = git_subrepo('pull bar', cwd=env.owner / 'foo')

    assert_output_matches(
        result.stdout.strip(),
        "Subrepo 'bar' pulled from '../bar' (master).",
        'subrepo pull command output is correct'
    )
