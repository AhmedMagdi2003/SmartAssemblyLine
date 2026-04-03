import paho.mqtt.client as mqtt
import json

class ProductionStreamer:
    def __init__(self, broker="localhost", port=1883, topic="factory/assembly/boxes"):
        self.client = mqtt.Client()
        self.topic = topic
        try:
            self.client.connect(broker, port, 60)
            self.client.loop_start() # Runs network loop in the background
            print(f"[NETWORK] Connected to MQTT Broker at {broker}:{port}")
        except ConnectionRefusedError:
            print("[WARNING] MQTT Broker not found. Data will not be streamed.")

    def broadcast(self, payload):
        """Converts the dictionary payload to JSON and publishes it."""
        try:
            self.client.publish(self.topic, json.dumps(payload))
        except Exception as e:
            print(f"[ERROR] Failed to publish stream: {e}")