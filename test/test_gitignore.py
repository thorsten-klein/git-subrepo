"""Tests for git subrepo with .gitignore"""

import subprocess
from conftest import (
    assert_file_exists,
    assert_gitrepo_comment_block,
    assert_gitrepo_field,
    git_rev_parse,
    git_subrepo,
    assert_output_matches,
)


def test_gitignore(env):
    """Test subrepo pull with .gitignore"""
    env.clone_foo_and_bar()
    env.subrepo_clone_bar_into_foo()

    # Add new file to bar and push
    env.add_new_files('Bar2', cwd=env.owner / 'bar')
    subprocess.run(
        ['git', 'push'], cwd=env.owner / 'bar', check=True, capture_output=True
    )

    # Add .gitignore to foo
    gitignore_path = env.owner / 'foo' / '.gitignore'
    gitignore_path.write_text('.*\n')
    subprocess.run(
        ['git', 'add', '--force', '.gitignore'], cwd=env.owner / 'foo', check=True
    )
    subprocess.run(
        ['git', 'commit', '-m', 'Add gitignore'],
        cwd=env.owner / 'foo',
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'push'], cwd=env.owner / 'foo', check=True, capture_output=True
    )

    # Do the pull and check output
    result = git_subrepo('pull bar', cwd=env.owner / 'foo')
    assert_output_matches(
        result.stdout.strip(),
        f"Subrepo 'bar' pulled from '{env.upstream}/bar' (master).",
        'subrepo pull command output is correct',
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

    version = git_subrepo('--version', cwd=env.owner / 'foo').stdout.strip()
    assert_gitrepo_field(gitrepo, 'cmdver', version)
