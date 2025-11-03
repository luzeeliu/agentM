import asyncio
from typing import List, Optional

from langchain_core.tools import BaseTool, BaseToolkit, ToolException
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from pydantic_core import to_json
from jsonschema_pydantic import jsonschema_to_pydantic
from pydantic import BaseModel

from .mcp_server_config import McpServerConfig, get_cached_tools, save_tools_cache

# discover tool from server and make a wrapper
class McpToolkit(BaseToolkit):
    # tool name
    name: str
    # connection parameters for the server
    server_param: StdioServerParameters
    # tools excluded from this server
    excluded_tools: List[str] = []
    # server session
    _session: Optional[ClientSession] = None
    _tools: List[BaseTool] = []
    _client = None
    # set asynic lock for initialization once
    _init_lock: asyncio.Lock = None
    
    def __init__(self, **data):
        super().__init__(**data)
        self._init_lock = asyncio.Lock()
        self._tools = []
        
    async def _start_session(self):
        # use async lock and initialize only once
        async with self._init_lock:
            if self._session:
                return self._session
            
            # get specific server
            self._client = stdio_client(self.server_param)
            # get read and write stream form client
            read, write = await self._client.__aenter__()
            # create session
            self._session = ClientSession(read, write)
            # because clientsession is an async function so it method need await
            await self._session.__aenter__()
            await self._session.initialize()
            return self._session
    
    async def initialize(self, force_refresh: bool = False):
        if force_refresh:
            self._tools = []
        if self._tools and not force_refresh:
            return
        # get tool from server
        cached_tools = get_cached_tools(self.server_param)
        if cached_tools and not force_refresh:
            for tool in cached_tools:
                if tool.name in self.excluded_tools:
                    continue
                # convert cached MCP tool metadata into LangChain tool instances
                self._tools.append(McpTool(
                    toolkit=self,
                    name=tool.name,
                    description=tool.description,
                    args_schema=jsonschema_to_pydantic(tool.inputSchema),
                    toolkit_name=self.name,
                    session=self._session
                ))
            return
        try:
            await self._start_session()
            # flash tool list
            tools: types.ListToolsResult = await self._session.list_tools()
            save_tools_cache(self.server_param, tools.tools)
            for tool in tools.tools:
                if tool.name in self.excluded_tools:
                    continue
                self._tools.append(McpTool(
                    toolkit=self,
                    name=tool.name,
                    description=tool.description,
                    args_schema=jsonschema_to_pydantic(tool.inputSchema),
                    toolkit_name=self.name,
                    session=self._session
                ))
        except Exception as e:
            print(f"Error gathering tools for {self.server_param.command} {' '.join(self.server_param.args)}: {e}")
            raise e
    
    async def close(self):
        try:
            if self._session:
                try:
                    # Add timeout to prevent hanging
                    async with asyncio.timeout(2.0):
                        await self._session.__aexit__(None, None, None)
                except asyncio.TimeoutError:
                    pass
                except Exception as e:
                    pass
        finally:
            try:
                if self._client:
                    try:
                        # Add timeout to prevent hanging
                        async with asyncio.timeout(2.0):
                            await self._client.__aexit__(None, None, None)
                    except asyncio.TimeoutError:
                        pass
                    except Exception as e:
                        pass
            except:
                pass
    
    def get_tools(self):
        return self._tools
    

class McpTool(BaseTool):
    toolkit_name: str
    name: str
    description: str
    args_schema: type[BaseModel]
    session: Optional[ClientSession]
    toolkit: McpToolkit
    
    hand_tool_error: bool = True
    
    def _run(self, **kwargs):
        raise NotImplementedError("only async function is supported")

    async def _arun(self, **kwargs):
        if not self.session:
            self.session = await self.toolkit._start_session()

        # use call tool to connect MCP server tool box
        result = await self.session.call_tool(self.name, kwargs)
        content = to_json(result.content).decode()
        if result.isError:
            raise ToolException(content)
        return content


async def convert_mcp_tool_to_langchain_tool(server_config: McpServerConfig, force_update: bool = False):
    toolkit = McpToolkit(
        name = server_config.server_name,
        server_param = server_config.server_param,
        excluded_tools = server_config.excluded_tools
    )
    await toolkit.initialize(force_refresh=force_update)
    return toolkit

