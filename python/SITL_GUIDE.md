# SITL (Software In The Loop) Integration Guide

This drone controller now includes enhanced SITL support for safe testing and development.

## 🚁 Features Added

### 1. Automatic SITL Configuration
- **Auto-disables ARMING_CHECK** (sets `ARMING_CHECK=0`) when SITL is detected
- **Detects SITL connections** automatically based on connection string patterns
- **Preserves hardware safety** - only applies to SITL connections

### 2. Enhanced Arming Process
- **Ensures GUIDED mode** before attempting to arm
- **Waits for confirmation** that vehicle is actually armed
- **Better error reporting** with detailed feedback

### 3. Safe Takeoff Function
- **Validates prerequisites** (armed, GUIDED mode)
- **Monitors altitude progress** during takeoff
- **Configurable timeout** and target altitude
- **95% threshold** for takeoff completion

### 4. Maintained WebSocket Integration
- **All existing functionality preserved**
- **New commands added** without breaking changes
- **Real-time telemetry** continues to work

## 🔧 Configuration

### For SITL Testing:
Update your `config.py`:
```python
# SITL connection (choose one)
DEFAULT_CONNECTION_STRING = "tcp:127.0.0.1:5760"  # Standard SITL
# DEFAULT_CONNECTION_STRING = "udp:127.0.0.1:14550"  # Alternative SITL port

DEFAULT_BAUD_RATE = 115200
```

### For Hardware Drone:
```python
# Hardware connection
DEFAULT_CONNECTION_STRING = "/dev/ttyACM0"  # or /dev/ttyUSB0
DEFAULT_BAUD_RATE = 115200
```

## 🚀 New WebSocket Commands

### SITL Setup Command
```json
{
  "type": "sitl_setup",
  "id": "unique_id"
}
```
**Response:**
```json
{
  "status": "ok",
  "detail": "SITL setup successful",
  "id": "unique_id"
}
```

### Enhanced Takeoff Command
```json
{
  "type": "takeoff",
  "payload": {"altitude": 15.0},
  "id": "unique_id"
}
```
**Response:**
```json
{
  "status": "ok",
  "detail": "takeoff to 15.0m successful",
  "id": "unique_id"
}
```

## 🧪 Testing with SITL

### 1. Start SITL Simulator
```bash
# Terminal 1: Start SITL
sim_vehicle.py --console --map --aircraft test

# Wait for "Ready to FLY" message
```

### 2. Update Configuration
```python
# config.py
DEFAULT_CONNECTION_STRING = "tcp:127.0.0.1:5760"
```

### 3. Start Your Application
```bash
# Terminal 2: Start Python WebSocket server
python main.py

# Terminal 3: Start Node.js backend
cd backend && npm run dev

# Terminal 4: Start frontend
cd frontend && npm run dev
```

### 4. Test New Features
1. **Connect**: Click "Connect" - should auto-configure SITL
2. **Arm**: Click "ARM" - should set GUIDED mode and arm
3. **Takeoff**: Use new takeoff command with altitude
4. **Monitor**: Watch real-time telemetry and map updates

## 🔍 Frontend Integration

The frontend automatically receives all new command responses:

```typescript
// Example takeoff usage
const handleTakeoff = async () => {
  try {
    const response = await sendCommand("takeoff", { altitude: 12.0 });
    if (response.status === "ok") {
      toast.success("🚀 Takeoff successful!");
    }
  } catch (error) {
    toast.error("❌ Takeoff failed: " + error.detail);
  }
};
```

## ⚠️ Safety Notes

### SITL vs Hardware Behavior:
- **SITL**: ARMING_CHECK disabled automatically for easy testing
- **Hardware**: ARMING_CHECK remains enabled for safety
- **Auto-detection**: Based on connection string patterns

### Connection Patterns That Trigger SITL Mode:
- `tcp:127.0.0.1:5760`
- `udp:127.0.0.1:14550`
- Any string containing: `127.0.0.1`, `localhost`, `tcp:`, `udp:`, `:14550`, `:5760`

### Hardware Connections (Normal Safety):
- `/dev/ttyACM0`
- `/dev/ttyUSB0`
- `/dev/serial/by-id/...`

## 🐛 Troubleshooting

### "SITL setup failed"
- Check SITL is running: `ps aux | grep sim_vehicle`
- Verify connection string in config.py
- Check SITL console for parameter errors

### "Arming failed"
- Check vehicle mode (should be GUIDED)
- Verify GPS lock in SITL
- Check SITL console for error messages

### "Takeoff failed"
- Ensure vehicle is armed first
- Check altitude is reasonable (1-100m)
- Monitor SITL console for mode changes

## 📊 Example Test Sequence

```bash
# 1. Start SITL
sim_vehicle.py --console --map

# 2. In SITL console, verify ready:
STABILIZE> mode GUIDED
GUIDED> arm throttle
ARMED GUIDED> takeoff 10

# 3. Test via WebSocket:
# Connect -> SITL Setup -> Arm -> Takeoff
```

Your drone controller now provides a complete SITL testing environment while maintaining full compatibility with hardware drones! 🎯