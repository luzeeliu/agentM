#!/bin/bash
# Build script for AgentM Docker container
# This script provides better error reporting and build progress visibility

set -e  # Exit on error

echo "==============================================="
echo "Building AgentM Docker Container"
echo "==============================================="
echo ""

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose not found. Please install Docker Compose."
    exit 1
fi

# Clean up old build artifacts (optional - uncomment if needed)
# echo "Cleaning up old build cache..."
# docker builder prune -f

echo "Starting Docker build..."
echo "This may take several minutes on first build."
echo ""

# Build with progress output
# Use --progress=plain for detailed output, or remove for default output
docker-compose build --progress=plain

echo ""
echo "==============================================="
echo "Build completed successfully!"
echo "==============================================="
echo ""
echo "To start the container, run:"
echo "  docker-compose up -d"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f"
echo ""
