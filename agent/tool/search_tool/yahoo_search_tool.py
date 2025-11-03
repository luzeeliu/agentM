from search_engine_parser.core.engines.yahoo import Search as YahooSearch
from langchain_core.tools import BaseTool
from typing import Type 
import json
from pydantic import BaseModel, Field, PrivateAttr

class YahooSearchArgs(BaseModel):
    query: str = Field(..., description="The search query string.")
    page: int = Field(1, description="page argument used by the library")
    
class YahooSearchTool(BaseTool):
    name: str = "yahoo_search_tool"
    args_schema: Type[BaseModel] = YahooSearchArgs
    description: str = """"A tool to perform Yahoo searches
    Return search result with titles, URLs, and snippets.
    Use this to find current information about any topic."""
    
    def _run(self, query: str, page: int = 1):
        try:
            print(f"[YahooSearchTool] Searching for: {query}")
            search_engine = YahooSearch()
            results = search_engine.search(query, page)

            ans = []

            # Try different ways to access the results based on library version
            for accessor in (
                lambda k: getattr(results, k, None),  # attribute access
                lambda k: results.get(k) if hasattr(results, 'get') else None,  # mapping style
            ):
                try:
                    titles = accessor("titles") or []
                    links = accessor("links") or []
                    descs = accessor("descriptions") or []

                    if isinstance(titles, list) and isinstance(links, list) and isinstance(descs, list):
                        size = min(len(titles), len(links), len(descs))
                        ans = [
                            {"title": titles[i], "url": links[i], "content": descs[i]}
                            for i in range(size)
                        ]
                        if ans:
                            print(f"[YahooSearchTool] Found {len(ans)} results")
                            return json.dumps({"results": ans}, ensure_ascii=False)
                except Exception:
                    pass

            # Fallback: try to convert to dict
            try:
                if hasattr(results, '__dict__'):
                    d = results.__dict__
                else:
                    d = dict(results)

                titles = d.get("titles", [])
                links = d.get("links", [])
                descs = d.get("descriptions", [])

                size = min(len(titles), len(links), len(descs))
                ans = [
                    {"title": titles[i], "url": links[i], "content": descs[i]}
                    for i in range(size)
                ]

                if ans:
                    print(f"[YahooSearchTool] Found {len(ans)} results")
                    return json.dumps({"results": ans}, ensure_ascii=False)
                else:
                    return json.dumps({"results": [], "message": "No results found"}, ensure_ascii=False)

            except Exception as e:
                print(f"[YahooSearchTool] Error parsing results: {e}")
                import traceback
                traceback.print_exc()
                return json.dumps({"error": str(e), "results": []}, ensure_ascii=False)

        except Exception as e:
            print(f"[YahooSearchTool] Error: {e}")
            import traceback
            traceback.print_exc()
            return json.dumps({"error": str(e), "results": []}, ensure_ascii=False)

            
    async def _arun(self, query: str, page: int = 1):
        return self._run(query, page)            
    
