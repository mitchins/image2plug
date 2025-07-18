FROM continuumio/miniconda3:latest

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgeos-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy environment file and create conda environment
COPY environment.yml .
RUN conda env create -f environment.yml && \
    conda clean -afy

# Activate environment in shell
SHELL ["conda", "run", "-n", "image2plug", "/bin/bash", "-c"]

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p db uploads web_results static

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD conda run -n image2plug python -c "import requests; requests.get('http://localhost:8000/api/stats')" || exit 1

# Start the web server
CMD ["conda", "run", "-n", "image2plug", "python", "web_server.py"]