from pathlib import Path
import sys
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np
import time
from src.comms.receiver import RawSocketStream

points = []
saved_polygon = []
config_path = PROJECT_ROOT / "config" / "tracker_params.yaml"

try:
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    existing_polygon = config.get("roi", {}).get("polygon", [])
    if existing_polygon:
        saved_polygon = [list(point) for point in existing_polygon]
        print(f"Loaded existing belt polygon from config: {saved_polygon}")
        print("Calibration starts with no editable points. Left-click to add new points.")
except Exception as e:
    print(f"Could not load existing config points: {e}")


def draw_polygon(frame, polygon_points, point_color, line_color, closed):
    if not polygon_points:
        return

    for point in polygon_points:
        cv2.circle(frame, (point[0], point[1]), 5, point_color, -1)

    if len(polygon_points) > 1:
        pts_array = np.array(polygon_points, np.int32).reshape((-1, 1, 2))
        cv2.polylines(frame, [pts_array], closed and len(polygon_points) > 2, line_color, 2)


def mouse_callback(event, x, y,flag,param):
    if event == cv2.EVENT_LBUTTONDOWN:
        print(f"X:{x},Y:{y}]")
        points.append([x, y])   
    if event == cv2.EVENT_RBUTTONDOWN and len(points) > 0:
        points.pop()

# Stream configuration from Pi camera
stream = RawSocketStream(ip='deltapi.local', port=1234).start()
time.sleep(1.0) # Wait for stream startup

cv2.namedWindow("Calibration Tool", cv2.WINDOW_NORMAL)
cv2.setMouseCallback("Calibration Tool", mouse_callback)

while True:
    ret, frame = stream.read()
    if not ret or frame is None:
        time.sleep(0.01)
        continue

    display_frame = frame.copy()
    draw_polygon(display_frame, saved_polygon, (255, 255, 0), (255, 255, 0), True)
    draw_polygon(display_frame, points, (0, 0, 255), (0, 255, 0), False)

    cv2.imshow("Calibration Tool", display_frame)

    key = cv2.waitKey(33) & 0xFF

    if key == 27:
        break

    elif key == ord('c') or key == ord('C'):
        points.clear()
        print("Cleared all points.")

    elif key == ord(' '):  # pause
        print("Paused: click to add points | ENTER to resume | 'c' to clear")

        paused_frame = frame.copy()

        while True:
            temp_frame = paused_frame.copy()

            draw_polygon(temp_frame, saved_polygon, (255, 255, 0), (255, 255, 0), True)
            draw_polygon(temp_frame, points, (0, 0, 255), (0, 255, 0), False)

            cv2.imshow("Calibration Tool", temp_frame)

            key2 = cv2.waitKey(1) & 0xFF

            if key2 == 13 or key2 == 10: 
                break

            elif key2 == ord('c') or key2 == ord('C'):
                points.clear()
                print("Cleared all points.")

            elif key2 == 27:
                stream.stop()
                cv2.destroyAllWindows()
                exit()

stream.stop()
cv2.destroyAllWindows()

# FINAL OUTPUT
print("\n--- COPY THIS LINE ---")
print(f"zone_polygon = np.array({points}, np.int32)")
print("----------------------")

if points:
    save_choice = input("Do you want to save the new polygon points directly to tracker_params.yaml? (y/n) [y]: ").strip().lower() != 'n'
    if save_choice:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            import re
            new_polygon_str = f"polygon: {points}"
            updated_content, count = re.subn(r"polygon:\s*\[.*\]", new_polygon_str, content)
            
            if count > 0:
                with open(config_path, "w", encoding="utf-8") as f:
                    f.write(updated_content)
                print(f"Successfully saved new polygon points to {config_path}")
            else:
                print("Could not locate 'polygon' key in tracker_params.yaml to auto-save.")
        except Exception as e:
            print(f"Error saving to tracker_params.yaml: {e}")


# tracking -----------------------------




from pathlib import Path import sys import time import cv2 # Ensure project root is in path PROJECT_ROOT = Path(__file__).resolve().parents[1] if sys.path[0] != str(PROJECT_ROOT): sys.path.insert(0, str(PROJECT_ROOT)) from src.core.tracking import AssemblyLineTracker # Your working RTSP stream STREAM_URL = "rtsp://deltapi.local:8554/cam" WINDOW_NAME = "Production Tracker" from src.comms.receiver import RawSocketStream def main(): print(f"[NETWORK] Starting stream listener...", flush=True) try: stream = RawSocketStream(ip='deltapi.local', port=1234).start() except Exception as exc: raise RuntimeError( "Could not open the camera stream at deltapi.local:1234. " "Make sure the Pi FFmpeg sender is running and reachable on the local network." ) from exc print("[NETWORK] Waiting for first camera frame...", flush=True) startup_deadline = time.time() + 10.0 while time.time() < startup_deadline: ret, frame = stream.read() if ret and frame is not None: print("[NETWORK] Camera stream is live.", flush=True) break if stream.stopped: stream.stop() raise RuntimeError( f"Camera stream stopped before delivering a frame. " f"Last error: {stream.connection_error or 'unknown'}" ) time.sleep(0.05) else: stream.stop() raise RuntimeError( "Timed out waiting for the camera stream. " "Make sure the Pi FFmpeg sender is running on tcp://deltapi.local:1234." ) print("[PIPELINE] Loading YOLO tracker...", flush=True) tracker = AssemblyLineTracker(config_path="config/tracker_params.yaml") cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL) print("[PIPELINE] Stream connected. Tracking locked to 24 FPS...", flush=True) # 24 FPS Timing Math TARGET_FPS = 24 TARGET_FRAME_TIME = 1.0 / TARGET_FPS while True: loop_start_time = time.time() ret, frame = stream.read() if stream.stopped: print( f"[NETWORK] Camera stream stopped. Last error: " f"{stream.connection_error or 'unknown'}", flush=True, ) break if not ret or frame is None: time.sleep(0.01) continue ai_start_time = time.time() annotated_frame, box_data = tracker.process_frame( frame.copy(), frame_timestamp=time.time(), ) ai_end_time = time.time() ai_ms = (ai_end_time - ai_start_time) * 1000 cv2.putText(annotated_frame, f"AI: {ai_ms:.1f} ms | Target: 24 FPS", (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2) cv2.imshow(WINDOW_NAME, annotated_frame) if cv2.waitKey(1) & 0xFF == ord('q'): break # --- The 24 FPS Pacer --- # Calculate how long this whole loop took elapsed_time = time.time() - loop_start_time # If we finished faster than 41.6ms, sleep for the remainder to lock at 24 FPS time_to_sleep = TARGET_FRAME_TIME - elapsed_time if time_to_sleep > 0: time.sleep(time_to_sleep) stream.stop() cv2.destroyAllWindows() if __name__ == "__main__": main()