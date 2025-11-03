
import os
import re
import time
from typing import Optional
from dotenv import load_dotenv

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
    """Web scraper for UNSW Handbook using Playwright for JavaScript rendering."""

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._page = None
        self.current_url = None
        self.base_url = "https://www.handbook.unsw.edu.au"

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
        self._browser = self._playwright.chromium.launch(headless=headless)
        self._page = self._browser.new_page()

        # Set a reasonable timeout
        self._page.set_default_timeout(30000)  # 30 seconds

        return f"Browser started (headless={headless})"

    def navigate_to_program(self, program_code: str, year: str = "2026", level: str = "postgraduate") -> str:
        """Navigate to a specific program page.

        Args:
            program_code: Program code (e.g., "8543")
            year: Handbook year (default: "2026")
            level: "postgraduate" or "undergraduate" (default: "postgraduate")

        Returns:
            Success message with page title
        """
        if not self._page:
            return "Error: Browser not started. Call start_browser() first."

        url = f"{self.base_url}/{level}/programs/{year}/{program_code}"

        try:
            self._page.goto(url, wait_until="networkidle")

            # Wait for main content to load
            self._page.wait_for_selector("h1", timeout=10000)

            # Extra wait for dynamic content
            time.sleep(2)

            self.current_url = url

            title = self._page.title()
            h1 = self._page.query_selector("h1")
            h1_text = h1.inner_text() if h1 else "Unknown"

            return f"Successfully loaded: {h1_text}\nPage title: {title}\nURL: {url}"

        except PlaywrightTimeout:
            return f"Timeout loading page: {url}\nThe page took too long to load."
        except Exception as e:
            return f"Error loading page: {str(e)}\nURL: {url}"

    def navigate_to_course(self, course_code: str, year: str = "2026") -> str:
        """Navigate to a specific course page.

        Args:
            course_code: Course code (e.g., "COMP9021")
            year: Handbook year (default: "2026")

        Returns:
            Success message
        """
        if not self._page:
            return "Error: Browser not started. Call start_browser() first."

        levels = ["postgraduate", "undergraduate"]
        last_err = None
        for lvl in levels:
            url = f"{self.base_url}/{lvl}/courses/{year}/{course_code}"
            try:
                self._page.goto(url, wait_until="networkidle")
                self._page.wait_for_selector("h1", timeout=10000)
                self.current_url = url
                return f"Successfully loaded course: {self._page.title()}\nURL: {url}"
            except Exception as e:
                last_err = e

        # fallback to site search if direct URLs fail
        return self.search_course_via_ui(course_code, year)
    """ 
    def search_course_via_ui(self, course_code: str, year: str = "2026") -> str:
        if not self._page:
            return "Error: Browser not started. Call start_browser() first."

        # open any handbook page with the mini search (home is fine)
        self._page.goto(self.base_url, wait_until="domcontentloaded")

        # focus the mini search input and search
        box = self._page.locator('input#mini-search-input, input[title*="Search by code"]')
        box.wait_for(timeout=10000)
        box.fill(course_code)
        self._page.keyboard.press("Enter")

        # wait for results dropdown/list to render
        self._page.wait_for_timeout(800)  # small pause for suggestions
        # click the exact course link for the requested year if present; otherwise first match
        target = self._page.locator(
            f'a[href*="/courses/{year}/{course_code}"]'
        )
        if not target.count():
            target = self._page.locator(f'a:has-text("{course_code}")').first
        target.click(timeout=10000)

        # verify page loaded
        self._page.wait_for_selector("h1", timeout=10000)
        self.current_url = self._page.url
        return f"Opened via search: {self._page.title()}\nURL: {self.current_url}"
    """  

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

    def extract_program_overview(self) -> str:
        """Extract program overview from current page.

        Returns:
            Program overview information
        """
        if not self._page:
            return "Error: No page loaded"

        try:
            result = []

            # Get title
            h1 = self._page.query_selector("h1")
            if h1:
                result.append(f"Program: {h1.inner_text()}\n")

            # Get program description/overview
            # Try different selectors for overview content
            overview_selectors = [
                ".program-overview",
                ".overview",
                "[class*='overview']",
                ".program-description",
                "main p"
            ]

            for selector in overview_selectors:
                elements = self._page.query_selector_all(selector)
                if elements:
                    for elem in elements[:3]:  # Limit to first 3
                        text = elem.inner_text().strip()
                        if text and len(text) > 30:
                            result.append(f"{text}\n")

            # Look for UoC in page text
            page_text = self._page.content()
            credit_match = re.search(r'(\d+)\s*(?:UoC|units of credit)', page_text, re.IGNORECASE)
            if credit_match:
                result.append(f"\nTotal Credits: {credit_match.group(1)} UoC\n")

            if not result:
                # Fallback: get first few paragraphs
                paragraphs = self._page.query_selector_all("p")
                for p in paragraphs[:5]:
                    text = p.inner_text().strip()
                    if len(text) > 50:
                        result.append(f"{text}\n")

            return "\n".join(result) if result else "No overview information found."

        except Exception as e:
            return f"Error extracting overview: {str(e)}"

    def extract_courses(self) -> str:
        """Extract all courses listed on current page.

        Returns:
            List of courses with codes and names
        """
        if not self._page:
            return "Error: No page loaded"

        try:
            courses = []

            # Get full page HTML
            page_content = self._page.content()

            # Pattern to match course codes (e.g., COMP9021, INFS1000)
            course_pattern = re.compile(r'\b([A-Z]{4}\d{4})\b')

            # Find all course codes
            course_codes = course_pattern.findall(page_content)

            # Remove duplicates while preserving order
            seen = set()
            unique_codes = []
            for code in course_codes:
                if code not in seen:
                    seen.add(code)
                    unique_codes.append(code)

            # Try to find course names
            for code in unique_codes[:50]:  # Limit to 50 courses
                # Look for text near the course code
                # Try to find link or nearby text
                selector = f"text={code}"
                try:
                    elem = self._page.query_selector(selector)
                    if elem:
                        # Get parent element to find course name
                        parent = elem.evaluate("el => el.parentElement")
                        if parent:
                            parent_text = elem.evaluate("el => el.parentElement.innerText")
                            # Extract course name (text after code)
                            name_match = re.search(rf'{code}\s*[-–]?\s*([^()\n]+)', parent_text)
                            if name_match:
                                course_name = name_match.group(1).strip()

                                # Look for UoC
                                uoc_match = re.search(r'(\d+)\s*UoC', parent_text)
                                uoc = uoc_match.group(1) if uoc_match else "?"

                                courses.append(f"{code} - {course_name} ({uoc} UoC)")
                            else:
                                courses.append(f"{code}")
                        else:
                            courses.append(f"{code}")
                except:
                    courses.append(f"{code}")

            if courses:
                return "\n".join(courses)
            else:
                return "No courses found. Try viewing the full page text with get_full_page_text()"

        except Exception as e:
            return f"Error extracting courses: {str(e)}"

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

            # Find sentences containing keyword
            lines = page_text.split('\n')
            matches = [line.strip() for line in lines if keyword.lower() in line.lower()]

            if matches:
                # Remove duplicates
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
            filename: Screenshot filename (default: "handbook_screenshot.png")

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


