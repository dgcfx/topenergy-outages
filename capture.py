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
        try:
            page = browser.new_page()
            print(f"Loading {URL}...")
            page.goto(URL, wait_until="networkidle")

            # Wait for the page's JS to define the data variable we need
            print("Waiting for frontendInitData to be available...")
            page.wait_for_function("() => typeof window.frontendInitData !== 'undefined'", timeout=20000)

            # Directly evaluate and get the object. Playwright handles the conversion to a Python dict.
            data = page.evaluate("() => window.frontendInitData")

            if not data:
                print("Warning: frontendInitData was empty or null.")
                data = {}

            # Save full JSON with timestamp
            ts = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%SZ")
            json_filename = f"{HISTORY_DIR}/{ts}.json"
            with open(json_filename, "w") as f:
                json.dump({
                    "timestamp": ts,
                    "customersCurrentlyOff": data.get("outageList", {}).get("customersCurrentlyOff", 0),
                    "rawFrontendInitData": data
                }, f, indent=2)
            print(f"Saved data to {json_filename}")

            # Screenshot just the map
            print("Taking screenshot...")
            map_element = page.locator("#map").first
            # Wait for the map to be visible before taking a screenshot
            map_element.wait_for(state="visible", timeout=10000)
            page.wait_for_timeout(2000) # Allow time for map tiles to render
            map_element.screenshot(path=f"{FRAME_DIR}/{ts}.png")
            map_element.screenshot(path="latest.jpg")
            print("Saved screenshots.")

        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()
