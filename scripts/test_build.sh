#!/bin/bash
# Quick script to test Docker build with better error reporting

echo "=========================================="
echo "Testing Docker Build"
echo "=========================================="
echo ""

# Check Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "[ERROR] Docker is not running!"
    echo "Please start Docker Desktop and try again."
    exit 1
fi

echo "[OK] Docker is running"
echo ""

# Run pre-build checks
echo "Running pre-build checks..."
python scripts/pre_build_check.py
if [ $? -ne 0 ]; then
    echo "[ERROR] Pre-build checks failed!"
    exit 1
fi

echo ""
echo "=========================================="
echo "Building Docker Image"
echo "=========================================="
echo ""

# Build the image
docker-compose build

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "[SUCCESS] Docker build completed!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "  1. docker-compose up -d"
    echo "  2. docker exec -it agentm python scripts/test_mcp_in_docker.py"
    echo ""
else
    echo ""
    echo "=========================================="
    echo "[ERROR] Docker build failed!"
    echo "=========================================="
    echo ""
    echo "Check the error messages above."
    echo "Common issues:"
    echo "  - Dependency conflicts (check requirements.txt)"
    echo "  - Network issues (can't download packages)"
    echo "  - Disk space (check 'docker system df')"
    echo ""
    exit 1
fi
