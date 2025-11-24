import os
import glob
import json
import shutil
import requests

DATA_DIR = "data/history"
PUBLIC_DIR = "public"
OUTAGES_JSON = os.path.join(PUBLIC_DIR, "outages.json")

def get_last_processed_file():
    """Reads the state file and returns the last processed filename."""
    if not os.path.exists(OUTAGES_JSON):
        print("State file not found. Will process all history.")
        return None, {} # Return no file and no existing data

    try:
        with open(OUTAGES_JSON, "r") as f:
            data = json.load(f)
        # The state data is now the top-level object
        last_file = data.get("lastProcessedFile")
        if last_file and "events" in data:
            # Return the full path for accurate comparison
            print(f"Last processed file was: {os.path.basename(last_file)}")
            # Convert list of events back to a dictionary keyed by ID for processing
            events_dict = {event['id']: event for event in data['events']}
            return last_file, {"events": events_dict}
        else:
            print("No marker found in state file. Will process all history.")
            return None, {}
    except (json.JSONDecodeError, FileNotFoundError):
        print("Could not read or parse state file. Will process all history.")
        return None, {}

def find_new_files(last_processed_file):
    """Finds all data files newer than the last processed one."""
    all_files = sorted(glob.glob(os.path.join(DATA_DIR, "**", "*.json"), recursive=True))
    
    if not last_processed_file:
        return all_files

    # Find the index of the last processed file and return the slice of files after it
    # This is efficient because the list is sorted chronologically by filename
    for i, f in enumerate(all_files):
        if f.replace("\\", "/") == last_processed_file.replace("\\", "/"):
            return all_files[i+1:]

    # If the last processed file was not found (maybe deleted?), re-process everything
    print("Warning: Last processed file not found in history. Re-processing all files.")
    return all_files

def format_event_body(outage, details):
    """Creates the formatted body text for the calendar event."""
    if not details:
        # If no details were captured, create a simpler body
        return f"**Outage ID:** {outage.get('name', 'N/A')}\n**Customers Affected:** {outage.get('customersCurrentlyOff', 'N/A')}"

    # Replace commas in streets with newlines for readability
    affected_roads = details.get("streets", {}).get("showStreets", "N/A").replace(", ", "\n")

    body_parts = [
        f"**Outage ID:** {outage.get('name', 'N/A')}",
        f"**Status:** {details.get('status', 'N/A')}",
        f"**Feeder / Circuit:** {details.get('feeder', 'N/A')}",
        f"**Cause:** {details.get('cause', 'N/A')}",
        f"**Customers Affected:** {details.get('customersAffected', 'N/A')}",
        f"**Suburbs:** {details.get('suburbs', 'N/A')}",
        "---",
        "**Affected Roads:**",
        affected_roads,
        "---",
        f"**Estimated Time Frame:** {outage.get('startDateTime', 'N/A')} to {outage.get('endDateTime', 'N/A')}",
        f"**Last Updated:** {details.get('lastUpdateTime', 'N/A')}"
    ]

    return "\n".join(body_parts)

def get_all_outages_from_file(data):
    """Extracts both active and planned outages from a raw data file."""
    outage_list = data.get("rawFrontendInitData", {}).get("outageList", {})
    active = outage_list.get("active", [])
    planned = outage_list.get("planned", [])
    return active + planned

def process_files(new_files, existing_data):
    """
    Processes new data files to identify and update outage events.
    Returns a dictionary of all events.
    """
    events = existing_data.get("events", {})
    
    # Track which outage IDs were active in the previous file processed
    # This helps us determine when an outage has ended.
    previously_active_ids = set(events.keys())

    for file_path in new_files:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Get the timestamp and ensure it's in the correct ISO 8601 format
        # This handles historical data that used hyphens in the time part.
        timestamp_str = data.get("timestamp", "")
        # A valid timestamp like "2025-11-22T10:00:00Z" will be unaffected.
        # An invalid one like "2025-11-22T10-00-00Z" will be corrected.
        timestamp = timestamp_str[:10] + timestamp_str[10:].replace('-', ':')
        all_current_outages = get_all_outages_from_file(data)
        
        current_active_ids = {outage['name'] for outage in all_current_outages if outage.get('isActive')}

        # Find newly started outages
        for outage in all_current_outages:
            outage_id = outage.get("name")
            if not outage_id:
                continue

            if outage_id not in events:
                print(f"  - New outage started: {outage_id} at {timestamp}")
                
                # Fetch detailed data for the new outage
                details = get_outage_details(outage_id)
                
                events[outage_id] = {
                    "id": outage_id,
                    "title": f"{outage.get('circuitName', 'Unknown')} ({outage.get('customersCurrentlyOff')} customers)",
                    "start": timestamp,
                    "end": None, # End time is unknown for now
                    "allDay": False, # Keep original field name for now
                    "extendedProps": { # Keep original field name for now
                        "type": outage.get("type"),
                        "customers": outage.get("customersCurrentlyOff"),
                        "circuit": outage.get("circuitName"),
                        "body": format_event_body(outage, details) # Add the detailed body here
                    }
                }

        # Find finished outages (were active before, but are not now)
        finished_outages = previously_active_ids - current_active_ids
        for outage_id in finished_outages:
            if outage_id in events and events[outage_id]["end"] is None:
                print(f"  - Outage finished: {outage_id} at {timestamp}")
                events[outage_id]["end"] = timestamp

        previously_active_ids = current_active_ids

    return events

def main():
    print("\n--- Starting data processing ---")
    os.makedirs(PUBLIC_DIR, exist_ok=True)

    last_processed_file, existing_data = get_last_processed_file()
    new_files = find_new_files(last_processed_file)

    if not new_files:
        print("No new data files to process. Exiting.")
        return

    print(f"Found {len(new_files)} new data files to process.")

    events = process_files(new_files, existing_data)

    # Prepare the final JSON structure
    output_data = {
        "lastProcessedFile": new_files[-1].replace("\\", "/"),
        "events": list(events.values())
    }

    with open(OUTAGES_JSON, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\nSuccessfully processed data and created {OUTAGES_JSON}")

if __name__ == "__main__":
    main()