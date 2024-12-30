import os
import shutil
import argparse
import sys

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Create a directory for each video file inside the input directory."
    )

    parser.add_argument(
        '--input-dir',
        required=True,
        help='Path to the input directory containing video files.'
    )

    parser.add_argument(
        '--output-dir',
        required=True,
        help='Path to the output directory where individual video directories will be created.'
    )

    return parser.parse_args()

def is_video_file(filename):
    video_extensions = ['.mp4', '.mov', '.mkv' ]
    _, ext = os.path.splitext(filename)
    return ext.lower() in video_extensions

def create_video_directories(input_dir, output_dir):
    # Ensure input directory exists
    if not os.path.isdir(input_dir):
        print(f"Error: Input directory '{input_dir}' does not exist or is not a directory.")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Iterate over files in input directory
    for item in os.listdir(input_dir):
        input_path = os.path.join(input_dir, item)
        
        # Process only files (skip directories)
        if os.path.isfile(input_path) and is_video_file(item):
            # Get the video file name without extension for the directory name
            video_name, _ = os.path.splitext(item)
            
            # Sanitize directory name (optional: remove problematic characters)
            sanitized_video_name = sanitize_directory_name(video_name)
            
            video_dir = os.path.join(output_dir, sanitized_video_name)
            
            # Create the directory for the video
            os.makedirs(video_dir, exist_ok=True)
            
            # Define the destination path for the video
            destination_path = os.path.join(video_dir, item)
            
            try:
                # Copy the video file to the destination directory
                shutil.copy2(input_path, destination_path)
                print(f"Copied '{item}' to '{video_dir}'")
            except Exception as e:
                print(f"Failed to copy '{item}': {e}")

def sanitize_directory_name(name):
    """
    Sanitize the directory name by removing or replacing characters
    that are problematic in file systems.
    """
    # For simplicity, replace spaces with underscores and remove other problematic characters
    sanitized = name.replace(' ', '_')
    sanitized = ''.join(c for c in sanitized if c.isalnum() or c in ('_', '-', '.'))
    return sanitized

def main():
    args = parse_arguments()
    create_video_directories(args.input_dir, args.output_dir)

if __name__ == "__main__":
    main()