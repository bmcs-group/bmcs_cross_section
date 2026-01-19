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
