import os
import json
import re
from datetime import datetime
from playwright.sync_api import sync_playwright
import requests

URL = "https://outages.topenergy.co.nz"
FRAME_DIR = "frames"
HISTORY_DIR = "data/history"

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

            # Get current year and month for directory structure
            now = datetime.utcnow()
            year_month = now.strftime("%Y-%m")
            
            # Define monthly subdirectories
            monthly_frame_dir = os.path.join(FRAME_DIR, year_month)
            monthly_history_dir = os.path.join(HISTORY_DIR, year_month)
            os.makedirs(monthly_frame_dir, exist_ok=True)
            os.makedirs(monthly_history_dir, exist_ok=True)

            # --- NEW: Fetch detailed data for active outages ---
            detailed_outage_info = {}
            active_outages = data.get("outageList", {}).get("active", [])
            if active_outages:
                print(f"Found {len(active_outages)} active outage(s). Fetching details...")
                for outage in active_outages:
                    outage_id = outage.get("name")
                    if outage_id:
                        try:
                            detail_url = f"{URL}/api/outage/{outage_id}/info"
                            response = requests.get(detail_url, timeout=10)
                            response.raise_for_status()
                            detailed_outage_info[outage_id] = response.json()
                            print(f"  - Successfully fetched details for {outage_id}")
                        except requests.exceptions.RequestException as e:
                            print(f"  - Warning: Could not fetch details for {outage_id}. Error: {e}")

            # Save full JSON with timestamp
            # Create two separate timestamp formats
            filename_ts = now.strftime("%Y-%m-%dT%H-%M-%SZ") # For Windows-safe filenames
            json_ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")     # For valid ISO 8601 timestamps

            json_filename = os.path.join(monthly_history_dir, f"{filename_ts}.json")
            with open(json_filename, "w") as f:
                json.dump({
                    "timestamp": json_ts, # Use the correct format inside the JSON
                    "rawFrontendInitData": data,
                    "detailedOutageInfo": detailed_outage_info # Embed the new detailed data
                }, f, indent=2)
            print(f"Saved data to {json_filename}")

            # Screenshot just the map
            print("Taking screenshot...")
            map_element = page.locator("#map").first
            map_element.wait_for(state="visible", timeout=10000)
            page.wait_for_timeout(2000) # Allow time for map tiles to render
            map_element.screenshot(path=os.path.join(monthly_frame_dir, f"{filename_ts}.png"))
            map_element.screenshot(path="latest.jpg")
            print("Saved screenshots.")

        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    main()
