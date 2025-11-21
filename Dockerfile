FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

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

# Upgrade pip in separate step using python -m pip (more reliable)
RUN python -m pip install --upgrade pip setuptools wheel

# Install backend requirements first (smaller file)
RUN python -m pip install --no-cache-dir --prefer-binary -r backend/requirements.txt
RUN python -m pip install --no-cache-dir --prefer-binary -r ./requirements.txt

# Install agent requirements individually to isolate potential segfault issues
# Core dependencies
RUN python -m pip install --no-cache-dir --prefer-binary \
    python-dotenv==1.0.1

# LangChain ecosystem (most likely to cause segfault due to size/complexity)
RUN python -m pip install --no-cache-dir --prefer-binary \
    langchain-core \
    langchain \
    langchain-google-genai \
    langgraph 

# Web scraping & automation
RUN python -m pip install --no-cache-dir --prefer-binary \
    playwright==1.48.0 \
    requests==2.31.0 \
    beautifulsoup4==4.12.3

# Search tools
RUN python -m pip install --no-cache-dir --prefer-binary \
    search-engine-parser \
    google-search-results

# MCP support
RUN python -m pip install --no-cache-dir --prefer-binary \
    mcp \
    langchain-mcp-adapters \
    jsonschema-pydantic

# Install Playwright browsers
RUN playwright install chromium

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
