import json
import os
import dotenv
from typing import Type
from pydantic import BaseModel, Field, PrivateAttr
from langchain_core.tools import BaseTool
dotenv.load_dotenv()

        
class GoogleSearchArgs(BaseModel):
    query: str = Field(..., description="The search query string.")
    max_results: int = Field(5, description="Maximum number of search results to return.")

class GoogleSearchTool(BaseTool):
    name: str = "google_search"
    args_schema: Type[BaseModel] = GoogleSearchArgs
    description: str = """A tool to search the web using Google.
    Returns search results with titles, URLs, and snippets.
    Use this to find current information about any topic."""
    
    def _run(self, query: str, max_results: int = 5) -> str:
        # Lazy import to avoid hard dependency at startup
        try:
            from serpapi import GoogleSearch  # type: ignore
        except Exception as ie:
            return json.dumps({
                "error": f"serpapi module not available: {ie}. Install 'google-search-results' or remove GoogleSearchTool.",
                "results": []
            }, ensure_ascii=False)
        api_key = os.getenv("GOOGLE_API_KEY")
        results = []
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is not set")
        try:
            params = {
                "engine": "google",
                "q": query,
                "api_key": api_key,
            }
            search = GoogleSearch(params)
            search_results = search.get_dict()
            text_block = search_results['organic_results'][:max_results]
            for i in text_block:
                results.append({
                    "title": i['title'],
                    "url" : i['link'],
                    "snippet" : i['snippet']
                })
            return json.dumps({"results": results}, ensure_ascii=False)
        except Exception as e:
            print(f"[GoogleSearch] Error: {e}")
            import traceback
            traceback.print_exc()
            return json.dumps({"error": str(e), "results": []}, ensure_ascii=False)


    async def _arun(self, query: str, max_results: int = 5) -> str:
        return self._run(query, max_results)
