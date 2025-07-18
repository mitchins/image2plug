# image2plug Web Deployment Guide

This guide covers deploying the image2plug web application with Cloudflare integration for a portfolio-ready demo.

## Architecture Overview

```
[User] -> [Cloudflare] -> [Home Docker Container]
              |               |
         Frontend CDN      [FastAPI + Daemon]
              |               |
         Static Assets    [SQLite + Results]
```

## Prerequisites

- **For Docker deployment:** Docker and Docker Compose installed
- **For local development:** Conda (Miniconda or Anaconda)
- Domain name (optional, can use IP)
- Cloudflare account (free tier sufficient)

## Local Development

### Quick Start

```bash
# Clone and enter directory
git clone <repo>
cd image2plug

# Start with Docker Compose
docker-compose up --build

# Access the application
open http://localhost:8000
```

### Conda Setup (Recommended for local development)

```bash
# Setup conda environment
./setup-conda.sh

# Activate environment
conda activate image2plug

# Start the server
python web_server.py
```

### Manual Setup (Alternative)

```bash
# Create conda environment manually
conda env create -f environment.yml
conda activate image2plug

# Create directories
mkdir -p db uploads web_results static

# Start the server
python web_server.py
```

## Production Deployment

### 1. Docker Container Setup

**Build and run the container:**

```bash
# Build the image
docker build -t image2plug-web .

# Run the container
docker run -d \
  --name image2plug \
  --restart unless-stopped \
  -p 8000:8000 \
  -v $(pwd)/db:/app/db \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/web_results:/app/web_results \
  image2plug-web
```

**Or use Docker Compose:**

```bash
docker-compose up -d
```

### 2. Cloudflare Setup

#### Option A: Full Proxy (Recommended)

**Steps:**
1. Add your domain to Cloudflare
2. Point your domain to your home IP address
3. Enable "Proxy" (orange cloud) in DNS settings
4. Configure SSL/TLS settings

**DNS Configuration:**
```
Type: A
Name: image2plug (or @)
Content: YOUR_HOME_IP
Proxy: Enabled (orange cloud)
```

**Cloudflare Settings:**
- SSL/TLS Mode: "Full (strict)" if you have SSL, "Flexible" if not
- Always Use HTTPS: On
- Automatic HTTPS Rewrites: On
- Security Level: Medium or High

#### Option B: Split Hosting

**Frontend on Cloudflare Pages:**
1. Fork/copy the `static/` directory to a new repository
2. Deploy to Cloudflare Pages
3. Update API URLs to point to your home server

**API on Home Server:**
- Configure CORS to allow your Cloudflare Pages domain
- Use a subdomain like `api.yourdomain.com`

### 3. Security Configuration

**Update `web_server.py` for production:**

```python
# Update allowed hosts
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["yourdomain.com", "www.yourdomain.com"]
)

# Update CORS origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

**Firewall Configuration:**
```bash
# Only allow HTTP/HTTPS traffic
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

### 4. SSL Certificate (if not using Cloudflare proxy)

**Using Let's Encrypt with Nginx:**

```nginx
# /etc/nginx/sites-available/image2plug
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name yourdomain.com;
    
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Environment Variables

Create a `.env` file for production configuration:

```bash
# Production settings
PYTHONUNBUFFERED=1
FASTAPI_ENV=production
MAX_FILE_SIZE=52428800  # 50MB
RATE_LIMIT_JOBS_PER_MINUTE=5
RATE_LIMIT_API_PER_MINUTE=60
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

## Monitoring and Maintenance

### Health Checks

```bash
# Check application health
curl http://localhost:8000/api/stats

# Check Docker container status
docker ps
docker logs image2plug
```

### Log Management

```bash
# View logs
docker logs -f image2plug

# Rotate logs (add to crontab)
docker exec image2plug find /app -name "*.log" -size +100M -delete
```

### Database Maintenance

```bash
# Backup database
docker exec image2plug cp /app/db/jobs.db /app/db/jobs_backup_$(date +%Y%m%d).db

# Purge old jobs (via API)
curl -X POST http://localhost:8000/api/admin/purge?days=30
```

### Resource Monitoring

**Basic monitoring script:**

```bash
#!/bin/bash
# monitor.sh

# Check disk space
df -h /home/user/image2plug/

# Check memory usage
docker stats image2plug --no-stream

# Check job queue status
curl -s http://localhost:8000/api/stats | jq .
```

## Cloudflare Optimization

### Page Rules

Create page rules for better performance:

1. **Static assets caching:**
   - URL: `yourdomain.com/static/*`
   - Settings: Cache Level = Cache Everything, Edge Cache TTL = 1 month

2. **API rate limiting:**
   - URL: `yourdomain.com/api/*`
   - Settings: Security Level = High

### Security Features

Enable these Cloudflare security features:

- **DDoS Protection:** Automatic
- **Web Application Firewall (WAF):** Enable managed rules
- **Bot Fight Mode:** Enable
- **Rate Limiting:** Configure additional limits if needed

## Troubleshooting

### Common Issues

**Container won't start:**
```bash
# Check logs
docker logs image2plug

# Check file permissions
ls -la db/ uploads/ web_results/

# Fix permissions
chmod 755 db uploads web_results
```

**Job processing fails:**
```bash
# Check worker thread status
docker exec image2plug ps aux

# Check available disk space
docker exec image2plug df -h
```

**High memory usage:**
```bash
# Restart container
docker restart image2plug

# Purge old jobs
curl -X POST http://localhost:8000/api/admin/purge?days=7
```

### Performance Tuning

**For high traffic:**

```yaml
# docker-compose.yml
services:
  image2plug:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'
```

**Database optimization:**
```sql
-- Run periodically to optimize SQLite
VACUUM;
REINDEX;
```

## Portfolio Presentation

### Demo Setup

1. **Prepare sample images** in the web interface
2. **Show the job queue** with various statuses
3. **Demonstrate real-time updates** 
4. **Display generated results** (DXF, STL, proof reports)

### Key Features to Highlight

- **Material UI design** - Professional, responsive interface
- **Real-time job monitoring** - WebSocket-like updates via polling
- **File security** - UUID-based result URLs, rate limiting
- **Scalable architecture** - Containerized, cloud-ready
- **Full-stack implementation** - Python, FastAPI, SQLite, Docker, Cloudflare

### Technical Talking Points

- **Job queue system** - Demonstrates async processing patterns
- **Rate limiting** - Shows understanding of API security
- **Docker deployment** - Modern containerization practices  
- **Cloudflare integration** - CDN and security best practices
- **Clean architecture** - Separation of concerns, modular design

This deployment showcases production-ready full-stack development skills suitable for a portfolio project.