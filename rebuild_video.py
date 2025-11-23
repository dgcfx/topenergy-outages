import os
import glob
import shutil
import subprocess

FRAME_DIR = "frames"
TEMP_DIR = "temp_frames"
CHUNK_FILENAME = "daily_chunk.mp4"
MASTER_FILENAME = "outages.mp4"

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

    # --- Process all available frames ---
    files_to_process = files
    print(f"\nProcessing {len(files_to_process)} files...")

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

    print(f"\n--- Stamping complete. Rendering video chunk: {CHUNK_FILENAME} ---")

    # --- Create video from stamped frames ---
    stamped_files = sorted(glob.glob(os.path.join(TEMP_DIR, "*.png")))
    concat_list_path = os.path.join(TEMP_DIR, "concat_list.txt")

    with open(concat_list_path, "w") as f:
        for sf in stamped_files:
            # The paths in the concat list must be relative to the concat file's location.
            filename = os.path.basename(sf)
            f.write(f"file '{filename}'\n")
            # For the concat demuxer, we must specify the duration of each image.
            # 1/8 fps = 0.125 seconds.
            f.write("duration 0.125\n")

    # Build the ffmpeg command to create the video chunk
    command = [
        "ffmpeg", "-y",
        # --- INPUT OPTIONS ---
        "-f", "concat",
        "-safe", "0",
        "-i", "concat_list.txt", # Now relative to the new working directory
        # --- OUTPUT OPTIONS ---
        # Dynamically crop the height to the nearest even number for x264 compatibility
        "-vf", "crop=iw:floor(in_h/2)*2", 
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "28", "-tune", "stillimage",
        f"../{CHUNK_FILENAME}" # The output path is now relative to the temp_frames dir
    ]

    try:
        # Run the command with the working directory set to TEMP_DIR
        subprocess.run(command, check=True, capture_output=True, text=True, cwd=TEMP_DIR)
        if not os.path.exists(CHUNK_FILENAME):
            raise RuntimeError(f"ffmpeg command ran but output file was not created: {CHUNK_FILENAME}")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: ffmpeg failed while creating video chunk.")
        print(f"  - Stderr: {e.stderr}")
        raise
    
    print(f"\n--- Stitching {CHUNK_FILENAME} to {MASTER_FILENAME} ---")

    # --- Stitch the new chunk to the master video ---
    temp_master = "temp_master.mp4"
    concat_list_path = "concat_list.txt"

    if os.path.exists(MASTER_FILENAME):
        print(f"Found existing master video. Preparing to append.")
        with open(concat_list_path, "w") as f:
            f.write(f"file '{MASTER_FILENAME}'\n")
            f.write(f"file '{CHUNK_FILENAME}'\n")
        
        command = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list_path,
            "-c", "copy", temp_master
        ]
    else:
        print(f"No master video found. The new chunk will become the master.")
        shutil.move(CHUNK_FILENAME, temp_master)
        command = None # No command to run

    if command:
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"ERROR: ffmpeg failed while stitching videos.")
            print(f"  - Stderr: {e.stderr}")
            raise

    # --- Verify the new master video and perform cleanup ---
    print("\n--- Verifying and cleaning up ---")
    try:
        subprocess.run(["ffprobe", "-v", "error", temp_master], check=True)
        print("SUCCESS: New master video is valid.")
        shutil.move(temp_master, MASTER_FILENAME)
        print(f"Updated {MASTER_FILENAME}.")

        # On success, clean up everything
        shutil.rmtree(TEMP_DIR)
        if os.path.exists(CHUNK_FILENAME): os.remove(CHUNK_FILENAME)
        if os.path.exists(concat_list_path): os.remove(concat_list_path)
        for f in files_to_process: # Delete the original source frames
            os.remove(f)
        print("Cleaned up temporary files and original frames.")

    except (subprocess.CalledProcessError, FileNotFoundError):
        print("CRITICAL FAILURE: New master video is corrupt. Aborting to protect old video and frames.")
        raise

    print(f"\n--- Python script finished successfully. ---")

if __name__ == "__main__":
    main()