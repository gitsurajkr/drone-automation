WS_HOST = "0.0.0.0"
WS_PORT = 8765
DRONE_ID = "drone_001"
TELEMETRY_INTERVAL = 1

# Connection settings
# For hardware drone, use: "/dev/ttyACM0" or "/dev/ttyUSB0"
# For SITL, use: "tcp:127.0.0.1:5760" or "udp:127.0.0.1:14550"
DEFAULT_CONNECTION_STRING = "/dev/ttyACM0"
DEFAULT_BAUD_RATE = 115200

# SITL auto-detection patterns
SITL_PATTERNS = ["127.0.0.1", "localhost", "tcp:", "udp:", ":14550", ":5760"]