"""Tests for git subrepo pull with merge conflicts"""

import subprocess
from conftest import (
    assert_exists,
    assert_gitrepo_field,
    git_rev_parse,
    git_subrepo,
    assert_output_matches,
    assert_output_like,
)


def test_pull_merge(env):
    """Test subrepo pull - conflict - merge - push"""
    env.clone_foo_and_bar()
    env.subrepo_clone_bar_into_foo()

    # Add new file to bar and push
    env.add_new_files('Bar2', cwd=env.owner / 'bar')
    subprocess.run(
        ['git', 'push'], cwd=env.owner / 'bar', check=True, capture_output=True
    )

    # Test foo/bar/.gitrepo file contents before
    gitrepo = env.owner / 'foo' / 'bar' / '.gitrepo'
    foo_pull_commit = git_rev_parse('HEAD^', cwd=env.owner / 'foo')
    bar_head_commit = git_rev_parse('HEAD^', cwd=env.owner / 'bar')

    assert_gitrepo_field(gitrepo, 'commit', bar_head_commit)
    assert_gitrepo_field(gitrepo, 'parent', foo_pull_commit)

    foo_pull_commit = git_rev_parse('HEAD', cwd=env.owner / 'foo')

    # Pull, modify in foo, and push
    git_subrepo('pull bar', cwd=env.owner / 'foo')
    env.modify_files_ex('bar/Bar2', cwd=env.owner / 'foo')
    subprocess.run(
        ['git', 'push'], cwd=env.owner / 'foo', check=True, capture_output=True
    )

    # Modify in bar and push
    env.modify_files_ex('Bar2', cwd=env.owner / 'bar')
    subprocess.run(
        ['git', 'push'], cwd=env.owner / 'bar', check=True, capture_output=True
    )

    # Try to pull (will conflict), resolve manually
    result = git_subrepo('pull bar', cwd=env.owner / 'foo', check=False)
    if result.returncode != 0:
        # Resolve conflict
        worktree_dir = env.owner / 'foo' / '.git' / 'tmp' / 'subrepo' / 'bar'
        (worktree_dir / 'Bar2').write_text('Merged Bar2\n')
        subprocess.run(['git', 'add', 'Bar2'], cwd=worktree_dir, check=True)

        merge_msg_file = env.owner / 'foo' / '.git' / 'worktrees' / 'bar' / 'MERGE_MSG'
        subprocess.run(
            ['git', 'commit', f'--file={merge_msg_file}'],
            cwd=worktree_dir,
            check=True,
            capture_output=True,
        )

        git_subrepo('commit bar', cwd=env.owner / 'foo')
        git_subrepo('clean bar', cwd=env.owner / 'foo')

    # Check files exist
    assert_exists(env.owner / 'foo' / 'bar' / 'Bar2', should_exist=True)
    assert_exists(env.owner / 'bar' / 'Bar2', should_exist=True)

    # Check merge result
    bar2_content = (env.owner / 'foo' / 'bar' / 'Bar2').read_text()
    assert_output_matches(
        bar2_content.strip(), 'Merged Bar2', "The readme file in the mainrepo is merged"
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
        'git subrepo commit \\(merge\\) bar',
        "subrepo pull should have merge message",
    )

    # Test foo/bar/.gitrepo file contents
    bar_head_commit = git_rev_parse('HEAD', cwd=env.owner / 'bar')
    assert_gitrepo_field(gitrepo, 'commit', bar_head_commit)
    assert_gitrepo_field(gitrepo, 'parent', foo_pull_commit)

    # Push
    git_subrepo('push bar', cwd=env.owner / 'foo')

    # Check commit message after push
    foo_new_commit_message = subprocess.run(
        ['git', 'log', '--format=%B', '-n', '1'],
        cwd=env.owner / 'foo',
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    assert_output_like(
        foo_new_commit_message,
        'git subrepo push bar',
        "subrepo push should not have merge message",
    )

    # Pull in bar
    subprocess.run(
        ['git', 'pull'], cwd=env.owner / 'bar', check=True, capture_output=True
    )

    # Check files
    assert_exists(env.owner / 'foo' / 'bar' / 'Bar2', should_exist=True)
    assert_exists(env.owner / 'bar' / 'Bar2', should_exist=True)

    # Check content in both repos
    foo_bar2_content = (env.owner / 'foo' / 'bar' / 'Bar2').read_text()
    assert_output_matches(
        foo_bar2_content.strip(),
        'Merged Bar2',
        "The readme file in the mainrepo is merged",
    )

    bar_bar2_content = (env.owner / 'bar' / 'Bar2').read_text()
    assert_output_matches(
        bar_bar2_content.strip(),
        'Merged Bar2',
        "The readme file in the subrepo is merged",
    )
