"""Post-merge public Streamlit Cloud verification; uses no account data."""
from __future__ import annotations

import os
from pathlib import Path
import time

from playwright.sync_api import sync_playwright

URL = os.getenv(
    "PHASE3_PUBLIC_URL",
    "https://market-intelligence-operations-console-7ejfn7tyabjcktlo7kdy22.streamlit.app",
)
RELEASE = "3A-COMMITTEE-DEVELOPMENT-2026-11-22"
OUT = Path(os.getenv("PHASE3_SCREENSHOT_DIR", "artifacts/phase3-cloud"))
OUT.mkdir(parents=True, exist_ok=True)


def verify(page, label):
    last_error = None
    # First production rebuild or wake-up may take longer than a normal page load.
    for attempt in range(4):
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
            page.get_by_text(RELEASE, exact=False).wait_for(state="visible", timeout=25_000)
            page.get_by_text("INVESTMENT DECISION COCKPIT", exact=False).wait_for(
                state="visible", timeout=25_000
            )
            page.get_by_text("Top 10 Multi-Asset Opportunities", exact=False).wait_for(
                state="visible", timeout=25_000
            )
            break
        except Exception as exc:
            last_error = exc
            print(f"{label} attempt {attempt + 1}: {type(exc).__name__}: {exc}", flush=True)
            try:
                title = page.title()
                body = page.locator("body").inner_text(timeout=5_000)
                print(f"{label} diagnostic: title={title!r}; body={body[:1000]!r}", flush=True)
                page.screenshot(path=str(OUT / f"{label}-failure-{attempt+1}.png"), full_page=True)
            except Exception as diagnostic_exc:
                print(f"{label} diagnostic unavailable: {type(diagnostic_exc).__name__}", flush=True)
            if attempt == 3:
                raise AssertionError(f"{label}: release marker or decision cockpit not verified") from last_error
            time.sleep(10)
    page.screenshot(path=str(OUT / f"{label}.png"), full_page=True)
    metrics = page.evaluate(
        "() => ({scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth})"
    )
    print(f"{label}: release and cockpit verified; viewport {metrics}", flush=True)
    if label == "mobile" and metrics["scrollWidth"] > metrics["innerWidth"] + 80:
        raise AssertionError("Mobile layout has excessive horizontal overflow")


def main():
    with sync_playwright() as browser_tool:
        browser = browser_tool.chromium.launch(headless=True)
        desktop = browser.new_page(viewport={"width": 1400, "height": 900})
        verify(desktop, "desktop")
        mobile = browser.new_page(viewport={"width": 390, "height": 844},
                                  device_scale_factor=3, is_mobile=True, has_touch=True)
        verify(mobile, "mobile")
        browser.close()


if __name__ == "__main__":
    main()
