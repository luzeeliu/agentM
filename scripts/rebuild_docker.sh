#!/bin/bash
# Script to rebuild Docker container with updated dependencies

echo "=========================================="
echo "Rebuilding Docker Container"
echo "=========================================="
echo ""

echo "This will:"
echo "  1. Stop the current container"
echo "  2. Rebuild the image with updated Pydantic (>=2.10.0)"
echo "  3. Start the new container"
echo "  4. Test MCP integration"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "[1/4] Stopping current container..."
docker-compose down

echo ""
echo "[2/4] Rebuilding image (this may take a few minutes)..."
docker-compose build --no-cache

if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] Build failed! Check the error messages above."
    exit 1
fi

echo ""
echo "[3/4] Starting new container..."
docker-compose up -d

if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] Failed to start container!"
    exit 1
fi

echo ""
echo "Waiting for container to be ready..."
sleep 3

echo ""
echo "[4/4] Testing MCP integration..."
docker exec -it agentm python scripts/test_mcp_in_docker.py

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "[SUCCESS] Rebuild complete!"
    echo "=========================================="
    echo ""
    echo "Your agent is now running with:"
    echo "  - Pydantic >= 2.10.0"
    echo "  - 8 MCP tools (4 arxiv + 4 web-search)"
    echo ""
    echo "Access the API at: http://localhost:8000"
    echo "View logs: docker-compose logs -f"
    echo ""
else
    echo ""
    echo "=========================================="
    echo "[WARNING] Rebuild succeeded but tests failed"
    echo "=========================================="
    echo ""
    echo "Check logs: docker-compose logs agentm"
    echo ""
fi
