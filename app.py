import asyncio
import sys
import time

import media_fetcher
from ble_handler import BLEHandler
from config import LASTFM_API_KEY, LASTFM_API_SECRET

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

current_track_id = None
ble_handler = BLEHandler("iPodLink")

def format_metadata_string(properties: dict) -> str:
    title = properties.get('title', '')
    artist = properties.get('artist', '')
    album = properties.get('album_title', '')
    art_url = properties.get('album_art_url', '')
    return f"{title}|{artist}|{album}|{art_url}"

async def media_session_monitor():
    global current_track_id
    active_session = None
    loop = asyncio.get_running_loop()

    async def handle_media_properties_changed(session_to_update):
        global current_track_id
        properties = await media_fetcher.get_media_properties(session_to_update)
        new_track_id = f"{properties.get('artist','')}-{properties.get('title','')}"

        if new_track_id != current_track_id and properties.get('title'):
            print("\n--- New Song Detected ---")
            current_track_id = new_track_id
            enriched_properties = media_fetcher.enrich_with_lastfm(properties, LASTFM_API_KEY, LASTFM_API_SECRET)
            metadata_string = format_metadata_string(enriched_properties)
            
            # --- THIS IS THE UPDATE ---
            # Print all the data being sent, including the Art URL.
            print(f"  Title: {enriched_properties.get('title')}")
            print(f"  Artist: {enriched_properties.get('artist')}")
            print(f"  Album: {enriched_properties.get('album_title')}")
            print(f"  Art URL: {enriched_properties.get('album_art_url')}")
            
            await ble_handler.send_metadata(metadata_string)

    while True:
        if ble_handler.client and ble_handler.client.is_connected:
            session = await media_fetcher.get_current_media_session()
            if session:
                if active_session is None or active_session.source_app_user_model_id != session.source_app_user_model_id:
                    print(f"Latching onto new media session: {session.source_app_user_model_id}")
                    active_session = session
                    active_session.add_media_properties_changed(
                        lambda sender, args: loop.call_soon_threadsafe(
                            asyncio.create_task, handle_media_properties_changed(sender)
                        )
                    )
                    await handle_media_properties_changed(active_session)
            else:
                if active_session is not None:
                    print("\nMedia session ended.")
                    active_session = None
                    current_track_id = None
                    await ble_handler.send_metadata("|||")
        
        await asyncio.sleep(2)

async def main():
    print("Starting iPod Companion App... Press Ctrl+C to exit.")
    asyncio.create_task(media_session_monitor())
    while True:
        if not ble_handler.client or not ble_handler.client.is_connected:
            print("Attempting to connect to iPodLink service...")
            await ble_handler.connect()
        await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting.")