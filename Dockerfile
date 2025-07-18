FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
      libgl1-mesa-glx \
      libglib2.0-0 \
      libsm6 \
      libxext6 \
      libxrender-dev \
      libgomp1 \
      libgeos-dev && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install python dependencies
COPY requirements.txt .
COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements.txt -r requirements-web.txt

# Copy application code
COPY . .

# Create non-root user and switch to it
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/stats')" || exit 1

# Start the web server
CMD ["uvicorn", "web_server:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

# Example requirements.txt snippet:
# flask
# requests
# numpy
# pillow
# geos
# (Add other dependencies from environment.yml converted to pip requirements)