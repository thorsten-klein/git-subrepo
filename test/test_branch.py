"""Tests for git subrepo branch command"""

import subprocess
import time
from conftest import assert_exists, git_subrepo, assert_output_matches


def test_branch(env):
    """Test basic subrepo branch functionality"""
    env.clone_foo_and_bar()
    env.subrepo_clone_bar_into_foo()

    # Get timestamp before
    foo_file = env.owner / 'foo' / 'Foo'
    before = foo_file.stat().st_mtime

    # Make changes
    env.add_new_files('bar/file', cwd=env.owner / 'foo')
    env.add_new_files('.gitrepo', cwd=env.owner / 'foo')

    # Save original state
    original_head_ref = (env.owner / 'foo' / '.git' / 'HEAD').read_text().strip()
    original_head_commit = subprocess.run(
        ['git', 'rev-parse', 'HEAD'],
        cwd=env.owner / 'foo',
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    original_gitrepo = (env.owner / 'foo' / 'bar' / '.gitrepo').read_text()

    # Make sure that time stamps differ
    time.sleep(1)

    result = git_subrepo('branch bar', cwd=env.owner / 'foo')
    assert_output_matches(
        result.stdout.strip(),
        "Created branch 'subrepo/bar' and worktree '.git/tmp/subrepo/bar'.",
        "subrepo branch command output is correct",
    )

    # Check timestamp after
    after = foo_file.stat().st_mtime

    # Assert original state (HEAD and gitrepo unchanged)
    current_head_ref = (env.owner / 'foo' / '.git' / 'HEAD').read_text().strip()
    current_head_commit = subprocess.run(
        ['git', 'rev-parse', 'HEAD'],
        cwd=env.owner / 'foo',
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    current_gitrepo = (env.owner / 'foo' / 'bar' / '.gitrepo').read_text()

    assert current_head_ref == original_head_ref, "Current HEAD is still same"
    assert current_head_commit == original_head_commit, (
        "Current HEAD commit is still same"
    )
    assert current_gitrepo == original_gitrepo, "bar/.gitrepo has not changed"

    # Check that we haven't checked out any temporary files
    assert before == after, "No modification on Foo"

    # Check temporary directory exists
    assert_exists(
        env.owner / 'foo' / '.git' / 'tmp' / 'subrepo' / 'bar', should_exist=True
    )

    # Check that correct branch is checked out
    result = subprocess.run(
        ['git', 'branch'],
        cwd=env.owner / 'foo' / '.git' / 'tmp' / 'subrepo' / 'bar',
        capture_output=True,
        text=True,
        check=True,
    )
    current_branch = [line for line in result.stdout.split('\n') if '*' in line][0]
    assert current_branch.strip() == '* subrepo/bar', "Correct branch is checked out"
