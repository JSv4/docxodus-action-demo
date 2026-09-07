"""Smoke-test the generated site, navigation, images, and narrow-screen layout."""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory="_site"))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            options = {"headless": True}
            if os.environ.get("CHROME_PATH"):
                options["executable_path"] = os.environ["CHROME_PATH"]
            browser = playwright.chromium.launch(**options)
            page = browser.new_page(viewport={"width": 1400, "height": 1100})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}/")
            assert page.locator(".card").count() > 0
            page.wait_for_function("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)")
            page.screenshot(path="/tmp/docxodus-preview-landing.png", full_page=True)
            page.get_by_role("link", name="View full redline", exact=False).first.click()
            page.wait_for_function("document.getElementById('position').textContent.includes('of')")
            assert "1 of" in page.locator("#position").inner_text()
            assert page.locator("#previous").is_disabled()
            page.locator("#next").click()
            assert "2 of" in page.locator("#position").inner_text()
            assert page.locator("#document").evaluate("f => f.contentDocument.querySelectorAll('ins').length") > 0
            assert page.locator("#document").evaluate("f => f.contentWindow.scrollY") > 0
            # Empty spans/anchors must not absorb prose when the browser parses HTML.
            distribution = page.frame_locator("#document").locator("p").filter(has_text="Distribution of Remaining Assets").first
            if distribution.count():
                assert distribution.evaluate("e => e.querySelector('span').textContent.trim()") == '2.2'
                assert distribution.evaluate("e => e.children.length") > 10
                assert distribution.evaluate("e => e.getBoundingClientRect().height") < 400
                distribution.screenshot(path="/tmp/docxodus-distribution-fixed.png")
                page.locator("#changes").select_option("review-change-2")
            page.screenshot(path="/tmp/docxodus-preview-viewer.png", full_page=True)
            page.reload()
            page.wait_for_function("document.getElementById('position').textContent.includes('2 of')")
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_function("document.getElementById('document').contentDocument.getElementById('review-change-2').parentElement.getBoundingClientRect().top < 40")
            page.screenshot(path="/tmp/docxodus-preview-mobile.png", full_page=True)
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Mobile overflow"
            assert not errors, errors
            browser.close()
        for comment in json.loads(Path("_preview_comments.json").read_text()):
            assert len(comment["body"]) < 65536, "PR comment exceeds GitHub limit"
            assert "<ins>" in comment["body"] and "<del>" in comment["body"]
            assert "preview-1-" in comment["body"]
            assert "with surrounding text" in comment["body"]
            assert "⤢ Expand excerpt 1 in full document" in comment["body"]
        print("Preview navigation, images, deep links, mobile layout, and inline comment checks passed")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
