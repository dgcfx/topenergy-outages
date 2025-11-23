import os
import glob
import shutil
import subprocess

FRAME_DIR = "frames"
TEMP_DIR = "temp_frames"

def main():
    """
    Finds PNG frames, stamps a timestamp on the first 5,
    and saves them to a temporary directory.
    """
    print("--- Python script starting: Finding frames ---")

    # Use glob to find all .png files in the frames directory
    files = glob.glob(os.path.join(FRAME_DIR, "*.png"))

    if not files:
        print("No new frames found. Exiting.")
        return

    files.sort() # Sort the files alphabetically/chronologically

    # --- Create a clean temporary directory ---
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR)
    print(f"Created temporary directory: {TEMP_DIR}")

    # --- Process only the first 5 files for a quick test ---
    files_to_process = files[:5]
    print(f"\nProcessing {len(files_to_process)} files for this test run...")

    for input_path in files_to_process:
        filename = os.path.basename(input_path)
        raw_ts = os.path.splitext(filename)[0]
        output_path = os.path.join(TEMP_DIR, filename)

        # Create readable timestamp (e.g., 2025-11-21T06:45:40Z)
        timestamp = raw_ts.replace("-", ":", 2).replace("T", "T", 1)

        # Write timestamp to a temporary file to avoid shell escaping issues
        timestamp_file_path = os.path.join(TEMP_DIR, f"{raw_ts}.txt")
        with open(timestamp_file_path, "w") as f:
            f.write(timestamp)

        print(f"  - Stamping {filename}...")

        # Build the ffmpeg command as a list of arguments
        command = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf:textfile={timestamp_file_path}:fontcolor=white:fontsize=24:box=1:boxcolor=black@0.5:boxborderw=5:x=15:y=15",
            "-frames:v", "1",
            output_path
        ]

        # Run the command and verify
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
            if not os.path.exists(output_path):
                raise RuntimeError(f"ffmpeg command ran but output file was not created: {output_path}")
        except subprocess.CalledProcessError as e:
            print(f"ERROR: ffmpeg failed for {filename}.")
            print(f"  - Stderr: {e.stderr}")
            raise # Stop the script if any command fails

    print(f"\n--- Python script finished: Stamped {len(files_to_process)} frames into {TEMP_DIR}/ ---")

if __name__ == "__main__":
    main()