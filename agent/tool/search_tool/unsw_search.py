import os
import re
import time
import json
from typing import Optional, List, Dict
from dotenv import load_dotenv
from langchain_core.tools import BaseTool
from typing import Type
from pydantic import BaseModel


try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("Playwright not installed. Install with:")
    print("pip install playwright")
    print("playwright install")
    exit(1)

# Load environment variables
load_dotenv()

class HandbookScraperPlaywright:
    """Intelligent web scraper for UNSW Handbook using search-first approach with Playwright."""

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._page = None
        self.current_url = None
        self.base_url = "https://www.handbook.unsw.edu.au"
        self.search_url = f"{self.base_url}/search"

    def start_browser(self, headless: bool = True) -> str:
        """Start browser session.

        Args:
            headless: Run browser in headless mode (default: True)

        Returns:
            Success message
        """
        if self._browser:
            return "Browser already started"

        self._playwright = sync_playwright().start()
        launch_args = {"headless": headless, "args": ["--no-sandbox", "--disable-setuid-sandbox"]}
        self._browser = self._playwright.chromium.launch(**launch_args)
        self._page = self._browser.new_page()

        # Set a reasonable timeout
        #self._page.set_default_timeout(30000)  # 30 seconds

        return f"Browser started (headless={headless})"


    def _extract_search_results(self, limit: int = 5) -> List[Dict[str, str]]:
        """Extract search results from the current search results page.
        
        Args:
            limit: Maximum number of results to extract
            
        Returns:
            List of dictionaries containing result information
        """
        results = []
        
        try:
            # Wait for results container
            self._page.wait_for_selector(".search-results, [class*='result']", timeout=5000)
            
            # Try multiple selectors to find result links
            result_selectors = [
                "a[href*='/undergraduate/']",
                "a[href*='/postgraduate/']",
            ]
            
            all_links = []
            for selector in result_selectors:
                links = self._page.query_selector_all(selector)
                all_links.extend(links)
            
            # Remove duplicates by href
            seen_hrefs = set()
            unique_links = []
            for link in all_links:
                href = link.get_attribute("href")
                if href and href not in seen_hrefs:
                    seen_hrefs.add(href)
                    unique_links.append(link)
            
            # Extract information from each link
            for link in unique_links[:limit]:
                try:
                    href = link.get_attribute("href")
                    text = link.inner_text().strip()
                    
                    if not href or not text:
                        continue
                    
                    # Make href absolute if relative
                    if href.startswith("/"):
                        href = f"{self.base_url}{href}"
                    
                    # Extract type and code from URL
                    result_type = "Unknown"
                    code = ""
                    year = ""
                    
                    if "/courses/" in href:
                        result_type = "Course"
                        # Extract course code and year from URL
                        match = re.search(r'/courses/(\d+)/([A-Z]{4}\d{4})', href)
                        if match:
                            year = match.group(1)
                            code = match.group(2)
                    elif "/programs/" in href:
                        result_type = "Program"
                        # Extract program code and year from URL
                        match = re.search(r'/programs/(\d+)/(\d+)', href)
                        if match:
                            year = match.group(1)
                            code = match.group(2)
                    
                    # Extract code from text if not found in URL
                    if not code:
                        code_match = re.search(r'\b([A-Z]{4}\d{4}|\d{4})\b', text)
                        if code_match:
                            code = code_match.group(1)
                    
                    results.append({
                        "title": text,
                        "url": href,
                        "type": result_type,
                        "code": code,
                        "year": year
                    })
                    
                except Exception as e:
                    print(f"Error extracting result: {e}")
                    continue
            
        except Exception as e:
            print(f"Error in _extract_search_results: {e}")
        
        return results

    def navigate_to_final(self, query: str, idx: int = 0) -> str:
        """Navigate to final result using intelligent search.
        
        Args:
            query: Program code (e.g., "8543")
            year: Handbook year (default: "2026")
            
        Returns:
            Success message with page details
        """
        if not self._page:
            return "Error: Browser not started. Call start_browser() first."
        
        # Search for the program
        query = f"{query}"
        
        try:
            search_url = f"{self.search_url}?q={query}"
            self._page.goto(search_url, wait_until="networkidle")
            time.sleep(2)
            
            results = self._extract_search_results(limit=2)

            # Find the best match

            if not results:
                return f"Could not find program {query}"

            # Navigate to the first result (best match)
            best_match = results[idx]
            self._page.goto(best_match['url'], wait_until="networkidle")
            self._page.wait_for_selector("h1", timeout=10000)
            time.sleep(2)

            self.current_url = best_match['url']
                      
            return len(results), best_match['url']
            
        except Exception as e:
            return f"Error navigating to program: {str(e)}"



    def get_full_page_text(self) -> str:
        """Get all visible text from current page.

        Returns:
            Full page text content
        """
        if not self._page:
            return "Error: No page loaded"

        try:
            # Get text content from body
            body = self._page.query_selector("body")
            if body:
                text = body.inner_text()
                return text
            else:
                return "Error: Could not find page body"
        except Exception as e:
            return f"Error extracting text: {str(e)}"


    def search_page(self, keyword: str) -> str:
        """Search for keyword in current page.

        Args:
            keyword: Keyword to search for

        Returns:
            Text snippets containing keyword
        """
        if not self._page:
            return "Error: No page loaded"

        try:
            page_text = self.get_full_page_text()
            lines = page_text.split('\n')
            matches = [line.strip() for line in lines if keyword.lower() in line.lower()]

            if matches:
                unique_matches = []
                seen = set()
                for match in matches:
                    if match and match not in seen and len(match) > 5:
                        seen.add(match)
                        unique_matches.append(match)

                return f"Found {len(unique_matches)} mentions:\n\n" + "\n\n".join(unique_matches[:10])
            else:
                return f"No matches for '{keyword}'"

        except Exception as e:
            return f"Error searching: {str(e)}"

    def take_screenshot(self, filename: str = "handbook_screenshot.png") -> str:
        """Take screenshot of current page.

        Args:
            filename: Screenshot filename

        Returns:
            Success message with filename
        """
        if not self._page:
            return "Error: No page loaded"

        try:
            self._page.screenshot(path=filename)
            return f"Screenshot saved: {filename}"
        except Exception as e:
            return f"Error taking screenshot: {str(e)}"

    def get_current_url(self) -> str:
        """Get current page URL.

        Returns:
            Current URL or error message
        """
        if self.current_url:
            return f"Current URL: {self.current_url}"
        else:
            return "No page loaded"

    def close_browser(self) -> str:
        """Close browser and clean up resources.

        Returns:
            Success message
        """
        try:
            if self._page:
                self._page.close()
                self._page = None
            if self._browser:
                self._browser.close()
                self._browser = None
            if self._playwright:
                self._playwright.stop()
                self._playwright = None

            self.current_url = None
            return "Browser closed successfully"

        except Exception as e:
            return f"Error closing browser: {str(e)}"


class hand_book_search_args(BaseModel):
    query: str = "specific course or program code"
    #keyward: str = "actually search topic or attribute in this course or program, example: 'prerequisite', '"
    
class HandbookSearch(BaseTool):
    name: str = "UNSW_Handbook_Search"
    description: str = """
    Search for a specific course or program code in the UNSW Handbook
    attention: only search course code formatlike "comp9517","MATH1234"
    only search program code format like "8543"
    the pipeline of this tool is:
    1. open brower
    2. use search to get web search result
    3. entry the search result url
    4. fetch page content
    5. search specific line include keyword
    """
    args_schema: Type[hand_book_search_args] = hand_book_search_args

    def _run(self, query: str):
        try:
            results = []
            scraper = HandbookScraperPlaywright()
            scraper.start_browser(headless=True)
            num, url = scraper.navigate_to_final(query, 0) 
            results.append({
                "url": url,
                "content": scraper.get_full_page_text()
            })
                
            if num == 2:
                num, url = scraper.navigate_to_final(query, 1)
                results.append({
                    "url": url,
                    "content": scraper.get_full_page_text()
                })
            scraper.close_browser()
            return json.dumps({"results": results}, ensure_ascii=False)
        except Exception as e:
            return f"Error: {str(e)}"
    
    async def _arun(self, query: str):
        raise self._run(query)

