"""Tests for zsh compatibility"""
import subprocess
import pytest
from pathlib import Path


def test_zsh(env):
    """Test that .rc works with various zsh versions"""
    # Check if docker is available
    result = subprocess.run(
        ['which', 'docker'],
        capture_output=True,
        text=True,
        check=False
    )

    if result.returncode != 0:
        pytest.skip("The 'docker' utility is not installed")

    # Test with various zsh versions
    zsh_versions = ['5.8', '5.6', '5.0.1', '4.3.11']

    for zsh_version in zsh_versions:
        result = subprocess.run(
            [
                'docker', 'run', '--rm', '-it',
                f'--volume={env.test_dir}:/git-subrepo',
                '--entrypoint=',
                f'zshusers/zsh:{zsh_version}',
                'zsh', '-c', 'source /git-subrepo/.rc 2>&1'
            ],
            capture_output=True,
            text=True,
            check=False
        )

        error_output = result.stdout.strip() if result.returncode != 0 else ''
        assert error_output == '', f"'source .rc' works for zsh-{zsh_version}"
