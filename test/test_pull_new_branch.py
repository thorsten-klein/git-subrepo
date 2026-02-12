"""Tests for git subrepo pull with new branch"""

import subprocess
from conftest import (
    assert_gitrepo_comment_block,
    assert_gitrepo_field,
    git_rev_parse,
    git_subrepo,
    assert_output_matches,
)


def test_pull_new_branch(env):
    """Test subrepo pull switching to a new branch"""
    env.clone_foo_and_bar()
    env.subrepo_clone_bar_into_foo()

    # Create and push new branch in bar
    subprocess.run(
        ['git', 'checkout', '-b', 'branch1'],
        cwd=env.owner / 'bar',
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'push', '--set-upstream', 'origin', 'branch1'],
        cwd=env.owner / 'bar',
        check=True,
        capture_output=True,
    )

    # Test subrepo file content
    gitrepo = env.owner / 'foo' / 'bar' / '.gitrepo'

    foo_pull_commit = git_rev_parse('HEAD^', cwd=env.owner / 'foo')
    bar_head_commit = git_rev_parse('HEAD', cwd=env.owner / 'bar')

    assert_gitrepo_comment_block(gitrepo)
    assert_gitrepo_field(gitrepo, 'remote', str(env.upstream / 'bar'))
    assert_gitrepo_field(gitrepo, 'branch', 'master')
    assert_gitrepo_field(gitrepo, 'commit', bar_head_commit)
    assert_gitrepo_field(gitrepo, 'parent', foo_pull_commit)

    version = git_subrepo('--version', cwd=env.owner / 'foo').stdout.strip()
    assert_gitrepo_field(gitrepo, 'cmdver', version)

    # Pull with new branch
    git_subrepo('pull bar -b branch1 -u', cwd=env.owner / 'foo')

    # Verify branch was updated
    foo_pull_commit = git_rev_parse('HEAD^', cwd=env.owner / 'foo')
    bar_head_commit = git_rev_parse('HEAD', cwd=env.owner / 'bar')

    assert_gitrepo_comment_block(gitrepo)
    assert_gitrepo_field(gitrepo, 'remote', str(env.upstream / 'bar'))
    assert_gitrepo_field(gitrepo, 'branch', 'branch1')
    assert_gitrepo_field(gitrepo, 'commit', bar_head_commit)
    assert_gitrepo_field(gitrepo, 'parent', foo_pull_commit)
    assert_gitrepo_field(gitrepo, 'cmdver', version)

    # Check that we detect that we don't need to pull
    result = git_subrepo('pull bar', cwd=env.owner / 'foo')

    assert_output_matches(
        result.stdout.strip(),
        "Subrepo 'bar' is up to date.",
        'subrepo detects that we dont need to pull',
    )
