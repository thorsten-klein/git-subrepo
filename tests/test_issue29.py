"""Tests for issue #29"""
import subprocess
from conftest import (
    git_subrepo, assert_output_matches
)


def test_issue29(env):
    """Test issue #29: Multiple repos pushing and pulling to same subrepo"""
    # Make 3 new repos
    share_dir = env.tmp / 'share'
    main1_dir = env.tmp / 'main1'
    main2_dir = env.tmp / 'main2'

    share_dir.mkdir()
    main1_dir.mkdir()
    main2_dir.mkdir()

    subprocess.run(['git', 'init'], cwd=share_dir, check=True, capture_output=True)
    subprocess.run(['git', 'init'], cwd=main1_dir, check=True, capture_output=True)
    subprocess.run(['git', 'init'], cwd=main2_dir, check=True, capture_output=True)

    # Add an empty 'readme' to the share repo
    (share_dir / '.gitattributes').write_text('* text eol=lf\n')
    (share_dir / 'readme').touch()
    subprocess.run(['git', 'add', 'readme', '.gitattributes'], cwd=share_dir, check=True)
    subprocess.run(
        ['git', 'commit', '-m', 'Initial share'],
        cwd=share_dir,
        check=True,
        capture_output=True
    )
    # To push into here later we must not have working copy on master branch
    subprocess.run(
        ['git', 'checkout', '-b', 'temp'],
        cwd=share_dir,
        check=True,
        capture_output=True
    )

    # Clone the share repo into main1
    (main1_dir / 'main1').touch()
    subprocess.run(['git', 'add', 'main1'], cwd=main1_dir, check=True)
    subprocess.run(
        ['git', 'commit', '-m', 'Initial main1'],
        cwd=main1_dir,
        check=True,
        capture_output=True
    )
    git_subrepo(
        f'clone ../share share -b {env.defaultbranch}',
        cwd=main1_dir
    )

    # Clone the share repo into main2
    (main2_dir / 'main2').touch()
    subprocess.run(['git', 'add', 'main2'], cwd=main2_dir, check=True)
    subprocess.run(
        ['git', 'commit', '-m', 'Initial main2'],
        cwd=main2_dir,
        check=True,
        capture_output=True
    )
    git_subrepo(
        f'clone ../share share -b {env.defaultbranch}',
        cwd=main2_dir
    )

    # Make a change to the main1 subrepo and push it
    msg_main1 = "main1 initial add to subrepo"
    readme_path = main1_dir / 'share' / 'readme'
    with open(readme_path, 'a') as f:
        f.write(f"{msg_main1}\n")
    subprocess.run(['git', 'add', 'share/readme'], cwd=main1_dir, check=True)
    subprocess.run(
        ['git', 'commit', '-m', msg_main1],
        cwd=main1_dir,
        check=True,
        capture_output=True
    )
    git_subrepo('push share', cwd=main1_dir)

    # Check that the subrepo-push/share branch was deleted after push
    result = subprocess.run(
        ['git', 'branch', '--list', 'subrepo-push/share'],
        cwd=main1_dir,
        capture_output=True,
        text=True,
        check=True
    )
    assert result.stdout.strip() == '', "The subrepo-push/share branch was deleted after push"

    # Pull in the subrepo changes from above into main2
    # Make a local change to the main2 subrepo and push it
    msg_main2 = "main2 initial add to subrepo"
    git_subrepo('pull share', cwd=main2_dir)
    readme_path = main2_dir / 'share' / 'readme'
    with open(readme_path, 'a') as f:
        f.write(f"{msg_main2}\n")
    subprocess.run(['git', 'add', 'share/readme'], cwd=main2_dir, check=True)
    subprocess.run(
        ['git', 'commit', '-m', msg_main2],
        cwd=main2_dir,
        check=True,
        capture_output=True
    )
    git_subrepo('push share', cwd=main2_dir)

    # Go back into main1 and pull the subrepo updates
    git_subrepo('pull share', cwd=main1_dir)

    # The readme file should have both changes
    readme_content = (main1_dir / 'share' / 'readme').read_text()
    expected = f"{msg_main1}\n{msg_main2}\n"
    assert_output_matches(
        readme_content,
        expected,
        "The readme file in the share repo has both subrepo commits"
    )
