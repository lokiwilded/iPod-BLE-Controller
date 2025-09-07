import asyncio
from bleak import BleakClient, BleakScanner

# These unique IDs MUST match the ones in your ESP32 firmware
SERVICE_UUID = "19B10000-E8F2-537E-4F6C-D104768A1214"
METADATA_CHAR_UUID = "19B10001-E8F2-537E-4F6C-D104768A1214"

class BLEHandler:
    """Manages the entire BLE connection lifecycle."""

    def __init__(self, device_name="iPodLink"):
        self.device_name = device_name
        self.client = None

    async def connect(self):
        """Scans for the iPod and connects to the custom metadata service."""
        print(f"Scanning for '{self.device_name}'...")
        device = await BleakScanner.find_device_by_name(self.device_name, timeout=10.0)
        
        if not device:
            print(f"--> Custom service '{self.device_name}' not found.")
            return False

        print(f"Found device. Connecting to {device.address}...")
        self.client = BleakClient(device, disconnected_callback=self._handle_disconnect)
        
        try:
            await self.client.connect()
            print("--> Connected successfully to custom service!")
            
            # --- THIS IS THE FIX ---
            # Add a short, crucial delay to allow for service discovery to complete
            # before the main app tries to send any data. This prevents the race condition.
            await asyncio.sleep(1.0) 
            
            return self.client.is_connected
        except Exception as e:
            print(f"--> Failed to connect: {e}")
            self.client = None
            return False

    def _handle_disconnect(self, client):
        print("--> Device disconnected from custom service.")
        self.client = None

    async def send_metadata(self, metadata_str: str):
        """Sends the formatted metadata string to the iPod."""
        if self.client and self.client.is_connected:
            try:
                await self.client.write_gatt_char(METADATA_CHAR_UUID, metadata_str.encode('utf-8'))
            except Exception as e:
                print(f"--> Failed to send metadata: {e}")

    async def disconnect(self):
        if self.client and self.client.is_connected:
            await self.client.disconnect()