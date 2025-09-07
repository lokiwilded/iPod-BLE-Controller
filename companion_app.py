import asyncio
import pylast
from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as MediaManager

# --- CONFIGURATION ---
# PASTE YOUR LAST.FM API CREDENTIALS HERE
LASTFM_API_KEY = "5b67c219940470dfad057455d244be54"
LASTFM_API_SECRET = "6dd76c2807ebf43c3b35f0452e1bb2ed"

# --- SETUP ---
# Set up a connection to the Last.fm network
try:
    network = pylast.LastFMNetwork(api_key=LASTFM_API_KEY, api_secret=LASTFM_API_SECRET)
except pylast.WSError as e:
    print(f"Error connecting to Last.fm: {e}")
    print("Please check your API key and secret in the script.")
    network = None

# Global variable to keep track of the current song to avoid reprints
current_track_id = None

async def get_media_info(session):
    """Fetches and returns media properties from a session."""
    info = await session.try_get_media_properties_async()
    return {prop: info.__getattribute__(prop) for prop in dir(info)}

def enrich_media_info(properties):
    """Enriches media info with data from Last.fm if available."""
    artist = properties.get('artist')
    title = properties.get('title')
    
    if not artist or not title or not network:
        return properties # Not enough info or network not available

    try:
        # Search for the track on Last.fm
        track = network.get_track(artist, title)
        if track and track.get_album():
            properties['album_title'] = track.get_album().get_title()
            # Get the large album art image URL
            properties['album_art_url'] = track.get_album().get_cover_image(pylast.SIZE_LARGE)
    except pylast.WSError:
        # Handle cases where the track isn't found on Last.fm
        pass # Keep the original data from Windows
        
    return properties

def print_media_info(properties):
    """Prints the formatted media information."""
    artist = properties.get('artist', 'Unknown Artist')
    title = properties.get('title', 'No Title')
    album = properties.get('album_title', 'Unknown Album')
    album_art_url = properties.get('album_art_url', 'Not Found')

    print("\n--- Now Playing (Enriched) ---")
    print(f"  Title: {title}")
    print(f"  Artist: {artist}")
    print(f"  Album: {album}")
    print(f"  Art URL: {album_art_url}")
    print("------------------------------")

async def main():
    """Main loop to monitor media sessions and song changes."""
    global current_track_id
    manager = await MediaManager.request_async()
    session = None
    
    # Get a reference to the running event loop
    loop = asyncio.get_running_loop()

    async def handle_media_change():
        global current_track_id
        current_session = manager.get_current_session()
        if current_session:
            new_properties = await get_media_info(current_session)
            new_track_id = f"{new_properties.get('artist','')}-{new_properties.get('title','')}"
            if new_track_id != current_track_id and new_properties.get('title'):
                current_track_id = new_track_id
                enriched_properties = enrich_media_info(new_properties)
                print_media_info(enriched_properties)

    def media_properties_changed_handler(sender, args):
        # This is the fix: We use a thread-safe call to schedule our
        # async task on the main event loop we captured earlier.
        loop.call_soon_threadsafe(asyncio.create_task, handle_media_change())

    while True:
        current_session = manager.get_current_session()
        if current_session:
            if session is None or session.source_app_user_model_id != current_session.source_app_user_model_id:
                session = current_session
                session.add_media_properties_changed(media_properties_changed_handler)
                await handle_media_change() # Handle initial song
        else:
            session = None

        await asyncio.sleep(2)

if __name__ == "__main__":
    if network:
        try:
            print("Starting Companion App... Press Ctrl+C to exit.")
            asyncio.run(main())
        except KeyboardInterrupt:
            print("\nExiting.")
