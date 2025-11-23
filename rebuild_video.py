import os
import glob

FRAME_DIR = "frames"

def main():
    """
    Finds all PNG frames, sorts them, and prints the list.
    """
    print("--- Python script starting: Finding frames ---")

    # Use glob to find all .png files in the frames directory
    files = glob.glob(os.path.join(FRAME_DIR, "*.png"))

    if not files:
        print("No frames found. Exiting.")
        return

    files.sort() # Sort the files alphabetically/chronologically

    for f in files:
        print(f"Found: {f}")

    print(f"--- Python script finished: Found {len(files)} frames ---")

if __name__ == "__main__":
    main()