#!/usr/bin/env python3
"""Check Pydantic and MCP package versions for compatibility."""

import sys

def check_versions():
    """Check installed package versions."""
    print("=" * 70)
    print("Package Version Check")
    print("=" * 70)
    print()

    packages = [
        'pydantic',
        'mcp',
        'langchain-core',
        'langchain-mcp-adapters',
        'fastapi',
    ]

    for package_name in packages:
        try:
            if package_name == 'langchain-mcp-adapters':
                import langchain_mcp_adapters
                version = langchain_mcp_adapters.__version__ if hasattr(langchain_mcp_adapters, '__version__') else 'unknown'
            elif package_name == 'langchain-core':
                import langchain_core
                version = langchain_core.__version__ if hasattr(langchain_core, '__version__') else 'unknown'
            elif package_name == 'pydantic':
                import pydantic
                version = pydantic.__version__
            elif package_name == 'mcp':
                import mcp
                version = mcp.__version__ if hasattr(mcp, '__version__') else 'unknown'
            elif package_name == 'fastapi':
                import fastapi
                version = fastapi.__version__

            print(f"[OK] {package_name:25s} {version}")
        except ImportError:
            print(f"[ERROR] {package_name:25s} NOT INSTALLED")
        except Exception as e:
            print(f"[WARN] {package_name:25s} Error: {e}")

    print()
    print("=" * 70)
    print("Compatibility Check")
    print("=" * 70)
    print()

    # Check pydantic version
    try:
        import pydantic
        version = tuple(map(int, pydantic.__version__.split('.')[:2]))
        if version >= (2, 10):
            print(f"[OK] Pydantic {pydantic.__version__} is compatible with MCP")
        elif version >= (2, 9):
            print(f"[WARN] Pydantic {pydantic.__version__} might work, but 2.10+ is recommended")
        else:
            print(f"[ERROR] Pydantic {pydantic.__version__} is too old for MCP")
            print(f"        Please upgrade: pip install 'pydantic>=2.10.0'")
            return False
    except ImportError:
        print("[ERROR] Pydantic not installed")
        return False

    print()
    return True


if __name__ == "__main__":
    success = check_versions()
    sys.exit(0 if success else 1)
