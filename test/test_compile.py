"""Tests for git-subrepo compilation"""

import subprocess


def test_compile(env):
    """Test that git-subrepo bash scripts can be sourced"""
    # Test sourcing lib/git-subrepo
    result = subprocess.run(
        ['bash', '-c', 'source lib/git-subrepo'],
        cwd=env.test_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, 'source lib/git-subrepo should succeed'
