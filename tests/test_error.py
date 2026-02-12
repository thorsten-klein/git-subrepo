"""Tests for git subrepo error messages"""
import subprocess
import os
from conftest import (
    git_subrepo, assert_output_matches, assert_output_like
)


def test_error(env):
    """Test all error message conditions in git-subrepo"""
    # Set environment variable to enable error testing
    orig_errors = os.environ.get('GIT_SUBREPO_TEST_ERRORS')
    os.environ['GIT_SUBREPO_TEST_ERRORS'] = 'true'

    try:
        env.clone_foo_and_bar()

        # Test: can't create a branch that exists
        git_subrepo(f'--quiet clone {env.upstream}/foo', cwd=env.owner / 'bar')
        env.add_new_files('foo/file', cwd=env.owner / 'bar')
        git_subrepo('--quiet branch foo', cwd=env.owner / 'bar')
        output = env.catch('git subrepo branch foo', cwd=env.owner / 'bar')

        assert_output_matches(
            output,
            "git-subrepo: Branch 'subrepo/foo' already exists. Use '--force' to override.",
            "Error OK: can't create a branch that exists"
        )

        git_subrepo('--quiet clean foo', cwd=env.owner / 'bar')
        subprocess.run(
            ['git', 'reset', '--quiet', '--hard', 'HEAD^'],
            cwd=env.owner / 'bar',
            check=True,
            capture_output=True
        )

        # Test: unknown command option
        output = env.catch('git subrepo clone --foo', cwd=env.owner / 'bar')
        assert_output_like(
            output,
            "error: unknown option `foo",
            "Error OK: unknown command option"
        )

        # Test: unknown command
        output = env.catch('git subrepo main 1 2 3', cwd=env.owner / 'bar')
        assert_output_matches(
            output,
            "git-subrepo: 'main' is not a command. See 'git subrepo help'.",
            "Error OK: unknown command"
        )

        # Test: --update requires --branch or --remote options
        output = env.catch('git subrepo pull --update', cwd=env.owner / 'bar')
        assert_output_matches(
            output,
            "git-subrepo: Can't use '--update' without '--branch' or '--remote'.",
            "Error OK: --update requires --branch or --remote options"
        )

        # Test: Invalid option '--all' for 'clone'
        output = env.catch('git subrepo clone --all', cwd=env.owner / 'bar')
        assert_output_matches(
            output,
            "git-subrepo: Invalid option '--all' for 'clone'.",
            "Error OK: Invalid option '--all' for 'clone'"
        )

        # Test: check subdir is not absolute path
        output = env.catch('git subrepo pull /home/user/bar/foo', cwd=env.owner / 'bar')
        assert_output_like(
            output,
            "git-subrepo: The subdir '.*/home/user/bar/foo' should not be absolute path.",
            "Error OK: check subdir is not absolute path"
        )

        # Test: commands require subdir
        for cmd in ['pull', 'push', 'fetch', 'branch', 'commit', 'clean']:
            output = env.catch(f'git subrepo {cmd}', cwd=env.owner / 'bar')
            assert_output_matches(
                output,
                f"git-subrepo: Command '{cmd}' requires arg 'subdir'.",
                f"Error OK: check that '{cmd}' requires subdir"
            )

        # Test: extra arguments for clone
        output = env.catch('git subrepo clone foo bar baz quux', cwd=env.owner / 'bar')
        assert_output_matches(
            output,
            "git-subrepo: Unknown argument(s) 'baz quux' for 'clone' command.",
            "Error OK: extra arguments for clone"
        )

        # Test: check error in subdir guess
        output = env.catch('git subrepo clone .git', cwd=env.owner / 'bar')
        assert_output_matches(
            output,
            "git-subrepo: Can't determine subdir from '.git'.",
            "Error OK: check error in subdir guess"
        )

        # Test: check for valid subrepo subdir
        output = env.catch('git subrepo pull lala', cwd=env.owner / 'bar')
        assert_output_matches(
            output,
            "git-subrepo: No 'lala/.gitrepo' file.",
            "Error OK: check for valid subrepo subdir"
        )

        # Test: check repo is on a branch
        commit = subprocess.run(
            ['git', 'rev-parse', 'master'],
            cwd=env.owner / 'bar',
            capture_output=True,
            text=True,
            check=True
        ).stdout.strip()
        subprocess.run(
            ['git', 'checkout', '--quiet', commit],
            cwd=env.owner / 'bar',
            check=True,
            capture_output=True
        )
        output = env.catch('git subrepo status', cwd=env.owner / 'bar')
        assert_output_matches(
            output,
            "git-subrepo: Must be on a branch to run this command.",
            "Error OK: check repo is on a branch"
        )
        subprocess.run(
            ['git', 'checkout', '--quiet', 'master'],
            cwd=env.owner / 'bar',
            check=True,
            capture_output=True
        )

        # Test: check inside working tree
        output = env.catch('git subrepo status', cwd=env.owner / 'bar' / '.git')
        assert_output_like(
            output,
            "git-subrepo: (Can't 'subrepo status' outside a working tree\\.|Not inside a git repository\\.)",
            "Error OK: check inside working tree"
        )

        # Test: check no working tree changes
        (env.owner / 'bar' / 'me').touch()
        subprocess.run(['git', 'add', 'me'], cwd=env.owner / 'bar', check=True)
        output = env.catch(f'git subrepo clone {env.upstream}/foo', cwd=env.owner / 'bar')
        assert_output_like(
            output,
            "git-subrepo: Can't clone subrepo. Working tree has changes.",
            "Error OK: check no working tree changes"
        )
        subprocess.run(
            ['git', 'reset', '--quiet', '--hard'],
            cwd=env.owner / 'bar',
            check=True,
            capture_output=True
        )

        # Test: check cwd is at top level
        output = env.catch('git subrepo status', cwd=env.test_dir / 'lib')
        assert_output_like(
            output,
            "git-subrepo: (Need to run subrepo command from top level directory of the repo\\.|Not inside a git repository\\.)",
            "Error OK: check cwd is at top level"
        )

        # Test: non-empty clone subdir target
        output = env.catch('git subrepo clone dummy bard', cwd=env.owner / 'bar')
        assert_output_matches(
            output,
            "git-subrepo: The subdir 'bard' exists and is not empty.",
            "Error OK: non-empty clone subdir target"
        )

        # Test: clone non-repo
        output = env.catch('git subrepo clone dummy-repo', cwd=env.owner / 'bar')
        assert_output_matches(
            output,
            "git-subrepo: Command failed: 'git ls-remote --symref dummy-repo'.",
            "Error OK: clone non-repo"
        )

    finally:
        # Restore environment
        if orig_errors:
            os.environ['GIT_SUBREPO_TEST_ERRORS'] = orig_errors
        else:
            os.environ.pop('GIT_SUBREPO_TEST_ERRORS', None)
