# Security Policy

## Supported Versions

We release patches for security vulnerabilities for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it by:

1. **DO NOT** open a public GitHub issue
2. Email security details to: pgmac@pgmac.net
3. Include the following information:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

You should receive a response within 48 hours. If the vulnerability is confirmed, we will:

1. Release a security patch as soon as possible
2. Credit you in the security advisory (unless you prefer to remain anonymous)
3. Publish a security advisory on GitHub

## Security Best Practices

### For Deployment

1. **Run as non-root user**: The Docker image runs as user `statuspage` (UID 1000)
2. **Read-only status.dat**: Mount Nagios status.dat as read-only
3. **Restrict API access**: Use firewall rules or reverse proxy to limit access
4. **Enable HTTPS**: Always use HTTPS in production with a reverse proxy
5. **Secure secrets**: Store API tokens and credentials securely
6. **Regular updates**: Keep the application and dependencies up to date

### For API Authentication

The API includes Basic Authentication for write operations:

```yaml
# In config.yaml
api:
  auth:
    enabled: true
    username: "admin"
    password: "secure-password-here"  # Use strong passwords!
```

**Recommendations:**
- Use environment variables for credentials: `API_AUTH_PASSWORD`
- Generate strong passwords (32+ characters)
- Rotate credentials regularly
- Consider using a reverse proxy with OAuth2 for additional security

### For Development

1. **Never commit secrets**: Use `.env` files (already in `.gitignore`)
2. **Run security scans**: Use `uv run safety check` before committing
3. **Review dependencies**: Keep dependencies updated
4. **Follow secure coding**: Run linters and type checkers

## Security Scanning

This project uses multiple security tools:

### OpenSSF Scorecard
- Automated weekly scans
- Results published to GitHub Security tab
- Badge: [![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/pgmac/nagios-public-status-page/badge)](https://scorecard.dev/viewer/?uri=github.com/pgmac/nagios-public-status-page)

### Dependabot
- Automated dependency updates
- Security vulnerability alerts
- Automatic pull requests for updates

### GitHub Code Scanning
- SARIF results from Scorecard
- Automated security analysis

## Known Security Considerations

### 1. Status.dat File Access
The application requires read access to Nagios `status.dat`. This file may contain sensitive information about your infrastructure:

- **Mitigation**: Use hostgroup/servicegroup filtering to limit exposed data
- **Recommendation**: Only include hosts/services you want publicly visible

### 2. Database Storage
Incident data is stored in SQLite:

- **Mitigation**: Database file is not exposed via web server
- **Recommendation**: Ensure proper file permissions (600 or 640)

### 3. RSS Feeds
RSS feeds expose incident information publicly:

- **Mitigation**: Feeds respect the same filtering as the main dashboard
- **Recommendation**: Review what data is included before enabling public access

## Compliance

This project follows these security standards:

- **CIS Docker Benchmark**: Dockerfile follows security best practices
- **OWASP Top 10**: Protection against common vulnerabilities
- **Principle of Least Privilege**: Runs as non-root user
- **Defense in Depth**: Multiple security layers

## Security Updates

Security updates are released as:

- **Patch versions** (0.1.x) for security fixes
- Published to PyPI and Docker registries immediately
- Announced via GitHub Security Advisories
- Tagged with `security` label

Subscribe to GitHub releases to be notified of security updates.
