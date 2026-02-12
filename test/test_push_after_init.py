"""Tests for git subrepo push after init"""

import subprocess
from conftest import (
    assert_exists,
    assert_gitrepo_field,
    git_subrepo,
    assert_output_matches,
)


def test_push_after_init(env):
    """Test push after init (issue #122)"""
    # Create directory and init git locally
    # This will test some corner cases when you don't have any previous commits to rely on
    init_dir = env.owner / 'init'
    init_dir.mkdir(parents=True)

    subprocess.run(['git', 'init'], cwd=init_dir, check=True, capture_output=True)

    doc_dir = init_dir / 'doc'
    doc_dir.mkdir()

    env.add_new_files('doc/FooBar', cwd=init_dir)
    git_subrepo('init doc', cwd=init_dir)

    upstream_dir = env.owner / 'upstream'
    upstream_dir.mkdir()
    subprocess.run(
        ['git', 'init', '--bare'], cwd=upstream_dir, check=True, capture_output=True
    )

    # Push
    result = git_subrepo('push doc --remote=../upstream', cwd=init_dir)

    assert_output_matches(
        result.stdout.strip(),
        "Subrepo 'doc' pushed to '../upstream' (master).",
        'Command output is correct',
    )

    # Test init/doc/.gitrepo file contents
    gitrepo = init_dir / 'doc' / '.gitrepo'
    assert_gitrepo_field(gitrepo, 'remote', '../upstream')
    assert_gitrepo_field(gitrepo, 'branch', 'master')

    # Clone upstream and verify
    up_dir = env.owner / 'up'
    subprocess.run(
        ['git', 'clone', str(upstream_dir), str(up_dir)],
        check=True,
        capture_output=True,
    )

    assert_exists(up_dir / '.git', should_exist=True)
    assert_exists(up_dir / '.gitrepo', should_exist=False)
