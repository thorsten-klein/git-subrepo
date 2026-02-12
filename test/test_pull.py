"""Tests for git subrepo pull command"""
import subprocess
from pathlib import Path
from conftest import (
    assert_exists, assert_file_exists,
    assert_gitrepo_comment_block, assert_gitrepo_field,
    git_rev_parse, git_subrepo, assert_output_matches,
    assert_output_like
)


def test_pull(env):
    """Test basic subrepo pull functionality"""
    env.clone_foo_and_bar()
    env.subrepo_clone_bar_into_foo()

    # Add new file to bar and push
    env.add_new_files('Bar2', cwd=env.owner / 'bar')
    subprocess.run(['git', 'push'], cwd=env.owner / 'bar', check=True, capture_output=True)

    # Do the pull and check output
    result = git_subrepo('pull bar', cwd=env.owner / 'foo')
    assert_output_matches(
        result.stdout.strip(),
        f"Subrepo 'bar' pulled from '{env.upstream}/bar' (master).",
        'subrepo pull command output is correct'
    )

    # Test subrepo file content
    gitrepo = env.owner / 'foo' / 'bar' / '.gitrepo'
    assert_file_exists(env.owner / 'foo' / 'bar' / 'Bar2')
    assert_file_exists(gitrepo)

    # Test foo/bar/.gitrepo file contents
    foo_pull_commit = git_rev_parse('HEAD^', cwd=env.owner / 'foo')
    bar_head_commit = git_rev_parse('HEAD', cwd=env.owner / 'bar')

    assert_gitrepo_comment_block(gitrepo)
    assert_gitrepo_field(gitrepo, 'remote', str(env.upstream / 'bar'))
    assert_gitrepo_field(gitrepo, 'branch', 'master')
    assert_gitrepo_field(gitrepo, 'commit', bar_head_commit)
    assert_gitrepo_field(gitrepo, 'parent', foo_pull_commit)

    # Get version
    result = git_subrepo('--version', cwd=env.owner / 'foo')
    version = result.stdout.strip()
    assert_gitrepo_field(gitrepo, 'cmdver', version)

    # Check commit messages
    result = subprocess.run(
        ['git', 'log', '--format=%B', '-n', '1'],
        cwd=env.owner / 'foo',
        capture_output=True,
        text=True,
        check=True
    )
    foo_new_commit_message = result.stdout.strip()

    assert_output_like(
        foo_new_commit_message,
        'git subrepo pull bar',
        'Subrepo pull commit message OK'
    )

    bar_commit_short = subprocess.run(
        ['git', 'rev-parse', '--short', bar_head_commit],
        capture_output=True,
        text=True,
        check=True
    ).stdout.strip()

    assert_output_like(
        foo_new_commit_message,
        f'merged:   "{bar_commit_short}',
        'Pull commit contains merged'
    )

    # Check that we detect that we don't need to pull
    result = git_subrepo('pull bar', cwd=env.owner / 'foo')
    assert_output_matches(
        result.stdout.strip(),
        "Subrepo 'bar' is up to date.",
        'subrepo detects that we dont need to pull'
    )

    # Test pull if we have rebased the original subrepo so that our clone
    # commit is no longer present in the history
    subprocess.run(
        ['git', 'reset', '--hard', 'master^^'],
        cwd=env.owner / 'bar',
        check=True,
        capture_output=True
    )
    env.add_new_files('Bar3', cwd=env.owner / 'bar')
    subprocess.run(
        ['git', 'push', '--force'],
        cwd=env.owner / 'bar',
        check=True,
        capture_output=True
    )

    # Check that pull_failed doesn't exist yet
    assert_exists(env.owner / 'foo' / 'pull_failed', should_exist=False)

    # Try to pull (should fail)
    result = git_subrepo('pull bar', cwd=env.owner / 'foo', check=False)
    if result.returncode != 0:
        # Create marker file on failure
        (env.owner / 'foo' / 'pull_failed').touch()

    # We check that the control file was created
    assert_exists(env.owner / 'foo' / 'pull_failed', should_exist=True)
