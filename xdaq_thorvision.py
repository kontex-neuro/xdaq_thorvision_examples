import signal
import time
import os

from pyxdaq.xdaq import get_XDAQ
from pythorvision import ThorVisionClient


is_running = True


def _handle_sigint(sig, frame):
    """Catch Ctrl+C and tell the main loop to exit."""
    global is_running
    is_running = False


signal.signal(signal.SIGINT, _handle_sigint)


xdaq = get_XDAQ()


client = ThorVisionClient()
# Recording directory name
# will be created in the current working directory
recordings_dir = "recordings"
cameras = client.list_cameras()

if not cameras:
    print("No cameras found.")
    exit(1)

print(f"Found {len(cameras)} cameras:")
for camera in cameras:
    print(f" - {camera.id}: {camera.name}")


def start_recording():
    """
    Start recording on all cameras
    """
    print(f"[Camera] Starting {len(cameras)} camera(s) for {duration_sec} seconds...")
    streams = []

    existing_files = set()
    if os.path.exists(recordings_dir):
        existing_files = set(os.listdir(recordings_dir))

    # Start all cameras connected to XDAQ
    for camera in cameras:
        # Find the first JPEG capability
        jpeg_cap = next(
            (cap for cap in camera.capabilities if cap.media_type == "image/jpeg"), None
        )
        if not jpeg_cap:
            print(f"[Camera] No JPEG capability for {camera.id}, skipping")
            continue

        stream = client.start_stream_with_recording(
            camera=camera,
            capability=jpeg_cap,
            output_dir=recordings_dir,
            gstreamer_debug=False,
        )
        streams.append((camera, stream))

    return streams, existing_files


def stop_recording(streams: dict, duration_sec: int, existing_files: set):
    """
    Stop recording on all cameras
    """
    while time.time() - start_time < duration_sec:
        time.sleep(0.1)

    # Stop all cameras
    for camera, _ in streams:
        try:
            client.stop_stream(camera.id)
            print(f"[Camera] Stopped stream for {camera.id}")
        except Exception as e:
            print(f"[Camera] Error stopping stream for {camera.id}: {e}")

    # Print newly recorded files
    print(f"Recorded {len(streams)} cameras in {os.path.abspath(recordings_dir)}")
    if os.path.exists(recordings_dir):
        current_files = set(os.listdir(recordings_dir))
        new_files = current_files - existing_files

        for filename in new_files:
            file_path = os.path.join(recordings_dir, filename)

            if os.path.isfile(file_path):
                print(f"  - {file_path}")


def on_data_received(data: bytes, error: str):
    """
    Called in a dedicated thread whenever a data frame arrives.

    NOTE: this callback holds the Python GIL. If you do heavy work here, the
    Python-side queue may back up (HW keeps running, but this queue grows).
    It's OK to compute here as long as it keeps up with the target rate.

    CALLBACK LIFETIME: even after xdaq.stop(), this callback may still be
    invoked until exiting the start_receiving_buffer context.
    """

    if error:
        print(f"[XDAQ error] {error}")
        return

    if not data:
        return

    buffer = bytearray(data)
    length = len(buffer)
    # Press Ctrl+C will set is_running to False,
    # XDAQ notifies this callback here, it could be the last data chunk.
    # Skip processing of the last data chunk and just return here.
    if not is_running:
        return

    # Parse: convert buffer to samples
    samples = xdaq.buffer_to_samples(buffer)
    print(f"[XDAQ] Chunk: {length:8d} B | Timestep: {samples.ts[0]:8d}", end="\r")


print("Starting XDAQ acquisition and camera recording for 10 seconds...")
duration_sec = 10
streams, existing_files = start_recording()
start_time = time.time()

# Start receiving data from headstages, video is still recording in the background
with xdaq.start_receiving_buffer(
    on_data_received,
):
    # Kick off acquisition
    xdaq.start(continuous=True)

    # Wait until SIGINT or until the run duration (10 seconds) is reached
    while is_running and (time.time() - start_time < duration_sec):
        time.sleep(0.1)

    # After the run duration is reached, set is_running to False manually
    is_running = False

    # Stop acquisition
    xdaq.stop(wait=True)
    # Callback may still run until we exit this block

stop_recording(streams, duration_sec, existing_files)
print("\nExiting...")
