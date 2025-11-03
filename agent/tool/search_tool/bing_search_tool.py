import json
import requests
import random
from bs4 import BeautifulSoup
from typing import Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from . import HEADERS, USER_AGENTS

class BingSearchArgs(BaseModel):
    query: str = Field(..., description="The search query string.")
    max_results: int = Field(5, description="Maximum number of search results to return.")
    

class BingSearchTool(BaseTool):
    name: str = "bing_search_tool"
    args_schema: Type[BaseModel] = BingSearchArgs
    description: str = """A tool to perform Bing searches
    return seatch result with titles, URLs, and snippets.
    Use this to find current information about any topic."""
    _base_url: list = ["https://www.bing.com", "https://cn.bing.com"]
    
    
    def _run(self, query: str, max_results: int = 5) -> str:
        try:
            print(f"[BingSearchTool] Searching for: {query}")
            results = []

            # Try each base URL until we get results
            for base_url in self._base_url:
                if results:  # If we already have results, break
                    break

                try:
                    # Use HTML scraping (Bing doesn't provide free JSON API)
                    search_url = f"{base_url}/search"
                    params = {"q": query}

                    # Use random user agent to avoid detection
                    headers = HEADERS.copy()
                    headers["User-Agent"] = random.choice(USER_AGENTS)

                    print(f"[BingSearchTool] Trying {base_url}")
                    response = requests.get(search_url, params=params, headers=headers, timeout=15)

                    if response.status_code != 200:
                        print(f"[BingSearchTool] Got status code {response.status_code}, trying next URL")
                        continue

                    soup = BeautifulSoup(response.content, 'html.parser')

                    # Extract search results from Bing's HTML structure
                    search_items = soup.select('li.b_algo')

                    if not search_items:
                        print(f"[BingSearchTool] No results found with selector 'li.b_algo', trying alternative selectors")
                        # Try alternative selectors
                        search_items = soup.select('ol#b_results > li')

                    for item in search_items[:max_results]:
                        try:
                            # Extract title and URL
                            link_elem = item.select_one('h2 a')
                            if not link_elem:
                                continue

                            title = link_elem.get_text(strip=True)
                            url = link_elem.get('href', '')

                            # Extract snippet/description
                            snippet_elem = (
                                item.select_one('div.b_caption p') or
                                item.select_one('p') or
                                item.select_one('div.b_caption')
                            )
                            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''

                            # Only add if we have valid title and URL
                            if title and url:
                                results.append({
                                    "title": title,
                                    "url": url,
                                    "content": snippet
                                })
                        except Exception as item_error:
                            print(f"[BingSearchTool] Error parsing item: {item_error}")
                            continue

                    if results:
                        print(f"[BingSearchTool] Successfully found {len(results)} results from {base_url}")

                except requests.exceptions.RequestException as req_error:
                    print(f"[BingSearchTool] Request error for {base_url}: {req_error}")
                    continue
                except Exception as parse_error:
                    print(f"[BingSearchTool] Parse error for {base_url}: {parse_error}")
                    continue

            # Return results or error message
            if results:
                return json.dumps({"results": results}, ensure_ascii=False)
            else:
                error_msg = f"No search results found for query: {query}"
                print(f"[BingSearchTool] {error_msg}")
                return json.dumps({"error": error_msg, "results": []}, ensure_ascii=False)

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"[BingSearchTool] {error_msg}")
            import traceback
            traceback.print_exc()
            return json.dumps({"error": error_msg, "results": []}, ensure_ascii=False)
