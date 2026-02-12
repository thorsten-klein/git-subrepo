"""Tests for git subrepo init command"""

import subprocess
import shutil
from conftest import (
    assert_exists,
    assert_file_exists,
    assert_gitrepo_comment_block,
    assert_gitrepo_field,
    git_subrepo,
    assert_output_matches,
)


def test_init(env):
    """Test basic subrepo init functionality"""
    # Clone init repo
    subprocess.run(
        ['git', 'clone', str(env.upstream / 'init'), str(env.owner / 'init')],
        check=True,
        capture_output=True,
    )

    gitrepo = env.owner / 'init' / 'doc' / '.gitrepo'

    # Test that the initial repo looks ok
    assert_exists(env.owner / 'init' / '.git', should_exist=True)
    assert_file_exists(env.owner / 'init' / 'ReadMe')
    assert_exists(env.owner / 'init' / 'doc', should_exist=True)
    assert_file_exists(env.owner / 'init' / 'doc' / 'init.swim')
    assert_exists(gitrepo, should_exist=False)

    # Do the init
    result = git_subrepo('init doc', cwd=env.owner / 'init')

    assert_output_matches(
        result.stdout.strip(),
        "Subrepo created from 'doc' (with no remote).",
        'Command output is correct',
    )

    assert_exists(gitrepo, should_exist=True)

    # Test init/doc/.gitrepo file contents
    version = git_subrepo('--version', cwd=env.owner / 'init').stdout.strip()

    assert_gitrepo_comment_block(gitrepo)
    assert_gitrepo_field(gitrepo, 'remote', 'none')
    assert_gitrepo_field(gitrepo, 'branch', 'master')
    assert_gitrepo_field(gitrepo, 'commit', '')
    assert_gitrepo_field(gitrepo, 'parent', '')
    assert_gitrepo_field(gitrepo, 'method', 'merge')
    assert_gitrepo_field(gitrepo, 'cmdver', version)

    # Remove and re-clone
    shutil.rmtree(env.owner / 'init')
    subprocess.run(
        ['git', 'clone', str(env.upstream / 'init'), str(env.owner / 'init')],
        check=True,
        capture_output=True,
    )

    # Init with options
    git_subrepo(
        'init doc -r git@github.com:user/repo -b foo -M rebase', cwd=env.owner / 'init'
    )

    assert_gitrepo_field(gitrepo, 'remote', 'git@github.com:user/repo')
    assert_gitrepo_field(gitrepo, 'branch', 'foo')
    assert_gitrepo_field(gitrepo, 'commit', '')
    assert_gitrepo_field(gitrepo, 'parent', '')
    assert_gitrepo_field(gitrepo, 'method', 'rebase')
    assert_gitrepo_field(gitrepo, 'cmdver', version)
