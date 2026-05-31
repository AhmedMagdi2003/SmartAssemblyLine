from pathlib import Path
import sys
import os
import threading
import time
import numpy as np
from flask import Flask, Response

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
cv2.setNumThreads(0) 

from src.core.tracking import AssemblyLineTracker

STREAM_URL = "rtsp://192.168.1.50:8554/cam"

# --- Web Server Setup ---
app = Flask(__name__)
output_frame = None
lock = threading.Lock()

class CameraStream:
    def __init__(self, src=STREAM_URL):
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;5000000|fflags;nobuffer|flags;low_delay"
        self.cap = cv2.VideoCapture(src)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not connect to {src}.")
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.ret, self.frame = self.cap.read()
        self.stopped = False

    def start(self):
        threading.Thread(target=self.update, args=(), daemon=True).start()
        return self

    def update(self):
        while not self.stopped:
            self.ret, self.frame = self.cap.read()
            if not self.ret:
                self.stopped = True

    def read(self):
        return self.ret, self.frame

    def stop(self):
        self.stopped = True
        self.cap.release()

def run_ai_pipeline():
    global output_frame
    
    print("[PIPELINE] Loading YOLO tracker...", flush=True)
    tracker = AssemblyLineTracker(config_path="config/tracker_params.yaml")
    
    print("[PIPELINE] Warming up GPU...", flush=True)
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    tracker.process_frame(dummy_frame)

    print(f"[NETWORK] Connecting to {STREAM_URL}...", flush=True)
    stream = CameraStream(STREAM_URL).start()
    time.sleep(1.0) 

    print("[WEB SERVER] Starting! Open http://127.0.0.1:5000 in your Windows browser.", flush=True)
    
    while True:
        ret, frame = stream.read()
        
        if not ret or stream.stopped or frame is None:
            continue

        # Run YOLO inference
        annotated_frame, box_data = tracker.process_frame(
            frame.copy(),
            frame_timestamp=time.time(),
        )
        
        # Safely update the global frame for the web server to grab
        with lock:
            output_frame = annotated_frame.copy()

def generate_web_stream():
    global output_frame
    while True:
        with lock:
            if output_frame is None:
                continue
            # Encode the frame as a JPEG
            flag, encoded_image = cv2.imencode(".jpg", output_frame)
            if not flag:
                continue

        # Yield the image in a byte format the browser can stream
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + 
               bytearray(encoded_image) + b'\r\n')

@app.route("/")
def index():
    return """
    <html>
        <head>
            <title>Smart Assembly Line AI Feed</title>
            <style>
                body { background-color: #121212; color: white; font-family: sans-serif; text-align: center; margin-top: 50px; }
                img { border: 3px solid #00FF00; border-radius: 10px; max-width: 80%; box-shadow: 0px 0px 20px #00FF00; }
            </style>
        </head>
        <body>
            <h1>Live Production Tracker</h1>
            <img src="/video_feed" />
        </body>
    </html>
    """

@app.route("/video_feed")
def video_feed():
    return Response(generate_web_stream(), mimetype="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    # Start the AI in the background
    threading.Thread(target=run_ai_pipeline, daemon=True).start()
    
    # Start the web server on the main thread
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)