# Repository Security Configuration

This document outlines the recommended security settings for the GitHub repository based on OpenSSF Scorecard best practices.

## Branch Protection Rules

Configure these settings for the `main` branch at:
**Settings → Branches → Add branch protection rule**

### Required Settings

```yaml
Branch name pattern: main

✅ Require a pull request before merging
   ✅ Require approvals: 1
   ✅ Dismiss stale pull request approvals when new commits are pushed
   ✅ Require review from Code Owners (if CODEOWNERS file exists)
   ✅ Require approval of the most recent reviewable push

✅ Require status checks to pass before merging
   ✅ Require branches to be up to date before merging
   Required status checks:
      - build (python-app.yml - pytest, ruff, typecheck)
      - lint (build.yml - ruff)
      - build_docker_image (build.yml - Docker build)

✅ Require conversation resolution before merging

✅ Require signed commits

✅ Require linear history

✅ Do not allow bypassing the above settings
   - Even administrators should follow these rules

✅ Restrict who can push to matching branches
   - Add specific users/teams who can push directly (if any)
   - Generally, leave empty to require PRs for everyone

✅ Allow force pushes: DISABLED
✅ Allow deletions: DISABLED
```

## Repository Settings

### General Settings

**Settings → General**

```yaml
Features:
  ✅ Issues
  ✅ Discussions (optional)
  ⬜ Projects
  ✅ Wiki (optional)
  ⬜ Sponsorships

Pull Requests:
  ✅ Allow merge commits
  ⬜ Allow squash merging (optional)
  ⬜ Allow rebase merging (optional)
  ✅ Always suggest updating pull request branches
  ✅ Allow auto-merge
  ✅ Automatically delete head branches

Archives:
  ⬜ Include Git LFS objects in archives
```

### Security Settings

**Settings → Security → Code security and analysis**

```yaml
Private vulnerability reporting:
  ✅ Enable (allows security researchers to report privately)

Dependency graph:
  ✅ Enable (required for Dependabot)

Dependabot alerts:
  ✅ Enable (get notified of vulnerabilities)

Dependabot security updates:
  ✅ Enable (automatic PRs for security fixes)

Dependabot version updates:
  ✅ Enable (uses .github/dependabot.yml config)

Code scanning:
  ✅ Enable (uses CodeQL or other SARIF tools)
  ✅ Default setup or Advanced setup with workflows

Secret scanning:
  ✅ Enable (scans for leaked secrets)
  ✅ Push protection (blocks pushes with secrets)
```

### Actions Settings

**Settings → Actions → General**

```yaml
Actions permissions:
  ◉ Allow all actions and reusable workflows

Workflow permissions:
  ◉ Read repository contents and packages permissions
  ✅ Allow GitHub Actions to create and approve pull requests

Fork pull request workflows:
  ⬜ Run workflows from fork pull requests
  ⬜ Send write tokens to workflows from fork pull requests
  ⬜ Send secrets to workflows from fork pull requests
```

**Why these settings:**
- Fork PRs don't need write access (security)
- PRs from forks should be reviewed before running workflows
- Prevents malicious PRs from forks accessing secrets

## Required Secrets

Configure these at: **Settings → Secrets and variables → Actions**

### Repository Secrets

```yaml
PYPI_TOKEN:
  Description: PyPI API token for publishing packages
  Required for: python-app.yml workflow
  How to get: https://pypi.org/manage/account/token/

DOCKER_USERNAME:
  Description: Docker Hub username
  Required for: build.yml workflow

DOCKER_PASSWORD:
  Description: Docker Hub password or access token
  Required for: build.yml workflow
  Recommendation: Use access token, not password
  How to get: https://hub.docker.com/settings/security
```

### Repository Variables (Optional)

```yaml
No required variables at this time
```

## CODEOWNERS File

Create `.github/CODEOWNERS` to specify code owners:

```
# Default owner for everything
* @pgmac

# GitHub Actions workflows
/.github/workflows/ @pgmac

# Security sensitive files
/SECURITY.md @pgmac
/REPOSITORY_SECURITY.md @pgmac
/.github/dependabot.yml @pgmac

# Docker and deployment
/Dockerfile @pgmac
/docker-compose.yml @pgmac

# Python source code
/src/ @pgmac

# Documentation
*.md @pgmac
```

## OpenSSF Scorecard Checks

The following settings help improve your OpenSSF Scorecard score:

### Branch Protection (Weight: High)
✅ Implemented via branch protection rules above

### CI Tests (Weight: Low)
✅ Implemented via python-app.yml and build.yml workflows

### Code Review (Weight: High)
✅ Implemented via required PR approvals

### Dangerous Workflow (Weight: High)
✅ Mitigated by:
- Not running workflows on fork PRs
- Using environment variables for untrusted input
- No write permissions by default

### Dependency Update Tool (Weight: High)
✅ Implemented via Dependabot (.github/dependabot.yml)

### Fuzzing (Weight: Medium)
⚠️  Not yet implemented (future enhancement)

### License (Weight: Medium)
✅ Implemented (LICENSE file with MIT license)

### Maintained (Weight: Medium)
✅ Active development and regular commits

### Pinned Dependencies (Weight: Medium)
✅ Python: Using pyproject.toml with version constraints
✅ GitHub Actions: Pinned to specific versions with SHA
⚠️  Consider pinning Docker base images to specific digests

### SAST (Weight: Medium)
✅ Implemented via:
- Ruff linter (security checks)
- Type checking with ty
- OpenSSF Scorecard workflow

### Security Policy (Weight: Medium)
✅ Implemented (SECURITY.md file)

### Signed Releases (Weight: High)
✅ Implemented via:
- GitHub attestations for Docker images
- PyPI publishes signed packages

### Token Permissions (Weight: High)
✅ Implemented via:
- Minimal permissions in workflows
- `permissions:` blocks in all workflows

### Vulnerabilities (Weight: High)
✅ Implemented via:
- Dependabot security updates
- Regular dependency updates

### Webhooks (Weight: Medium)
⚠️  No webhooks configured (not applicable)

## Recommended GitHub Actions Pinning

Pin all GitHub Actions to specific commit SHAs for security:

```yaml
# Instead of:
- uses: actions/checkout@v4

# Use:
- uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # v4.1.1
```

Update the following workflows:
- `.github/workflows/python-app.yml`
- `.github/workflows/build.yml`
- `.github/workflows/scorecard.yml`

## Monitoring and Alerts

### Enable Notifications

1. **Security Advisories**: Watch repository → Custom → Security alerts
2. **Dependabot Alerts**: Automatic via email
3. **Failed Workflows**: Settings → Notifications → Actions

### Regular Reviews

- **Weekly**: Check Dependabot PRs and merge if tests pass
- **Weekly**: Review OpenSSF Scorecard results
- **Monthly**: Audit repository security settings
- **Quarterly**: Review and rotate secrets/tokens

## Additional Security Measures

### Pre-commit Hooks (Optional)

Consider adding pre-commit hooks locally:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: check-yaml
      - id: check-json
      - id: detect-private-key
      - id: trailing-whitespace
      - id: end-of-file-fixer

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix]
```

### Docker Image Signing

Consider signing Docker images with Cosign:

```bash
# Sign image
cosign sign pgmac/nagios-public-status-page:v1.0.0

# Verify signature
cosign verify pgmac/nagios-public-status-page:v1.0.0
```

## Compliance Checklist

Before considering the repository fully secured:

- [ ] Branch protection rules enabled
- [ ] Required status checks configured
- [ ] Dependabot enabled and configured
- [ ] OpenSSF Scorecard workflow running
- [ ] SECURITY.md created
- [ ] Secrets configured (PYPI_TOKEN, DOCKER credentials)
- [ ] CODEOWNERS file created (optional)
- [ ] GitHub Actions pinned to SHAs (recommended)
- [ ] Secret scanning enabled
- [ ] Code scanning enabled
- [ ] Signed commits required
- [ ] Review scorecard results and address issues

## Resources

- [OpenSSF Scorecard](https://github.com/ossf/scorecard)
- [GitHub Branch Protection](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [Dependabot Documentation](https://docs.github.com/en/code-security/dependabot)
- [GitHub Actions Security](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
- [OpenSSF Best Practices](https://bestpractices.coreinfrastructure.org/)
