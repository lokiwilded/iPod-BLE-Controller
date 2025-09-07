import os
from dotenv import load_dotenv

# Load variables from the .env file into the environment
load_dotenv()

# Get the Last.fm credentials from the environment
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
LASTFM_API_SECRET = os.getenv("LASTFM_API_SECRET")

# Basic validation to ensure the keys are present
if not LASTFM_API_KEY or not LASTFM_API_SECRET:
    print("ERROR: Last.fm API key and secret are not set in the .env file.")
    print("Please create a .env file and add your credentials.")
    exit()
