import unittest
from unittest.mock import patch

from src.comms.mqtt_config import configure_mqtt_client, load_mqtt_settings


class FakeClient:
    def __init__(self):
        self.credentials = None
        self.tls_called = False

    def username_pw_set(self, username, password=None):
        self.credentials = (username, password)

    def tls_set(self):
        self.tls_called = True


class MqttConfigTests(unittest.TestCase):
    def test_load_mqtt_settings_uses_defaults(self):
        with patch.dict("os.environ", {}, clear=True):
            settings = load_mqtt_settings()

        self.assertEqual(settings["host"], "localhost")
        self.assertEqual(settings["port"], 1883)
        self.assertEqual(settings["topic"], "factory/assembly/boxes")
        self.assertIsNone(settings["username"])
        self.assertIsNone(settings["password"])
        self.assertFalse(settings["tls_enabled"])

    def test_load_mqtt_settings_reads_auth_and_tls(self):
        with patch.dict(
            "os.environ",
            {
                "MQTT_HOST": "broker.example.com",
                "MQTT_PORT": "8883",
                "MQTT_TOPIC": "factory/assembly/custom",
                "MQTT_USERNAME": "alice",
                "MQTT_PASSWORD": "secret",
                "MQTT_TLS_ENABLED": "true",
                "MQTT_KEEPALIVE": "120",
            },
            clear=True,
        ):
            settings = load_mqtt_settings()

        self.assertEqual(settings["host"], "broker.example.com")
        self.assertEqual(settings["port"], 8883)
        self.assertEqual(settings["topic"], "factory/assembly/custom")
        self.assertEqual(settings["username"], "alice")
        self.assertEqual(settings["password"], "secret")
        self.assertTrue(settings["tls_enabled"])
        self.assertEqual(settings["keepalive"], 120)

    def test_configure_mqtt_client_applies_credentials_and_tls(self):
        client = FakeClient()

        configure_mqtt_client(
            client,
            {
                "username": "alice",
                "password": "secret",
                "tls_enabled": True,
            },
        )

        self.assertEqual(client.credentials, ("alice", "secret"))
        self.assertTrue(client.tls_called)
