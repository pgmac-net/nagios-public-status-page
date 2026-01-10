# Deployment Guide

This guide covers multiple deployment options for the Nagios Public Status Page.

## Table of Contents

1. [Docker Deployment](#docker-deployment)
2. [Docker Compose Deployment](#docker-compose-deployment)
3. [Systemd Service Deployment](#systemd-service-deployment)
4. [Manual Deployment](#manual-deployment)
5. [Configuration](#configuration)
6. [Troubleshooting](#troubleshooting)

---

## Docker Deployment

### Prerequisites

- Docker installed
- Access to Nagios `status.dat` file

### Quick Start

1. **Build the Docker image:**

```bash
docker build -t nagios-status-page .
```

2. **Run the container:**

```bash
docker run -d \
  --name nagios-status-page \
  -p 8000:8000 \
  -v /usr/local/nagios/var/status.dat:/nagios/status.dat:ro \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -e NAGIOS_STATUS_DAT_PATH=/nagios/status.dat \
  -e NAGIOS_HOSTGROUPS=public-status \
  -e NAGIOS_SERVICEGROUPS=public-status-services \
  nagios-status-page
```

3. **Access the dashboard:**

Open your browser to `http://localhost:8000`

### Docker Environment Variables

Override configuration settings using environment variables:

```bash
# Nagios configuration
NAGIOS_STATUS_DAT_PATH=/nagios/status.dat
NAGIOS_HOSTGROUPS=public-status,web-servers
NAGIOS_SERVICEGROUPS=public-status-services

# Polling configuration
POLLING_INTERVAL_SECONDS=300
POLLING_STALENESS_THRESHOLD_SECONDS=600

# Database
DATABASE_PATH=/app/data/status.db

# API configuration
API_HOST=0.0.0.0
API_PORT=8000
API_CORS_ORIGINS=["*"]

# RSS configuration
RSS_TITLE=System Status
RSS_LINK=https://status.example.com
RSS_DESCRIPTION=Live system status updates
RSS_MAX_ITEMS=50
```

---

## Docker Compose Deployment

### Prerequisites

- Docker and Docker Compose installed
- Access to Nagios `status.dat` file

### Quick Start

1. **Edit `docker-compose.yml`:**

Update the volume mount for your Nagios status.dat location:

```yaml
volumes:
  - /usr/local/nagios/var/status.dat:/nagios/status.dat:ro
```

Update environment variables as needed.

2. **Start the service:**

```bash
docker-compose up -d
```

3. **View logs:**

```bash
docker-compose logs -f
```

4. **Stop the service:**

```bash
docker-compose down
```

### Production Configuration

For production deployments, consider:

1. **Use a reverse proxy (nginx/Traefik):**

```yaml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - status-page

  status-page:
    # ... existing configuration
    expose:
      - "8000"
    # Remove ports section - only expose internally
```

2. **Enable TLS/SSL:**

Mount SSL certificates and configure nginx to handle HTTPS.

3. **Set resource limits:**

```yaml
services:
  status-page:
    # ... existing configuration
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
```

---

## Systemd Service Deployment

### Prerequisites

- Linux system with systemd
- Python 3.11+ and uv installed
- Access to Nagios `status.dat` file

### Installation Steps

1. **Clone the repository:**

```bash
cd /opt
git clone https://github.com/your-org/public-status-page.git
cd public-status-page
```

2. **Install dependencies:**

```bash
uv sync
```

3. **Configure the application:**

```bash
cp config.yaml.example config.yaml
# Edit config.yaml with your settings
```

4. **Create systemd service file:**

```bash
sudo cp deploy/nagios-status-page.service /etc/systemd/system/
sudo systemctl daemon-reload
```

5. **Edit the service file if needed:**

```bash
sudo nano /etc/systemd/system/nagios-status-page.service
```

Update paths and settings as required.

6. **Enable and start the service:**

```bash
sudo systemctl enable nagios-status-page
sudo systemctl start nagios-status-page
```

7. **Check status:**

```bash
sudo systemctl status nagios-status-page
sudo journalctl -u nagios-status-page -f
```

### Service Management

```bash
# Start service
sudo systemctl start nagios-status-page

# Stop service
sudo systemctl stop nagios-status-page

# Restart service
sudo systemctl restart nagios-status-page

# View logs
sudo journalctl -u nagios-status-page -f

# View recent logs
sudo journalctl -u nagios-status-page -n 100
```

---

## Manual Deployment

### Prerequisites

- Python 3.11+
- uv or pip
- Access to Nagios `status.dat` file

### Installation Steps

1. **Clone and install:**

```bash
git clone https://github.com/your-org/public-status-page.git
cd public-status-page
uv sync
```

2. **Configure:**

```bash
cp config.yaml.example config.yaml
# Edit config.yaml
```

3. **Run manually:**

```bash
# Activate virtual environment (if using uv)
source .venv/bin/activate

# Run with uvicorn
uvicorn status_page.main:app --host 0.0.0.0 --port 8000

# Or run with python
python -m uvicorn status_page.main:app --host 0.0.0.0 --port 8000
```

4. **Run in background with nohup:**

```bash
nohup uvicorn status_page.main:app --host 0.0.0.0 --port 8000 > status_page.log 2>&1 &
```

---

## Configuration

### Nagios Hostgroups and Servicegroups

In your Nagios configuration, add hosts and services to the appropriate groups:

```nagios
# Host definition
define host {
    host_name           webserver01
    address             192.168.1.10
    hostgroups          linux-servers,public-status
    ...
}

# Service definition
define service {
    service_description HTTP
    host_name           webserver01
    servicegroups       web-services,public-status-services
    ...
}
```

### Application Configuration

Edit `config.yaml`:

```yaml
nagios:
  status_dat_path: "/usr/local/nagios/var/status.dat"
  hostgroups:
    - "public-status"
  servicegroups:
    - "public-status-services"

polling:
  interval_seconds: 300
  staleness_threshold_seconds: 600

database:
  path: "./data/status.db"

api:
  host: "0.0.0.0"
  port: 8000
  cors_origins:
    - "*"

rss:
  title: "System Status"
  link: "https://status.example.com"
  description: "Live system status updates"
  max_items: 50
```

### Environment Variables

Environment variables override `config.yaml` settings. Use format:

```bash
# Top-level: SECTION_KEY
export API_HOST="127.0.0.1"
export API_PORT=8080

# Lists: SECTION_KEY with comma-separated values
export NAGIOS_HOSTGROUPS="group1,group2"
export API_CORS_ORIGINS='["https://example.com"]'
```

---

## Troubleshooting

### Container won't start

**Check logs:**
```bash
docker logs nagios-status-page
```

**Common issues:**
- status.dat path incorrect: Verify volume mount
- Permission denied: Ensure status.dat is readable
- Port already in use: Change port mapping

### Data not updating

**Check polling:**
```bash
# Check health endpoint
curl http://localhost:8000/api/health

# Check logs for errors
docker logs -f nagios-status-page
```

**Common issues:**
- status.dat not accessible
- Hostgroup/servicegroup filters too restrictive
- Polling interval too long

### No incidents showing

**Verify filtering:**
```bash
# Check hosts endpoint
curl http://localhost:8000/api/hosts

# Check if incidents exist
curl http://localhost:8000/api/incidents?hours=168
```

**Common causes:**
- No hosts/services match the hostgroup/servicegroup filters
- All systems currently UP/OK
- Incident cleanup removed old incidents

### Database errors

**Reset database:**
```bash
# Stop service
docker-compose down

# Remove database
rm -f data/status.db

# Restart service (will recreate database)
docker-compose up -d
```

### Performance issues

**Check resource usage:**
```bash
docker stats nagios-status-page
```

**Optimize:**
- Reduce polling frequency
- Limit hostgroups/servicegroups
- Increase staleness threshold
- Use smaller RSS max_items

### Frontend not loading

**Check static files:**
```bash
# Verify static directory exists in container
docker exec nagios-status-page ls -la /app/static

# Check API is responding
curl http://localhost:8000/api/status
```

**Browser console:**
Open browser developer tools and check for:
- CORS errors
- 404 errors for static files
- JavaScript errors

---

## Production Best Practices

### Security

1. **Run behind reverse proxy:** Use nginx/Apache for SSL termination
2. **Restrict CORS origins:** Don't use `["*"]` in production
3. **File permissions:** Ensure status.dat is read-only
4. **Network isolation:** Use Docker networks or firewalls
5. **Regular updates:** Keep dependencies up to date

### Monitoring

1. **Health checks:** Monitor `/api/health` endpoint
2. **Log aggregation:** Send logs to centralized logging
3. **Alerting:** Alert on health check failures
4. **Metrics:** Track API response times and database size

### Backups

1. **Database backups:** Regularly backup `data/status.db`
2. **Configuration backups:** Version control config files
3. **Recovery testing:** Test restore procedures

### Scaling

1. **Read replicas:** For high traffic, consider database read replicas
2. **Caching:** Add Redis/Memcached for API responses
3. **CDN:** Serve static files from CDN
4. **Load balancing:** Multiple instances behind load balancer

---

## Support

For issues, feature requests, or questions:
- GitHub Issues: https://github.com/your-org/public-status-page/issues
- Documentation: See README.md

## License

[Your License Here]
