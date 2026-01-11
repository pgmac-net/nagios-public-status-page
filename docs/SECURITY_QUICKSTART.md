# Security Quick Start

5-minute security setup for your repository.

## 🚀 Essential Settings (Do These First)

### 1. Branch Protection (2 minutes)

**Settings → Branches → Add rule**

```
Branch: main

✅ Require pull requests (1 approval)
✅ Require status checks: build, lint, build_docker_image
✅ Require conversation resolution
✅ No force pushes
✅ No deletions
```

**Status checks will appear after first workflow run**

### 2. Security Features (1 minute)

**Settings → Security → Code security and analysis**

```
✅ Dependabot alerts
✅ Dependabot security updates
✅ Secret scanning
✅ Push protection
```

### 3. Required Secrets (2 minutes)

**Settings → Secrets → Actions**

```
Add secrets:
- PYPI_TOKEN (from pypi.org/manage/account/token/)
- DOCKER_USERNAME (your Docker Hub username)
- DOCKER_PASSWORD (from hub.docker.com/settings/security - use token, not password)
```

## ✅ Verification

After setup, verify:

```bash
# This should be blocked:
git push origin main
# Expected: "main is protected and requires a pull request"

# This is the correct way:
git checkout -b feature/test
git push origin feature/test
# Then create PR on GitHub
```

## 📊 Monitor Security

**Weekly checks:**
- Review Dependabot PRs
- Check OpenSSF Scorecard score
- Merge security updates

**Badge to add to your README:**
```markdown
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/pgmac-net/nagios-public-status-page/badge)](https://scorecard.dev/viewer/?uri=github.com/pgmac-net/nagios-public-status-page)
```

## 📚 Detailed Guides

- Full setup: [BRANCH_PROTECTION_SETUP.md](BRANCH_PROTECTION_SETUP.md)
- All settings: [REPOSITORY_SECURITY.md](REPOSITORY_SECURITY.md)
- User policy: [SECURITY.md](SECURITY.md)

## 🎯 OpenSSF Scorecard

After workflows run, check your score:
https://scorecard.dev/viewer/?uri=github.com/pgmac-net/nagios-public-status-page

**Target**: 8.0+ score

## 🔧 Optional (But Recommended)

### Signed Commits

```bash
# Generate key
gpg --full-generate-key

# Configure git
git config --global commit.gpgsign true

# Add to GitHub
gpg --armor --export YOUR_KEY_ID
# Paste at: Settings → SSH and GPG keys
```

### CODEOWNERS

Create `.github/CODEOWNERS`:
```
* @pgmac
/.github/ @pgmac
```

Then enable in branch protection:
- ✅ Require review from Code Owners

## ⚠️ Common Issues

**Status checks not appearing?**
- Push this commit first
- Wait for workflows to run
- Return to add status checks

**Dependabot not working?**
- Enable in Security settings
- Wait 24 hours for first scan

**Secrets not working?**
- Verify secret names match exactly
- Check Actions logs for errors

## 🎉 Done!

Your repository is now protected with:
- ✅ Required code review
- ✅ Automated testing
- ✅ Dependency scanning
- ✅ Secret protection
- ✅ OpenSSF compliance

**Next**: Create a test PR to verify everything works!
