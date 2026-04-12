import json
import csv
from pathlib import Path

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

BROKER = "localhost"
TOPIC = "factory/assembly/boxes"
LOG_DIR = Path(__file__).resolve().parents[2] / "data" / "logs"
FIELDNAMES = [
    "uuid",
    "yolo_session_id",
    "timestamp_iso",
    "shift",
    "shift_count",
    "transit_time_sec",
    "orientation_deg",
    "status",
]

LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_log_path(payload, log_dir=LOG_DIR):
    """Build the daily per-shift CSV path for a payload."""
    shift = payload.get("shift", "Unknown")
    date_str = payload.get("timestamp_iso", "0000-00-00")[:10]
    return Path(log_dir) / f"shift_{shift}_{date_str}.csv"


def handle_csv_logging(payload, log_dir=LOG_DIR):
    """Routes the incoming data to the correct shift's CSV file."""
    filename = get_log_path(payload, log_dir=log_dir)
    filename.parent.mkdir(parents=True, exist_ok=True)
    file_exists = filename.is_file()
    row = {field: payload.get(field, "") for field in FIELDNAMES}

    with filename.open(mode="a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)

        if not file_exists:
            writer.writeheader()

        writer.writerow(row)
        print(f"[SAVED] Box {payload['yolo_session_id']} -> {filename}")

def on_message(client, userdata, msg):
    """Callback triggered every time a new box crosses the line."""
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        
        # Module 1: Save to CSV
        handle_csv_logging(payload)
        
        # Module 2: (Future) Push to Cloud DB
        # e.g., mongodb_client.insert_one(payload)
        
    except json.JSONDecodeError:
        print("[ERROR] Corrupted payload received.")

if __name__ == "__main__":
    print(f"Starting Data Logger. Listening to {TOPIC}...")
    if mqtt is None:
        raise RuntimeError("paho-mqtt is not installed. Run `pip install -r requirements.txt` first.")
    client = mqtt.Client()
    client.on_message = on_message
    
    client.connect(BROKER, 1883, 60)
    client.subscribe(TOPIC)
    
    # Keep the script running forever, listening for live data
    client.loop_forever()
