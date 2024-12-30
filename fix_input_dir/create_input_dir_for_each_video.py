import os
import shutil
import argparse
import sys
import logging

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
    video_extensions = ['.mp4', '.mov', '.mkv', '.avi']
    _, ext = os.path.splitext(filename)
    return ext.lower() in video_extensions

def sanitize_directory_name(name):
    """
    Sanitize the directory name by removing or replacing characters
    that are problematic in file systems.
    """
    # Replace spaces with underscores
    sanitized = name.replace(' ', '_')
    # Keep only alphanumerics, underscores, hyphens, and dots
    sanitized = ''.join(c for c in sanitized if c.isalnum() or c in ('_', '-', '.'))
    # Remove trailing dots
    sanitized = sanitized.rstrip('.')
    return sanitized

def remove_trailing_dot(file_path):
    """
    Removes a trailing dot from the file name if present.
    """
    if file_path.endswith('.'):
        new_path = file_path.rstrip('.')
        os.rename(file_path, new_path)
        logging.info(f"Renamed '{file_path}' to '{new_path}'")
        print(f"Renamed '{file_path}' to '{new_path}'")
        return new_path
    return file_path

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
            # Check and remove trailing dot if present
            corrected_input_path = remove_trailing_dot(input_path)
            corrected_item = os.path.basename(corrected_input_path)
            
            # Get the video file name without extension for the directory name
            video_name, _ = os.path.splitext(corrected_item)
            
            # Sanitize directory name (remove trailing dots)
            sanitized_video_name = sanitize_directory_name(video_name)
            
            video_dir = os.path.join(output_dir, sanitized_video_name)
            
            # Create the directory for the video
            os.makedirs(video_dir, exist_ok=True)
            
            # Define the destination path for the video
            destination_path = os.path.join(video_dir, corrected_item)
            
            try:
                # Copy the video file to the destination directory
                shutil.copy2(corrected_input_path, destination_path)
                print(f"Copied '{corrected_item}' to '{video_dir}'")
                logging.info(f"Copied '{corrected_item}' to '{video_dir}'")
            except Exception as e:
                print(f"Failed to copy '{corrected_item}': {e}")
                logging.error(f"Failed to copy '{corrected_item}': {e}")

def main():
    # Configure logging
    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    args = parse_arguments()
    create_video_directories(args.input_dir, args.output_dir)

if __name__ == "__main__":
    main()