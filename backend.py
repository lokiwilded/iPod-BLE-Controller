import asyncio
import threading
from queue import Queue

import media_fetcher
import system_info
from ble_handler import BLEHandler
from config import LASTFM_API_KEY, LASTFM_API_SECRET

class BackendThread(threading.Thread):
    def __init__(self, ui_queue: Queue):
        super().__init__(daemon=True)
        self.ui_queue = ui_queue
        self.ble_handler = BLEHandler("iPodLink")
        self.active_session = None

    def run(self):
        asyncio.run(self.main())

    def format_bt_payload(self, properties: dict) -> str:
        """Formats all data into the single string for the iPod."""
        title = properties.get('title', '')
        artist = properties.get('artist', '')
        album = properties.get('album_title', '')
        art_url = properties.get('album_art_url', '')
        pos = int(properties.get('timeline', {}).get('position', 0))
        end = int(properties.get('timeline', {}).get('end_time', 0))
        vol = properties.get('volume', 0)
        return f"{title}|{artist}|{album}|{art_url}|{pos}|{end}|{vol}"

    async def main(self):
        """The main asyncio event loop for all background tasks."""
        tasks = [
            self.connection_manager(),
            self.media_session_monitor(),
            self.volume_monitor(),
            self.progress_corrector()
        ]
        await asyncio.gather(*tasks)

    async def connection_manager(self):
        """Dedicated task to manage the BLE connection."""
        while True:
            if not self.ble_handler.client or not self.ble_handler.client.is_connected:
                self.ui_queue.put({"type": "status_update", "message": "Scanning for iPod..."})
                await self.ble_handler.connect()
                if self.ble_handler.client and self.ble_handler.client.is_connected:
                     self.ui_queue.put({"type": "status_update", "message": "Connected"})
                else:
                    self.ui_queue.put({"type": "status_update", "message": "Disconnected. Retrying..."})
            await asyncio.sleep(5)

    async def volume_monitor(self):
        """Continuously checks system volume."""
        last_vol = -1
        while True:
            if self.ble_handler.client and self.ble_handler.client.is_connected:
                current_vol = system_info.get_master_volume_level()
                if current_vol != last_vol:
                    last_vol = current_vol
                    self.ui_queue.put({"type": "volume_update", "value": current_vol})
            await asyncio.sleep(0.5)

    async def progress_corrector(self):
        """Periodically sends the true song position to the UI for correction."""
        while True:
            if self.active_session:
                timeline = await system_info.get_timeline_properties(self.active_session)
                self.ui_queue.put({"type": "progress_correction", "data": timeline})
            await asyncio.sleep(5) # Send correction every 5 seconds

    async def media_session_monitor(self):
        """Finds a media session and handles song changes."""
        current_track_id = None
        loop = asyncio.get_running_loop()

        async def handle_media_properties_changed(session_to_update):
            nonlocal current_track_id
            properties = await media_fetcher.get_media_properties(session_to_update)
            new_track_id = f"{properties.get('artist','')}-{properties.get('title','')}"

            if new_track_id != current_track_id and properties.get('title'):
                current_track_id = new_track_id
                enriched_properties = media_fetcher.enrich_with_lastfm(properties, LASTFM_API_KEY, LASTFM_API_SECRET)
                enriched_properties['timeline'] = await system_info.get_timeline_properties(session_to_update)
                enriched_properties['volume'] = system_info.get_master_volume_level()
                self.ui_queue.put({"type": "media_update", "data": enriched_properties})
                bt_payload = self.format_bt_payload(enriched_properties)
                await self.ble_handler.send_metadata(bt_payload)

        while True:
            session = await media_fetcher.get_current_media_session()
            if session:
                if self.active_session is None or self.active_session.source_app_user_model_id != session.source_app_user_model_id:
                    self.active_session = session
                    self.active_session.add_media_properties_changed(
                        lambda sender, args: loop.call_soon_threadsafe(
                            asyncio.create_task, handle_media_properties_changed(sender)
                        )
                    )
                    await handle_media_properties_changed(self.active_session)
            else:
                if self.active_session is not None:
                    self.active_session = None
                    current_track_id = None
                    self.ui_queue.put({"type": "media_update", "data": {}})
                    await self.ble_handler.send_metadata("||||||")
            await asyncio.sleep(2)