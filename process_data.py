import os
import glob
import json
import shutil

DATA_DIR = "data/history"
PUBLIC_DIR = "public"
OUTAGES_JSON = os.path.join(PUBLIC_DIR, "outages.json")

def get_last_processed_file():
    """Reads the state file and returns the last processed filename."""
    if not os.path.exists(OUTAGES_JSON):
        print("State file not found. Will process all history.")
        return None

    try:
        with open(OUTAGES_JSON, "r") as f:
            data = json.load(f)
        # The state data is now the top-level object
        last_file = data.get("lastProcessedFile")
        if last_file:
            # Return the full path for accurate comparison
            print(f"Last processed file was: {os.path.basename(last_file)}")
            return last_file
        else:
            print("No marker found in state file. Will process all history.")
            return None
    except (json.JSONDecodeError, FileNotFoundError):
        print("Could not read or parse state file. Will process all history.")
        return None

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
        
        timestamp = data.get("timestamp")
        outage_list = data.get("rawFrontendInitData", {}).get("outageList", {})
        active_outages = outage_list.get("active", [])
        
        current_active_ids = {outage['name'] for outage in active_outages}

        # Find newly started outages
        for outage in active_outages:
            outage_id = outage.get("name")
            if not outage_id:
                continue

            if outage_id not in events:
                print(f"  - New outage started: {outage_id} at {timestamp}")
                events[outage_id] = {
                    "id": outage_id,
                    "title": f"{outage.get('circuitName', 'Unknown')} ({outage.get('customersCurrentlyOff')} customers)",
                    "start": timestamp,
                    "end": None, # End time is unknown for now
                    "allDay": False,
                    "extendedProps": {
                        "type": outage.get("type"),
                        "customers": outage.get("customersCurrentlyOff"),
                        "circuit": outage.get("circuitName"),
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

    last_processed_file = get_last_processed_file()
    new_files = find_new_files(last_processed_file)

    if not new_files:
        print("No new data files to process. Exiting.")
        return

    print(f"Found {len(new_files)} new data files to process.")
    
    events = process_files(new_files, {}) # Start with empty data for now

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