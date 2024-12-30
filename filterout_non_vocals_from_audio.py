
import torch
import sys
import logging
import os
import subprocess
import demucs.separate
import shutil

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



# Validate if CUDA is available
def validate_device(device):
    """
    Check if CUDA is available and return the appropriate device.
    """
    if device.lower() == 'gpu':
        if torch.cuda.is_available():
            logging.info("CUDA is available. Using GPU.")
            return 'cuda'
        else:
            logging.warning("CUDA is not available. Falling back to CPU.")
            return 'cpu'
    return 'cpu'


# Separate Audio Function (Ensure this is defined before process_video)
def separate_audio(input_audio_path, video_dir, device):
    """
    Use Demucs to separate the audio and extract both the vocal and non-vocal tracks.
    """
    
    if device == 'cuda':
        logging.info("Using GPU for audio separation.")
    else:
        logging.info("Using CPU for audio separation.")
        
    try:
        # Run Demucs for audio separation, explicitly specifying output directory
        print(f"Running Demucs separation on: {input_audio_path} with device: {device}")
        demucs.separate.main([
            '-n', 'htdemucs',
            '--two-stems=vocals',
            '--out', video_dir,
            '--device', device,
            input_audio_path
        ])  # Separate into vocals and no_vocals
        
        # Assuming the output directory structure; adjust as per actual Demucs output
        separated_dir = os.path.join(video_dir, 'htdemucs', f'{os.path.splitext(os.path.basename(input_audio_path))[0]}')
        logging.info(f"Demucs output directory: {separated_dir}")

        # Find the 'vocals.wav' and 'no_vocals.wav' files from Demucs output
        vocals_path = os.path.join(separated_dir, 'vocals.wav')
        non_vocals_path = os.path.join(separated_dir, 'no_vocals.wav')

        if os.path.exists(vocals_path) and os.path.exists(non_vocals_path):
            logging.info(f"Found vocals.wav at: {vocals_path} and no_vocals.wav at: {non_vocals_path}")

            # Construct the new names with the original file name and suffixes
            base_name = os.path.splitext(os.path.basename(input_audio_path))[0]
            new_vocals_path = os.path.join(video_dir, f'{base_name}_vocals.wav')
            new_non_vocals_path = os.path.join(video_dir, f'{base_name}_non_vocals.wav')

            # Move both files to the desired locations
            shutil.move(vocals_path, new_vocals_path)
            shutil.move(non_vocals_path, new_non_vocals_path)
            logging.info(f"Moved vocals.wav to: {new_vocals_path} and no_vocals.wav to: {new_non_vocals_path}")
            
            # Process the vocals.wav to convert it to mono and reduce bitrate
            processed_vocals_path = os.path.join(video_dir, f'{base_name}_vocals_processed')
            logging.info(f"Processing vocals to mono and reducing bitrate: {processed_vocals_path}")
            # ffmpeg_command = f"ffmpeg -y -i \"{new_vocals_path}\" -ac 1 -ar 16000 -b:a 48k \"{processed_vocals_path}\""
            # ffmpeg_command = f"ffmpeg -y -i \"{new_vocals_path}\" -c:a libmp3lame -ac 1 -ar 16000 -b:a 64k \"{processed_vocals_path}.mp3\""
            
            # ffmpeg_command = f"ffmpeg -y -i \"{new_vocals_path}\" -map 0:a -c:a libmp3lame -ac 1 -ar 16000 -b:a 64k -map_metadata -1 \"{processed_vocals_path}.mp3\""
            
            ffmpeg_command = f"""
            ffmpeg -y -i "{new_vocals_path}" \
                -map 0:a -vn -sn -dn \
                -c:a libmp3lame \
                -ac 1 \
                -ar 16000 \
                -b:a 64k \
                -map_metadata -1 \
                "{processed_vocals_path}.mp3"
            """
            subprocess.run(ffmpeg_command, shell=True, check=True)
            logging.info(f"Processed vocals file saved at: {processed_vocals_path}")

            # Remove the htdemucs directory and everything underneath it
            shutil.rmtree(os.path.join(video_dir, 'htdemucs'))
            logging.info(f"Removed the htdemucs directory and its contents.")

            return processed_vocals_path, new_non_vocals_path
        else:
            logging.error(f"Error: No vocals.wav or no_vocals.wav found in the 'separated' directory.")
            return None, None

    except Exception as e:
        logging.error(f"Error processing with Demucs: {e}")
        return None, None