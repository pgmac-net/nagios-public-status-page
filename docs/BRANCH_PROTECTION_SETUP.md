# Branch Protection Setup Guide

Follow these steps to configure branch protection for the `main` branch.

## Step 1: Navigate to Branch Protection Settings

1. Go to your repository: https://github.com/pgmac-net/nagios-public-status-page
2. Click **Settings** (top menu)
3. Click **Branches** (left sidebar under "Code and automation")
4. Click **Add branch protection rule** (or **Add rule**)

## Step 2: Configure Branch Name Pattern

```
Branch name pattern: main
```

## Step 3: Configure Protection Rules

### ✅ Require a pull request before merging

**Check this box**, then configure the following sub-options:

- ✅ **Require approvals**: Set to `1`
  - This requires at least one approval before merging

- ✅ **Dismiss stale pull request approvals when new commits are pushed**
  - Forces re-approval if code changes after review

- ✅ **Require review from Code Owners**
  - Only applies if you create a CODEOWNERS file (recommended)
  - You can create `.github/CODEOWNERS` with:
    ```
    * @pgmac
    /.github/ @pgmac
    /src/ @pgmac
    ```

- ✅ **Require approval of the most recent reviewable push**
  - Ensures the most recent changes are approved

### ✅ Require status checks to pass before merging

**Check this box**, then:

1. ✅ **Require branches to be up to date before merging**
   - Ensures branch is current with main before merging

2. **Search for and add these status checks:**

   Type in the search box to find these checks (they'll appear after workflows run):

   - `build` (from python-app.yml)
   - `lint` (from build.yml)
   - `build_docker_image / Build & Push Docker image` (from build.yml)

   **Note**: Status checks will only appear in the list after they've run at least once. If you don't see them yet:
   - Push a commit to trigger the workflows
   - Come back after workflows complete
   - Add the status checks

### ✅ Require conversation resolution before merging

**Check this box**
- All PR comments must be resolved before merging

### ✅ Require signed commits

**Check this box**
- All commits must be signed with GPG/SSH

**How to set up commit signing:**
```bash
# Generate GPG key
gpg --full-generate-key

# List keys and copy the key ID
gpg --list-secret-keys --keyid-format=long

# Configure git
git config --global user.signingkey YOUR_KEY_ID
git config --global commit.gpgsign true

# Add GPG key to GitHub
gpg --armor --export YOUR_KEY_ID
# Copy output and add to: GitHub Settings → SSH and GPG keys → New GPG key
```

### ✅ Require linear history

**Check this box**
- Prevents merge commits, enforces rebase or squash

### ⚠️ Do not allow bypassing the above settings

**Check this box**
- Even repository admins must follow these rules
- Ensures consistent process for everyone

### 🚫 Restrict who can push to matching branches

**Optional**: Add specific users/teams who can push directly

**Recommendation**: Leave empty to require PRs from everyone, including maintainers

### ❌ Allow force pushes

**LEAVE UNCHECKED** (disabled)
- Prevents rewriting history on main branch

### ❌ Allow deletions

**LEAVE UNCHECKED** (disabled)
- Prevents accidental deletion of main branch

## Step 4: Save Changes

Click **Create** (or **Save changes**) at the bottom

## Step 5: Verify Settings

After saving, you should see:
- Branch protection rule for `main` listed
- Green checkmark next to each enabled rule
- Status checks listed (if workflows have run)

## Step 6: Test the Protection

Try to push directly to main:
```bash
# This should fail
git checkout main
echo "test" >> test.txt
git add test.txt
git commit -m "test direct push"
git push origin main
# Should see: "main is protected and requires a pull request"
```

## Troubleshooting

### Status checks don't appear in the list

**Solution**:
1. Merge this commit with the new workflows to main
2. Wait for workflows to run (they trigger on push to main)
3. Return to branch protection settings
4. The status checks will now be available to select

### Can't require signed commits yet

**Solution**:
- You can enable this later after setting up GPG signing
- It's recommended but not critical for initial setup

### Need to bypass temporarily

**If you need to bypass temporarily** (use sparingly):
1. Go to branch protection settings
2. Check "Allow specified actors to bypass required pull requests"
3. Add yourself temporarily
4. Remove after completing the operation

## Additional Security Settings

After branch protection is configured, also enable these:

### Security Features

**Settings → Security → Code security and analysis**

Enable all of these:

- ✅ **Dependabot alerts** - Get notified of vulnerabilities
- ✅ **Dependabot security updates** - Automatic security PRs
- ✅ **Grouped security updates** - Bundle security updates
- ✅ **Secret scanning** - Scan for leaked secrets
- ✅ **Push protection** - Block pushes containing secrets

### Actions Settings

**Settings → Actions → General**

1. **Workflow permissions**:
   - Select: "Read repository contents and packages permissions"
   - ✅ Check: "Allow GitHub Actions to create and approve pull requests"

2. **Fork pull request workflows**:
   - ⬜ Leave unchecked: "Run workflows from fork pull requests"
   - ⬜ Leave unchecked: "Send write tokens to workflows from fork pull requests"
   - ⬜ Leave unchecked: "Send secrets to workflows from fork pull requests"

### Required Secrets

**Settings → Secrets and variables → Actions → Repository secrets**

Add these secrets:

1. **PYPI_TOKEN**
   - Get from: https://pypi.org/manage/account/token/
   - Needed for: Publishing to PyPI

2. **DOCKER_USERNAME**
   - Your Docker Hub username
   - Needed for: Docker image publishing

3. **DOCKER_PASSWORD**
   - Your Docker Hub access token (not password)
   - Get from: https://hub.docker.com/settings/security
   - Needed for: Docker image publishing

## Verification Checklist

After completing all steps:

- [ ] Branch protection rule created for `main`
- [ ] Required PR approvals: 1
- [ ] Required status checks configured (or will add after first run)
- [ ] Conversation resolution required
- [ ] Signed commits required (or planned)
- [ ] Linear history required
- [ ] No bypass allowed
- [ ] Force pushes disabled
- [ ] Deletions disabled
- [ ] Security features enabled (Dependabot, secret scanning, push protection)
- [ ] Actions permissions configured
- [ ] Required secrets added (PYPI_TOKEN, DOCKER credentials)

## Next Steps

1. **Test the setup**: Create a test PR to verify all rules work
2. **Monitor Dependabot**: Check for PRs within a week
3. **Review Scorecard**: Check results after workflow runs
4. **Create CODEOWNERS**: Add `.github/CODEOWNERS` file (optional)

## Need Help?

- Branch Protection: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches
- Signed Commits: https://docs.github.com/en/authentication/managing-commit-signature-verification
- Dependabot: https://docs.github.com/en/code-security/dependabot
- OpenSSF Scorecard: https://github.com/ossf/scorecard
