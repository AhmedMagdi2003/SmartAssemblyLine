import json

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None

from src.comms.mqtt_config import configure_mqtt_client, load_mqtt_settings

class ProductionStreamer:
    def __init__(self, broker=None, port=None, topic=None):
        settings = load_mqtt_settings()
        broker = broker or settings["host"]
        port = port or settings["port"]
        self.topic = topic or settings["topic"]
        self.client = None
        self.is_connected = False
        if mqtt is None:
            print("[WARNING] paho-mqtt is not installed. Data will not be streamed.")
            return

        self.client = mqtt.Client()
        try:
            configure_mqtt_client(self.client, settings)
            self.client.connect(broker, port, settings["keepalive"])
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
