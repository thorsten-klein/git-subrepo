"""Tests for git subrepo push command"""

import subprocess
from conftest import (
    assert_exists,
    assert_file_exists,
    assert_gitrepo_field,
    assert_commit_count,
    git_rev_parse,
    git_subrepo,
    assert_output_matches,
)


def test_push(env):
    """Test basic subrepo push functionality"""
    env.clone_foo_and_bar()

    # In the main repo, clone the subrepo and make a series of commits
    git_subrepo(f'clone {env.upstream}/bar', cwd=env.owner / 'foo')
    env.add_new_files('bar/FooBar', cwd=env.owner / 'foo')
    env.add_new_files('./FooBar', cwd=env.owner / 'foo')
    env.modify_files('bar/FooBar', cwd=env.owner / 'foo')
    env.modify_files('./FooBar', cwd=env.owner / 'foo')
    env.modify_files('./FooBar', 'bar/FooBar', cwd=env.owner / 'foo')

    # Add new file in bar and push
    env.add_new_files('bargy', cwd=env.owner / 'bar')
    subprocess.run(
        ['git', 'push'], cwd=env.owner / 'bar', check=True, capture_output=True
    )

    # Do the subrepo pull and push
    subprocess.run(
        ['git', 'config', 'user.name', 'PushUser'], cwd=env.owner / 'foo', check=True
    )
    subprocess.run(
        ['git', 'config', 'user.email', 'push@push'], cwd=env.owner / 'foo', check=True
    )
    git_subrepo('pull --quiet bar', cwd=env.owner / 'foo')
    result = git_subrepo('push bar', cwd=env.owner / 'foo')

    assert_output_matches(
        result.stdout.strip(),
        f"Subrepo 'bar' pushed to '{env.upstream}/bar' (master).",
        'push message is correct',
    )

    # Pull in OWNER/bar
    subprocess.run(
        ['git', 'pull'], cwd=env.owner / 'bar', check=True, capture_output=True
    )

    # Check commit author/committer
    pull_commit = subprocess.run(
        ['git', 'log', 'HEAD', '-1', '--pretty=format:%an %ae %cn %ce'],
        cwd=env.owner / 'bar',
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    assert_output_matches(
        pull_commit,
        "PushUser push@push PushUser push@push",
        "Pull commit has PushUser as both author and committer",
    )

    # Check subrepo commit author/committer
    subrepo_commit = subprocess.run(
        ['git', 'log', 'HEAD^', '-1', '--pretty=format:%an %ae %cn %ce'],
        cwd=env.owner / 'bar',
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    assert_output_matches(
        subrepo_commit,
        "FooUser foo@foo PushUser push@push",
        "Subrepo commits has FooUser as author but PushUser as committer",
    )

    # Check that all commits arrived in subrepo
    assert_commit_count(env.owner / 'bar', 'HEAD', 7)

    # Test foo/bar/.gitrepo file contents
    gitrepo = env.owner / 'foo' / 'bar' / '.gitrepo'
    foo_pull_commit = git_rev_parse('HEAD^', cwd=env.owner / 'foo')
    bar_head_commit = git_rev_parse('HEAD', cwd=env.owner / 'bar')

    assert_gitrepo_field(gitrepo, 'remote', str(env.upstream / 'bar'))
    assert_gitrepo_field(gitrepo, 'branch', 'master')
    assert_gitrepo_field(gitrepo, 'commit', bar_head_commit)
    assert_gitrepo_field(gitrepo, 'parent', foo_pull_commit)

    version = git_subrepo('--version', cwd=env.owner / 'foo').stdout.strip()
    assert_gitrepo_field(gitrepo, 'cmdver', version)

    # Make more commits in main repo
    env.add_new_files('bar/FooBar2', cwd=env.owner / 'foo')
    env.modify_files('bar/FooBar', cwd=env.owner / 'foo')

    result = git_subrepo('push bar', cwd=env.owner / 'foo')
    assert_output_matches(
        result.stdout.strip(),
        f"Subrepo 'bar' pushed to '{env.upstream}/bar' (master).",
        'push message is correct',
    )

    # Pull the changes from UPSTREAM/bar in OWNER/bar
    subprocess.run(
        ['git', 'pull'], cwd=env.owner / 'bar', check=True, capture_output=True
    )

    assert_file_exists(env.owner / 'bar' / 'Bar')
    assert_file_exists(env.owner / 'bar' / 'FooBar')
    assert_exists(env.owner / 'bar' / 'bard', should_exist=True)
    assert_file_exists(env.owner / 'bar' / 'bargy')
    assert_exists(env.owner / 'bar' / '.gitrepo', should_exist=False)

    # Sequential pushes
    env.add_new_files('bar/FooBar3', cwd=env.owner / 'foo')
    env.modify_files('bar/FooBar', cwd=env.owner / 'foo')
    git_subrepo('push bar', cwd=env.owner / 'foo')
    env.add_new_files('bar/FooBar4', cwd=env.owner / 'foo')
    env.modify_files('bar/FooBar3', cwd=env.owner / 'foo')

    result = git_subrepo('push bar', cwd=env.owner / 'foo')
    assert_output_matches(
        result.stdout.strip(),
        f"Subrepo 'bar' pushed to '{env.upstream}/bar' (master).",
        'Sequential pushes are correct',
    )

    # Make changes in subrepo
    subprocess.run(
        ['git', 'pull'], cwd=env.owner / 'bar', check=True, capture_output=True
    )
    env.add_new_files('barBar2', cwd=env.owner / 'bar')
    subprocess.run(
        ['git', 'push'], cwd=env.owner / 'bar', check=True, capture_output=True
    )

    # Make changes in main repo
    env.add_new_files('bar/FooBar5', cwd=env.owner / 'foo')
    env.modify_files('bar/FooBar3', cwd=env.owner / 'foo')

    # Try to push (should fail)
    result = git_subrepo('push bar', cwd=env.owner / 'foo', check=False)

    assert_output_matches(
        result.stderr.strip() if result.returncode != 0 else result.stdout.strip(),
        "git-subrepo: There are new changes upstream, you need to pull first.",
        'Stopped by other push',
    )
