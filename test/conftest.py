"""Pytest configuration and fixtures for git-subrepo tests"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest


class TestEnvironment:
    """Test environment with helper functions"""

    def __init__(self, tmp_dir: Path, test_dir: Path):
        self.tmp = tmp_dir
        self.test_dir = test_dir
        self.upstream = tmp_dir / "upstream"
        self.owner = tmp_dir / "owner"
        self.collab = tmp_dir / "collab"
        self.test_home = tmp_dir / "home"

        # Get default branch
        git_version = subprocess.run(
            ['git', '--version'], capture_output=True, text=True, check=True
        ).stdout.strip()
        match = re.search(r'(\d+)\.(\d+)', git_version)
        if match:
            git_major = int(match.group(1))
            git_minor = int(match.group(2))
            if git_major > 2 or (git_major == 2 and git_minor >= 28):
                result = subprocess.run(
                    ['git', 'config', '--global', '--get', 'init.defaultbranch'],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.defaultbranch = (
                    result.stdout.strip() if result.returncode == 0 else 'master'
                )
            else:
                self.defaultbranch = 'master'
        else:
            self.defaultbranch = 'master'

    def run(self, cmd, cwd=None, check=True, capture_output=True):
        """Run a shell command"""
        if isinstance(cmd, str):
            result = subprocess.run(
                cmd,
                shell=True,
                cwd=cwd,
                capture_output=capture_output,
                text=True,
                check=check,
            )
        else:
            result = subprocess.run(
                cmd, cwd=cwd, capture_output=capture_output, text=True, check=check
            )
        return result

    def clone_foo_and_bar(self):
        """Clone foo and bar repos into owner directory"""
        # Clone foo (main repo)
        self.run(f'git clone "{self.upstream}/foo" "{self.owner}/foo"', check=True)
        self.run('git config core.autocrlf input', cwd=self.owner / 'foo')
        self.run('git config user.name "FooUser"', cwd=self.owner / 'foo')
        self.run('git config user.email "foo@foo"', cwd=self.owner / 'foo')

        # Clone bar (subrepo)
        self.run(f'git clone "{self.upstream}/bar" "{self.owner}/bar"', check=True)
        self.run('git config core.autocrlf input', cwd=self.owner / 'bar')
        self.run('git config user.name "BarUser"', cwd=self.owner / 'bar')
        self.run('git config user.email "bar@bar"', cwd=self.owner / 'bar')

    def subrepo_clone_bar_into_foo(self):
        """Clone bar subrepo into foo"""
        self.run(f'git subrepo clone "{self.upstream}/bar"', cwd=self.owner / 'foo')

    def add_new_files(self, *files, cwd=None):
        """Add new files and commit"""
        for file in files:
            file_path = Path(cwd) / file if cwd else Path(file)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(f"new file {file}\n")
            self.run(['git', 'add', '--force', str(file)], cwd=cwd)
        # Commit with the last file name
        self.run(
            ['git', 'commit', '--quiet', '-m', f'add new file: {files[-1]}'], cwd=cwd
        )

    def remove_files(self, *files, cwd=None):
        """Remove files and commit"""
        for file in files:
            self.run(['git', 'rm', file], cwd=cwd)
        # Commit with the last file name
        self.run(
            ['git', 'commit', '--quiet', '-m', f'Removed file: {files[-1]}'], cwd=cwd
        )

    def modify_files(self, *files, cwd=None):
        """Modify files and commit"""
        for file in files:
            file_path = Path(cwd) / file if cwd else Path(file)
            with open(file_path, 'a') as f:
                f.write('a new line\n')
            self.run(['git', 'add', str(file)], cwd=cwd)
        self.run(['git', 'commit', '-m', f'modified file: {files[-1]}'], cwd=cwd)

    def modify_files_ex(self, *files, cwd=None):
        """Modify files (append filename) and commit"""
        for file in files:
            file_path = Path(cwd) / file if cwd else Path(file)
            with open(file_path, 'a') as f:
                f.write(f'{file}\n')
            self.run(['git', 'add', str(file)], cwd=cwd)
        self.run(['git', 'commit', '-m', f'modified file: {files[-1]}'], cwd=cwd)

    def catch(self, cmd, cwd=None):
        """Catch command output (including errors)"""
        result = self.run(cmd, cwd=cwd, check=False)
        # Return stderr if command failed, otherwise stdout
        return (
            result.stderr.strip() if result.returncode != 0 else result.stdout.strip()
        )


@pytest.fixture(scope='function')
def env(tmp_path):
    """Setup test environment for each test"""
    # Get the git-subrepo root directory
    test_file = Path(__file__).parent.parent

    # Create temporary directories
    tmp_dir = tmp_path
    test_env = TestEnvironment(tmp_dir, test_file)

    # Set up temporary home directory for git config
    test_home = tmp_dir / "home"
    test_home.mkdir()

    # Save original environment
    orig_home = os.environ.get('HOME')
    orig_git_config_global = os.environ.get('GIT_CONFIG_GLOBAL')
    orig_git_config_system = os.environ.get('GIT_CONFIG_SYSTEM')
    orig_path = os.environ.get('PATH')
    orig_cwd = os.getcwd()

    # Set up environment
    os.environ['HOME'] = str(test_home)
    os.environ['GIT_CONFIG_GLOBAL'] = str(test_home / '.gitconfig')
    os.environ['GIT_CONFIG_SYSTEM'] = '/dev/null'

    # Add git-subrepo to PATH
    lib_dir = test_file / 'lib'
    os.environ['PATH'] = f"{lib_dir}:{orig_path}"

    # Set up git configuration
    subprocess.run(['git', 'config', '--global', 'user.name', 'Test User'], check=True)
    subprocess.run(
        ['git', 'config', '--global', 'user.email', 'test@example.com'], check=True
    )
    subprocess.run(['git', 'config', '--global', 'core.autocrlf', 'input'], check=True)
    subprocess.run(['git', 'config', '--global', 'core.filemode', 'true'], check=True)
    subprocess.run(['git', 'config', '--global', 'pull.rebase', 'false'], check=True)
    subprocess.run(
        ['git', 'config', '--global', 'advice.detachedHead', 'false'], check=True
    )
    subprocess.run(['git', 'config', '--global', 'color.ui', 'false'], check=True)

    # Set init.defaultBranch if supported
    git_version = subprocess.run(
        ['git', '--version'], capture_output=True, text=True, check=True
    ).stdout.strip()
    match = re.search(r'(\d+)\.(\d+)', git_version)
    if match:
        git_major = int(match.group(1))
        git_minor = int(match.group(2))
        if git_major > 2 or (git_major == 2 and git_minor >= 28):
            subprocess.run(
                ['git', 'config', '--global', 'init.defaultBranch', 'master'],
                check=True,
            )

    # Create test directories
    test_env.upstream.mkdir(parents=True)
    test_env.owner.mkdir(parents=True)
    test_env.collab.mkdir(parents=True)

    # Copy test repos
    repo_dir = test_file / 'test' / 'repo'
    for repo in ['foo', 'bar', 'init']:
        src = repo_dir / repo
        dst = test_env.upstream / repo
        if src.exists():
            shutil.copytree(src, dst)

    yield test_env

    # Cleanup
    os.chdir(orig_cwd)
    if orig_home:
        os.environ['HOME'] = orig_home
    else:
        os.environ.pop('HOME', None)

    if orig_git_config_global:
        os.environ['GIT_CONFIG_GLOBAL'] = orig_git_config_global
    else:
        os.environ.pop('GIT_CONFIG_GLOBAL', None)

    if orig_git_config_system:
        os.environ['GIT_CONFIG_SYSTEM'] = orig_git_config_system
    else:
        os.environ.pop('GIT_CONFIG_SYSTEM', None)

    if orig_path:
        os.environ['PATH'] = orig_path


# Assertion helpers
def assert_exists(path, should_exist=True):
    """Assert that a path exists or doesn't exist"""
    path = Path(path)
    if should_exist:
        assert path.exists(), f"Path '{path}' should exist but doesn't"
    else:
        assert not path.exists(), f"Path '{path}' should not exist but does"


def assert_file_exists(path, should_exist=True):
    """Assert that a file exists or doesn't exist"""
    path = Path(path)
    if should_exist:
        assert path.is_file(), f"File '{path}' should exist but doesn't"
    else:
        assert not path.is_file(), f"File '{path}' should not exist but does"


def assert_dir_exists(path, should_exist=True):
    """Assert that a directory exists or doesn't exist"""
    path = Path(path)
    if should_exist:
        assert path.is_dir(), f"Directory '{path}' should exist but doesn't"
    else:
        assert not path.is_dir(), f"Directory '{path}' should not exist but does"


def assert_in_index(file_path, cwd, should_exist=True):
    """Assert that a file exists in the git index"""
    result = subprocess.run(
        ['git', 'ls-tree', '--full-tree', '--name-only', '-r', 'HEAD', file_path],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    exists = bool(result.stdout.strip())
    if should_exist:
        assert exists, f"File '{file_path}' should exist in index but doesn't"
    else:
        assert not exists, f"File '{file_path}' should not exist in index but does"


def assert_gitrepo_comment_block(gitrepo_path):
    """Assert that .gitrepo file has correct comment block"""
    expected = """; DO NOT EDIT (unless you know what you are doing)
;
; This subdirectory is a git "subrepo", and this file is maintained by the
; git-subrepo command. See https://github.com/ingydotnet/git-subrepo#readme
;"""

    with open(gitrepo_path, 'r') as f:
        content = f.read()

    # Extract comment lines
    comment_lines = [line for line in content.split('\n') if line.startswith(';')]
    actual = '\n'.join(comment_lines)

    assert actual == expected, (
        f"Comment block mismatch.\nExpected:\n{expected}\nActual:\n{actual}"
    )


def assert_gitrepo_field(gitrepo_path, field, expected_value):
    """Assert that .gitrepo file has correct field value"""
    result = subprocess.run(
        ['git', 'config', f'--file={gitrepo_path}', f'subrepo.{field}'],
        capture_output=True,
        text=True,
        check=False,
    )
    actual_value = result.stdout.strip()
    assert actual_value == expected_value, (
        f".gitrepo field '{field}' should be '{expected_value}' but is '{actual_value}'"
    )


def assert_commit_count(repo_path, ref, expected_count):
    """Assert commit count for a ref"""
    result = subprocess.run(
        ['git', 'rev-list', '--count', ref],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    actual_count = int(result.stdout.strip())
    assert actual_count == expected_count, (
        f"Commit count should be {expected_count} but is {actual_count}"
    )


def git_rev_parse(ref, cwd):
    """Get commit SHA for a ref"""
    result = subprocess.run(
        ['git', 'rev-parse', ref], cwd=cwd, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def git_config(key, cwd, file=None):
    """Get git config value"""
    cmd = ['git', 'config']
    if file:
        cmd.extend([f'--file={file}'])
    cmd.append(key)

    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def git_subrepo(args, cwd, check=True):
    """Run git subrepo command"""
    if isinstance(args, str):
        cmd = f'git subrepo {args}'
    else:
        cmd = ['git', 'subrepo'] + args

    result = subprocess.run(
        cmd,
        shell=isinstance(cmd, str),
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )
    return result


def assert_output_matches(actual, expected, description=""):
    """Assert that output matches expected value"""
    assert actual == expected, f"{description}\nExpected: {expected}\nActual: {actual}"


def assert_output_contains(output, pattern, description=""):
    """Assert that output contains pattern"""
    assert pattern in output, (
        f"{description}\nPattern '{pattern}' not found in:\n{output}"
    )


def assert_output_not_contains(output, pattern, description=""):
    """Assert that output doesn't contain pattern"""
    assert pattern not in output, (
        f"{description}\nPattern '{pattern}' should not be in:\n{output}"
    )


def assert_output_like(output, pattern, description=""):
    """Assert that output matches regex pattern"""
    assert re.search(pattern, output), (
        f"{description}\nPattern '{pattern}' not found in:\n{output}"
    )


def assert_output_unlike(output, pattern, description=""):
    """Assert that output doesn't match regex pattern"""
    assert not re.search(pattern, output), (
        f"{description}\nPattern '{pattern}' should not be found in:\n{output}"
    )
