import cv2
import numpy as np
points = []

def mouse_callback(event, x, y,flag,param):
    if event == cv2.EVENT_LBUTTONDOWN:
        print(f"X:{x},Y:{y}]")
        points.append([x, y])   
    if event == cv2.EVENT_RBUTTONDOWN and len(points)>1:
        points.pop()

video_path = 'data/videos/test_video.mp4'
cap = cv2.VideoCapture(video_path)

cv2.namedWindow("Calibration Tool")

cv2.setMouseCallback("Calibration Tool", mouse_callback)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    for point in points:
        cv2.circle(frame, (point[0], point[1]), 5, (0, 0, 255), -1)

    if len(points) > 1:
        pts_array = np.array(points, np.int32).reshape((-1, 1, 2))
        cv2.polylines(frame, [pts_array], False, (0, 255, 0), 2)

    cv2.imshow("Calibration Tool", frame)

    key = cv2.waitKey(33) & 0xFF

    if key == 27:
        break

    elif key == ord(' '):  # pause
        print("Paused: click to add points | ENTER to resume")

        paused_frame = frame.copy()

        while True:
            temp_frame = paused_frame.copy()

            # redraw points
            for point in points:
                cv2.circle(temp_frame, (point[0], point[1]), 5, (0, 0, 255), -1)

            if len(points) > 1:
                pts_array = np.array(points, np.int32).reshape((-1, 1, 2))
                cv2.polylines(temp_frame, [pts_array], False, (0, 255, 0), 2)

            cv2.imshow("Calibration Tool", temp_frame)

            key2 = cv2.waitKey(1) & 0xFF

            if key2 == 13 or key2 == 10: 
                break

            elif key2 == 27:
                cap.release()
                cv2.destroyAllWindows()
                exit()

cap.release()
cv2.destroyAllWindows()

# FINAL OUTPUT
print("\n--- COPY THIS LINE ---")
print(f"zone_polygon = np.array({points}, np.int32)")
print("----------------------")