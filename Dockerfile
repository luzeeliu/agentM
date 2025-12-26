FROM python:3.11-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1

WORKDIR /app

# Install system dependencies
# - Node.js for MCP tooling (arxiv-paper-mcp)
# - Basic build tools for Python packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        gnupg \
        git \
        build-essential \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g corepack \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (split into smaller steps to avoid segfault)
COPY backend/requirements.txt ./backend/requirements.txt
COPY requirements.txt ./requirements.txt


# Upgrade pip and install uv (faster, less memory-intensive installer)
RUN python -m pip install --upgrade pip setuptools wheel uv

# Install PyTorch (CPU version) using uv to avoid build-time segfaults (Exit Code 139)
# The CUDA version (~2.5GB) often crashes Docker builds on WSL/Desktop due to memory limits.
# Switching to CPU version (~200MB) fixes this.
RUN uv pip install --system --no-cache torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install backend requirements first (smaller file)
RUN uv pip install --system --no-cache -r backend/requirements.txt
RUN uv pip install --system --no-cache -r ./requirements.txt

# Install agent requirements individually to isolate potential segfault issues
# Core dependencies
RUN uv pip install --system --no-cache \
    python-dotenv==1.0.1

# LangChain ecosystem (split to avoid MemoryError)
RUN uv pip install --system --no-cache langchain-core
RUN uv pip install --system --no-cache langchain
RUN uv pip install --system --no-cache langchain-google-genai
RUN uv pip install --system --no-cache langgraph 

# Web scraping & automation
RUN uv pip install --system --no-cache \
    playwright==1.48.0 \
    requests==2.31.0 \
    beautifulsoup4==4.12.3

# Search tools
RUN uv pip install --system --no-cache \
    search-engine-parser \
    google-search-results

# MCP support
RUN uv pip install --system --no-cache \
    mcp \
    langchain-mcp-adapters \
    jsonschema-pydantic

# Install Playwright browsers
RUN playwright install-deps chromium

# Pre-install MCP servers to avoid runtime downloads
# Currently only arxiv MCP server is used
# Search tools (google, duckduckgo, yahoo, bing) are now integrated directly in Python
RUN npm install -g @langgpt/arxiv-paper-mcp

# Copy project files
COPY . .

# Make scripts executable (if they exist)
RUN chmod +x scripts/check_mcp_servers.py 2>/dev/null || true \
    && chmod +x scripts/test_mcp_in_docker.py 2>/dev/null || true

EXPOSE 8000

# Optional: Uncomment to verify MCP servers on container build
# RUN python scripts/check_mcp_servers.py

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
