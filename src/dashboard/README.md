# Live Dashboard: Smart Assembly Line

## Overview
This module provides a real-time web dashboard for the Smart Assembly Line project. It bridges the industrial edge (MQTT) with modern web browsers (WebSockets) using a high-speed FastAPI asynchronous server.

When a tracked carton crosses the finish line on the vision node, the data is instantly broadcast to this dashboard with zero-page reloading.

## System Architecture
* **Data Source:** YOLOv8 Vision Node (`src/core/tracking.py`)
* **Message Broker:** Mosquitto MQTT (`localhost:1883`)
* **Backend Bridge:** FastAPI + Uvicorn (`localhost:8000`)
* **Frontend UI:** HTML5 + Vanilla JS (WebSockets)

## Prerequisites
Before running the dashboard, ensure you have the OS-level broker and Python dependencies installed:

```bash
# 1. Install Mosquitto MQTT Broker (Linux/Ubuntu)
sudo apt update
sudo apt install -y mosquitto mosquitto-clients

# 2. Install Python Web Dependencies
pip install fastapi uvicorn websockets paho-mqtt