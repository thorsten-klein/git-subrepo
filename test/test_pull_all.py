"""Tests for git subrepo pull --all command"""

import subprocess
from conftest import assert_output_matches


def test_pull_all(env):
    """Test subrepo pull --all functionality"""
    env.clone_foo_and_bar()

    # Clone two subrepos
    subprocess.run(
        ['git', 'subrepo', 'clone', '../bar', 'bar1'],
        cwd=env.owner / 'foo',
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'subrepo', 'clone', '../bar', 'bar2'],
        cwd=env.owner / 'foo',
        check=True,
        capture_output=True,
    )

    # Modify bar
    env.modify_files('Bar', cwd=env.owner / 'bar')

    # Pull all subrepos
    subprocess.run(
        ['git', 'subrepo', 'pull', '--all'],
        cwd=env.owner / 'foo',
        check=True,
        capture_output=True,
    )

    # Check that both were updated
    bar1_content = (env.owner / 'foo' / 'bar1' / 'Bar').read_text()
    assert_output_matches(
        bar1_content.strip(), 'a new line', 'bar1/Bar content correct'
    )

    bar2_content = (env.owner / 'foo' / 'bar2' / 'Bar').read_text()
    assert_output_matches(
        bar2_content.strip(), 'a new line', 'bar2/Bar content correct'
    )
