#!/usr/bin/env python3
"""
Pre-build check script to verify all MCP configuration is correct
before building the Docker image.
"""

import json
import sys
from pathlib import Path


def check_mcp_config():
    """Verify mcp-server-config.json is valid."""
    print("=" * 70)
    print("Checking MCP Configuration")
    print("=" * 70)

    config_path = Path(__file__).parent.parent / "agent" / "tool" / "mcp" / "mcp-server-config.json"

    if not config_path.exists():
        print(f"[ERROR] Config file not found: {config_path}")
        return False

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        print(f"[OK] Config file is valid JSON")
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in config file: {e}")
        return False

    servers = config.get('mcpServers', {})
    if not servers:
        print("[WARN] No MCP servers configured")
        return True

    print(f"[OK] Found {len(servers)} MCP server(s) configured")
    print()

    all_ok = True
    for name, server_config in servers.items():
        print(f"  Server: {name}")
        command = server_config.get('command')
        args = server_config.get('args', [])

        if not command:
            print(f"    [ERROR] No command specified")
            all_ok = False
            continue

        print(f"    Command: {command}")
        print(f"    Args: {args}")

        # Check if it's the optimized Docker command
        if name == 'arxiv':
            if command == 'arxiv-paper-mcp':
                print(f"    [OK] Using pre-installed binary (optimized for Docker)")
            elif command == 'npx':
                print(f"    [WARN] Using npx (works but slower in Docker)")
                print(f"          Consider: 'command': 'arxiv-paper-mcp', 'args': []")

        print()

    return all_ok


def check_requirements():
    """Verify requirements.txt has langchain-mcp-adapters."""
    print("=" * 70)
    print("Checking Requirements")
    print("=" * 70)

    req_path = Path(__file__).parent.parent / "requirements.txt"

    if not req_path.exists():
        print(f"[ERROR] requirements.txt not found")
        return False

    with open(req_path, 'r') as f:
        content = f.read()

    if 'langchain-mcp-adapters' in content:
        print("[OK] langchain-mcp-adapters is in requirements.txt")
    else:
        print("[ERROR] langchain-mcp-adapters is missing from requirements.txt")
        print("        Add: langchain-mcp-adapters>=0.1.12")
        return False

    if 'mcp>=' in content:
        print("[OK] mcp is in requirements.txt")
    else:
        print("[WARN] mcp might be missing from requirements.txt")

    print()
    return True


def check_dockerfile():
    """Verify Dockerfile has arxiv-paper-mcp pre-installed."""
    print("=" * 70)
    print("Checking Dockerfile")
    print("=" * 70)

    dockerfile_path = Path(__file__).parent.parent / "Dockerfile"

    if not dockerfile_path.exists():
        print(f"[ERROR] Dockerfile not found")
        return False

    with open(dockerfile_path, 'r') as f:
        content = f.read()

    checks = [
        ('npm install -g @langgpt/arxiv-paper-mcp', 'arxiv-paper-mcp pre-installation'),
        ('nodejs', 'Node.js installation'),
        ('COPY requirements.txt', 'Python requirements copy'),
        ('pip install', 'Python package installation'),
    ]

    all_ok = True
    for check_str, description in checks:
        if check_str in content:
            print(f"[OK] {description} found")
        else:
            print(f"[WARN] {description} not found")
            if check_str == 'npm install -g @langgpt/arxiv-paper-mcp':
                all_ok = False

    print()
    return all_ok


def check_mcp_client():
    """Verify mcp_client.py exists and uses langchain_mcp_adapters."""
    print("=" * 70)
    print("Checking MCP Client")
    print("=" * 70)

    client_path = Path(__file__).parent.parent / "agent" / "tool" / "mcp" / "mcp_client.py"

    if not client_path.exists():
        print(f"[ERROR] mcp_client.py not found")
        return False

    with open(client_path, 'r') as f:
        content = f.read()

    if 'from langchain_mcp_adapters.tools import load_mcp_tools' in content:
        print("[OK] mcp_client.py uses langchain_mcp_adapters")
    else:
        print("[ERROR] mcp_client.py doesn't import langchain_mcp_adapters")
        return False

    if 'def get_mcp_tools()' in content:
        print("[OK] get_mcp_tools() function exists")
    else:
        print("[ERROR] get_mcp_tools() function not found")
        return False

    print()
    return True


def check_tool_box():
    """Verify tool_box.py imports mcp_client."""
    print("=" * 70)
    print("Checking Tool Box Integration")
    print("=" * 70)

    toolbox_path = Path(__file__).parent.parent / "agent" / "tool" / "tool_box.py"

    if not toolbox_path.exists():
        print(f"[ERROR] tool_box.py not found")
        return False

    with open(toolbox_path, 'r') as f:
        content = f.read()

    if 'from .mcp.mcp_client import get_mcp_tools' in content:
        print("[OK] tool_box.py imports get_mcp_tools")
    else:
        print("[ERROR] tool_box.py doesn't import get_mcp_tools")
        return False

    if '_ensure_mcp_tools()' in content or 'get_mcp_tools()' in content:
        print("[OK] tool_box.py calls MCP tool loading")
    else:
        print("[WARN] tool_box.py might not be loading MCP tools")

    print()
    return True


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("MCP Docker Pre-Build Verification")
    print("=" * 70)
    print()

    results = {
        'MCP Config': check_mcp_config(),
        'Requirements': check_requirements(),
        'Dockerfile': check_dockerfile(),
        'MCP Client': check_mcp_client(),
        'Tool Box': check_tool_box(),
    }

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    all_passed = True
    for check_name, passed in results.items():
        status = "[OK] PASSED" if passed else "[ERROR] FAILED"
        print(f"{check_name:20s} {status}")
        if not passed:
            all_passed = False

    print("=" * 70)

    if all_passed:
        print("\n[SUCCESS] All checks passed! Ready to build Docker image.")
        print("\nNext steps:")
        print("  1. docker-compose build")
        print("  2. docker-compose up -d")
        print("  3. docker exec -it agentm python scripts/test_mcp_in_docker.py")
        sys.exit(0)
    else:
        print("\n[ERROR] Some checks failed. Please fix the issues above.")
        sys.exit(1)
