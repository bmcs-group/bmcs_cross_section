# SCITE Docker Deployment Guide

## Overview

This guide describes the procedure for deploying the SCITE Streamlit application on an internal institute server using Docker containerization.

## Prerequisites

- Docker installed on the target server (virtual machine)
- Git access to the repository
- Open port on the virtual machine (default: 8501 for Streamlit)
- Network configuration allowing access from university framework

## Local Development Environment

To ensure your development environment matches the Docker deployment, create a dedicated conda environment:

```bash
# Create the scite_env environment using mamba (much faster than conda)
cd /home/rch/Coding/scite
mamba env create -f environment_scite.yml

# Or if you don't have mamba installed, use conda (slower):
# conda env create -f environment_scite.yml

# Activate the environment
conda activate scite_env

# Install the package in editable mode
pip install -e .
```

**Note:** If you don't have mamba installed, install it with: `conda install -n base -c conda-forge mamba`

This environment includes only the core dependencies (numpy, scipy, sympy, matplotlib, streamlit) without legacy packages like `bmcs_utils` or `traits`, matching the Docker deployment configuration.

## Deployment Architecture

```
University Network
    ↓
VM Server (with open port)
    ↓
Docker Container (SCITE App)
    ↓
Streamlit (port 8501)
```

## Step 1: Create Dockerfile

Create a `Dockerfile` in the root of the SCITE project:

**Note on Dependencies:** The Dockerfile installs only the core dependencies needed for the Streamlit frontend (numpy, scipy, sympy, matplotlib, streamlit). Legacy traits-based modules (in `legacy/`, `pullout/`, `analytical_solutions/`) are NOT included in the Docker deployment as they're not used by the modern Streamlit interface.

```dockerfile
# Use Python 3.10 or higher as base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app

# Install Python dependencies (includes numpy, scipy, sympy, matplotlib, streamlit)
# Note: This installs only core dependencies from pyproject.toml
# Legacy modules (traits-based) are NOT included in Docker deployment
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Expose Streamlit default port
EXPOSE 8501

# Set environment variables for Streamlit
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Command to run the application
CMD ["streamlit", "run", "scite/streamlit_app/scite_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

## Step 2: Test Docker Build Locally (Optional but Recommended)

Before deploying to the server, test the Docker build on your local laptop:

### 2.1 Create the Dockerfile

In the root of your project (`/home/rch/Coding/scite/`), create the `Dockerfile` with the content shown in Step 1.

### 2.2 Create the .dockerignore

Create `.dockerignore` in the project root (see Step 3 below for content).

### 2.3 Build the Docker Image Locally

```bash
# Navigate to project root
cd /home/rch/Coding/scite

# Build the Docker image
docker build -t scite-app:test .
```

This will take a few minutes as it downloads the Python base image and installs all dependencies.

### 2.4 Run the Container Locally

```bash
# Run the container
docker run -d \
  --name scite-test \
  -p 8501:8501 \
  scite-app:test

# Check if container is running
docker ps
```

### 2.5 Access the Application

Open your browser and navigate to:
```
http://localhost:8501
```

You should see the SCITE application running in your browser.

### 2.6 View Logs (if needed)

```bash
# View logs in real-time
docker logs -f scite-test

# Or view last 50 lines
docker logs --tail 50 scite-test
```

### 2.7 Stop and Clean Up After Testing

```bash
# Stop the container
docker stop scite-test

# Remove the container
docker rm scite-test

# Optional: Remove the image to free space
docker rmi scite-app:test
```

### 2.8 Troubleshooting Local Build

**If build fails:**
- Check that you're in the project root directory
- Ensure `pyproject.toml` and `setup.py` are present
- Check Docker logs for specific errors: `docker logs scite-test`

**If you can't access localhost:8501:**
- Check if port 8501 is already in use: `sudo lsof -i :8501`
- Kill existing Streamlit processes: `pkill streamlit`
- Verify container is running: `docker ps`

**If dependencies fail to install:**
- Check your internet connection
- Try building without cache: `docker build --no-cache -t scite-app:test .`

Once local testing is successful, you can proceed with confidence to deploy on the server.

## Step 3: Create .dockerignore

Create a `.dockerignore` file to exclude unnecessary files:

```
.git
.gitignore
__pycache__
*.pyc
*.pyo
*.pyd
.Python
env
venv
*.egg-info
.DS_Store
.vscode
.idea
notebooks/temp
*.ipynb_checkpoints
build
dist
```

## Step 3: Build Docker Image

On the server, navigate to the project directory and build the image:

```bash
# Clone or update the repository
cd /path/to/scite
git pull origin main

# Build the Docker image
docker build -t scite-app:latest .

# Verify the image was created
docker images | grep scite-app
```

## Step 4: Run Docker Container

### Basic Run Command

```bash
docker run -d \
  --name scite-container \
  -p 8501:8501 \
  --restart unless-stopped \
  scite-app:latest
```

### Run with Volume Mounts (for data persistence)

```bash
docker run -d \
  --name scite-container \
  -p 8501:8501 \
  -v /host/path/data:/app/data \
  --restart unless-stopped \
  scite-app:latest
```

### Options Explained

- `-d`: Run in detached mode (background)
- `--name`: Container name for easy reference
- `-p 8501:8501`: Map host port 8501 to container port 8501
- `-v`: Mount volumes for persistent data (optional)
- `--restart unless-stopped`: Auto-restart container on server reboot

## Step 5: Server Network Configuration

### Firewall Configuration

On the VM server, ensure port 8501 is open:

```bash
# For Ubuntu/Debian with ufw
sudo ufw allow 8501/tcp
sudo ufw status

# For RedHat/CentOS with firewalld
sudo firewall-cmd --permanent --add-port=8501/tcp
sudo firewall-cmd --reload
```

### University Network Access

Contact IT department to:
1. Open port 8501 on the VM's external interface
2. Configure NAT/port forwarding if needed
3. Set up DNS entry (e.g., scite.institute.university.edu)
4. Optional: Configure reverse proxy (nginx/apache) for HTTPS

## Step 6: Access the Application

Once deployed, access the application at:

```
http://<vm-server-ip>:8501
# or
http://scite.institute.university.edu:8501
```

## Container Management

### View Running Containers

```bash
docker ps
```

### View Logs

```bash
# Follow logs in real-time
docker logs -f scite-container

# View last 100 lines
docker logs --tail 100 scite-container
```

### Stop Container

```bash
docker stop scite-container
```

### Restart Container

```bash
docker restart scite-container
```

### Remove Container

```bash
docker stop scite-container
docker rm scite-container
```

### Remove Image

```bash
docker rmi scite-app:latest
```

## Updating the Application

When code changes are made:

```bash
# 1. Stop and remove old container
docker stop scite-container
docker rm scite-container

# 2. Update code
cd /path/to/scite
git pull origin main

# 3. Rebuild image
docker build -t scite-app:latest .

# 4. Run new container
docker run -d \
  --name scite-container \
  -p 8501:8501 \
  --restart unless-stopped \
  scite-app:latest
```

## Alternative: Docker Compose

For easier management, create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  scite-app:
    build: .
    container_name: scite-container
    ports:
      - "8501:8501"
    restart: unless-stopped
    environment:
      - STREAMLIT_SERVER_PORT=8501
      - STREAMLIT_SERVER_ADDRESS=0.0.0.0
      - STREAMLIT_SERVER_HEADLESS=true
    volumes:
      - ./data:/app/data
```

Then use:

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# Rebuild and restart
docker-compose up -d --build
```

## Production Recommendations

### 1. Use Reverse Proxy (nginx)

Create `/etc/nginx/sites-available/scite`:

```nginx
server {
    listen 80;
    server_name scite.institute.university.edu;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2. Enable HTTPS with Let's Encrypt

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d scite.institute.university.edu
```

### 3. Resource Limits

Add resource constraints to docker run:

```bash
docker run -d \
  --name scite-container \
  -p 8501:8501 \
  --memory="2g" \
  --cpus="2.0" \
  --restart unless-stopped \
  scite-app:latest
```

### 4. Health Checks

Add to Dockerfile:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8501/_stcore/health || exit 1
```

## Monitoring

### Check Container Stats

```bash
docker stats scite-container
```

### Set up Logging

```bash
# Configure log rotation in /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker logs scite-container

# Check if port is already in use
sudo lsof -i :8501
```

### Cannot access from network

```bash
# Verify container is running
docker ps

# Check port binding
docker port scite-container

# Test locally
curl http://localhost:8501
```

### Permission issues

```bash
# Run with specific user
docker run -d \
  --name scite-container \
  -p 8501:8501 \
  --user $(id -u):$(id -g) \
  scite-app:latest
```

## Security Considerations

1. **Use environment variables for secrets** - Never hardcode credentials
2. **Regular updates** - Keep base image and dependencies updated
3. **Non-root user** - Consider running as non-root inside container
4. **Network isolation** - Use Docker networks to isolate containers
5. **HTTPS only** - Use reverse proxy with SSL for production

## Backup and Recovery

```bash
# Backup container data
docker cp scite-container:/app/data /backup/location

# Create image from running container
docker commit scite-container scite-app:backup-$(date +%Y%m%d)

# Save image to tar file
docker save scite-app:latest > scite-app-backup.tar

# Load image from tar file
docker load < scite-app-backup.tar
```

## Contact and Support

For server configuration and network access:
- Contact: IT Department / Network Administrator
- Issues: University firewall, port forwarding, DNS configuration

For application issues:
- Repository: https://github.com/cscp-group/scite
- Contact: rostislav.chudoba@rwt-aachen.de
