# Smart Assembly Line: Edge Vision & Analytics Pipeline

## Project Overview
This repository contains a real-time, industrial-grade computer vision pipeline designed for automated packing lines. It utilizes a hybrid edge-to-cloud architecture, combining a fine-tuned YOLO object detection model with OpenCV geometric analysis to track cartons, calculate spatial orientation, and stream production metrics.

Designed with modularity in mind, the core vision system operates independently from the data logging and dashboard layers via an MQTT Publisher/Subscriber architecture. This allows for lightweight edge deployment (e.g., Raspberry Pi 5) while offloading heavy data aggregation to a local server or cloud database.

## Core Features
* **Persistent Edge Tracking:** Utilizes BotSort to maintain unique IDs across frames, preventing flickering and handling temporary occlusions.
* **Spatial Orientation Analytics:** Employs Otsu's Binarization and geometric moments to calculate the exact rotational angle (-45° to 45°) of cartons for robotic arm synchronization.
* **Asynchronous MQTT Streaming:** Publishes structured JSON payloads (UUID, ISO timestamps, lifespan, angle) instantly upon a box crossing the finish line, preventing main-loop network blocking.
* **Shift-Aware Production Logging:** Automatically categorizes data into factory shifts, generating dynamic CSV logs for time-series analysis and dashboard integration.
* **Digital ROI Fence:** Features a custom calibration tool to map the exact polygon of the conveyor belt, filtering out background factory noise.

## Repository Architecture
```text
SmartAssemblyLine/
├── config/                 
│   ├── tracker_params.yaml # Centralized thresholds, ROI, and shift schedules
│   └── botsort.yaml        # DeepSORT/BotSort hyper-parameters
├── data/
│   ├── logs/               # Auto-generated CSV shift logs
│   ├── videos/             # Test footage
│   └── weights/            # Best YOLO model checkpoints
├── src/                    
│   ├── comms/               
│   │   └── streamer.py     # MQTT publishing node
│   ├── core/               
│   │   ├── tracking.py     # Main YOLO tracker and frame processing logic
│   │   └── orientation.py  # OpenCV angle calculation math
│   ├── data/
│   │   └── logger.py       # MQTT subscriber for CSV log generation
│   └── utils/
│       └── analytics.py    # UUID generation, timestamps, and shift management
├── scripts/                
│   ├── train.py            # Model training pipeline
│   ├── ROICalibration.py   # Interactive tool to capture belt polygon coordinates
│   └── run_pipeline.py     # Main video loop and system entry point
├── requirements.txt
└── Readme.md
---

### 2. Plain Text Checkpoint & Test Plan

Here is a raw text summary of exactly what the codebase currently does. You can save this as `TEST_PLAN.txt` or use it to prompt other tools/agents so they understand exactly how the system is currently wired.

```text
=== SMART ASSEMBLY LINE: PIPELINE CHECKPOINT ===

1. CURRENT CAPABILITIES
- The system reads a video frame and detects boxes using YOLOv8.
- It filters out boxes outside the calibrated polygon (ROI).
- It ignores boxes that are too small (noise filtering).
- It tracks boxes using BotSort to maintain consistent IDs.
- It measures how long a box has been inside the ROI (lifespan).
- When a box crosses the horizontal "finish line" AND meets the minimum lifespan, it triggers an "Exit Event".

2. THE "EXIT EVENT" WORKFLOW (Fires exactly once per box)
- Step A: The system locks the box ID so it cannot be counted twice.
- Step B: orientation.py calculates the box's angle (-45 to 45 degrees).
- Step C: analytics.py generates a unique UUID (e.g., BOX-20260403-Morning-001), checks the current factory shift, and builds a JSON dictionary.
- Step D: streamer.py instantly broadcasts this JSON payload to the "factory/assembly/boxes" MQTT topic on localhost:1883.

3. THE BACKGROUND LOGGER
- A completely separate script (logger.py) runs in the background.
- It listens to the MQTT topic.
- When it receives a JSON payload, it extracts the Shift and Date.
- It automatically creates or appends to a CSV file (e.g., data/logs/shift_Morning_Shift_2026-04-03.csv).

4. HOW TO RUN A FULL SYSTEM TEST
Step 1: Start the MQTT Broker (must be running on OS level).
Step 2: Open Terminal 1 -> Run `python src/data/logger.py` (It will wait silently).
Step 3: Open Terminal 2 -> Run `python scripts/run_pipeline.py`.
Step 4: Watch the video. Every time a box crosses the line, Terminal 2 should print "[STREAM] Dispatched: BOX-UUID". 
Step 5: Terminal 1 should instantly print "[SAVED] Box X -> shift_file.csv".
S