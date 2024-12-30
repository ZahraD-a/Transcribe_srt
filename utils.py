
import sys
import logging
import os
from datetime import datetime, timedelta
import re

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        # Uncomment the following line to also log to a file
        # logging.FileHandler("transcription.log")
    ]
)
logger = logging.getLogger(__name__)

def convert_to_srt(transcription_response):
    """
    Convert the transcription response into SRT format.
    """
    # Access segments directly as an attribute
    segments = transcription_response.segments if hasattr(transcription_response, 'segments') else []
    
    if not segments:
        logging.warning("No transcription segments found.")
        return ""

    srt_output = []
    index = 1

    for segment in segments:
        try:
            # Access segment attributes directly
            start_time = segment.start if hasattr(segment, 'start') else None
            end_time = segment.end if hasattr(segment, 'end') else None
            text = segment.text.strip() if hasattr(segment, 'text') else ''

            if start_time is None or end_time is None or not text:
                logging.warning(f"Skipping incomplete segment: {segment}")
                continue

            # Format the start and end times in SRT format (HH:MM:SS,MS)
            start_str = format_time(start_time)
            end_str = format_time(end_time)

            srt_output.append(f"{index}")
            srt_output.append(f"{start_str} --> {end_str}")
            srt_output.append(text)
            srt_output.append("")  # Blank line to separate subtitles

            index += 1
        except Exception as e:
            logging.error(f"Error processing segment {segment}: {e}")
            continue

    return "\n".join(srt_output)


def format_time(seconds):
    """
    Convert seconds to SRT time format: HH:MM:SS,MS
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:02}"

def save_srt_file(srt_content, output_path):
    """
    Save the SRT content to the specified output file.
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as srt_file:
            srt_file.write(srt_content)
        logging.info(f"SRT file saved: {output_path}")
    except Exception as e:
        logging.error(f"Error saving SRT file: {e}")

# Helper function to parse SRT timestamp
def parse_srt_timestamp(timestamp: str) -> timedelta:
    return datetime.strptime(timestamp, "%H:%M:%S,%f") - datetime(1900, 1, 1)

# Helper function to format timedelta to SRT timestamp format
def format_srt_timestamp(td: timedelta) -> str:
    total_seconds = int(td.total_seconds())
    milliseconds = int((td.total_seconds() - total_seconds) * 1000)
    formatted_time = str(timedelta(seconds=total_seconds))
    if '.' in formatted_time:
        formatted_time = formatted_time.split('.')[0]
    # Ensure hours are zero-padded to 2 digits
    if len(formatted_time.split(':')[0]) < 2:
        formatted_time = f"0{formatted_time}"
    return f"{formatted_time},{milliseconds:03d}"

# Estimate audio length based on word count (words per minute average 150)
def estimate_audio_length(word_count: int, wpm=50) -> timedelta:
    audio_length_minutes = word_count / wpm
    return timedelta(minutes=audio_length_minutes)

# Function to fix the start time of the first subtitle based on the audio length estimate
def fix_first_segment_start_time(srt_file_path):
    """
    Adjust the start time of the first subtitle segment based on an estimated audio length.
    """
    try:
        with open(srt_file_path, 'r', encoding='utf-8') as file:
            srt_content = file.read()

        # Split the SRT content into blocks for each subtitle
        srt_blocks = srt_content.strip().split('\n\n')

        if not srt_blocks:
            logging.warning(f"No subtitle blocks found in {srt_file_path}.")
            return

        # Get the first subtitle block (index 0)
        first_segment = srt_blocks[0]
        
        # Extract the timestamp and content from the first segment
        match = re.match(r'(\d+)\n([\d:,]+) --> ([\d:,]+)\n(.+)', first_segment, re.DOTALL)
        if match:
            segment_number = match.group(1)
            start_time = match.group(2)
            end_time = match.group(3)
            text = match.group(4)

            # Count the words in the segment text (naive word count)
            word_count = len(text.split())
            
            # Estimate the audio length for the segment
            estimated_audio_length = estimate_audio_length(word_count)

            # Calculate the correct start time for the first segment
            end_time_obj = parse_srt_timestamp(end_time)
            correct_start_time = end_time_obj - estimated_audio_length

            # Format the new start time
            corrected_start_time = format_srt_timestamp(correct_start_time)

            # Replace the start time in the first segment
            updated_first_segment = first_segment.replace(start_time, corrected_start_time, 1)
            
            # Reconstruct the entire SRT content with the updated first segment
            updated_srt_content = updated_first_segment + '\n\n' + '\n\n'.join(srt_blocks[1:])

            # Write the updated content back to the SRT file
            with open(srt_file_path, 'w', encoding='utf-8') as file:
                file.write(updated_srt_content)

            logging.info(f"First segment start time corrected to: {corrected_start_time}")
        else:
            logging.error(f"Failed to parse SRT content in {srt_file_path}.")
    except Exception as e:
        logging.error(f"Error in fix_first_segment_start_time: {e}")