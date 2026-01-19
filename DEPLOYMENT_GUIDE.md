# SCITE Deployment Guide - streamlit.imb.rwth-aachen.de

## Overview
This guide provides step-by-step commands for deploying SCITE to `streamlit.imb.rwth-aachen.de` at `/opt/streamlit-app`.

---

## Phase 1: Initial Server Inspection

### Step 1: SSH into the server
```bash
ssh username@streamlit.imb.rwth-aachen.de
```

### Step 2: Inspect current setup
```bash
# Check current directory structure
ls -la /opt/streamlit-app/

# Check if Python/conda is installed
which python3
python3 --version
which conda
conda --version

# Check running processes
ps aux | grep streamlit

# Check which port is currently used
sudo netstat -tulpn | grep streamlit
# or
sudo ss -tulpn | grep streamlit

# Check if systemd service exists
sudo systemctl list-units --type=service | grep streamlit
ls -la /etc/systemd/system/ | grep streamlit
```

---

## Phase 2: Prepare the Repository

### Step 3: Clone or update the repository
```bash
# Navigate to deployment directory
cd /opt/streamlit-app

# If directory is empty, clone the repo
sudo git clone https://github.com/cscp-group/scite.git .

# If repo already exists, update it
sudo git pull origin master

# Verify the main app file exists
ls -la scite/streamlit_app/scite_app.py
```

---

## Phase 3: Python Environment Setup

### Option A: Using venv (recommended for simplicity)

```bash
# Navigate to app directory
cd /opt/streamlit-app

# Create virtual environment
sudo python3 -m venv venv

# Activate the environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install the package in editable mode
pip install -e .

# Verify installation
pip list | grep -E "streamlit|numpy|scipy|sympy|matplotlib"
```

### Option B: Using conda

```bash
# Navigate to app directory
cd /opt/streamlit-app

# Check if environment file exists
cat environment_scite.yml

# Create conda environment
sudo /opt/conda/bin/conda env create -f environment_scite.yml

# Or create manually if file doesn't exist
sudo /opt/conda/bin/conda create -n scite_env python=3.10 -y
sudo /opt/conda/bin/conda activate scite_env
sudo /opt/conda/bin/conda install -c conda-forge numpy scipy sympy matplotlib streamlit -y

# Install the package
pip install -e .
```

---

## Phase 4: Streamlit Configuration

### Step 4: Create Streamlit config directory and files
```bash
# Create config directory
sudo mkdir -p /opt/streamlit-app/.streamlit

# Create config.toml with server settings
sudo tee /opt/streamlit-app/.streamlit/config.toml > /dev/null << 'EOF'
[server]
port = 8501
address = "0.0.0.0"
headless = true
enableCORS = false
enableXsrfProtection = true

[browser]
gatherUsageStats = false
serverAddress = "streamlit.imb.rwth-aachen.de"
serverPort = 8501

[theme]
primaryColor = "#1f77b4"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F0F2F6"
textColor = "#262730"
EOF

# Verify config file
cat /opt/streamlit-app/.streamlit/config.toml
```

### Step 5: Test the app manually (optional)
```bash
# Activate environment (venv)
cd /opt/streamlit-app
source venv/bin/activate

# Or activate environment (conda)
# conda activate scite_env

# Run streamlit manually to test
streamlit run scite/streamlit_app/scite_app.py

# Press Ctrl+C to stop when verified
```

---

## Phase 5: Create Systemd Service (Production)

### Step 6: Create systemd service file
```bash
# Create service file
sudo tee /etc/systemd/system/scite-streamlit.service > /dev/null << 'EOF'
[Unit]
Description=SCITE Streamlit Application
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/streamlit-app
Environment="PATH=/opt/streamlit-app/venv/bin"
ExecStart=/opt/streamlit-app/venv/bin/streamlit run scite/streamlit_app/scite_app.py --server.port=8501 --server.address=0.0.0.0

# If using conda instead, use this ExecStart:
# ExecStart=/opt/conda/envs/scite_env/bin/streamlit run scite/streamlit_app/scite_app.py --server.port=8501 --server.address=0.0.0.0

Restart=always
RestartSec=10
StandardOutput=append:/var/log/scite-streamlit/output.log
StandardError=append:/var/log/scite-streamlit/error.log

[Install]
WantedBy=multi-user.target
EOF

# Create log directory
sudo mkdir -p /var/log/scite-streamlit
sudo chown www-data:www-data /var/log/scite-streamlit

# Set proper permissions for the app directory
sudo chown -R www-data:www-data /opt/streamlit-app

# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable scite-streamlit.service

# Start the service
sudo systemctl start scite-streamlit.service

# Check status
sudo systemctl status scite-streamlit.service
```

---

## Phase 6: Verify Deployment

### Step 7: Check if app is running
```bash
# Check service status
sudo systemctl status scite-streamlit.service

# Check if port 8501 is listening
sudo netstat -tulpn | grep 8501
# or
sudo ss -tulpn | grep 8501

# View logs
sudo tail -f /var/log/scite-streamlit/output.log
sudo tail -f /var/log/scite-streamlit/error.log

# Test locally on server
curl http://localhost:8501
```

### Step 8: Configure firewall (if needed)
```bash
# Check firewall status
sudo ufw status

# If firewall is active, allow port 8501
sudo ufw allow 8501/tcp
sudo ufw status

# For firewalld (if using RedHat/CentOS)
sudo firewall-cmd --permanent --add-port=8501/tcp
sudo firewall-cmd --reload
```

### Step 9: Test from your local machine
```bash
# From your laptop, test access
curl http://streamlit.imb.rwth-aachen.de:8501

# Or open in browser
# http://streamlit.imb.rwth-aachen.de:8501
```

---

## Service Management Commands

```bash
# Start service
sudo systemctl start scite-streamlit.service

# Stop service
sudo systemctl stop scite-streamlit.service

# Restart service
sudo systemctl restart scite-streamlit.service

# Check status
sudo systemctl status scite-streamlit.service

# View logs (real-time)
sudo journalctl -u scite-streamlit.service -f

# View recent logs
sudo journalctl -u scite-streamlit.service -n 100

# View logs in file
sudo tail -f /var/log/scite-streamlit/output.log
sudo tail -f /var/log/scite-streamlit/error.log
```

---

## Updating the Application

When you push updates to the repository:

```bash
# SSH into server
ssh username@streamlit.imb.rwth-aachen.de

# Navigate to app directory
cd /opt/streamlit-app

# Pull latest changes
sudo git pull origin master

# If dependencies changed, reinstall
source venv/bin/activate  # or conda activate scite_env
pip install -e .

# Restart service
sudo systemctl restart scite-streamlit.service

# Verify it's running
sudo systemctl status scite-streamlit.service
```

---

## Troubleshooting

### App won't start
```bash
# Check logs
sudo journalctl -u scite-streamlit.service -n 50
sudo tail -50 /var/log/scite-streamlit/error.log

# Check permissions
ls -la /opt/streamlit-app/
sudo chown -R www-data:www-data /opt/streamlit-app

# Test manually
cd /opt/streamlit-app
source venv/bin/activate
streamlit run scite/streamlit_app/scite_app.py
```

### Port already in use
```bash
# Check what's using port 8501
sudo lsof -i :8501
sudo netstat -tulpn | grep 8501

# Kill old streamlit processes
sudo pkill -f streamlit

# Restart service
sudo systemctl restart scite-streamlit.service
```

### Cannot access from outside
```bash
# Check if app is listening on 0.0.0.0
sudo ss -tulpn | grep 8501

# Check firewall
sudo ufw status
sudo ufw allow 8501/tcp

# Check if service is running
sudo systemctl status scite-streamlit.service

# Test from server
curl http://localhost:8501
```

### Module import errors
```bash
# Verify environment and dependencies
source venv/bin/activate
pip list

# Reinstall package
cd /opt/streamlit-app
pip install -e .

# Check Python path
python -c "import sys; print('\n'.join(sys.path))"
```

---

## Alternative: Simple Screen Session (Quick Test)

If you want a quick test without systemd:

```bash
# SSH into server
ssh username@streamlit.imb.rwth-aachen.de

# Start a screen session
screen -S scite

# Navigate and activate environment
cd /opt/streamlit-app
source venv/bin/activate

# Run streamlit
streamlit run scite/streamlit_app/scite_app.py --server.port=8501 --server.address=0.0.0.0

# Detach from screen: Ctrl+A, then D

# Reattach later
screen -r scite

# List sessions
screen -ls

# Kill session
screen -X -S scite quit
```

---

## Quick Reference

| Action | Command |
|--------|---------|
| SSH to server | `ssh username@streamlit.imb.rwth-aachen.de` |
| Check service | `sudo systemctl status scite-streamlit.service` |
| Restart service | `sudo systemctl restart scite-streamlit.service` |
| View logs | `sudo journalctl -u scite-streamlit.service -f` |
| Update code | `cd /opt/streamlit-app && sudo git pull origin master` |
| Test locally | `curl http://localhost:8501` |
| Access URL | `http://streamlit.imb.rwth-aachen.de:8501` |

---

## Next Steps After Deployment

1. **Set up reverse proxy (optional)** - Use nginx for HTTPS and cleaner URLs
2. **Configure SSL certificate** - Use Let's Encrypt for HTTPS
3. **Set up monitoring** - Monitor app health and logs
4. **Backup strategy** - Regular backups of configuration

---

## Contact

For issues or questions:
- Repository: https://github.com/cscp-group/scite
- Contact: rostislav.chudoba@rwth-aachen.de
