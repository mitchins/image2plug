#!/bin/bash

# image2plug Web Server Startup Script

set -e

echo "🚀 Starting image2plug Web Application"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create required directories
echo "📁 Creating required directories..."
mkdir -p db uploads web_results static

# Set proper permissions
chmod 755 db uploads web_results

# Stop any existing containers
echo "🛑 Stopping any existing containers..."
docker-compose down 2>/dev/null || true

# Build and start the application
echo "🔨 Building and starting the application..."
docker-compose up --build -d

# Wait for the application to start
echo "⏳ Waiting for application to start..."
sleep 10

# Check if the application is running
if curl -f http://localhost:8000/api/stats >/dev/null 2>&1; then
    echo "✅ Application is running successfully!"
    echo ""
    echo "🌐 Web Interface: http://localhost:8000"
    echo "📊 API Documentation: http://localhost:8000/docs"
    echo "📈 Health Check: http://localhost:8000/api/stats"
    echo ""
    echo "📋 Useful commands:"
    echo "  View logs:     docker-compose logs -f"
    echo "  Stop app:      docker-compose down"
    echo "  Restart app:   docker-compose restart"
    echo ""
else
    echo "❌ Application failed to start. Check logs with: docker-compose logs"
    exit 1
fi