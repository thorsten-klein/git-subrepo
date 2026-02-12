"""Tests for git subrepo clone command"""

import subprocess
from conftest import (
    assert_exists,
    assert_file_exists,
    assert_dir_exists,
    assert_gitrepo_comment_block,
    assert_gitrepo_field,
    git_rev_parse,
    git_subrepo,
    assert_output_matches,
)


def test_clone(env):
    """Test basic subrepo clone functionality"""
    env.clone_foo_and_bar()

    # Create empty repo for testing
    empty_dir = env.owner / 'empty'
    empty_dir.mkdir()
    subprocess.run(['git', 'init'], cwd=empty_dir, check=True, capture_output=True)

    # Test that the repos look ok
    assert_dir_exists(env.owner / 'foo' / '.git')
    assert_file_exists(env.owner / 'foo' / 'Foo')
    assert_exists(env.owner / 'foo' / 'bar', should_exist=False)
    assert_dir_exists(env.owner / 'bar' / '.git')
    assert_file_exists(env.owner / 'bar' / 'Bar')
    assert_dir_exists(env.owner / 'empty' / '.git')

    # Do the subrepo clone and test the output
    result = git_subrepo(f'clone {env.upstream}/bar', cwd=env.owner / 'foo')
    assert_output_matches(
        result.stdout.strip(),
        f"Subrepo '{env.upstream}/bar' (master) cloned into 'bar'.",
        'subrepo clone command output is correct',
    )

    # Check no remotes created
    result = subprocess.run(
        ['git', 'remote', '-v'],
        cwd=env.owner / 'foo',
        capture_output=True,
        text=True,
        check=True,
    )
    remotes = [line for line in result.stdout.split('\n') if 'subrepo/bar' in line]
    assert len(remotes) == 0, 'No remotes created'

    # Test clone into empty repository fails
    result = git_subrepo(f'clone {env.upstream}/bar', cwd=empty_dir, check=False)
    assert_output_matches(
        result.stderr.strip(),
        "git-subrepo: You can't clone into an empty repository",
        'subrepo empty clone command output is correct',
    )

    # Check that subrepo files look ok
    gitrepo = env.owner / 'foo' / 'bar' / '.gitrepo'
    assert_dir_exists(env.owner / 'foo' / 'bar')
    assert_file_exists(env.owner / 'foo' / 'bar' / 'Bar')
    assert_file_exists(gitrepo)
    assert_exists(env.owner / 'empty' / 'bar', should_exist=False)

    # Test foo/bar/.gitrepo file contents
    foo_clone_commit = git_rev_parse('HEAD^', cwd=env.owner / 'foo')
    bar_head_commit = git_rev_parse('HEAD', cwd=env.owner / 'bar')

    assert_gitrepo_comment_block(gitrepo)
    assert_gitrepo_field(gitrepo, 'remote', str(env.upstream / 'bar'))
    assert_gitrepo_field(gitrepo, 'branch', 'master')
    assert_gitrepo_field(gitrepo, 'commit', bar_head_commit)
    assert_gitrepo_field(gitrepo, 'parent', foo_clone_commit)

    # Get version
    result = git_subrepo('--version', cwd=env.owner / 'foo')
    version = result.stdout.strip()
    assert_gitrepo_field(gitrepo, 'cmdver', version)

    # Make sure status is clean
    result = subprocess.run(
        ['git', 'status', '-s'],
        cwd=env.owner / 'foo',
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == '', 'status is clean'

    result = subprocess.run(
        ['git', 'status', '-s'],
        cwd=empty_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == '', 'status is clean (empty)'
