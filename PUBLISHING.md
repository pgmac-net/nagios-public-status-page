# Publishing to PyPI

This guide explains how to publish the Nagios Public Status Page to PyPI.

## Prerequisites

1. **PyPI Account**: Create an account at https://pypi.org/account/register/
2. **API Token**: Generate an API token at https://pypi.org/manage/account/token/
   - Store it securely, you'll need it for authentication

## Publishing Steps

### 1. Update Version

Edit `pyproject.toml` and increment the version number:

```toml
version = "0.1.0"  # Update this for each release
```

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

## Using GitHub Actions (Automated Publishing)

You can automate publishing with GitHub Actions. Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Install uv
        run: pip install uv

      - name: Build package
        run: uv build

      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: |
          pip install twine
          twine upload dist/*
```

Then add your PyPI API token as a GitHub secret named `PYPI_API_TOKEN`.

## Release Checklist

Before each release:

- [ ] Update version in `pyproject.toml`
- [ ] Update `CHANGELOG.md` (if you have one)
- [ ] Run tests: `uv run pytest`
- [ ] Run linters: `uv run ruff check src` and `uv run pylint src`
- [ ] Run type check: `uv run ty check src`
- [ ] Update `README.md` if needed
- [ ] Build and test locally
- [ ] Test on TestPyPI
- [ ] Create git tag: `git tag v0.1.0 && git push origin v0.1.0`
- [ ] Publish to PyPI
- [ ] Create GitHub release with release notes

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
