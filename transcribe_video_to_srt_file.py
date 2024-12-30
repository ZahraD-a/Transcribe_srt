import sys
import logging
import os
import argparse
import subprocess
import asyncio
import shutil
import time
from filterout_non_vocals_from_audio import validate_device, separate_audio
from cleaning_and_sanitization import cleanup_output_dir 
from azure_openai import load_api_credentials, create_client
from utils import convert_to_srt, format_time, save_srt_file,  fix_first_segment_start_time



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


# Define supported languages (expand as needed)
SUPPORTED_LANGUAGES = {
    "en": "English",
    # Add other supported languages here, e.g., "es": "Spanish"
}


# Check if the video has subtitles
def has_subtitles(video_path):
    """
    Check if the given video file contains subtitles.
    """
    try:
        probe = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 's', '-show_entries', 'stream=index', '-of', 'csv=p=0', video_path],
            capture_output=True, text=True
        )
        return bool(probe.stdout.strip())
    except subprocess.CalledProcessError:
        return False

# Function to extract subtitles from video
def detach_subtitles(input_video, output_subtitles):
    """
    Extract subtitles from the input video and save them to the specified output file.
    """
    try:
        if has_subtitles(input_video):
            subprocess.run(['ffmpeg', '-i', input_video, '-map', '0:s:0', '-c', 'copy', output_subtitles], check=True)
            logging.info(f"Subtitles extracted to {output_subtitles}")
        else:
            logging.info(f"No subtitles found in {input_video}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error during subtitle extraction: {e}")

def detach_audio(input_video, output_audio, output_video_no_audio):
    """
    Detach audio from the input video and save both the audio and the video without audio.
    """
    try:
        logging.info(f"Detaching audio from: {input_video}")
        
        # Detach and convert audio
        ffmpeg_audio_command = [
            'ffmpeg',
            '-y',  # Overwrite output files without asking
            '-i', input_video,
            '-vn',
            '-acodec', 'pcm_s16le',
            '-ar', '16000',
            '-ac', '1',
            output_audio
        ]
        logging.info(f"Extracting and converting audio with command: {' '.join(ffmpeg_audio_command)}")
        subprocess.run(ffmpeg_audio_command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logging.info(f"Audio detached and converted to {output_audio}")
        
        # Detach video without audio
        ffmpeg_video_command = [ 
            'ffmpeg',
            '-y',
            '-i', input_video,
            '-an',
            '-vcodec', 'copy',
            output_video_no_audio
        ]
        logging.info(f"Extracting video without audio with command: {' '.join(ffmpeg_video_command)}")
        subprocess.run(ffmpeg_video_command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logging.info(f"Video (without audio) saved to {output_video_no_audio}")
        
    except subprocess.CalledProcessError as e:
        logging.error(f"Error during audio detachment: {e.stderr.decode().strip()}")


# Asynchronous function to transcribe multiple audio files concurrently using Azure OpenAI
async def transcribe_audio(audio_paths, video_output_dir, 
                           speech_to_text, client, deployment_id):
    """
    Transcribe multiple audio files concurrently using Azure OpenAI.
    """
    # Define the maximum number of concurrent tasks
    MAX_CONCURRENT_TRANSACTIONS = 1
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TRANSACTIONS)
    
    async def sem_transcribe(audio_path):
        async with semaphore:
            return await transcribe_single_audio(audio_path, video_output_dir, speech_to_text, client, deployment_id)
    
    tasks = [sem_transcribe(audio_path) for audio_path in audio_paths]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle exceptions
    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            logging.error(f"Transcription task for {audio_paths[idx]} failed with exception: {result}")


# Asynchronous function to transcribe a single audio file using Azure OpenAI
async def transcribe_single_audio(audio_path, video_output_dir, 
                                  speech_to_text, client, deployment_id):
    """
    Transcribe a single audio file using Azure OpenAI and save the SRT file.
    """
    
    print("client and deployment from transcribe_single_audio: ", client, deployment_id)
    # Ensure the language is English as per user preference
    if speech_to_text != "en":
        logging.error("Currently, only English ('en') is supported for transcription.")
        return

    lang = "en"
    desired_target_lang = "english language"

    if os.path.exists(audio_path):
        start_time = time.time()
        logging.info(f"Starting processing for {audio_path} at {time.ctime(start_time)}")
        
        output_srt_file = os.path.join(video_output_dir, f"{os.path.basename(audio_path)}_{lang}.srt")
        
        try:
            # Run the transcription in a separate thread to avoid blocking the event loop
            loop = asyncio.get_running_loop()
            with open(audio_path, "rb") as audio_file:
                # Define the transcription function
                def run_transcription():
                    return client.audio.transcriptions.create(
                        file=audio_file,          
                        model=deployment_id,
                        language=lang,
                        prompt=f"use the provided audio file, and convert audio speech language into {desired_target_lang}. The output srt formatted file must only contain {desired_target_lang} and not a mix of languages. If the audio file contain only music or some section contain music then ignore music and non vocals.",
                        response_format="verbose_json",
                        timestamp_granularities=["segment"],
                    )
                
                # Execute the transcription function in a thread pool executor
                srt = await loop.run_in_executor(None, run_transcription)
            
            # Debugging: Print type and attributes of the transcription response
            logging.debug(f"Type of srt: {type(srt)}")
            logging.debug(f"srt attributes: {dir(srt)}")
            logging.debug(f"srt content: {srt}")
            
            if srt:
                logging.info("English transcription and alignment completed.")
                # Save English SRT
                srt_content_en = convert_to_srt(srt)
                intermediate_srt_path_en = output_srt_file
                save_srt_file(srt_content_en, intermediate_srt_path_en)
                fix_first_segment_start_time(intermediate_srt_path_en)
            else:
                logging.error(f"Failed to generate English SRT for {intermediate_srt_path_en}.")
        
        except Exception as e:
            logging.error(f"Error during transcription for {audio_path}: {e}")
        
        end_time = time.time()
        logging.info(f"Finished processing for {audio_path} at {time.ctime(end_time)}")
        logging.info(f"Time taken for ASR model: {end_time - start_time:.2f} seconds")
    else:
        logging.warning(f"Audio file '{audio_path}' not found. Skipping transcription.")


# Process each video
def process_video(video_dir, video_path, output_dir, detach_subtitles_flag, detach_audio_flag, speech_to_text, filter_two_stems, device=None,  video_base_name_for_subtitle_name=None, client=None, deployment_id=None):
    """
    Process a single video: detach subtitles, detach audio, separate audio stems, and transcribe audio.

    Args:
        video_path (str): Path to the video file.
        output_dir (str): Directory where processed files will be saved.
        detach_subtitles_flag (bool): Whether to detach subtitles.
        detach_audio_flag (bool): Whether to detach audio.
        speech_to_text (str): Language for speech-to-text conversion.
        filter_two_stems (bool): Whether to separate audio into two stems.
        device (str): Device to use ('cpu' or 'gpu').
        client (AzureOpenAI): Azure OpenAI client.
        deployment_id (str): Azure deployment ID.
        
    """
    print(device, "from inside the process_video")
    
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    logging.info(f"VARIABLE video_name from inside process directory: {video_name} ")
    logging.info(f"VARIABLE video_dir from inside process directory: {video_dir} ")
    logging.info(f"WE ARE GOING TO USE: {video_dir} ")
    video_output_dir = os.path.join(output_dir, video_dir)
    logging.info(f"VARIABLE video_output_dir video_name from inside process directory: {video_output_dir} ")
    os.makedirs(video_output_dir, exist_ok=True)
    
    # Copy the original video to the video_output_dir
    try:
        shutil.copy(video_path, video_output_dir)
        logging.info(f"Video copied to: {video_output_dir}")
        logging.info(f"Video copied to: {video_output_dir}")
    except Exception as e:
        logging.error(f"Error copying video {video_path} to {video_output_dir}: {e}")
        return

    output_subtitles = os.path.join(video_output_dir, f"{video_dir}_subtitles.srt")
    output_audio = os.path.join(video_output_dir, f"{video_dir}_audio.wav")  # Detached audio
    output_video_no_audio = os.path.join(video_output_dir, f"{video_dir}_no_audio.mp4")

    audio_paths = []  # Initialize the list to store audio paths

    # Step 1: Detach subtitles if flag is set
    if detach_subtitles_flag:
        detach_subtitles(video_path, output_subtitles)
        if os.path.exists(output_subtitles) and os.path.getsize(output_subtitles) > 0:
            try:
                with open(output_subtitles, 'r') as f:
                    subtitles_content = f.read()
                    logging.info(f"Subtitles found:\n{subtitles_content}")
                    logging.info(f"Subtitles extracted to {output_subtitles}")
            except Exception as e:
                logging.error(f"No subtitles found error: {e}")
        else:
            logging.info(f"No subtitles found in {video_path}")

    # Step 2: Detach audio if flag is set
    if detach_audio_flag:
        detach_audio(video_path, output_audio, output_video_no_audio)

        # Step 3: Filter out videos with two audio stems (only if Step 2 was successful)
        if filter_two_stems:
            # Check if detach_audio was successful by verifying the existence of output_audio
            if os.path.exists(output_audio):
                vocals_path, non_vocals_path = separate_audio(output_audio, video_output_dir, device)
                if vocals_path and non_vocals_path:
                    logging.info(f"Separated audio into {vocals_path} and {non_vocals_path}")
                    
                    # ---- Additional Cleanup Steps Start ----
                    # Step 1: Ensure only the processed vocals file is used
                    processed_vocals_path = os.path.join(video_output_dir, f"{video_dir}_audio_vocals_processed.mp3")
                    logging.info(f"Processed vocals path: {processed_vocals_path}")
                    if os.path.exists(processed_vocals_path):
                        logging.info(f"Found processed vocals file: {processed_vocals_path}")
                        # Remove the original vocals.wav if it exists
                        original_vocals_path = os.path.join(video_output_dir, f"{video_dir}_audio_vocals.wav")
                        if os.path.exists(original_vocals_path):
                            os.remove(original_vocals_path)
                            logging.info(f"Removed original vocals file: {original_vocals_path}")
                        else:
                            logging.info(f"Original vocals file not found at: {original_vocals_path}")
                        # Set audio_paths to only the processed vocals
                        audio_paths = [processed_vocals_path]
                    else:
                        logging.error(f"Error: Processed vocals file not found at: {processed_vocals_path}")
                        logging.info("Falling back to using the original audio for transcription.")
                        audio_paths = [output_audio]
                    # ---- Additional Cleanup Steps End ----
                else:
                    logging.error("Audio separation failed. Falling back to original audio for transcription.")
                    audio_paths = [output_audio]
            else:
                logging.error(f"Error: Audio file {output_audio} not found after detaching audio.")
                logging.info("Skipping filtering and proceeding with original audio for transcription.")
                audio_paths = [output_audio]
        else:
            # If not filtering, use the detached audio for transcription
            if os.path.exists(output_audio):
                audio_paths = [output_audio]
            else:
                logging.error(f"Detached audio file {output_audio} not found.")
    else:
        # If not detaching audio, look for existing audio files (optional)
        # For this script, we'll proceed only if audio is detached
        logging.info("Audio detachment not requested. Skipping audio processing.")
        audio_paths = []

    # Handle transcription if audio exists
    transcription_tasks = []
    for audio_path in audio_paths:
        if os.path.exists(audio_path):
            logging.info(f"Audio file found: {audio_path}")
            transcription_tasks.append(audio_path)
        else:
            logging.warning(f"Audio file {audio_path} not found. Skipping transcription.")
            
    print("client and deployment: ", client, deployment_id)

    if transcription_tasks:
        # Run the asynchronous transcription
        try:
            asyncio.run(transcribe_audio(
                transcription_tasks,  # List of audio paths
                video_output_dir,
                speech_to_text,
                client,
                deployment_id
            ))
            # Cleanup: Remove all files except .srt files
            cleanup_output_dir(video_output_dir)
            # video_dir_name = os.path.basename(video_output_dir)
            # new_filename = f"{video_dir_name}_subtitles.srt"
            # os.rename(new_filename, f"{video_base_name_for_subtitle_name}.srt")
            # logging.info(f"Renamed {new_filename} to {video_base_name_for_subtitle_name}.srt")
        except Exception as e:
            logging.error(f"Error during asynchronous transcription: {e}")
    else:
        logging.info("No valid audio files found for transcription.")

# Function to convert .mov to .mp4
def converting_non_mp4_to_mp4(input_video_path, output_video_path):
    """
    Convert a .mov video to .mp4 format using ffmpeg.

    Parameters:
    - input_video_path (str): Path to the input .mov video.
    - output_video_path (str): Desired path for the output .mp4 video.
    """
    try:
        logging.info(f"Starting conversion: {input_video_path} to {output_video_path}")
        
        # ffmpeg command to convert .mov to .mp4
        ffmpeg_command = [
            'ffmpeg',
            '-i', input_video_path,          # Input file
            '-c:v', 'libx264',               # Video codec
            '-c:a', 'aac',                   # Audio codec
            '-strict', 'experimental',       # Allow experimental codecs if needed
            output_video_path                 # Output file
        ]
        
        # Execute the ffmpeg command
        subprocess.run(ffmpeg_command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        logging.info(f"Successfully converted {input_video_path} to {output_video_path}")
        
    except subprocess.CalledProcessError as e:
        error_message = e.stderr.decode().strip()
        logging.error(f"Error converting {input_video_path} to mp4: {error_message}")


def main():
    parser = argparse.ArgumentParser(description="Process videos by detaching subtitles, detaching audio, and performing speech-to-text conversion.")
    
    parser.add_argument('--input-dir', required=True, help='Path to the directory containing the original videos to be processed.')
    
    parser.add_argument('--output-dir', help='Path to the directory where processed videos and files will be saved. If not provided, the parent directory of the input directory will be used.')
    
    parser.add_argument('--detach-subtitles', action='store_true', help='Flag to detach subtitles from the videos. If set, subtitles will be extracted and saved as .srt files.')
    
    parser.add_argument('--detach-audio', action='store_true', help='Flag to detach audio from the videos. If set, audio will be extracted and saved as .wav files, and the video without audio will be saved as well.')
    
    parser.add_argument('--device', default='cpu', help='Flag to specify the device this workload will be conducted on. The device is used for speeding up the process. Options are "cpu" for using the CPU and "gpu" for using the GPU (if CUDA is available).')
    
    parser.add_argument(
    '--speech-to-text',
    type=str,
    default='en',
    help='Language code for speech-to-text conversion. Example: "en" for English.'
    )

    parser.add_argument('--filter-two-stems', action='store_true', help='Flag to filter out videos with two audio stems (If this flag is used, you will get two audio files, vocals and non vocals) the vocals audio file will contain the sound words and non vocals will contain music.')
    
    # we are going to use only azure openai
    parser.add_argument('--secrets-dir',  required=True, help='Directory containing .env file with API key.')

    args = parser.parse_args()
    
    if not args.speech_to_text:
        logging.warning("The --speech-to-text flag was not used. Transcription will not be performed.")

    if args.speech_to_text.lower() not in SUPPORTED_LANGUAGES:
        logging.error(f"Unsupported language code: {args.speech_to_text}")
        sys.exit(1)
    
    # 1) Load credentials into a dictionary called `creds`
    creds = load_api_credentials(args.secrets_dir)
    if not creds:
        logging.error("API key not found in the secrets directory.")
        sys.exit(1)

     # 2) Create a client (Azure)
    client, deployment_id = create_client(creds)
    
    # Since we're only using Azure, no need for OpenAI API key
    azure_client = client  # For clarity
    
    # If output directory is not provided, use the parent directory of input directory
    if not args.output_dir:
        args.output_dir = os.path.dirname(os.path.abspath(args.input_dir))
        logging.info(f"Output directory not provided. Using parent directory: {args.output_dir}")
    
    # Validate and set the device
    device = validate_device(args.device)
    
    if not args.speech_to_text:
        logging.info("Important: The --speech-to-text flag must be used to perform transcription.")
        logging.warning("The --speech-to-text flag was not used. Transcription will not be performed.")
        # Depending on requirements, you might want to exit or continue
        # For this script, we'll continue without transcription
                   
    if not args.filter_two_stems:
        logging.info("Note: Using the --filter-two-stems flag can increase the quality of processed transcription, because audio comprised of vocals only yields better results.")
        logging.info("The --filter-two-stems flag was not used. Audio will not be separated into stems.")
        
    start_time = time.time()
    logging.info(f"Execution started at {time.ctime(start_time)}")

    # Process each video in the input directory
    for root, dirs, files in os.walk(args.input_dir):
        for video_file in files:
            video_path = os.path.join(root, video_file)
            
            # Extract the directory name
            video_dir = os.path.basename(os.path.dirname(video_path))
            
            logging.info(f"VARIABLE video_dir from main function: {video_dir}")
            logging.info(f"VARIABLE video_path from main function: {video_path}")
            logging.info(f"VARIABLE args.output_dir from main function: {args.output_dir}")
            
            # video_path = /mnt/c/Users/Hamid/Desktop/机械制造技术/（翻译后）机械制造技术/1.1.1 Introduction to mechanical engineering technology.mov and I want just video_base_name without .mov 
            video_base_name_with_ext = os.path.basename(video_path)
            video_base_name_for_subtitle_name, ext = os.path.splitext(video_base_name_with_ext)
            logging.info(f"VARIABLE video_base_name_for_subtitle_name for subtitles name: {video_base_name_for_subtitle_name}")
            
            # Check if the file has a supported video extension
            if video_file.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                if video_file.lower().endswith('.mov'):
                    # Define the output .mp4 path
                    output_mp4_path = os.path.splitext(video_path)[0] + '.mp4'
                    
                    # Convert .mov to .mp4
                    converting_non_mp4_to_mp4(video_path, output_mp4_path)
                    
                    # Check if conversion was successful
                    if os.path.exists(output_mp4_path):
                        logging.info(f"Processing converted video: {output_mp4_path}")
                        logging.info(f"Processing converted video: {output_mp4_path}")
                        
                        # Pass azure_client and deployment_id to process_video
                        process_video(
                            video_dir,
                            output_mp4_path, 
                            args.output_dir,
                            args.detach_subtitles, 
                            args.detach_audio, 
                            args.speech_to_text, 
                            args.filter_two_stems, 
                            device=device,
                            client=azure_client,
                            deployment_id=deployment_id,
                            video_base_name_for_subtitle_name=video_base_name_for_subtitle_name
                        )
                        
                        # Optionally, remove the original .mov file to save space
                        # os.remove(video_path)
                        # logging.info(f"Removed original .mov file: {video_path}")
                    else:
                        logging.info(f"Failed to convert {video_path}. Skipping processing.")
                else:
                    logging.info(f"Processing video: {video_path}")
                    
                    # Pass azure_client and deployment_id to process_video
                    process_video(
                        video_dir,
                        video_path, 
                        args.output_dir,
                        args.detach_subtitles, 
                        args.detach_audio, 
                        args.speech_to_text, 
                        args.filter_two_stems, 
                        device=device,
                        client=azure_client,
                        deployment_id=deployment_id,
                        video_base_name_for_subtitle_name=video_base_name_for_subtitle_name
                    )
            else:
                logging.info(f"Skipping unsupported file: {video_path}")
                        
    end_time = time.time()
    logging.info(f"Execution finished at {time.ctime(end_time)}")
    logging.info(f"Total time taken: {end_time - start_time:.2f} seconds")

if __name__ == '__main__':
    main()
