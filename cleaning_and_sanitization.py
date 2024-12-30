
import sys
import logging
import os
import re
import pysrt

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

def normalize_phrase(phrase):
    """
    Normalize the phrase by removing punctuation and reducing whitespace.
    """
    # Remove punctuation
    phrase = re.sub(r'[^\w\s]', '', phrase)
    # Reduce multiple spaces to single space
    phrase = re.sub(r'\s+', ' ', phrase)
    return phrase.strip().lower()

def sanitize_srt_file(srt_file_path, max_repeats=5, additional_phrases=None):
    """
    Sanitize the .srt file by:
    1. Removing phrases that are repeated more than or equal to max_repeats times.
    2. Removing additional specified phrases even if they appear only once.
    
    Args:
        srt_file_path (str): Path to the .srt file to be sanitized.
        max_repeats (int): Maximum allowed repetitions for any phrase.
        additional_phrases (set of str): Phrases to remove regardless of repetition count.
    
    Returns:
        None
    """
    try:
        # Create a backup of the original .srt file
        #backup_path = f"{srt_file_path}.backup"
        #shutil.copyfile(srt_file_path, backup_path)
        #logging.info(f"Backup created at: {backup_path}")

        # Load the subtitle file
        subtitles = pysrt.open(srt_file_path, encoding='utf-8')

        # Create a dictionary to count phrase occurrences (normalized)
        phrase_counts = {}
        for subtitle in subtitles:
            phrase = normalize_phrase(subtitle.text)
            if phrase in phrase_counts:
                phrase_counts[phrase] += 1
            else:
                phrase_counts[phrase] = 1

        # Identify phrases to remove (those repeated more than or equal to max_repeats times)
        over_repeated_phrases = {phrase for phrase, count in phrase_counts.items() if count >= max_repeats}
        logging.info(f"Phrases to remove (repeated >= {max_repeats} times): {over_repeated_phrases}")

        # Initialize additional_phrases if not provided
        if additional_phrases is None:
            additional_phrases = set()

        # Normalize and add additional phrases to remove
        normalized_additional_phrases = {normalize_phrase(phrase) for phrase in additional_phrases}
        logging.info(f"Additional phrases to remove: {normalized_additional_phrases}")

        # Combine all phrases to remove
        phrases_to_remove = over_repeated_phrases.union(normalized_additional_phrases)
        logging.info(f"Total phrases to remove: {phrases_to_remove}")

        # Remove subtitle entries containing the phrases to remove by modifying in-place
        subtitles[:] = [
            subtitle for subtitle in subtitles 
            if normalize_phrase(subtitle.text) not in phrases_to_remove
        ]

        # Clean the indexes to ensure sequential numbering
        subtitles.clean_indexes()

        # Save the cleaned subtitles back to the file
        subtitles.save(srt_file_path, encoding='utf-8')
        logging.info(f"Sanitized .srt file saved at: {srt_file_path}")

    except Exception as e:
        logging.error(f"Failed to sanitize .srt file {srt_file_path}: {e}")


def cleanup_output_dir(video_output_dir):
    """
    Remove all files in video_output_dir except those ending with .srt.
    Rename .srt files to <video_dir>_subtitles.srt.
    Sanitize the .srt file by removing over-repeated phrases.

    Args:
        video_output_dir (str): Path to the directory to clean up.
    """
    # Get the base name of the directory (e.g., 'PN结及其单向导电性')
    video_dir_name = os.path.basename(video_output_dir)
    
    # Define additional phrases to remove
    additional_phrases_to_remove = {
        "If the audio file contain only music or some section contain music then ignore music and non vocals."
        "The audio file must only contain english language and non vocals."
        "If the audio file contain only music or some section contain non vocals then ignore music and non vocals."
        "If the audio file contain only music and non vocals then ignore music and non vocals."
        "This is the audio file."
        "Does the video made by Jason Blazer reference in bildamic on davinci 3200?"
        "the files are not shown in davinci due to security reason."
        "The files share dictations"
        "If the audio file contain only music or some section contain music and non vocals then ignore music and non vocals."
        "Leave it in the menu Preview option."
        "The audio file must contain only music and non vocals."
        "If the audio file contain only music and non vocals then ignore music and non vocals."
        "If the audio file contain only music or some section contain music and non vocals then ignore music and non vocals."
        "I displayed that the audio file in SIREN use English speaking ASL and not a mixed language."
        "Don't forget to comment your opinion."
        "Because it not need it."
        "Hope this ..."
    }

    # Flag to check if a subtitle file has been renamed to prevent multiple renames
    subtitle_renamed = False

    for filename in os.listdir(video_output_dir):
        file_path = os.path.join(video_output_dir, filename)

        # Check if it's a file
        if os.path.isfile(file_path):
            # If the file is not an .srt file, remove it
            if not filename.lower().endswith('.srt'):
                try:
                    os.remove(file_path)
                    logging.info(f"Removed file: {file_path}")
                except Exception as e:
                    logging.error(f"Failed to remove file {file_path}: {e}")
            else:
                # If the file is an .srt file, rename it to <video_dir>_subtitles.srt
                if not subtitle_renamed:
                    new_filename = f"{video_dir_name}_subtitles.srt"
                    new_file_path = os.path.join(video_output_dir, new_filename)

                    # Check if the desired .srt file name already exists to avoid overwriting
                    if os.path.exists(new_file_path):
                        logging.warning(f"Subtitle file {new_file_path} already exists. Skipping rename.")
                    else:
                        try:
                            os.rename(file_path, new_file_path)
                            logging.info(f"Renamed {file_path} to {new_file_path}")
                            subtitle_renamed = True  # Prevent further renames

                            # Sanitize the renamed .srt file with additional phrases
                            sanitize_srt_file(new_file_path, max_repeats=5, additional_phrases=additional_phrases_to_remove)

                        except Exception as e:
                            logging.error(f"Failed to rename {file_path} to {new_file_path}: {e}")
                else:
                    # If a subtitle file has already been renamed, remove any additional .srt files
                    try:
                        os.remove(file_path)
                        logging.info(f"Removed additional subtitle file: {file_path}")
                    except Exception as e:
                        logging.error(f"Failed to remove additional subtitle file {file_path}: {e}")
