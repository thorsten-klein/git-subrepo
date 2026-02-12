"""Tests for git subrepo clone with annotated tag"""

import subprocess
from conftest import git_subrepo, assert_output_matches


def test_clone_annotated_tag(env):
    """Test cloning subrepo with annotated and lightweight tags"""
    env.clone_foo_and_bar()

    # Create tags in bar repo
    subprocess.run(
        ['git', 'tag', '-a', 'annotated_tag', '-m', 'My annotated tag'],
        cwd=env.owner / 'bar',
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'tag', 'lightweight_tag'],
        cwd=env.owner / 'bar',
        check=True,
        capture_output=True,
    )

    # Clone with lightweight tag
    result = git_subrepo(
        'clone ../bar/.git -b lightweight_tag light', cwd=env.owner / 'foo'
    )

    assert_output_matches(
        result.stdout.strip(),
        "Subrepo '../bar/.git' (lightweight_tag) cloned into 'light'.",
        'subrepo clone lightweight tag command output is correct',
    )

    # Clone with annotated tag
    result = git_subrepo(
        'clone ../bar/.git -b annotated_tag ann', cwd=env.owner / 'foo', check=False
    )

    # Should succeed even with annotated tag
    output = result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    assert_output_matches(
        output,
        "Subrepo '../bar/.git' (annotated_tag) cloned into 'ann'.",
        'subrepo clone annotated command output is correct',
    )
