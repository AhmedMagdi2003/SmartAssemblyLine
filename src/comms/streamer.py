import json

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

class ProductionStreamer:
    def __init__(self, broker="localhost", port=1883, topic="factory/assembly/boxes"):
        self.client = None
        self.topic = topic
        self.is_connected = False
        if mqtt is None:
            print("[WARNING] paho-mqtt is not installed. Data will not be streamed.")
            return

        self.client = mqtt.Client()
        try:
            self.client.connect(broker, port, 60)
            self.client.loop_start() # Runs network loop in the background
            self.is_connected = True
            print(f"[NETWORK] Connected to MQTT Broker at {broker}:{port}")
        except OSError as exc:
            print(f"[WARNING] MQTT Broker not available ({exc}). Data will not be streamed.")

    def broadcast(self, payload):
        """Converts the dictionary payload to JSON and publishes it."""
        try:
            if not self.is_connected:
                return
            self.client.publish(self.topic, json.dumps(payload))
        except Exception as e:
            print(f"[ERROR] Failed to publish stream: {e}")
