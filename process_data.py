import os
import glob
import json

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
        last_file = data.get("metadata", {}).get("lastProcessedFile")
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
        if f.replace("\", "/") == last_processed_file.replace("\", "/"):
            return all_files[i+1:]

    # If the last processed file was not found (maybe deleted?), re-process everything
    print("Warning: Last processed file not found in history. Re-processing all files.")
    return all_files

def main():
    print("\n--- Starting data processing (Step 1: Find new files) ---")
    last_file = get_last_processed_file()
    new_files = find_new_files(last_file)
    print(f"Found {len(new_files)} new data files to process.")
    for f in new_files[:10]: # Print the first 10 new files as a sample
        print(f"  - {f}")

if __name__ == "__main__":
    main()