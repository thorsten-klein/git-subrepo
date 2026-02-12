# Pytest Tests for git-subrepo

This directory contains pytest-based tests for git-subrepo, converted from the original Bash/prove tests.

## Requirements

Install test dependencies:

```bash
pip install -r requirements-test.txt
```

Or install pytest directly:

```bash
pip install pytest>=7.0.0 pytest-xdist>=3.0.0
```

## Running Tests

### Run all tests

```bash
pytest tests/
```

### Run tests with verbose output

```bash
pytest tests/ -v
```

### Run a specific test file

```bash
pytest tests/test_clone.py
```

### Run tests in parallel (faster)

```bash
pytest tests/ -n auto
```

### Run tests matching a pattern

```bash
pytest tests/ -k pull
```

This will run all tests with "pull" in the name (test_pull.py, test_pull_all.py, etc.)

## Test Structure

- **conftest.py**: Pytest fixtures and helper functions
  - `env` fixture: Sets up test environment with temporary directories
  - Helper functions: `assert_exists`, `assert_gitrepo_field`, `git_subrepo`, etc.

- **test_*.py**: Individual test files, one per original .t file
  - Each test function takes the `env` fixture as a parameter
  - Tests use the helper functions from conftest.py

## Test Coverage

All 38 original Bash tests have been converted:

### Core Functionality
- test_clone.py - Basic clone functionality
- test_pull.py - Basic pull functionality
- test_push.py - Basic push functionality
- test_branch.py - Branch creation
- test_clean.py - Cleanup functionality
- test_fetch.py - Fetch functionality
- test_init.py - Initialize subrepo
- test_status.py - Status command
- test_config.py - Config command

### Clone Tests
- test_clone_annotated_tag.py - Clone with annotated tags

### Pull Tests
- test_pull_all.py - Pull with --all flag
- test_pull_merge.py - Pull with merge strategy
- test_pull_message.py - Pull with custom message
- test_pull_new_branch.py - Pull from new branch
- test_pull_ours.py - Pull with --ours conflict resolution
- test_pull_theirs.py - Pull with --theirs conflict resolution
- test_pull_twice.py - Multiple pulls
- test_pull_worktree.py - Pull with worktrees

### Push Tests
- test_push_after_init.py - Push after init
- test_push_after_push_no_changes.py - Push with no changes after push
- test_push_force.py - Force push
- test_push_new_branch.py - Push to new branch
- test_push_no_changes.py - Push with no changes
- test_push_squash.py - Push with squash

### Branch Tests
- test_branch_all.py - Branch with --all
- test_branch_rev_list.py - Branch with revision list
- test_branch_rev_list_one_path.py - Branch with single path

### Special Cases
- test_encode.py - Special characters in directory names
- test_error.py - Error conditions and messages
- test_gitignore.py - .gitignore handling
- test_rebase.py - Rebase scenarios
- test_reclone.py - Reclone functionality
- test_submodule.py - Submodule compatibility
- test_compile.py - Compilation/syntax check
- test_zsh.py - Zsh compatibility

### Issue-Specific Tests
- test_issue29.py - Regression test for issue #29
- test_issue95.py - Regression test for issue #95
- test_issue96.py - Regression test for issue #96

## Comparison with Original Tests

The pytest tests provide the same coverage as the original Bash tests in `test/*.t`, but with:

- **Better isolation**: Each test runs in a fresh environment
- **Clearer output**: pytest provides detailed failure information
- **Parallel execution**: Can run tests in parallel with pytest-xdist
- **Better IDE integration**: Most IDEs have built-in pytest support
- **Cross-platform**: Python-based tests are more portable than Bash tests

## Development

When adding new tests:

1. Create a new file `tests/test_<name>.py`
2. Import helpers from conftest
3. Define test function with `env` fixture:

```python
from conftest import assert_exists, git_subrepo

def test_my_feature(env):
    env.clone_foo_and_bar()
    result = git_subrepo('clone ...', cwd=env.owner / 'foo')
    assert_exists(env.owner / 'foo' / 'bar')
```

## Continuous Integration

Both test frameworks are supported:

```bash
# Original Bash tests
make test

# Pytest tests
pytest tests/
```

Both should pass with the same results.
