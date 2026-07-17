import socket
import threading
import time
import cv2
import numpy as np

class RawSocketStream:
    """Bypasses cv2.VideoCapture and kills TCP buffering for true 0-latency."""
    def __init__(self, ip='deltapi.local', port=1234):
        print(f"[NETWORK] Connecting aggressive raw socket to {ip}:{port}...", flush=True)
        self.frame = None
        self.ret = False
        self.stopped = False
        self.last_frame_time = 0.0
        self.connection_error = None
        self.endpoint = f"{ip}:{port}"
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(10.0)
        
        # THE FIX 1: Kill Nagle's Algorithm. Force packets to send instantly without grouping.
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        # THE FIX 2: Increase the receive buffer so we grab whole images in one bite, not tiny pieces.
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        
        try:
            self.sock.connect((ip, port))
        except Exception as exc:
            self.connection_error = str(exc)
            try:
                self.sock.close()
            except Exception:
                pass
            raise RuntimeError(
                f"Could not connect to camera stream at {self.endpoint}: {exc}"
            ) from exc

        # THE FIX 3: Set socket to non-blocking AFTER connecting.
        self.sock.setblocking(False)

    def start(self):
        threading.Thread(target=self.update, daemon=True).start()
        return self

    def update(self):
        bytes_data = b''
        while not self.stopped:
            try:
                # THE FIX 4: Drain the entire OS TCP receive buffer in one go.
                # Read all available bytes until the OS buffer is completely empty.
                chunks = []
                while True:
                    try:
                        chunk = self.sock.recv(65536)
                        if not chunk:
                            self.stopped = True
                            break
                        chunks.append(chunk)
                    except BlockingIOError:
                        break
                    except socket.error as e:
                        # WSAEWOULDBLOCK (10035) indicates no more data is currently available on Windows.
                        if e.errno == 10035 or getattr(e, 'winerror', None) == 10035:
                            break
                        raise e
                
                if self.stopped:
                    break
                
                if chunks:
                    bytes_data += b''.join(chunks)
                    
                    # THE FIX 5: Find the LAST complete JPEG frame in the accumulated bytes.
                    b = bytes_data.rfind(b'\xff\xd9') # Find the LAST End-of-Image marker
                    if b != -1:
                        a = bytes_data.rfind(b'\xff\xd8', 0, b) # Find the Start-of-Image right before it
                        
                        if a != -1:
                            jpg_data = bytes_data[a:b+2]
                            # Decode ONLY the single latest frame.
                            frame = cv2.imdecode(np.frombuffer(jpg_data, dtype=np.uint8), cv2.IMREAD_COLOR)
                            
                            if frame is not None:
                                self.frame = frame
                                self.ret = True
                                self.last_frame_time = time.time()
                                self.connection_error = None
                                
                        # Throw away EVERYTHING before the end marker to prevent lag accumulation
                        bytes_data = bytes_data[b+2:]
                
                # Sleep briefly to yield CPU time
                time.sleep(0.001)
                
            except Exception as e:
                self.connection_error = str(e)
                self.stopped = True
                print(f"Socket error on {self.endpoint}: {e}")
                break

    def read(self):
        return self.ret, self.frame

    def has_recent_frame(self, stale_after=2.0):
        if self.last_frame_time <= 0:
            return False
        return (time.time() - self.last_frame_time) <= stale_after

    def stop(self):
        self.stopped = True
        try:
            self.sock.close()
        except Exception:
            pass
