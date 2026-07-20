import re, logging
from playwright.sync_api import sync_playwright
logger = logging.getLogger(__name__)

class WeiboCrawler:
    def __init__(self, headless=True, cookie_str=""):
        self.headless = headless
        self.cookie_str = cookie_str
        self._pw = None
        self._browser = None

    def _ensure_browser(self):
        if not self._browser:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(channel="chrome", headless=self.headless)

    def search(self, keyword, max_count=10):
        self._ensure_browser()
        page = self._browser.new_page()
        results = []
        try:
            url = "https://s.weibo.com/weibo?q=" + keyword
            if self.cookie_str:
                cookies = []
                for item in self.cookie_str.split(";"):
                    item = item.strip()
                    if "=" in item:
                        k, v = item.split("=", 1)
                        cookies.append({"name": k.strip(), "value": v.strip(), "domain": ".weibo.com", "path": "/"})
                page.context.add_cookies(cookies)
            page.goto(url, timeout=30000, wait_until="networkidle")
            page.wait_for_timeout(2000)
            text = page.inner_text("body")
            pattern = rf".{0,80}" + re.escape(keyword) + r".{0,220}"
            matches = re.findall(pattern, text, flags=re.S)
            seen = set()
            for item in matches:
                content = item.replace("\n", " ").strip()
                if not content or content in seen: continue
                seen.add(content)
                results.append({"title": content[:100], "content": content[:300], "url": url, "source": "微博"})
                if len(results) >= max_count: break
        except Exception as e:
            logger.warning("Weibo search failed for kw=%s: %s", keyword, e)
        finally:
            page.close()
        return results

    def close(self):
        if self._browser: self._browser.close()
        if self._pw: self._pw.stop()