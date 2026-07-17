from pathlib import Path
import sys
import time
import cv2

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if sys.path[0] != str(PROJECT_ROOT):
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.tracking import AssemblyLineTracker

WINDOW_NAME = "Production Tracker"
VIDEO_PATH = PROJECT_ROOT / "data" / "videos" / "videoproject 1.mp4"

def main():
    print(f"[VIDEO] Opening local video: {VIDEO_PATH}", flush=True)
    stream = cv2.VideoCapture(str(VIDEO_PATH))
    if not stream.isOpened():
        raise RuntimeError(
            f"Could not open local video at {VIDEO_PATH}."
        )

    print("[PIPELINE] Loading YOLO tracker...", flush=True)
    tracker = AssemblyLineTracker(config_path="config/tracker_params.yaml")

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

    print("[PIPELINE] Video connected. Tracking locked to 24 FPS...", flush=True)

    # 24 FPS Timing Math
    TARGET_FPS = 24
    TARGET_FRAME_TIME = 1.0 / TARGET_FPS

    while True:
        loop_start_time = time.time()

        ret, frame = stream.read()
        if not ret or frame is None:
            print("[VIDEO] End of local video reached.", flush=True)
            break

        ai_start_time = time.time()

        annotated_frame, box_data = tracker.process_frame(
            frame.copy(),
            frame_timestamp=time.time(),
        )
        
        ai_end_time = time.time()
        ai_ms = (ai_end_time - ai_start_time) * 1000
        
        cv2.putText(annotated_frame, f"AI: {ai_ms:.1f} ms | Target: 24 FPS", (10, 65), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow(WINDOW_NAME, annotated_frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        # --- The 24 FPS Pacer ---
        # Calculate how long this whole loop took
        elapsed_time = time.time() - loop_start_time
        
        # If we finished faster than 41.6ms, sleep for the remainder to lock at 24 FPS
        time_to_sleep = TARGET_FRAME_TIME - elapsed_time
        if time_to_sleep > 0:
            time.sleep(time_to_sleep)

    stream.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
