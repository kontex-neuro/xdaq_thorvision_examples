import signal
import time
import threading

from pyxdaq.pyxdaq.datablock import DataBlock
from pyxdaq.pyxdaq.xdaq import get_XDAQ
from PyThorVision.pythorvision import XdaqClient


is_running = True
recording_triggered = False


def _handle_sigint(sig, frame):
    """Catch Ctrl+C and tell the main loop to exit."""
    global is_running
    is_running = False


signal.signal(signal.SIGINT, _handle_sigint)


xdaq = get_XDAQ()
xdaq.enableDataStream("all", True)
num_streams = xdaq.numDataStream
frame_size = xdaq.getSampleSizeBytes()
sample_rate = xdaq.getSampleRate()
print(
    f"Frame size: {frame_size} bytes @ {sample_rate} Hz = "
    f"{frame_size * sample_rate / 1e6:.2f} MB/s"
)


client = XdaqClient()
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


def record_cameras(duration=10):
    """
    Start all cameras for N seconds and then stop them.
    """
    print(f"[Camera] Starting {len(cameras)} camera(s) for {duration} seconds...")
    streams = []

    for camera in cameras:
        # find the first JPEG capability
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

    time.sleep(duration)

    print("[Camera] Stopping streams...")
    for camera, _ in streams:
        try:
            client.stop_stream(camera.id)
            print(f"[Camera] Stopped stream for {camera.id}")
        except Exception as e:
            print(f"[Camera] Error stopping stream for {camera.id}: {e}")


def on_data_received(data: bytes, error: str):
    """
    Called in a dedicated thread whenever a data frame arrives.

    NOTE: this callback holds the Python GIL. If you do heavy work here, the
    Python-side queue may back up (HW keeps running, but this queue grows).
    It's OK to compute here as long as it keep up with the target rate.

    CALLBACK LIFETIME: even after xdaq.stop(), this callback may still be
    invoked until exit the start_receiving_aligned_buffer context.
    """
    global recording_triggered

    if error:
        print(f"[XDAQ error] {error}")
        return

    if not data:
        return

    buffer = bytearray(data)
    length = len(buffer)
    if length % frame_size != 0:
        if is_running:
            print(f"[Warning] invalid frame length {length}")
        else:
            # invalid frame length, could be the last data chunk.
            pass
        return

    block = DataBlock.from_buffer(xdaq.rhs, frame_size, buffer, num_streams)
    samples = block.to_samples()

    ts = samples.ts[0]
    if not recording_triggered and ts >= 100_000:
        recording_triggered = True
        print(f"[Trigger] Timestamp {ts} reached, starting camera recording!")

        # Start recording on all cameras for 10 seconds
        threading.Thread(target=record_cameras, args=(10,), daemon=True).start()

    print(f"[XDAQ] Chunk: {len(buffer):8d} B | Timestep: {ts:8d}", end="\r")


# Use the aligned-buffer context to start/stop the callback queue
with xdaq.start_receiving_aligned_buffer(
    frame_size,
    on_data_received,
):
    # Kick off acquisition
    xdaq.start(continuous=True)

    start_time = time.time()
    duration = 30

    # Wait until SIGINT
    # or until the run duration (30 seconds) is reached
    while is_running and (time.time() - start_time < duration):
        time.sleep(0.1)

    # Stop acquisition
    xdaq.stop(wait=True)
    # Callback may still run until we exit this block

print("\nExiting...")
