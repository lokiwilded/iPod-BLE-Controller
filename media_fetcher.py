import asyncio
import pylast
from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as MediaManager

async def get_current_media_session():
    """Finds the current media session (e.g., Spotify, Chrome)."""
    try:
        sessions = await MediaManager.request_async()
        return sessions.get_current_session()
    except Exception:
        return None

async def get_media_properties(session):
    """Extracts media properties (title, artist) from a session."""
    if not session:
        return {}
    try:
        info = await session.try_get_media_properties_async()
        return {
            "title": info.title,
            "artist": info.artist,
        }
    except Exception:
        return {}

# --- THIS IS THE FIX ---
# The function now correctly accepts the api_key and api_secret as arguments.
def enrich_with_lastfm(properties: dict, api_key: str, api_secret: str) -> dict:
    """Enriches media properties with data from Last.fm."""
    title = properties.get("title")
    artist = properties.get("artist")
    
    # Initialize the network object with the provided keys
    network = pylast.LastFMNetwork(api_key=api_key, api_secret=api_secret)
    
    album_title = ""
    album_art_url = ""

    if not title or not artist:
        return properties

    try:
        # Fetch track data from Last.fm
        track = network.get_track(artist, title)
        album = track.get_album()
        if album:
            album_title = album.get_title()
            # Get the "extralarge" image URL if available
            album_art_url = album.get_cover_image(size=3)
    except pylast.WSError:
        # This happens when the track is not found on Last.fm, which is normal.
        pass
    except Exception as e:
        print(f"[ERROR] Last.fm lookup failed: {e}")

    properties["album_title"] = album_title
    properties["album_art_url"] = album_art_url if album_art_url else ""
    return properties