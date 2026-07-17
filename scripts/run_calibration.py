from pathlib import Path
import sys
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np
import time

points = []
saved_polygon = []

config_path = PROJECT_ROOT / "config" / "tracker_params.yaml"

VIDEO_PATH = PROJECT_ROOT / "data" / "videos" / "videoproject 1.mp4"

try:
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    existing_polygon = config.get("roi", {}).get("polygon", [])

    if existing_polygon:
        saved_polygon = [list(point) for point in existing_polygon]
        print(f"Loaded existing belt polygon from config: {saved_polygon}")
        print(
            "Calibration starts with no editable points. "
            "Left-click to add new points."
        )

except Exception as e:
    print(f"Could not load existing config points: {e}")


def draw_polygon(frame, polygon_points, point_color, line_color, closed):
    if not polygon_points:
        return

    for point in polygon_points:
        cv2.circle(
            frame,
            (point[0], point[1]),
            5,
            point_color,
            -1,
        )

    if len(polygon_points) > 1:
        pts_array = np.array(
            polygon_points,
            np.int32,
        ).reshape((-1, 1, 2))

        cv2.polylines(
            frame,
            [pts_array],
            closed and len(polygon_points) > 2,
            line_color,
            2,
        )


def mouse_callback(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        print(f"X:{x}, Y:{y}")
        points.append([x, y])

    if event == cv2.EVENT_RBUTTONDOWN and len(points) > 0:
        removed_point = points.pop()
        print(f"Removed point: {removed_point}")


# Open local video
stream = cv2.VideoCapture(str(VIDEO_PATH))

if not stream.isOpened():
    raise RuntimeError(
        f"Could not open local video:\n{VIDEO_PATH}"
    )

print(f"Opened local video: {VIDEO_PATH}")

cv2.namedWindow("Calibration Tool", cv2.WINDOW_NORMAL)
cv2.setMouseCallback("Calibration Tool", mouse_callback)

while True:
    ret, frame = stream.read()

    if not ret or frame is None:
        print("End of video reached.")
        break

    display_frame = frame.copy()

    draw_polygon(
        display_frame,
        saved_polygon,
        (255, 255, 0),
        (255, 255, 0),
        True,
    )

    draw_polygon(
        display_frame,
        points,
        (0, 0, 255),
        (0, 255, 0),
        False,
    )

    cv2.imshow("Calibration Tool", display_frame)

    key = cv2.waitKey(33) & 0xFF

    if key == 27:
        break

    elif key == ord("c") or key == ord("C"):
        points.clear()
        print("Cleared all points.")

    elif key == ord(" "):
        print(
            "Paused: click to add points | "
            "ENTER to resume | 'c' to clear"
        )

        paused_frame = frame.copy()

        while True:
            temp_frame = paused_frame.copy()

            draw_polygon(
                temp_frame,
                saved_polygon,
                (255, 255, 0),
                (255, 255, 0),
                True,
            )

            draw_polygon(
                temp_frame,
                points,
                (0, 0, 255),
                (0, 255, 0),
                False,
            )

            cv2.imshow("Calibration Tool", temp_frame)

            key2 = cv2.waitKey(1) & 0xFF

            if key2 == 13 or key2 == 10:
                break

            elif key2 == ord("c") or key2 == ord("C"):
                points.clear()
                print("Cleared all points.")

            elif key2 == 27:
                stream.release()
                cv2.destroyAllWindows()
                raise SystemExit


stream.release()
cv2.destroyAllWindows()

# FINAL OUTPUT
print("\n--- COPY THIS LINE ---")
print(f"zone_polygon = np.array({points}, np.int32)")
print("----------------------")

if points:
    save_choice = (
        input(
            "Do you want to save the new polygon points directly "
            "to tracker_params.yaml? (y/n) [y]: "
        )
        .strip()
        .lower()
        != "n"
    )

    if save_choice:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()

            import re

            new_polygon_str = f"polygon: {points}"

            updated_content, count = re.subn(
                r"polygon:\s*\[.*\]",
                new_polygon_str,
                content,
            )

            if count > 0:
                with open(config_path, "w", encoding="utf-8") as f:
                    f.write(updated_content)

                print(
                    f"Successfully saved new polygon points to "
                    f"{config_path}"
                )

            else:
                print(
                    "Could not locate the 'polygon' key in "
                    "tracker_params.yaml to auto-save."
                )

        except Exception as e:
            print(f"Error saving to tracker_params.yaml: {e}")
