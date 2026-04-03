import paho.mqtt.client as mqtt
import json
import csv
import os

BROKER = "localhost"
TOPIC = "factory/assembly/boxes"
LOG_DIR = "../data/logs/"

os.makedirs(LOG_DIR, exist_ok=True)

def handle_csv_logging(payload):
    """Routes the incoming data to the correct shift's CSV file."""
    shift = payload.get("shift", "Unknown")
    
    # Extract just the date (YYYY-MM-DD) from the ISO timestamp
    date_str = payload.get("timestamp_iso", "0000-00-00")[:10] 
    
    # Dynamic filename: e.g., shift_Morning_Shift_2026-04-03.csv
    filename = os.path.join(LOG_DIR, f"shift_{shift}_{date_str}.csv")
    
    file_exists = os.path.isfile(filename)
    
    with open(filename, mode='a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=payload.keys())
        
        # Write headers if it's the first box of the shift
        if not file_exists:
            writer.writeheader()
            
        writer.writerow(payload)
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
    client = mqtt.Client()
    client.on_message = on_message
    
    client.connect(BROKER, 1883, 60)
    client.subscribe(TOPIC)
    
    # Keep the script running forever, listening for live data
    client.loop_forever()