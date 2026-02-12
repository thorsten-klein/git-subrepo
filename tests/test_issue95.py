"""Tests for issue #95"""
import subprocess
from conftest import (
    git_subrepo, assert_output_matches
)


def test_issue95(env):
    """Test issue #95: Pull after merge with feature branch"""
    # Make two new repos
    host_dir = env.tmp / 'host'
    sub_dir = env.tmp / 'sub'

    host_dir.mkdir()
    sub_dir.mkdir()

    subprocess.run(['git', 'init'], cwd=host_dir, check=True, capture_output=True)
    subprocess.run(['git', 'init'], cwd=sub_dir, check=True, capture_output=True)

    # Initialize host repo
    (host_dir / 'host').touch()
    subprocess.run(['git', 'add', 'host'], cwd=host_dir, check=True)
    subprocess.run(
        ['git', 'commit', '-m', 'host initial commit'],
        cwd=host_dir,
        check=True,
        capture_output=True
    )

    # Initialize sub repo
    (sub_dir / 'subrepo').touch()
    subprocess.run(['git', 'add', 'subrepo'], cwd=sub_dir, check=True)
    subprocess.run(
        ['git', 'commit', '-m', 'subrepo initial commit'],
        cwd=sub_dir,
        check=True,
        capture_output=True
    )

    # Make sub a subrepo of host
    git_subrepo('clone ../sub sub', cwd=host_dir)

    # Create a branch in host and make some changes in it
    subprocess.run(
        ['git', 'checkout', '-b', 'feature'],
        cwd=host_dir,
        check=True,
        capture_output=True
    )
    (host_dir / 'feature').touch()
    subprocess.run(['git', 'add', 'feature'], cwd=host_dir, check=True)
    subprocess.run(
        ['git', 'commit', '-m', 'feature added'],
        cwd=host_dir,
        check=True,
        capture_output=True
    )
    subprocess.run(
        ['git', 'checkout', env.defaultbranch],
        cwd=host_dir,
        check=True,
        capture_output=True
    )

    # Commit directly to subrepo
    with open(sub_dir / 'subrepo', 'a') as f:
        f.write("direct change in sub\n")
    subprocess.run(
        ['git', 'commit', '-a', '-m', 'direct change in sub'],
        cwd=sub_dir,
        check=True,
        capture_output=True
    )

    # Pull subrepo changes
    git_subrepo('pull sub', cwd=host_dir)

    # Commit directly to subrepo
    with open(sub_dir / 'subrepo', 'a') as f:
        f.write("another direct change in sub\n")
    subprocess.run(
        ['git', 'commit', '-a', '-m', 'another direct change in sub'],
        cwd=sub_dir,
        check=True,
        capture_output=True
    )

    # Commit to host/sub
    (host_dir / 'sub' / 'subrepo-host').write_text("change from host\n")
    subprocess.run(['git', 'add', 'sub/subrepo-host'], cwd=host_dir, check=True)
    subprocess.run(
        ['git', 'commit', '-m', 'change from host'],
        cwd=host_dir,
        check=True,
        capture_output=True
    )

    # Merge previously created feature branch
    subprocess.run(
        ['git', 'merge', '--no-ff', '--no-edit', 'feature'],
        cwd=host_dir,
        check=True,
        capture_output=True
    )

    # Pull subrepo changes - expected: successful pull without conflicts
    result = git_subrepo('pull sub', cwd=host_dir)

    assert_output_matches(
        result.stdout.strip(),
        f"Subrepo 'sub' pulled from '../sub' ({env.defaultbranch}).",
        "Pull after merge succeeded"
    )
