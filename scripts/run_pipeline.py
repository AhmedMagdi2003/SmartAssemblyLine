from pathlib import Path
import os
import sys
import threading
import time
import traceback

import cv2

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if sys.path[0] != str(PROJECT_ROOT):
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
except ImportError:
    pass
else:
    load_dotenv(PROJECT_ROOT / ".env")

from src.core.tracking import AssemblyLineTracker


WINDOW_NAME = "Production Tracker"
DEFAULT_STREAM_URL = "tcp://deltapi:1234?tcp_nodelay=1"
DEFAULT_VIDEO_PATH = PROJECT_ROOT / "data" / "videos" / "videoproject 1.mp4"
PIPELINE_ERROR_LOG = PROJECT_ROOT / "data" / "runtime" / "logs" / "pipeline.err.log"


def get_flag_env(name, default=False):
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def get_int_env(name, default):
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    try:
        return int(raw_value)
    except ValueError:
        print(f"[WARNING] Invalid integer for {name}: {raw_value!r}. Using {default}.", flush=True)
        return default


def log_pipeline_exception(context):
    PIPELINE_ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
    message = f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {context}\n"
    details = traceback.format_exc()
    with PIPELINE_ERROR_LOG.open("a", encoding="utf-8") as log_file:
        log_file.write(message)
        log_file.write(details)
        log_file.write("\n")
    print(f"[ERROR] {context}. Details saved to {PIPELINE_ERROR_LOG}", flush=True)


def resolve_video_path():
    configured_path = os.getenv("VISION_VIDEO_PATH", "").strip()
    if not configured_path:
        return DEFAULT_VIDEO_PATH

    video_path = Path(configured_path)
    if not video_path.is_absolute():
        video_path = PROJECT_ROOT / video_path
    return video_path


def resolve_pi_stream_url():
    stream_url = (
        os.getenv("PI_CAMERA_STREAM_URL")
        or os.getenv("VISION_STREAM_URL")
        or DEFAULT_STREAM_URL
    ).strip()

    if "listen" in stream_url:
        base_url = stream_url.split("?", 1)[0]
        stream_url = f"{base_url}?tcp_nodelay=1"
        print(
            "[WARNING] Removed '?listen...' from stream URL. "
            "The Raspberry Pi uses listen mode; this project connects as the client.",
            flush=True,
        )

    return stream_url


def _open_capture(source, error_message):
    capture = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(error_message)
    return capture


class LatestFrameCapture:
    """Read a live stream continuously and keep only the newest frame."""

    def __init__(self, stream_url):
        self.capture = _open_capture(
            stream_url,
            (
                "Could not open Raspberry Pi MJPEG stream.\n"
                f"Client URL used by this project: {stream_url}\n"
                "Run this on the Raspberry Pi first:\n"
                'ffmpeg -f v4l2 -input_format mjpeg -framerate 24 -video_size 640x480 '
                '-i /dev/video0 -c:v copy -f mjpeg '
                '"tcp://0.0.0.0:1234?listen&tcp_nodelay=1"\n'
                "Default client hostname is tcp://deltapi:1234?tcp_nodelay=1. If your network "
                "does not resolve deltapi, set PI_CAMERA_STREAM_URL to "
                "tcp://deltapi.local:1234 or tcp://<RASPBERRY_PI_IP>:1234."
            ),
        )

        self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.lock = threading.Lock()
        self.latest_frame = None
        self.stopped = False
        self.thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.thread.start()

    def _reader_loop(self):
        while not self.stopped:
            ret, frame = self.capture.read()
            if not ret or frame is None:
                time.sleep(0.01)
                continue

            with self.lock:
                self.latest_frame = frame

    def read(self):
        with self.lock:
            if self.latest_frame is None:
                return False, None
            return True, self.latest_frame.copy()

    def release(self):
        self.stopped = True
        if self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self.capture.release()


def open_stream_capture(stream_url):
    print(f"[CAMERA] Opening low-latency Raspberry Pi MJPEG stream: {stream_url}", flush=True)
    os.environ.setdefault(
        "OPENCV_FFMPEG_CAPTURE_OPTIONS",
        "fflags;nobuffer|flags;low_delay|probesize;32|analyzeduration;0",
    )
    return LatestFrameCapture(stream_url)


def open_video_capture(video_path):
    print(f"[VIDEO] Opening local test video: {video_path}", flush=True)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"Could not open local video at {video_path}.")
    return capture


def open_capture_source():
    source = os.getenv("VISION_SOURCE", "pi_stream").strip().lower()
    if source in {"pi", "pi_stream", "stream", "tcp", "mjpeg", "camera"}:
        return open_stream_capture(resolve_pi_stream_url()), True

    if source in {"video", "local_video", "local-video", "file"}:
        return open_video_capture(resolve_video_path()), False

    raise ValueError("Unsupported VISION_SOURCE. Use pi_stream or video.")


def create_display_window(frame):
    frame_height, frame_width = frame.shape[:2]
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_AUTOSIZE)
    print(
        f"[DISPLAY] Window uses original frame size: {frame_width}x{frame_height}",
        flush=True,
    )


def main():
    capture, is_live_source = open_capture_source()
    display_enabled = get_flag_env("VISION_DISPLAY", True)
    max_missed_live_frames = get_int_env("VISION_MAX_MISSED_FRAMES", 90)
    max_frames = get_int_env("VISION_MAX_FRAMES", 0)
    target_fps = get_int_env("VISION_TARGET_FPS", 24)
    target_frame_time = 1.0 / target_fps if target_fps > 0 else 0.0
    window_created = False

    try:
        print("[PIPELINE] Loading YOLO tracker...", flush=True)
        tracker = AssemblyLineTracker(config_path="config/tracker_params.yaml")

        print(f"[PIPELINE] Tracking target: {target_fps:.1f} FPS", flush=True)
        missed_live_frames = 0
        processed_frames = 0

        while True:
            loop_start_time = time.time()

            ret, frame = capture.read()
            if not ret or frame is None:
                if is_live_source and missed_live_frames < max_missed_live_frames:
                    missed_live_frames += 1
                    time.sleep(0.1)
                    continue

                if is_live_source:
                    print("[CAMERA] Pi camera stream stopped returning frames.", flush=True)
                else:
                    print("[VIDEO] End of local test video reached.", flush=True)
                break

            missed_live_frames = 0
            processed_frames += 1

            ai_start_time = time.time()
            try:
                annotated_frame, _ = tracker.process_frame(
                    frame.copy(),
                    frame_timestamp=time.time(),
                )
            except Exception:
                log_pipeline_exception("Frame processing failed; skipping this frame")
                annotated_frame = frame.copy()

            ai_ms = (time.time() - ai_start_time) * 1000
            cv2.putText(
                annotated_frame,
                f"AI: {ai_ms:.1f} ms | Target: {target_fps:.1f} FPS",
                (10, 65),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
            )

            if display_enabled:
                try:
                    if not window_created:
                        create_display_window(annotated_frame)
                        window_created = True
                    cv2.imshow(WINDOW_NAME, annotated_frame)
                except cv2.error:
                    display_enabled = False
                    log_pipeline_exception("Display window failed; continuing headless")

                if display_enabled and cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            if max_frames > 0 and processed_frames >= max_frames:
                print(f"[PIPELINE] Reached VISION_MAX_FRAMES={max_frames}; stopping.", flush=True)
                break

            elapsed_time = time.time() - loop_start_time
            time_to_sleep = target_frame_time - elapsed_time
            if time_to_sleep > 0:
                time.sleep(time_to_sleep)
    finally:
        capture.release()
        if window_created:
            try:
                cv2.destroyAllWindows()
            except cv2.error:
                pass


if __name__ == "__main__":
    main()
