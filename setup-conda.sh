#!/bin/bash

# image2plug Conda Environment Setup Script

set -e

echo "🐍 Setting up image2plug with Conda"

# Check if conda is installed
if ! command -v conda &> /dev/null; then
    echo "❌ Conda is not installed. Please install Miniconda or Anaconda first."
    echo "   Download from: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

# Check if environment.yml exists
if [ ! -f "environment.yml" ]; then
    echo "❌ environment.yml not found. Are you in the image2plug directory?"
    exit 1
fi

# Remove existing environment if it exists
echo "🧹 Removing existing environment (if any)..."
conda env remove -n image2plug -y 2>/dev/null || true

# Create conda environment
echo "📦 Creating conda environment..."
conda env create -f environment.yml

# Activate environment and verify installation
echo "✅ Verifying installation..."
eval "$(conda shell.bash hook)"
conda activate image2plug

# Test imports
python -c "
try:
    from job import JobStore, JobDaemon, JobStatus
    from workflow import run_workflow
    import fastapi
    import uvicorn
    print('✅ All packages installed successfully!')
except ImportError as e:
    print(f'❌ Import error: {e}')
    exit(1)
"

# Create required directories
echo "📁 Creating required directories..."
mkdir -p db uploads web_results static

echo ""
echo "🎉 Setup complete!"
echo ""
echo "To activate the environment:"
echo "  conda activate image2plug"
echo ""
echo "To start the web server:"
echo "  python web_server.py"
echo ""
echo "To start with Docker:"
echo "  ./start.sh"
echo ""
echo "To run tests:"
echo "  pytest tests/"
echo ""