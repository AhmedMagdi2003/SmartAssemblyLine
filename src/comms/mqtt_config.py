import os


DEFAULT_MQTT_HOST = "localhost"
DEFAULT_MQTT_PORT = 1883
DEFAULT_MQTT_TOPIC = "factory/assembly/boxes"
DEFAULT_MQTT_KEEPALIVE = 60
DEFAULT_MQTT_CONTROL_TOPIC = "phone/test"


def _env_flag(name, default=False):
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def load_mqtt_settings():
    return {
        "host": os.getenv("MQTT_HOST", DEFAULT_MQTT_HOST),
        "port": int(os.getenv("MQTT_PORT", str(DEFAULT_MQTT_PORT))),
        "topic": os.getenv("MQTT_TOPIC", DEFAULT_MQTT_TOPIC),
        "username": os.getenv("MQTT_USERNAME"),
        "password": os.getenv("MQTT_PASSWORD"),
        "keepalive": int(os.getenv("MQTT_KEEPALIVE", str(DEFAULT_MQTT_KEEPALIVE))),
        "tls_enabled": _env_flag("MQTT_TLS_ENABLED", default=False),
    }


def load_mqtt_control_settings():
    return {
        "host": os.getenv("MQTT_CONTROL_HOST", os.getenv("MQTT_HOST", DEFAULT_MQTT_HOST)),
        "port": int(os.getenv("MQTT_CONTROL_PORT", os.getenv("MQTT_PORT", str(DEFAULT_MQTT_PORT)))),
        "topic": os.getenv("MQTT_CONTROL_TOPIC", DEFAULT_MQTT_CONTROL_TOPIC),
        "username": os.getenv("MQTT_CONTROL_USERNAME", os.getenv("MQTT_USERNAME")),
        "password": os.getenv("MQTT_CONTROL_PASSWORD", os.getenv("MQTT_PASSWORD")),
        "keepalive": int(
            os.getenv("MQTT_CONTROL_KEEPALIVE", os.getenv("MQTT_KEEPALIVE", str(DEFAULT_MQTT_KEEPALIVE)))
        ),
        "tls_enabled": _env_flag(
            "MQTT_CONTROL_TLS_ENABLED",
            default=_env_flag("MQTT_TLS_ENABLED", default=False),
        ),
    }


def configure_mqtt_client(client, settings):
    username = settings.get("username")
    password = settings.get("password")
    if username:
        client.username_pw_set(username=username, password=password)

    if settings.get("tls_enabled"):
        client.tls_set()
