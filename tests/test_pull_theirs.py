"""Tests for git subrepo pull with conflict resolution using theirs"""
import subprocess
from conftest import (
    assert_exists, git_subrepo, assert_output_matches
)


def test_pull_theirs(env):
    """Test subrepo pull - conflict - use theirs - push"""
    env.clone_foo_and_bar()
    env.subrepo_clone_bar_into_foo()

    # Note: When you perform rebase ours/theirs are reversed, so this test case will
    # test using the subrepo change (theirs) although in the step below
    # we actually use git checkout --ours to accomplish this

    # Add new file to bar and push
    env.add_new_files('Bar2', cwd=env.owner / 'bar')
    subprocess.run(['git', 'push'], cwd=env.owner / 'bar', check=True, capture_output=True)

    # Pull, modify in foo, and push
    git_subrepo('pull bar', cwd=env.owner / 'foo')
    env.modify_files_ex('bar/Bar2', cwd=env.owner / 'foo')
    subprocess.run(['git', 'push'], cwd=env.owner / 'foo', check=True, capture_output=True)

    # Modify in bar and push
    env.modify_files_ex('Bar2', cwd=env.owner / 'bar')
    subprocess.run(['git', 'push'], cwd=env.owner / 'bar', check=True, capture_output=True)

    # Try to pull (will conflict), resolve using theirs (ours in rebase context)
    result = git_subrepo('pull bar', cwd=env.owner / 'foo', check=False)
    if result.returncode != 0:
        # Resolve conflict using theirs
        worktree_dir = env.owner / 'foo' / '.git' / 'tmp' / 'subrepo' / 'bar'
        subprocess.run(['git', 'checkout', '--theirs', 'Bar2'], cwd=worktree_dir, check=True)
        subprocess.run(['git', 'add', 'Bar2'], cwd=worktree_dir, check=True)

        merge_msg_file = env.owner / 'foo' / '.git' / 'worktrees' / 'bar' / 'MERGE_MSG'
        subprocess.run(
            ['git', 'commit', f'--file={merge_msg_file}'],
            cwd=worktree_dir,
            check=True,
            capture_output=True
        )

        git_subrepo('commit bar', cwd=env.owner / 'foo')
        git_subrepo('clean bar', cwd=env.owner / 'foo')

    # Check files exist
    assert_exists(env.owner / 'foo' / 'bar' / 'Bar2', should_exist=True)
    assert_exists(env.owner / 'bar' / 'Bar2', should_exist=True)

    # Check result (should be theirs)
    bar2_content = (env.owner / 'foo' / 'bar' / 'Bar2').read_text()
    expected = 'new file Bar2\nBar2\n'
    assert_output_matches(
        bar2_content,
        expected,
        "The readme file in the mainrepo is theirs"
    )

    # Push
    subprocess.run(['cat', 'bar/Bar2'], cwd=env.owner / 'foo', check=True)
    git_subrepo('push bar', cwd=env.owner / 'foo')

    # Pull in bar
    subprocess.run(['git', 'pull'], cwd=env.owner / 'bar', check=True, capture_output=True)

    # Check files
    assert_exists(env.owner / 'foo' / 'bar' / 'Bar2', should_exist=True)
    assert_exists(env.owner / 'bar' / 'Bar2', should_exist=True)

    # Check result in subrepo
    bar2_content = (env.owner / 'bar' / 'Bar2').read_text()
    assert_output_matches(
        bar2_content,
        expected,
        "The readme file in the subrepo is theirs"
    )
