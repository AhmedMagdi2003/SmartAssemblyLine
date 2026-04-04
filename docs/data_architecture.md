# Data Architecture & Streaming Pipeline

This document outlines how data is generated, transferred, and stored within the Smart Assembly Line system. The architecture relies on an **Event-Driven Publisher/Subscriber model** using MQTT.

## 1. Data Generation (The Trigger)
Data is **not** streamed continuously frame-by-frame. To preserve network bandwidth and database integrity, a data payload is generated exactly **once per carton**.

The trigger occurs when a tracked object meets two conditions:
1. Its center Y-coordinate crosses the `FINISH_LINE_Y` boundary.
2. It has been tracked continuously for longer than `MIN_LIFESPAN_SEC` (filters out false positives).

## 2. The JSON Payload
When triggered, the system calculates the box's orientation and generates a localized JSON payload. 

**Example Payload:**
`​`​`json
{
  "uuid": "BOX-20260404-Morning_Shift-0142",
  "yolo_session_id": 15,
  "timestamp_iso": "2026-04-04T08:21:31.045123",
  "shift": "Morning_Shift",
  "shift_count": 142,
  "transit_time_sec": 4.52,
  "orientation_deg": 12.5,
  "status": "COMPLETED"
}
`​`​`

## 3. Data Transfer (MQTT)
* **Protocol:** MQTT (via Mosquitto)
* **Topic:** `factory/assembly/boxes`
* **Frequency:** Asynchronous (Fires instantly upon a box crossing the line).
* **Broker:** Currently running on `localhost:1883` (can be updated to a cloud or Raspberry Pi IP in `tracker_params.yaml`).

## 4. Permanent Storage
Data is caught by a background subscriber script (`src/data/logger.py`) and written to disk.
* **Storage Format:** Comma-Separated Values (.csv)
* **Storage Location:** `data/logs/` directory.
* **File Rotation:** The logger dynamically creates a new CSV file for every unique combination of Date and Shift (e.g., `shift_Morning_Shift_2026-04-04.csv`).
* **Write Frequency:** Appended line-by-line in real-time as MQTT messages arrive.