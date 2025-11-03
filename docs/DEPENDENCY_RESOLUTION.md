# Dependency Resolution Fix

## Issue

When building the Docker image, you encountered a dependency conflict:

```
ERROR: Cannot install langchain-mcp-adapters because these package versions have conflicting dependencies.
The conflict is caused by:
    langchain-mcp-adapters requires langchain-core (>=1.0.0)
    requirements.txt specifies langchain-core==0.3.15
```

## Root Cause

`langchain-mcp-adapters>=0.1.12` requires `langchain-core>=1.0.0`, but the requirements.txt had an older pinned version `langchain-core==0.3.15`.

## Solution

Updated [requirements.txt](../requirements.txt) to use compatible version ranges:

```python
# Before (caused conflict):
langchain-core==0.3.15

# After (allows compatible versions):
langchain-core>=1.0.0,<2.0.0
```

### Full Updated LangChain Dependencies

```txt
# LangChain ecosystem
# Note: langchain-mcp-adapters requires langchain-core>=1.0.0
langchain-core>=1.0.0,<2.0.0
langchain>=0.3.7,<0.4.0
langchain-google-genai>=2.0.2,<3.0.0
langgraph>=0.2.44,<0.3.0

# MCP protocol support
mcp>=1.0.0
langchain-mcp-adapters>=0.1.12
```

## Why This Works

1. **Version Ranges**: Using `>=1.0.0,<2.0.0` allows pip to find compatible versions
2. **Upper Bounds**: The `<2.0.0` prevents breaking changes from major version updates
3. **Flexibility**: Pip can resolve dependencies across all packages

## Testing the Fix

### Local Testing

```bash
# Test dependency resolution
pip install --dry-run -r requirements.txt

# Should complete without errors
```

### Docker Testing

```bash
# Build the image
docker-compose build

# Should complete successfully without dependency conflicts
```

## Best Practices

### ✅ Do:
- Use version ranges for library dependencies: `package>=1.0.0,<2.0.0`
- Pin exact versions for your application: `your-app==1.0.0`
- Document version constraints with comments
- Test dependency resolution before committing

### ❌ Don't:
- Pin library versions too strictly unless you have a specific reason
- Use `==` for transitive dependencies
- Mix pinned and unpinned versions without reason

## Related Packages

The following packages work together and need compatible versions:

```
langchain-core ──┐
                 ├──> All must be compatible
langchain ───────┤
                 │
langchain-mcp-adapters ──┘
```

## Verification

After applying this fix, run:

```bash
python scripts/pre_build_check.py
```

Should output: `[SUCCESS] All checks passed! Ready to build Docker image.`

## Future Updates

When updating LangChain packages:

1. Check compatibility matrix in [LangChain docs](https://python.langchain.com/docs/versions/)
2. Update version ranges, not exact pins
3. Test locally first
4. Build Docker image to verify

## Additional Resources

- [pip dependency resolution](https://pip.pypa.io/en/latest/topics/dependency-resolution/)
- [LangChain versioning](https://python.langchain.com/docs/versions/)
- [langchain-mcp-adapters on PyPI](https://pypi.org/project/langchain-mcp-adapters/)
