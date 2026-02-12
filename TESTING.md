# Testing

This document describes how to run tests for git-subrepo.

## Prerequisites

The project uses [uv](https://github.com/astral-sh/uv) for Python dependency management.

### Installing uv

```bash
# On macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or with pip
pip install uv
```

## Running Tests

### Python Tests (pytest)

The project uses pytest for Python testing. All dependencies are managed by uv.

```bash
# Sync dependencies (first time or after updating pyproject.toml)
uv sync --dev

# Run all tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run specific test file
uv run pytest test/test_clone.py

# Run tests in parallel
uv run pytest -n auto

# Run tests with coverage
uv run pytest --cov=lib --cov-report=html
```

### Bash Tests (make test)

The project also has extensive bash test suite:

```bash
make test
```

This runs all bash tests located in the `test/` directory.

## Development Workflow

```bash
# Clone the repository
git clone https://github.com/ingydotnet/git-subrepo
cd git-subrepo

# Sync dependencies
uv sync --dev

# Run Python tests
uv run pytest -v

# Run bash tests
make test

# Run both
uv run pytest -v && make test
```

## Test Structure

- `test/` - Contains both Python and bash tests
- `test/conftest.py` - Pytest configuration and fixtures
- `test/test_*.py` - Python test files

## Continuous Integration

Tests are automatically run on CI for:
- Multiple Python versions (3.7+)
- Multiple platforms (Linux, macOS, Windows)

## Adding New Tests

### Python Tests

Create a new file `test/test_<feature>.py`:

```python
"""Tests for <feature>"""
from conftest import git_subrepo, assert_exists

def test_my_feature(env):
    """Test description"""
    # Your test code here
    pass
```

### Bash Tests

For bash tests, refer to the existing test files in `test/` directory.

## Troubleshooting

### Tests failing locally but passing in CI

Make sure you have synced dependencies:
```bash
uv sync --dev
```

### Permission errors

Ensure test files have execute permissions:
```bash
chmod +x test/*.t
```

### Git version

git-subrepo requires git >= 2.23. Check your version:
```bash
git --version
```
