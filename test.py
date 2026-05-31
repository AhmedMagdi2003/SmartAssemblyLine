import cv2
import os

STREAM_URL = "rtsp://192.168.1.50:8554/cam"

def main():
    print(f"1. Connecting to {STREAM_URL}...", flush=True)
    
    # Force TCP for WSL, disable FFmpeg internal buffering, and enable low delay
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;5000000|fflags;nobuffer|flags;low_delay"

    cap = cv2.VideoCapture(STREAM_URL)
    
    if not cap.isOpened():
        print("❌ ERROR: OpenCV completely failed to open the stream.", flush=True)
        return

    # CRITICAL: Force OpenCV to only keep 1 single frame in its stack. 
    # This prevents the 1-2 second lag accumulation.
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    print("2. Stream connected! Waiting for first frame...", flush=True)

    ret, frame = cap.read()
    if not ret:
        print("❌ ERROR: Connected, but the stream is totally empty (no frames).", flush=True)
        return

    print("3. First frame received! Opening window...", flush=True)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ ERROR: Connection dropped mid-stream.", flush=True)
            break

        cv2.imshow("RAW CAMERA TEST", frame)
        
        # Check for 'q' key to quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()