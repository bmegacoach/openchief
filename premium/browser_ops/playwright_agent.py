"""
Playwright Browser Agent — Premium Module
Feature flag: ENABLE_BROWSER_OPS=true
Headless browser automation for web research and scraping.
"""
import os
from event_logging.event_logger import EventLogger

ENABLED = os.getenv("ENABLE_BROWSER_OPS", "false").lower() == "true"

logger = EventLogger()


class PlaywrightAgent:
    """Headless browser automation using Playwright."""

    def __init__(self):
        self.enabled = ENABLED
        self._browser = None
        self._playwright = None

    def is_configured(self) -> bool:
        return self.enabled

    async def start(self):
        if not self.enabled:
            return
        try:
            from playwright.async_api import async_playwright  # type: ignore
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
            logger.log_event("browser_started", {})
        except ImportError:
            logger.log_event("browser_error", {"error": "playwright not installed"})
        except Exception as exc:
            logger.log_event("browser_error", {"error": str(exc)})

    async def stop(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.log_event("browser_stopped", {})

    async def fetch_page(self, url: str) -> dict:
        """Fetch a page and return its text content."""
        if not self.enabled or self._browser is None:
            return {"status": "unconfigured", "content": None}
        try:
            page = await self._browser.new_page()
            await page.goto(url, timeout=15000)
            content = await page.inner_text("body")
            await page.close()
            logger.log_event("page_fetched", {"url": url, "chars": len(content)})
            return {"status": "ok", "url": url, "content": content}
        except Exception as exc:
            logger.log_event("browser_error", {"url": url, "error": str(exc)})
            return {"status": "error", "error": str(exc)}

    async def screenshot(self, url: str, path: str = "screenshot.png") -> dict:
        """Take a screenshot of a URL."""
        if not self.enabled or self._browser is None:
            return {"status": "unconfigured"}
        try:
            page = await self._browser.new_page()
            await page.goto(url, timeout=15000)
            await page.screenshot(path=path, full_page=True)
            await page.close()
            logger.log_event("screenshot_taken", {"url": url, "path": path})
            return {"status": "ok", "path": path}
        except Exception as exc:
            logger.log_event("browser_error", {"error": str(exc)})
            return {"status": "error", "error": str(exc)}
