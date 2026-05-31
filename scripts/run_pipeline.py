from pathlib import Path
import sys
import os
import threading
import time
import cv2

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if sys.path[0] != str(PROJECT_ROOT):
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.tracking import AssemblyLineTracker

# Your working RTSP stream
STREAM_URL = "rtsp://192.168.1.50:8554/cam"
WINDOW_NAME = "Production Tracker"

import socket
import cv2
import numpy as np
import threading
import time

# ffmpeg -f v4l2 -framerate 15 -video_size 640x480 -i /dev/video0 -c:v mjpeg -q:v 3 -f mjpeg tcp://0.0.0.0:1234?listen
class RawSocketStream:
    """Bypasses cv2.VideoCapture and kills TCP buffering for true 0-latency."""
    def __init__(self, ip='192.168.1.50', port=1234):
        print(f"[NETWORK] Connecting aggressive raw socket to {ip}:{port}...", flush=True)
        self.frame = None
        self.ret = False
        self.stopped = False
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # THE FIX 1: Kill Nagle's Algorithm. Force packets to send instantly without grouping.
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # THE FIX 2: Increase the receive buffer so we grab whole images in one bite, not tiny pieces.
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        
        self.sock.connect((ip, port))

    def start(self):
        threading.Thread(target=self.update, daemon=True).start()
        return self

    def update(self):
        bytes_data = b''
        while not self.stopped:
            try:
                # Grab a massive chunk of data at once
                chunk = self.sock.recv(65536)
                if not chunk:
                    break
                bytes_data += chunk
                
                # THE FIX 3: Use 'rfind' (reverse find) to search from the END of the data.
                # If 3 frames arrived at the same time, this skips the old ones and only grabs the newest.
                b = bytes_data.rfind(b'\xff\xd9') # Find the LAST End-of-Image marker
                if b != -1:
                    a = bytes_data.rfind(b'\xff\xd8', 0, b) # Find the Start-of-Image right before it
                    
                    if a != -1:
                        jpg_data = bytes_data[a:b+2]
                        # Decode instantly
                        frame = cv2.imdecode(np.frombuffer(jpg_data, dtype=np.uint8), cv2.IMREAD_COLOR)
                        
                        if frame is not None:
                            self.frame = frame
                            self.ret = True
                            
                    # Throw away EVERYTHING before the end marker so we never process old data
                    bytes_data = bytes_data[b+2:]
                    
            except Exception as e:
                print(f"Socket error: {e}")
                break

    def read(self):
        return self.ret, self.frame

    def stop(self):
        self.stopped = True
        self.sock.close()

def main():
    print(f"[NETWORK] Starting stream listener...", flush=True)
    # Change this line:
    stream = RawSocketStream(ip='192.168.1.50', port=1234).start()
    print("[PIPELINE] Loading YOLO tracker...", flush=True)
    tracker = AssemblyLineTracker(config_path="config/tracker_params.yaml")
    

    time.sleep(1.0) 

    print("[PIPELINE] Stream connected. Tracking locked to 15 FPS...", flush=True)

    # 24 FPS Timing Math
    TARGET_FPS = 15
    TARGET_FRAME_TIME = 1.0 / TARGET_FPS

    while True:
        loop_start_time = time.time()

        ret, frame = stream.read()
        if not ret or stream.stopped or frame is None:
            continue

        ai_start_time = time.time()

        annotated_frame, box_data = tracker.process_frame(
            frame.copy(),
            frame_timestamp=time.time(),
        )
        
        ai_end_time = time.time()
        ai_ms = (ai_end_time - ai_start_time) * 1000
        
        cv2.putText(annotated_frame, f"AI: {ai_ms:.1f} ms | Target: 15 FPS", (10, 30), 
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

    stream.stop()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()