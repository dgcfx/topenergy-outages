import os
import re
import shutil

BASE_DIRS = ["frames", "data/history"]
FILENAME_PATTERN = re.compile(r"(\d{4}-\d{2})-\d{2}T.*")

def migrate_files():
    """
    A one-time script to move existing files from the root of the data/frame
    directories into their correct YYYY-MM subdirectories.
    """
    print("--- Starting file migration ---")
    for base_dir in BASE_DIRS:
        if not os.path.exists(base_dir):
            print(f"Directory '{base_dir}' not found, skipping.")
            continue

        print(f"\nScanning '{base_dir}' for files to migrate...")
        migrated_count = 0
        
        for item_name in os.listdir(base_dir):
            item_path = os.path.join(base_dir, item_name)
            
            # We only care about files at the root, not items already in subdirectories
            if os.path.isfile(item_path):
                match = FILENAME_PATTERN.match(item_name)
                if match:
                    year_month = match.group(1) # e.g., "2025-11"
                    target_dir = os.path.join(base_dir, year_month)
                    os.makedirs(target_dir, exist_ok=True)
                    destination_path = os.path.join(target_dir, item_name)
                    
                    print(f"  - Moving '{item_path}' to '{destination_path}'")
                    shutil.move(item_path, destination_path)
                    migrated_count += 1
        
        print(f"Migrated {migrated_count} files in '{base_dir}'.")

    print("\n--- Migration complete ---")

if __name__ == "__main__":
    migrate_files()