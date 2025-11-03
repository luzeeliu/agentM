from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, List

import dotenv
from mcp import StdioServerParameters, types
from pydantic import BaseModel, Field

dotenv.load_dotenv()

_CONFIG_PATH = Path(__file__).with_name("mcp-server-config.json")
_TOOL_CACHE_KEY = "toolCache"


def _expand_env_vars(value):
    """Recursively expand environment variables in strings, dicts, and lists."""
    if isinstance(value, str):
        # Replace ${VAR_NAME} with os.environ.get('VAR_NAME', '')
        def replacer(match):
            var_name = match.group(1)
            return os.environ.get(var_name, f"${{{var_name}}}")
        return re.sub(r'\$\{([^}]+)\}', replacer, value)
    elif isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    return value


class McpServerConfig(BaseModel):
    server_name: str
    server_param: StdioServerParameters
    excluded_tools: List[str] = Field(default_factory=list)


def _load_config_file() -> Dict:
    """Load the shared MCP configuration JSON if it exists."""
    if not _CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def load_mcp_server_configs() -> List[McpServerConfig]:
    """Return all configured MCP servers declared in the config JSON."""
    config_data = _load_config_file()
    servers = config_data.get("mcpServers", {})
    configs: List[McpServerConfig] = []

    for name, payload in servers.items():
        command = payload.get("command")
        if not command:
            continue

        args = payload.get("args") or []
        env = payload.get("env") or None
        excluded = payload.get("excluded_tools") or []

        # Expand environment variables in command, args, and env
        command = _expand_env_vars(command)
        args = _expand_env_vars(args)
        env = _expand_env_vars(env) if env else None

        server_param = StdioServerParameters(
            command=command,
            args=args,
            env=env,
        )
        configs.append(
            McpServerConfig(
                server_name=name,
                server_param=server_param,
                excluded_tools=excluded,
            )
        )

    return configs


def _cache_identifier(server_param: StdioServerParameters) -> str:
    """Build a stable identifier for persisting tool caches per server."""
    args = server_param.args or []
    env = server_param.env or {}
    env_part = ",".join(f"{key}={value}" for key, value in sorted(env.items()))
    return f"{server_param.command}|{' '.join(args)}|{env_part}"


def get_cached_tools(server_param: StdioServerParameters) -> List[types.Tool] | None:
    """Retrieve cached MCP tool descriptors for the given server."""
    config_data = _load_config_file()
    cache = config_data.get(_TOOL_CACHE_KEY, {})
    cached = cache.get(_cache_identifier(server_param))
    if not cached:
        return None
    return [types.Tool(**tool_data) for tool_data in cached]


def save_tools_cache(server_param: StdioServerParameters, tools: List[types.Tool]) -> None:
    """Persist MCP tool descriptors so subsequent runs can avoid re-fetching."""
    config_data = _load_config_file()
    cache = config_data.setdefault(_TOOL_CACHE_KEY, {})
    identifier = _cache_identifier(server_param)

    serialised: List[Dict] = []
    for tool in tools:
        if hasattr(tool, "model_dump"):
            serialised.append(tool.model_dump(mode="json"))
        elif hasattr(tool, "dict"):
            serialised.append(tool.dict())
        else:
            serialised.append(json.loads(tool.json()))

    cache[identifier] = serialised
    _CONFIG_PATH.write_text(json.dumps(config_data, indent=2), encoding="utf-8")
