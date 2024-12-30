
import os
import sys
import logging
from dotenv import load_dotenv

import openai # Import AzureOpenAI correctly. Replace with the appropriate import based on your SDK
from openai import AzureOpenAI  # Ensure this import is correct or replace with the appropriate class

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

def load_api_credentials(secrets_dir=None):
    """
    Load the .env file from the specified directory (or current dir) 
    and store credentials for multiple services in a single dictionary.

    Returns a dictionary like:
    {
        'azure_speech_to_text': {
            'api_key': '...',
            'endpoint': '...',
            'deployment_id': '...'
        }
    }
    """
    if secrets_dir:
        dotenv_path = os.path.join(secrets_dir, '.env')
    else:
        dotenv_path = '.env'  # Default to the current directory

    if not os.path.exists(dotenv_path):
        logging.error(f"No .env file found at {dotenv_path}.")
        return None
    
    # Load environment variables from .env
    load_dotenv(dotenv_path)
    
    # Debugging: Print each environment variable
    azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    
    print(f"AZURE_OPENAI_API_KEY: {azure_api_key}")
    print(f"AZURE_OPENAI_ENDPOINT: {azure_endpoint}")
    print(f"AZURE_OPENAI_DEPLOYMENT: {azure_deployment}")
    
    # Build a dictionary of credentials
    creds = {
        "azure_speech_to_text": {
            "api_key": azure_api_key,
            "endpoint": azure_endpoint,
            "deployment_id": azure_deployment
        }
    }
    
    print("Loaded credentials:", creds)

    # Optional: Validate or log missing keys
    for service_name, service_data in creds.items():
        if not service_data["api_key"]:
            logging.warning(f"API key missing for service '{service_name}'. Check your .env.")

    return creds

def create_client(creds):
    
    """
    Create and return an AzureOpenAI client if Azure keys are found.
    Exits the program if Azure credentials are missing.
    
    Returns:
        client, deployment_id
        - client: AzureOpenAI client
        - deployment_id: Azure deployment ID
    """
    

    # 2) Extract Azure credentials from creds
    azure_api_key = creds["azure_speech_to_text"]["api_key"]
    azure_endpoint = creds["azure_speech_to_text"]["endpoint"]
    azure_deployment = creds["azure_speech_to_text"]["deployment_id"]
    
    openai.api_key = creds["azure_speech_to_text"]["api_key"]
    openai.api_base = os.getenv("AZURE_OPENAI_ENDPOINT")
    openai.api_type = "azure"
    openai.api_version = "2024-02-01"
    

    # 3) Check if Azure keys are available (non-empty).
    if azure_api_key and azure_endpoint and azure_deployment:
        logging.info("Using Azure OpenAI credentials.")
        
        # Initialize the AzureOpenAI client
        client = AzureOpenAI(
            api_key=azure_api_key,  
            api_version="2024-02-01",  # Replace with your actual Azure OpenAI API version
            azure_endpoint=azure_endpoint
        )
        
        return client, azure_deployment
    else:
        logging.error("Azure API credentials are missing or incomplete. Exiting.")
        sys.exit(1)