# Smart Assembly Line: Carton Tracking & Orientation

## Project Overview
This project provides a real-time computer vision pipeline designed for industrial assembly lines. It utilizes a hybrid approach, combining a fine-tuned YOLO object detection model with OpenCV geometric analysis to track moving carton boxes, calculate their time on the line, and detect their exact rotational angle.

This system is designed to be lightweight enough for edge deployment (e.g., Raspberry Pi) while providing highly accurate data for robotic arm synchronization and PLC control.

## Core Features
* **Persistent Tracking:** Uses the ByteTrack algorithm to assign and hold unique IDs for each carton, preventing flickering.
* **Digital ROI Fence:** Includes a calibration tool to map the exact polygonal shape of the conveyor belt, filtering out background objects and shelves.
* **Adaptive Orientation:** Uses OpenCV with Otsu's Binarization to dynamically adapt to factory lighting changes and calculate the exact angle of the box.
* **Production Analytics:** Automatically logs entry times, calculates process duration, and keeps a running count of completed boxes.

## Installation
1. Ensure you have Python 3.8 or 3.9 installed.
2. Clone this repository to your local machine.
3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt

## Project Directory
SmartAssemblyLine/
├── config/                 # ALL magic numbers go here
│   ├── tracker_params.yaml # ROI polygons, min_area, lifespan rules
│   └── yolov8_botsort.yaml # DeepSORT/BotSort configs
├── data/
│   ├── sample_videos/      # Test footage
│   └── weights/            # Best model checkpoints (.pt, .onnx, .engine)
├── deployment/             # Edge deployment assets
│   ├── docker/             
│   ├── ros2_nodes/         # ROS2 wrappers for your vision pipeline
│   └── tensorrt/           # Exported models for the Pi 5
├── docs/                   # Documentation, wiring diagrams for ESP32
├── src/                    # Core library (NO executable scripts here)
│   ├── __init__.py
│   ├── core/               
│   │   ├── tracking.py     # YOLO + BotSort wrapper
│   │   └── orientation.py  # OpenCV angle calculation logic
│   └── utils/
│       ├── geometry.py     # ROI polygon math
│       └── logger.py       # Production analytics logging
├── scripts/                # Executable entry points
│   ├── train_model.py      
│   ├── run_calibration.py  
│   └── run_pipeline.py     # Main loop (formerly ModelTest.py)
├── requirements.txt
└── README.md