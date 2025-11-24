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

def format_full_history_body(event):
    """Creates the final, comprehensive body text from the detail history."""
    history = event.get("extendedProps", {}).get("detail_history", [])
    if not history:
        return f"**Outage ID:** {event.get('id', 'N/A')}"

    # Use the latest details for the main summary
    latest_entry = history[-1]
    latest_details = latest_entry.get("details", {})
    
    affected_roads = latest_details.get("streets", {}).get("showStreets", "N/A").replace(", ", "\n")

    body_parts = [
        f"**Outage ID:** {event.get('id', 'N/A')}",
        f"**Status:** {latest_details.get('status', 'N/A')}",
        f"**Feeder / Circuit:** {latest_details.get('feeder', 'N/A')}",
        f"**Cause:** {latest_details.get('cause', 'N/A')}",
        f"**Customers Affected:** {latest_details.get('customersAffected', 'N/A')}",
        f"**Suburbs:** {latest_details.get('suburbs', 'N/A')}",
        "---",
        "**Affected Roads:**",
        affected_roads,
        "---",
    ]

    if len(history) > 1:
        body_parts.append("**Update History:**")
        for entry in reversed(history):
            update_ts = entry.get('capture_ts', 'N/A')
            update_cause = entry.get('details', {}).get('cause', 'N/A')
            body_parts.append(f"- {update_ts}: {update_cause}")

    return "\n".join(body_parts)

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
        outage_list = data.get("rawFrontendInitData", {}).get("outageList", {})
        active_outages = outage_list.get("active", [])
        
        current_active_ids = {outage['name'] for outage in active_outages}

        # Find newly started outages
        for outage in active_outages:
            outage_id = outage.get("name")
            if not outage_id:
                continue

            # Always get the latest available details for the outage
            details = data.get("detailedOutageInfo", {}).get(outage_id)

            if outage_id not in events:
                print(f"  - New outage started: {outage_id} at {timestamp}")
                
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
                        "detail_history": [] # Initialize the history list
                    }
                }
            
            # --- New Logic: Append details to history if they are new ---
            if details:
                history = events[outage_id]["extendedProps"].get("detail_history", [])
                last_known_details = history[-1].get("details") if history else None

                if details != last_known_details:
                    print(f"  - Captured new/updated details for outage {outage_id} at {timestamp}")
                    history.append({
                        "capture_ts": timestamp,
                        "details": details
                    })
                    events[outage_id]["extendedProps"]["detail_history"] = history

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

    # --- New Step: Generate the final body text from the history for each event ---
    for event in events.values():
        event["extendedProps"]["body"] = format_full_history_body(event)

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