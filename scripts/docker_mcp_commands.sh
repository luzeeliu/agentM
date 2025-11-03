#!/bin/bash
# Quick reference commands for testing MCP integration in Docker

echo "╔════════════════════════════════════════════════════════════╗"
echo "║          Docker MCP Integration Commands                  ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Build the Docker image
echo "1. Build Docker image:"
echo "   docker-compose build"
echo ""

# Start the container
echo "2. Start container:"
echo "   docker-compose up -d"
echo ""

# Test MCP integration
echo "3. Test MCP integration inside container:"
echo "   docker exec -it agentm python scripts/test_mcp_in_docker.py"
echo ""

# Test MCP client directly
echo "4. Test MCP client module:"
echo "   docker exec -it agentm python -m agent.tool.mcp.mcp_client"
echo ""

# Check logs
echo "5. View container logs:"
echo "   docker-compose logs -f"
echo ""

# Access container shell
echo "6. Access container shell:"
echo "   docker exec -it agentm bash"
echo ""

# Verify MCP servers are installed
echo "7. Verify MCP servers:"
echo "   docker exec -it agentm which arxiv-paper-mcp"
echo "   docker exec -it agentm python -c 'from agent.tool.mcp.server import server; print(server)'"
echo ""

# Stop container
echo "8. Stop container:"
echo "   docker-compose down"
echo ""

# Rebuild from scratch
echo "9. Rebuild from scratch (no cache):"
echo "   docker-compose build --no-cache"
echo ""

echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    Quick Test                              ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Run full test sequence:"
echo "  docker-compose build && docker-compose up -d && docker exec -it agentm python scripts/test_mcp_in_docker.py"
echo ""
