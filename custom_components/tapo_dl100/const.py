"""Constants for the Tapo DL100 integration."""

DOMAIN = "tapo_dl100"
PLATFORMS = ["lock", "sensor"]

CONF_IP = "ip"
CONF_CLOUD_USERNAME = "cloud_username"
CONF_CLOUD_PASSWORD = "cloud_password"
CONF_POLL_SECONDS = "poll_seconds"

EVENT_LOCK_CHANGED = "tapo_dl100_lock_event"
SOURCE_HOME_ASSISTANT = "home_assistant"
SOURCE_EXTERNAL = "external"

SERVICE_PROBE_METHODS = "probe_methods"

DEFAULT_POLL_SECONDS = 300
