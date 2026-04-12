import cv2
from src.core.tracking import AssemblyLineTracker

def main():
    tracker = AssemblyLineTracker(config_path="config/tracker_params.yaml")
    cap = cv2.VideoCapture('data/videos/conveyor.mp4')

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break

        # The class handles all the heavy lifting
        frame_timestamp = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        if frame_timestamp <= 0:
            frame_timestamp = None
        annotated_frame, box_data = tracker.process_frame(
            frame,
            frame_timestamp=frame_timestamp,
        )

        cv2.imshow("Production Tracker", annotated_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
