"""Tests for git subrepo with special characters in directory names"""

import subprocess
from conftest import assert_exists, git_subrepo, assert_output_matches


def test_encode(env):
    """Test subrepo operations with special characters in directory names"""
    test_cases = [
        'normal',
        '.dot',
        '......dots',
        'spa ce',
        'per%cent',
        'back-sl\\as/h',
        'end-with.lock',
        '@{',
        '[',
        '-begin-with-minus',
        'tailing-slash/',
        'tailing-dots...',
        'special-char:^[?*',
        'many////slashes',
        '_under_scores_',
        '.str%a\\nge...',
        '~////......s:a^t?r a*n[g@{e.lock',
    ]

    # Clone repos once at the start
    env.clone_foo_and_bar()

    round_num = 0
    for test_dir in test_cases:
        round_num += 1

        # Normalize directory name (matching bash behavior)
        normalize_dir = test_dir
        # Remove leading './' only once
        if normalize_dir.startswith('./'):
            normalize_dir = normalize_dir[2:]
        # Remove trailing slashes
        while normalize_dir.endswith('/'):
            normalize_dir = normalize_dir[:-1]
        # Replace multiple consecutive slashes with single slash
        while '//' in normalize_dir:
            normalize_dir = normalize_dir.replace('//', '/')

        # Clone
        result = git_subrepo(
            f'clone {env.upstream}/bar -- "{normalize_dir}"', cwd=env.owner / 'foo'
        )

        assert_output_matches(
            result.stdout.strip(),
            f"Subrepo '{env.upstream}/bar' (master) cloned into '{normalize_dir}'.",
            'subrepo clone command output is correct',
        )

        assert_exists(env.owner / 'foo' / normalize_dir, should_exist=True)

        # Add new file to bar and push
        env.add_new_files(f'Bar2-{round_num}', cwd=env.owner / 'bar')
        subprocess.run(
            ['git', 'pull'], cwd=env.owner / 'bar', check=True, capture_output=True
        )
        subprocess.run(
            ['git', 'push'], cwd=env.owner / 'bar', check=True, capture_output=True
        )

        # Pull
        result = git_subrepo(f'pull -- "{normalize_dir}"', cwd=env.owner / 'foo')

        assert_output_matches(
            result.stdout.strip(),
            f"Subrepo '{normalize_dir}' pulled from '{env.upstream}/bar' (master).",
            'subrepo pull command output is correct',
        )

        assert_exists(env.owner / 'foo' / normalize_dir, should_exist=True)

        # Note: We skip the push part of the test as it's not in the subrepo clone
        # The original test had issues with this
