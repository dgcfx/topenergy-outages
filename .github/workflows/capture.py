import os
import json
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

URL = "https://outages.topenergy.co.nz"
FRAME_DIR = "frames"
HISTORY_DIR = "data/history"
os.makedirs(FRAME_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="networkidle")
        page.wait_for_timeout(8000)  # wait for map/polygons

        # Extract frontendInitData
        js = """() => {
            const script = Array.from(document.querySelectorAll('script')).find(s => s.textContent.includes('frontendInitData'));
            if (!script) return null;
            const match = script.textContent.match(/var frontendInitData = (.*});/s);
            return match ? match[1] + "}" : null;
        }"""
        raw_data = page.evaluate(js) or "{}"
        data = json.loads(raw_data)

        # Save full JSON with timestamp
        ts = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%SZ")
        with open(f"{HISTORY_DIR}/{ts}.json", "w") as f:
            json.dump({
                "timestamp": ts,
                "customersCurrentlyOff": data.get("outageList", {}).get("customersCurrentlyOff", 0),
                "rawFrontendInitData": data
            }, f, indent=2)

        # Screenshot just the map
        map_element = page.locator("#map").first
        map_element.screenshot(path=f"{FRAME_DIR}/{ts}.png")

        # Also save as latest.jpg for easy viewing
        map_element.screenshot(path="latest.jpg")

        browser.close()

if __name__ == "__main__":
    main()
