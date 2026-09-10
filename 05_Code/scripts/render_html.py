#!/usr/bin/env python3
"""Render workflow.html to a crisp PNG + PDF using Playwright (bundled Chromium)."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HTML = (ROOT / "workflow.html").as_uri()
PNG = ROOT / "data/people/scaleflow_workflow.png"
PDF = ROOT / "data/people/scaleflow_workflow.pdf"


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 1200}, device_scale_factor=2)
        pg.goto(HTML)
        pg.wait_for_timeout(400)
        h = pg.evaluate("document.querySelector('.page').scrollHeight")
        w = pg.evaluate("document.querySelector('.page').scrollWidth")
        pg.set_viewport_size({"width": int(w), "height": int(h) + 20})
        pg.wait_for_timeout(200)
        pg.screenshot(path=str(PNG), full_page=True)
        pg.pdf(path=str(PDF), width=f"{int(w)}px", height=f"{int(h)+40}px",
               print_background=True, margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        b.close()
    print("wrote", PNG.name, "and", PDF.name)


if __name__ == "__main__":
    main()
