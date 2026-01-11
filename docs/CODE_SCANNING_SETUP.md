# Code Scanning and Coverage Setup

This document explains the code scanning and test coverage systems configured for this repository.

## Overview

The repository uses multiple automated scanning and quality assurance tools:

1. **CodeQL** - Advanced security code scanning
2. **Codecov** - Test coverage reporting and tracking
3. **Ruff** - Fast Python linter
4. **ty** - Python type checking
5. **pytest** - Test framework with coverage

## CodeQL Security Scanning

### What is CodeQL?

CodeQL is GitHub's semantic code analysis engine that treats code as data, allowing you to query your codebase for security vulnerabilities and coding errors.

### Configuration

The CodeQL workflow is defined in `.github/workflows/codeql.yml` and runs:

- **On push to main** - Scans every commit to the main branch
- **On pull requests** - Scans all PR code before merge
- **Weekly schedule** - Runs every Monday at 2:00 AM UTC to catch new vulnerabilities

### What it Scans For

The workflow uses two query suites:

1. **security-extended** - Comprehensive security vulnerability detection including:
   - SQL injection
   - Cross-site scripting (XSS)
   - Command injection
   - Path traversal
   - Cryptographic issues
   - Authentication and authorization flaws

2. **security-and-quality** - Security issues plus code quality problems:
   - Code smells
   - Maintainability issues
   - Performance problems
   - Best practice violations

### Viewing Results

CodeQL results are available in multiple places:

1. **Security Tab** - Navigate to `https://github.com/pgmac-net/nagios-public-status-page/security/code-scanning`
2. **Pull Request Checks** - Automated comments appear on PRs if issues are found
3. **Actions Tab** - Full workflow logs available at each run

### Addressing CodeQL Findings

When CodeQL finds an issue:

1. Review the alert in the Security tab
2. Click the alert to see:
   - Detailed explanation of the vulnerability
   - Code location and data flow
   - Recommended fixes
   - CWE classification
3. Fix the code and push changes
4. CodeQL will automatically re-scan and close resolved alerts

## Codecov Test Coverage

### What is Codecov?

Codecov provides detailed test coverage analysis, showing which lines of code are tested and which are not. This helps identify gaps in test coverage and track coverage trends over time.

### Configuration

Coverage is collected in `.github/workflows/python-app.yml`:

```yaml
- name: Test with pytest
  run: |
    uv run pytest -v --tb=short --cov=nagios_public_status_page --cov-report=xml --cov-report=term

- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v5
  with:
    file: ./coverage.xml
    flags: unittests
    fail_ci_if_error: false
```

### Required Setup

To enable Codecov, you need to:

1. **Sign up at Codecov** - Visit https://codecov.io and sign in with GitHub
2. **Add the repository** - Enable coverage tracking for this repo
3. **Add secret** - Add `CODECOV_TOKEN` to GitHub repository secrets:
   - Go to Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `CODECOV_TOKEN`
   - Value: Token from Codecov dashboard

### Viewing Coverage Reports

Coverage data is available:

1. **Codecov Dashboard** - https://codecov.io/gh/pgmac-net/nagios-public-status-page
   - Overall coverage percentage
   - Coverage trend graphs
   - File-by-file breakdown
   - Line-by-line visualization

2. **Pull Request Comments** - Codecov bot comments on PRs showing:
   - Coverage change (increase/decrease)
   - Impact on overall coverage
   - Uncovered lines in the diff

3. **README Badge** - Shows current coverage percentage

### Coverage Goals

Target coverage levels:

- **Overall**: Aim for 80%+ coverage
- **Critical paths**: 100% coverage for security-sensitive code
- **New code**: PRs should not decrease overall coverage

## Local Development

### Running Tests with Coverage Locally

```bash
# Run tests with coverage report
uv run pytest --cov=nagios_public_status_page --cov-report=html --cov-report=term

# View HTML coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Running CodeQL Locally

CodeQL CLI is available for local analysis:

```bash
# Install CodeQL CLI
gh extension install github/gh-codeql

# Run analysis
gh codeql database create codeql-db --language=python
gh codeql database analyze codeql-db --format=sarif-latest --output=results.sarif
```

### Running Linters Locally

```bash
# Run Ruff
uv run ruff check src/ tests/

# Auto-fix Ruff issues
uv run ruff check --fix src/ tests/

# Run pylint
uv run pylint src/nagios_public_status_page/

# Run type checking
uvx ty check src
```

## Continuous Integration

### PR Requirements

Before a PR can be merged, it must pass:

1. ✅ All pytest tests
2. ✅ Ruff linting (no errors)
3. ✅ Type checking with ty
4. ✅ CodeQL security scan (no high-severity findings)
5. ✅ Coverage should not decrease significantly

### Workflow Integration

All checks run automatically:

- **python-app.yml** - Tests, linting, type checking, coverage
- **codeql.yml** - Security scanning
- **build.yml** - Docker linting and builds

Results are reported via:

- GitHub status checks on PRs
- PR comments with detailed results
- Job summaries in Actions tab
- Security tab alerts (for CodeQL)

## Troubleshooting

### CodeQL Issues

**Problem**: CodeQL finds false positives

**Solution**: Add a comment to suppress:
```python
# codeql[python/sql-injection]
# Safe: query is constructed from validated config, not user input
cursor.execute(query)
```

**Problem**: CodeQL scan times out

**Solution**: Increase timeout in `.github/workflows/codeql.yml`:
```yaml
timeout-minutes: 360  # Increase if needed
```

### Coverage Issues

**Problem**: Coverage not uploading to Codecov

**Solution**:
1. Check `CODECOV_TOKEN` secret is set correctly
2. Verify coverage.xml is being generated
3. Check Codecov action logs for errors

**Problem**: Coverage drops unexpectedly

**Solution**:
1. Review the diff to see uncovered lines
2. Add tests for new code
3. Check for deleted test files

### Linting Issues

**Problem**: Ruff reports errors locally but CI passes

**Solution**: Ensure you're using the same version:
```bash
uv sync  # Sync dependencies
uv run ruff --version  # Check version
```

## Best Practices

### Security

1. **Review all CodeQL alerts** - Don't ignore security findings
2. **Fix high-severity issues immediately** - Block PRs if needed
3. **Update dependencies regularly** - Use Dependabot for security patches
4. **Test security-sensitive code thoroughly** - Aim for 100% coverage

### Coverage

1. **Write tests for new features** - Don't decrease coverage
2. **Test edge cases** - Don't just test happy paths
3. **Mock external dependencies** - Test code in isolation
4. **Review coverage reports** - Identify untested code paths

### Code Quality

1. **Fix linting errors before committing** - Run ruff locally
2. **Use type hints** - Enable better static analysis
3. **Write docstrings** - Document complex logic
4. **Keep functions small** - Easier to test and analyze

## Additional Resources

- [CodeQL Documentation](https://codeql.github.com/docs/)
- [Codecov Documentation](https://docs.codecov.com/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [pytest Coverage Documentation](https://pytest-cov.readthedocs.io/)
- [OpenSSF Best Practices](https://bestpractices.coreinfrastructure.org/)
