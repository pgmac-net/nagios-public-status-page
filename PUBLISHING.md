# Publishing to PyPI

This guide explains how to publish the Nagios Public Status Page to PyPI.

## Automated Release Process (Recommended)

The project uses GitHub Actions to automatically publish releases. Simply create and push a semver tag:

```bash
# Create a semver tag
git tag v0.1.0
git push origin v0.1.0
```

GitHub Actions will automatically:
1. Run all tests, linting, and type checks
2. Update the version in `pyproject.toml` to match the tag
3. Build the Python package
4. Publish to PyPI
5. Build and push Docker images
6. Create a GitHub Release with distribution files

**Note:** You don't need to manually update the version in `pyproject.toml` - it's automatically extracted from the git tag.

## Prerequisites for Automated Publishing

1. **PyPI Account**: Create an account at https://pypi.org/account/register/
2. **API Token**: Generate an API token at https://pypi.org/manage/account/token/
3. **GitHub Secret**: Add your PyPI token as a GitHub secret named `PYPI_TOKEN`
4. **Docker Hub Credentials**: Add `DOCKER_USERNAME` and `DOCKER_PASSWORD` as GitHub secrets

## Manual Publishing Steps

If you need to publish manually for testing:

### 2. Clean Previous Builds

```bash
rm -rf dist/ build/ *.egg-info
```

### 3. Build the Package

Using uv (recommended):

```bash
uv build
```

This will create files in the `dist/` directory:
- `nagios_public_status_page-0.1.0.tar.gz` (source distribution)
- `nagios_public_status_page-0.1.0-py3-none-any.whl` (wheel)

### 4. Test the Build Locally (Optional)

Install the built package locally to test:

```bash
uv pip install dist/nagios_public_status_page-0.1.0-py3-none-any.whl
```

### 5. Publish to TestPyPI (Recommended First Time)

Test your package on TestPyPI first:

```bash
# Install twine if needed
uv pip install twine

# Upload to TestPyPI
uv run twine upload --repository testpypi dist/*
```

When prompted:
- Username: `__token__`
- Password: Your TestPyPI API token (starts with `pypi-`)

Then test installation from TestPyPI:

```bash
pip install --index-url https://test.pypi.org/simple/ nagios-public-status-page
```

### 6. Publish to PyPI

Once you've tested on TestPyPI and everything works:

```bash
uv run twine upload dist/*
```

When prompted:
- Username: `__token__`
- Password: Your PyPI API token (starts with `pypi-`)

### 7. Verify Publication

Check your package page: https://pypi.org/project/nagios-public-status-page/

Users can now install with:

```bash
pip install nagios-public-status-page
```

## GitHub Actions Workflows

The project includes two GitHub Actions workflows:

### 1. `python-app.yml` - Python Testing and PyPI Publishing

Triggers on:
- Pushes to `main` branch (runs tests only)
- Pull requests to `main` (runs tests and comments on PR)
- Tags starting with `v` (runs tests, publishes to PyPI, creates GitHub release)

On semver tags (e.g., `v1.0.0`), this workflow:
- Extracts version from the tag
- Updates `pyproject.toml` with the tag version
- Builds the Python package
- Publishes to PyPI
- Creates a GitHub Release with `.tar.gz` and `.whl` files

### 2. `build.yml` - Docker Build and Push

Triggers on:
- Tags starting with `v` (builds and pushes to registries)
- Pushes to `main` and pull requests (linting only, no push)

On semver tags, this workflow builds and pushes to:
- Docker Hub: `pgmac/nagios-public-status-page`
- GitHub Container Registry: `ghcr.io/pgmac/nagios-public-status-page`

With multiple tags: `latest`, `v1.0.0`, `v1.0`, `v1`, `sha-<hash>`

## Release Checklist

Before each release:

- [ ] Update `CHANGELOG.md` (if you have one)
- [ ] Run tests locally: `uv run pytest`
- [ ] Run linters locally: `uv run ruff check src`
- [ ] Run type check locally: `uvx ty check src`
- [ ] Update `README.md` if needed
- [ ] Commit all changes to `main`
- [ ] Create and push semver tag: `git tag v0.1.0 && git push origin v0.1.0`
- [ ] Monitor GitHub Actions workflows for completion
- [ ] Verify publication on PyPI: https://pypi.org/project/nagios-public-status-page/
- [ ] Verify Docker images on Docker Hub and GHCR
- [ ] Test installation: `pip install nagios-public-status-page==0.1.0`
- [ ] Test Docker image: `docker pull pgmac/nagios-public-status-page:v0.1.0`

**Note:** The version in `pyproject.toml` is automatically updated during the release workflow - do not update it manually.

## Versioning

This project uses [Semantic Versioning](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality additions
- **PATCH** version for backwards-compatible bug fixes

Examples:
- `0.1.0` - Initial beta release
- `0.1.1` - Bug fix
- `0.2.0` - New feature
- `1.0.0` - First stable release

## Troubleshooting

### Authentication Issues

If you get authentication errors, make sure:
- You're using `__token__` as the username
- Your API token includes the `pypi-` prefix
- Your token has the correct permissions

### Package Name Already Taken

If `nagios-public-status-page` is taken, you can:
1. Choose a different name in `pyproject.toml`
2. Add your organization prefix: `pgmac-status-page`

### Build Errors

If the build fails:
- Check all required files are included in `MANIFEST.in`
- Verify `pyproject.toml` syntax is correct
- Ensure all dependencies are properly listed

## Resources

- PyPI: https://pypi.org/
- TestPyPI: https://test.pypi.org/
- Python Packaging Guide: https://packaging.python.org/
- Twine Documentation: https://twine.readthedocs.io/
