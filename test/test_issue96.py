"""Tests for issue #96"""

import subprocess
from conftest import git_subrepo, assert_output_matches


def test_issue96(env):
    """Test issue #96: Push and pull with feature branch"""
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
        capture_output=True,
    )

    # Initialize sub repo
    (sub_dir / 'subrepo').touch()
    subprocess.run(['git', 'add', 'subrepo'], cwd=sub_dir, check=True)
    subprocess.run(
        ['git', 'commit', '-m', 'subrepo initial commit'],
        cwd=sub_dir,
        check=True,
        capture_output=True,
    )

    # Make sub a subrepo of host
    git_subrepo('clone ../sub sub', cwd=host_dir)

    # Commit some changes to the host repo
    (host_dir / 'feature').touch()
    subprocess.run(['git', 'add', 'feature'], cwd=host_dir, check=True)
    subprocess.run(
        ['git', 'commit', '-m', 'feature added'],
        cwd=host_dir,
        check=True,
        capture_output=True,
    )

    # Commit directly to subrepo
    with open(sub_dir / 'subrepo', 'a') as f:
        f.write("direct change in sub\n")
    subprocess.run(
        ['git', 'commit', '-a', '-m', 'direct change in sub'],
        cwd=sub_dir,
        check=True,
        capture_output=True,
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
        capture_output=True,
    )
    # Checkout temp branch otherwise push to master will fail
    subprocess.run(
        ['git', 'checkout', '-b', 'temp'], cwd=sub_dir, check=True, capture_output=True
    )

    # Commit to host/sub
    (host_dir / 'sub' / 'subrepo-host').write_text("change from host\n")
    subprocess.run(['git', 'add', 'sub/subrepo-host'], cwd=host_dir, check=True)
    subprocess.run(
        ['git', 'commit', '-m', 'change from host'],
        cwd=host_dir,
        check=True,
        capture_output=True,
    )

    # Pull subrepo changes - expected: successful pull without conflicts
    result = git_subrepo('pull sub', cwd=host_dir)

    assert_output_matches(
        result.stdout.strip(),
        f"Subrepo 'sub' pulled from '../sub' ({env.defaultbranch}).",
        "Pull succeeded",
    )

    # Push subrepo changes - expected: successful push without conflicts
    result = git_subrepo(f'push sub -b {env.defaultbranch} -u', cwd=host_dir)

    assert_output_matches(
        result.stdout.strip(),
        f"Subrepo 'sub' pushed to '../sub' ({env.defaultbranch}).",
        "Push succeeded",
    )
