# Docker Build Troubleshooting Guide

## Common Build Errors

### 1. `uv: not found` (Exit code 127)

**Error:**
```
RUN uv tool install mcp-server-fetch
/bin/sh: 1: uv: not found
exit code: 127
```

**Cause:** `uv` binary path is incorrect or PATH environment variable not set properly.

**Solution:**
The `uv` installer puts the binary in `/root/.local/bin`, not `/root/.cargo/bin`.

```dockerfile
# ❌ Wrong
RUN uv tool install mcp-server-fetch

# ❌ Wrong path
RUN /root/.cargo/bin/uv tool install mcp-server-fetch

# ✅ Correct - use full path
RUN /root/.local/bin/uv tool install mcp-server-fetch

# ✅ OR set PATH first
ENV PATH="/root/.local/bin:${PATH}"
RUN uv tool install mcp-server-fetch
```

### 2. Requirements.txt Build Failures

**Error:**
```
ERROR: Could not find a version that satisfies the requirement uv
ERROR: No matching distribution found for mcp-server-fetch
```

**Cause:** Invalid packages in requirements.txt. Tools like `uv` and MCP servers (`mcp-server-fetch`) are not Python packages.

**Solution:**
- `uv` is a tool installer (like `npm`), not a Python package
- `mcp-server-fetch` is an MCP server, not a library
- Remove them from requirements.txt
- Install via Dockerfile instead:

```dockerfile
# Install uv tool
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Install MCP servers using uv
RUN /root/.local/bin/uv tool install mcp-server-fetch
```

### 3. Package Version Conflicts

**Error:**
```
ERROR: Cannot install package-a and package-b because these package versions have conflicting dependencies.
```

**Solution:**
1. Pin specific versions that are compatible:
   ```
   package-a==1.2.3
   package-b==4.5.6
   ```

2. Or use version ranges:
   ```
   package-a>=1.2.0,<2.0.0
   package-b>=4.5.0
   ```

### 4. Rust Build Failures

**Error:**
```
cargo: command not found
OR
error: linker `cc` not found
```

**Solution:**
Ensure Rust is installed and PATH is set:

```dockerfile
# Install Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Then build
RUN cargo build --release
```

### 5. Git Clone Failures

**Error:**
```
fatal: could not create work tree dir 'repo': Permission denied
OR
git: command not found
```

**Solution:**
Install git in system dependencies:

```dockerfile
RUN apt-get update \
    && apt-get install -y git \
    && rm -rf /var/lib/apt/lists/*
```

### 6. Network/Download Timeouts

**Error:**
```
ERROR: Could not install packages due to an EnvironmentError: HTTPSConnectionPool
```

**Solution:**
1. Check network connection
2. Use `--prefer-binary` flag for pip:
   ```dockerfile
   RUN pip install --no-cache-dir --prefer-binary -r requirements.txt
   ```
3. Increase Docker build timeout if needed

### 7. Layer Caching Issues

**Problem:** Changes not reflecting in build

**Solution:**
Force rebuild without cache:
```bash
docker-compose build --no-cache
```

### 8. Permission Denied Errors

**Error:**
```
ERROR: /bin/sh: 1: cannot create /path/file: Permission denied
```

**Solution:**
Run as root (default in Dockerfile) or use `sudo`:
```dockerfile
RUN sudo command
# OR
USER root
RUN command
```

## Build Optimization Tips

### 1. Layer Caching
Order Dockerfile commands from least to most frequently changed:

```dockerfile
# ✅ Good - dependencies change less often
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

# ❌ Bad - invalidates cache on every code change
COPY . .
RUN pip install -r requirements.txt
```

### 2. Combine RUN Commands
Reduce layers by combining commands:

```dockerfile
# ✅ Good - one layer
RUN apt-get update \
    && apt-get install -y package1 package2 \
    && rm -rf /var/lib/apt/lists/*

# ❌ Bad - three layers
RUN apt-get update
RUN apt-get install -y package1 package2
RUN rm -rf /var/lib/apt/lists/*
```

### 3. Clean Up in Same Layer
Remove temporary files in the same RUN command:

```dockerfile
# ✅ Good - temp files not in final image
RUN git clone repo /tmp/repo \
    && cd /tmp/repo \
    && make install \
    && rm -rf /tmp/repo

# ❌ Bad - temp files remain in image
RUN git clone repo /tmp/repo
RUN cd /tmp/repo && make install
RUN rm -rf /tmp/repo  # Too late, already in previous layer
```

## Debugging Commands

### View build logs
```bash
docker-compose build 2>&1 | tee build.log
```

### Inspect failed build layer
```bash
docker build --progress=plain .
```

### Enter container for debugging
```bash
# Build up to a specific stage
docker build --target stage-name .

# Run container with shell
docker run -it --entrypoint /bin/bash image-name
```

### Check installed packages
```bash
# Inside container
which uv
which uvx
npm list -g
pip list
```

## Quick Reference

### File Locations in Container

| Tool | Install Path | Command Path |
|------|-------------|--------------|
| `uv`/`uvx` | `/root/.local/bin/` | `/root/.local/bin/uv` |
| Rust/Cargo | `/root/.cargo/bin/` | `/root/.cargo/bin/cargo` |
| npm global | `/usr/local/lib/node_modules/` | `/usr/local/bin/` |
| Python packages | `/usr/local/lib/python3.10/` | System PATH |

### PATH Configuration
```dockerfile
ENV PATH="/root/.local/bin:/root/.cargo/bin:/usr/local/bin:${PATH}"
```

This ensures all tools are accessible.

## Getting Help

1. Check the main [Docker MCP Setup Guide](DOCKER_MCP_SETUP.md)
2. Review [MCP README](agent/tool/mcp/README.md)
3. Run test scripts:
   ```bash
   python scripts/test_mcp_config.py
   python scripts/check_mcp_servers.py
   ```
