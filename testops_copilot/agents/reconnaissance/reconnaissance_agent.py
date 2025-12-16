
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError
from typing import Dict, Any, List
import json
import time
class ReconnaissanceAgent:
    def analyze_page(self, url: str, timeout: int = 90) -> Dict[str, Any]:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    context = browser.new_context(
                        viewport={"width": 1920, "height": 1080},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        ignore_https_errors=True
                    )
                    page = context.new_page()
                    # Используем load вместо networkidle для более быстрой загрузки
                    page.goto(url, wait_until="load", timeout=timeout * 1000)
                    page_structure = self._extract_page_structure(page, url)
                    browser.close()
                    return page_structure
            except PlaywrightTimeoutError:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                error_msg = f"Page load timeout after {max_retries} attempts for {url}"
                from shared.utils.logger import agent_logger
                agent_logger.error(f"Reconnaissance error: {error_msg}")
                # Возвращаем минимальную структуру вместо исключения, чтобы workflow мог продолжиться
                return {
                    "title": "Unknown",
                    "url": url,
                    "buttons": [],
                    "inputs": [],
                    "links": [],
                    "selectors": {},
                    "timestamp": time.time(),
                    "error": error_msg
                }
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                error_msg = f"Error analyzing page {url}: {str(e)}"
                from shared.utils.logger import agent_logger
                agent_logger.error(f"Reconnaissance error: {error_msg}", exc_info=True)
                # Возвращаем минимальную структуру вместо исключения
                return {
                    "title": "Unknown",
                    "url": url,
                    "buttons": [],
                    "inputs": [],
                    "links": [],
                    "selectors": {},
                    "timestamp": time.time(),
                    "error": error_msg
                }
    def _extract_page_structure(self, page: Page, url: str) -> Dict[str, Any]:
        title = page.title()
        buttons = page.evaluate("""
            () => {
                const buttons = Array.from(document.querySelectorAll('button, [role="button"], input[type="button"], input[type="submit"]'));
                return buttons.map(btn => ({
                    text: btn.textContent?.trim() || btn.value || '',
                    id: btn.id || '',
                    type: btn.type || 'button',
                    dataTestId: btn.getAttribute('data-testid') || ''
                }));
            }
        """)
        inputs = page.evaluate("""
            () => {
                const inputs = Array.from(document.querySelectorAll('input, textarea, select'));
                return inputs.map(input => ({
                    type: input.type || 'text',
                    id: input.id || '',
                    name: input.name || '',
                    placeholder: input.placeholder || '',
                    dataTestId: input.getAttribute('data-testid') || ''
                }));
            }
        """)
        links = page.evaluate("""
            () => {
                const links = Array.from(document.querySelectorAll('a[href]'));
                return links.map(link => ({
                    text: link.textContent?.trim() || '',
                    href: link.href || '',
                    id: link.id || '',
                    dataTestId: link.getAttribute('data-testid') || ''
                }));
            }
        """)
        selectors = self._generate_selectors(page)
        return {
            "title": title,
            "url": url,
            "buttons": buttons[:50],
            "inputs": inputs[:50],
            "links": links[:50],
            "selectors": selectors,
            "timestamp": time.time()
        }
    def _generate_selectors(self, page: Page) -> Dict[str, str]:
        selectors = {}
        testid_elements = page.evaluate("""
            () => {
                const elements = Array.from(document.querySelectorAll('[data-testid]'));
                const result = {};
                elements.forEach(el => {
                    const testId = el.getAttribute('data-testid');
                    if (testId) {
                        result[testId] = `[data-testid="${testId}"]`;
                    }
                });
                return result;
            }
        """)
        selectors.update(testid_elements)
        return selectors