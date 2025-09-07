from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

def get_master_volume_level():
    """Gets the current master volume level as a percentage (0-100)."""
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(
            IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = interface.QueryInterface(IAudioEndpointVolume)
        # GetMasterVolumeLevelScalar returns a value between 0.0 and 1.0
        return int(volume.GetMasterVolumeLevelScalar() * 100)
    except Exception:
        # Return a default/error value if something goes wrong
        return -1

async def get_timeline_properties(session):
    """
    Fetches the timeline properties (start, end, position) for a media session.
    Returns a dictionary with times in seconds.
    """
    if not session:
        return {}
    try:
        timeline = session.get_timeline_properties()
        return {
            "start_time": timeline.start_time.total_seconds(),
            "end_time": timeline.end_time.total_seconds(),
            "position": timeline.position.total_seconds(),
        }
    except Exception:
        return {}