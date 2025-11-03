#!/usr/bin/env python3
"""
Check MCP tool schemas for Gemini compatibility issues.
"""

import sys
sys.path.insert(0, '/app')

from agent.tool.mcp.mcp_client import get_mcp_tools
import json


def check_tool_schema(tool):
    """Check if a tool schema is compatible with Gemini."""
    print(f"\n{'='*70}")
    print(f"Tool: {tool.name}")
    print(f"{'='*70}")

    if hasattr(tool, 'args_schema'):
        schema = tool.args_schema
        if hasattr(schema, 'model_json_schema'):
            json_schema = schema.model_json_schema()
            print("Schema:")
            print(json.dumps(json_schema, indent=2))

            # Check for array fields without items
            def check_properties(props, path=""):
                issues = []
                for key, value in props.items():
                    current_path = f"{path}.{key}" if path else key

                    if isinstance(value, dict):
                        # Check if it's an array without items
                        if value.get('type') == 'array' and 'items' not in value:
                            issues.append(f"  [ERROR] {current_path}: array missing 'items' field")

                        # Check nested properties
                        if 'properties' in value:
                            issues.extend(check_properties(value['properties'], current_path))

                        # Check items if present
                        if 'items' in value and isinstance(value['items'], dict):
                            if 'properties' in value['items']:
                                issues.extend(check_properties(value['items']['properties'], f"{current_path}[]"))

                return issues

            if 'properties' in json_schema:
                issues = check_properties(json_schema['properties'])
                if issues:
                    print("\n[ISSUES FOUND]")
                    for issue in issues:
                        print(issue)
                    return False
                else:
                    print("\n[OK] No schema issues found")
                    return True
            else:
                print("\n[OK] No properties to check")
                return True
    else:
        print("[WARN] No args_schema found")
        return True


if __name__ == "__main__":
    print("\n" + "="*70)
    print("MCP Tool Schema Checker for Gemini Compatibility")
    print("="*70)

    tools = get_mcp_tools()
    print(f"\nChecking {len(tools)} tools...")

    problematic_tools = []
    for tool in tools:
        if not check_tool_schema(tool):
            problematic_tools.append(tool.name)

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    if problematic_tools:
        print(f"\n[ERROR] {len(problematic_tools)} tool(s) have schema issues:")
        for name in problematic_tools:
            print(f"  - {name}")
        print("\nThese tools should be excluded from Gemini.")
    else:
        print("\n[OK] All tools have valid schemas for Gemini!")
