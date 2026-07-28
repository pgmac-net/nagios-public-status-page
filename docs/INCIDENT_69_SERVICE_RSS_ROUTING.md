# Incident #69: Service RSS Feed Routing with Slashes

## Overview

Fixed a routing bug where service descriptions containing forward slashes were unreachable via the RSS feed endpoint. Services like "CPU / Load" or "Disk Space, /var" would return 404 errors.

## Problem

The RSS feed endpoint `/feed/service/{host_name}/{service_description}/rss.xml` used a simple route parameter `{service_description}` that does not match path segments containing slashes. The `/` character is treated as a path separator in HTTP routing, so a description like "Disk Space, /var" was interpreted as multiple path segments instead of a single parameter value.

### Impact

- Zero of the 82 existing service descriptions in production contain slashes, making this a latent bug
- Any new service with a slash in the description would be inaccessible via RSS
- Percent-encoded slashes (e.g., `%2F`) also failed to reach the endpoint

## Solution

Changed the route parameter from `{service_description}` to `{service_description:path}` using Starlette's `:path` converter. The path converter accepts any string including slashes, matching the rest of the path as a single parameter.

### Changes

**File: `src/nagios_public_status_page/api/routes.py` (line 932)**

```python
# Before
@rss_router.get("/service/{host_name}/{service_description}/rss.xml")

# After
@rss_router.get("/service/{host_name}/{service_description:path}/rss.xml")
```

**Docstring update:**

The `service_description` parameter docstring now reads:
> Service description (may contain / or other special characters; pass raw or percent-encoded, e.g. "Disk Space, /var" or "Disk%20Space%2C%20%2Fvar")

## Testing

Added three test cases in `tests/test_service_rss_slash_routing.py`:

1. **Raw slashes** - Service "CPU / Load" accessed as `/feed/service/macro/CPU / Load/rss.xml` → 200 OK
2. **Percent-encoded slashes** - Service "Disk Space, /var" accessed with URL-encoded description → 200 OK
3. **Nonexistent services** - Verifies 404 behavior is unchanged when no matching incidents exist

### Test Results

- All 3 new tests pass
- Full suite: 122 tests pass (119 original + 3 new)
- No regression in global/host RSS feeds or other endpoints

## Impact Assessment

- **Compatibility**: No breaking changes. Existing routes (global and host RSS, plain service names) unaffected
- **URL handling**: Routes accept both raw and percent-encoded slashes; HTTP clients typically encode automatically
- **Configuration**: No configuration changes required

## Implementation Notes

1. Starlette's `:path` converter is greedy but safe in this context because the `/rss.xml` suffix is hardcoded in the route and prevents ambiguity
2. The route receives both raw (if passed raw in URL) and percent-encoded (if passed encoded) slashes; the FastAPI dependency layer handles decoding as needed
3. Database queries remain unchanged; filtering by service description works identically

## Deployment

No database migration or configuration changes required. Simply update the application container/binary.

## PR

See [PR #72](https://github.com/pgmac-net/nagios-public-status-page/pull/72)
