from pathlib import Path
import sys
import json
import csv
import os

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

DB_IMPORT_ERROR = None
try:
    from src.db.repositories import save_box_event
except Exception as exc:
    save_box_event = None
    DB_IMPORT_ERROR = exc

from src.comms.mqtt_config import configure_mqtt_client, load_mqtt_settings

LOG_DIR = PROJECT_ROOT / "data" / "logs"
FIELDNAMES = [
    "uuid",
    "yolo_session_id",
    "timestamp_iso",
    "shift",
    "shift_date",
    "shift_count",
    "transit_time_sec",
    "orientation_deg",
    "status",
]

LOG_DIR.mkdir(parents=True, exist_ok=True)
MQTT_SETTINGS = load_mqtt_settings()


def _infer_shift_file_date(payload):
    shift_date = payload.get("shift_date")
    if shift_date:
        return str(shift_date)

    uuid_value = str(payload.get("uuid", ""))
    uuid_parts = uuid_value.split("-")
    if len(uuid_parts) >= 4 and len(uuid_parts[1]) == 8 and uuid_parts[1].isdigit():
        encoded_date = uuid_parts[1]
        return f"{encoded_date[:4]}-{encoded_date[4:6]}-{encoded_date[6:]}"

    return str(payload.get("timestamp_iso", "0000-00-00"))[:10]


def get_log_path(payload, log_dir=LOG_DIR):
    """Build the operational shift CSV path for a payload."""
    shift = payload.get("shift", "Unknown")
    date_str = _infer_shift_file_date(payload)
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


def persist_payload(payload, save_to_db=save_box_event, csv_handler=handle_csv_logging):
    """
    Save the payload to the database first, then mirror it to CSV as a backup.
    Returns one of: inserted, duplicate, csv_only.
    """
    if save_to_db is None:
        csv_handler(payload)
        return "csv_only"

    inserted = save_to_db(payload)
    if inserted:
        csv_handler(payload)
        return "inserted"

    print(f"[SKIP] Duplicate payload ignored: {payload.get('uuid', 'UNKNOWN_UUID')}")
    return "duplicate"

def on_message(client, userdata, msg):
    """Callback triggered every time a new box crosses the line."""
    try:
        payload = json.loads(msg.payload.decode('utf-8'))

        result = persist_payload(payload)
        if result == "inserted":
            print(f"[DB] Inserted payload {payload['uuid']}")
        elif result == "csv_only":
            print(f"[DB] Database unavailable, kept CSV backup for {payload['uuid']}")

    except json.JSONDecodeError:
        print("[ERROR] Corrupted payload received.")
    except ValueError as exc:
        print(f"[ERROR] Invalid payload: {exc}")
    except Exception as exc:
        print(f"[ERROR] Failed to persist payload: {exc}")

if __name__ == "__main__":
    print(
        "Starting Data Logger. "
        f"Listening to {MQTT_SETTINGS['topic']} on "
        f"{MQTT_SETTINGS['host']}:{MQTT_SETTINGS['port']}..."
    )
    if mqtt is None:
        raise RuntimeError("paho-mqtt is not installed. Run `pip install -r requirements.txt` first.")
    if save_box_event is None and DB_IMPORT_ERROR is not None:
        print(f"[WARNING] Database layer unavailable at startup: {DB_IMPORT_ERROR}")
    client = mqtt.Client()
    client.on_message = on_message

    configure_mqtt_client(client, MQTT_SETTINGS)
    client.connect(
        MQTT_SETTINGS["host"],
        MQTT_SETTINGS["port"],
        MQTT_SETTINGS["keepalive"],
    )
    client.subscribe(MQTT_SETTINGS["topic"])
    
    # Keep the script running forever, listening for live data
    client.loop_forever()
