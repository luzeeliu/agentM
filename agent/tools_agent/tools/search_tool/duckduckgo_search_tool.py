# Simple DuckDuckGo search using requests - more reliable than Playwright for search
import json
import requests
from typing import Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from bs4 import BeautifulSoup

class DuckDuckGoSearchArgs(BaseModel):
    query: str = Field(..., description="The search query string.")
    max_results: int = Field(5, description="Maximum number of search results to return.")


class DuckDuckGoSearchTool(BaseTool):
    name: str = "duckduckgo_search"
    args_schema: Type[BaseModel] = DuckDuckGoSearchArgs
    description: str = """A tool to search the web using DuckDuckGo.
    Returns search results with titles, URLs, and snippets.
    Use this to find current information about any topic."""

    def _run(self, query: str, max_results: int = 5) -> str:
        try:
            print(f"[DuckDuckGoSearchTool] Searching for: {query}")

            # Use DuckDuckGo's instant answer API
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            results = []

            # Get abstract if available
            if data.get('Abstract'):
                results.append({
                    "title": data.get('Heading', 'DuckDuckGo Summary'),
                    "url": data.get('AbstractURL', ''),
                    "content": data.get('Abstract', '')
                })

            # Get related topics
            for topic in data.get('RelatedTopics', [])[:max_results]:
                if isinstance(topic, dict) and 'Text' in topic:
                    results.append({
                        "title": topic.get('Text', '')[:100],
                        "url": topic.get('FirstURL', ''),
                        "content": topic.get('Text', '')
                    })

            # If no results, try the HTML search endpoint scraping
            if not results:
                print(f"[DuckDuckGoSearchTool] No instant answers, trying HTML search")
                html_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                html_response = requests.get(html_url, headers=headers, timeout=10)

                # Simple parsing - look for result links
                if html_response.status_code == 200:

                    soup = BeautifulSoup(html_response.text, 'html.parser')
                    for result_div in soup.find_all('div', class_='result')[:max_results]:
                        link = result_div.find('a', class_='result__a')
                        snippet = result_div.find('a', class_='result__snippet')
                        if link:
                            results.append({
                                "title": link.get_text(strip=True),
                                "url": link.get('href', ''),
                                "content": snippet.get_text(strip=True) if snippet else ''
                            })

            print(f"[DuckDuckGoSearchTool] Found {len(results)} results")
            return json.dumps({"results": results}, ensure_ascii=False)

        except Exception as e:
            print(f"[DuckDuckGoSearchTool] Error: {e}")
            import traceback
            traceback.print_exc()
            return json.dumps({"error": str(e), "results": []}, ensure_ascii=False)

    async def _arun(self, query: str, max_results: int = 5) -> str:
        return self._run(query, max_results)
