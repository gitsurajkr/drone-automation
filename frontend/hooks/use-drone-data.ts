"use client"

import { useState, useEffect, useRef } from "react"
import toast from "react-hot-toast"

export interface DroneData {
  altitude: number
  velocity: {
    vx: number
    vy: number
    vz: number
    avgspeed: number
  }
  battery: number
  gps: {
    latitude: number
    longitude: number
  }
  orientation: {
    roll: number
    pitch: number
    yaw: number
    // normalized 0..360 yaw for compass/heading displays
    heading: number
  }
  armed?: boolean
  mode?: string
  ekfOk?: boolean
  satellites?: number
  heading?: number
  groundspeed?: number
  climbRate?: number
  rawPayload?: any
  timestamp: number
}

export interface DroneAlert {
  id: string
  type: "warning" | "error" | "info"
  message: string
  timestamp: number
}

export interface DroneLog {
  id: string
  message: string
  timestamp: number
  type: "telemetry" | "command" | "system"
}

export interface BatteryEmergency {
  isActive: boolean
  batteryLevel: number
  distanceToHome?: number
  altitude: number
  gpsfix: number
  recommendation: string
  reason: string
  timeoutSeconds: number
  promptId: string
}

export function useDroneData() {
  const [droneData, setDroneData] = useState<DroneData | null>(null)
  const [alerts, setAlerts] = useState<DroneAlert[]>([])
  const [logs, setLogs] = useState<DroneLog[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [telemetryHistory, setTelemetryHistory] = useState<DroneData[]>([])
  const [batteryEmergency, setBatteryEmergency] = useState<BatteryEmergency>({
    isActive: false,
    batteryLevel: 0,
    distanceToHome: undefined,
    altitude: 0,
    gpsfix: 0,
    recommendation: '',
    reason: '',
    timeoutSeconds: 10,
    promptId: ''
  })
  const wsRef = useRef<WebSocket | null>(null)
  const pendingRef = useRef<Map<string, { resolve: (value?: any) => void, reject: (err?: any) => void }>>(new Map())



  useEffect(() => {
    let shouldStop = false;
    let retryDelay = 500; // ms

    function connect() {
      const ws = new WebSocket("ws://localhost:4001"); // Updated to match new backend port
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        toast.success("Connected to backend");
        retryDelay = 500; // reset
      };

      ws.onclose = () => {
        setIsConnected(false);
        toast.error("Disconnected from backend");
        if (!shouldStop) {
          setTimeout(() => {
            retryDelay = Math.min(5000, retryDelay * 2);
            connect();
          }, retryDelay);
        }
      };

      ws.onerror = () => {
        toast.error("WebSocket error");
      };

      function mapPayloadToDroneData(payload: any): DroneData {
        const radToDeg = (r: number) => (r ?? 0) * 180 / Math.PI
        // Normalize battery level (some payloads use level, others may be null)
        const batteryLevel = payload.battery?.level ?? payload.battery?.voltage ?? 0;

        return {
          altitude: typeof payload.location?.alt_rel === 'number' ? payload.location.alt_rel : (payload.location?.alt ?? 0),
          velocity: {
            vx: payload.velocity?.vx ?? 0,
            vy: payload.velocity?.vy ?? 0,
            vz: payload.velocity?.vz ?? 0,
            avgspeed: payload.groundspeed ?? (payload.velocity ? Math.sqrt((payload.velocity.vx ?? 0) ** 2 + (payload.velocity.vy ?? 0) ** 2 + (payload.velocity.vz ?? 0) ** 2) : 0),
          },
          battery: batteryLevel ?? 0,
          gps: {
            latitude: payload.location?.lat ?? 0,
            longitude: payload.location?.lon ?? 0,
          },

          orientation: {
            roll: payload.attitude?.roll ?? 0,
            pitch: payload.attitude?.pitch ?? 0,
            yaw: payload.attitude?.yaw ?? 0,
            heading: typeof payload.heading === 'number' ? payload.heading : ((radToDeg(payload.attitude?.yaw ?? 0) + 360) % 360),
          },
          armed: payload.armed ?? false,
          mode: payload.mode ?? payload.flight_mode ?? "unknown",
          ekfOk: payload.ekf?.ok ?? false,
          satellites: payload.gps?.satellites_visible ?? payload.gps?.satellites ?? 0,
          heading: payload.heading ?? 0,
          groundspeed: payload.groundspeed ?? 0,
          climbRate: payload.climb_rate ?? payload.velocity?.vz ?? 0,
          rawPayload: payload,
          timestamp: payload.timestamp ? new Date(payload.timestamp).getTime() : Date.now(),
        };
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          // If this is a response to a pending command, resolve the promise
          if (msg && msg.id) {
            const pending = pendingRef.current.get(msg.id);
            if (pending) {
              if (msg.status && msg.status === 'ok') {
                pending.resolve(msg);
                // Log successful command response
                setLogs((prev) => [
                  ...prev.slice(-99),
                  { id: Date.now().toString(), message: `Command response: ${JSON.stringify(msg)}`, timestamp: Date.now(), type: "system" },
                ]);
              } else {
                pending.reject(msg);
                // Log failed command response
                setLogs((prev) => [
                  ...prev.slice(-99),
                  { id: Date.now().toString(), message: `Command failed: ${JSON.stringify(msg)}`, timestamp: Date.now(), type: "system" },
                ]);
              }
              pendingRef.current.delete(msg.id);
              return;
            }
          }
          // If backend forwarded an error (for example Python backend not connected), show toast
          if (msg && (msg.error || msg.message && typeof msg.message === 'string' && msg.message.toLowerCase().includes('python'))) {
            if (msg.error) toast.error(msg.error)
            else if (msg.message) toast.error(msg.message)
          }
          if (msg.event_type === "DATA" && msg.payload) {
            const mapped = mapPayloadToDroneData(msg.payload);
            setDroneData(mapped);
            setTelemetryHistory((prev) => [...prev.slice(-49), mapped]);
          } else if (msg.event_type === "STATUS") {
            toast(msg.payload);
          } else if (msg.event_type === "ALERT") {
            setAlerts((prev) => [...prev.slice(-9), msg.payload]);
            toast.error(msg.payload.message);
          } else if (msg.type === "battery_emergency") {
            console.log("🚨 Battery emergency received:", msg);
            // Wait for the prompt ID in the next message
            setBatteryEmergency({
              isActive: true,
              batteryLevel: msg.battery_level,
              distanceToHome: msg.distance_to_home,
              altitude: msg.altitude,
              gpsfix: msg.gps_fix,
              recommendation: msg.recommendation,
              reason: msg.reason,
              timeoutSeconds: msg.timeout_seconds,
              promptId: '' // Will be set by battery_emergency_prompt message
            });
          } else if (msg.type === "battery_emergency_prompt") {
            console.log("📡 Battery emergency prompt ID received:", msg.prompt_id);
            setBatteryEmergency(prev => ({
              ...prev,
              promptId: msg.prompt_id
            }));
          } else if (msg.type === "battery_emergency_countdown") {
            console.log("⏰ Battery emergency countdown:", msg.remaining_seconds);
            // Frontend handles its own countdown, but we can log this
          } else if (msg.type === "battery_emergency_action") {
            console.log("✅ Battery emergency action taken:", msg.action);
            setBatteryEmergency(prev => ({
              ...prev,
              isActive: false
            }));
            toast.success(`Emergency action: ${msg.action}`);
          }
          setLogs((prev) => [
            ...prev.slice(-99),
            { id: Date.now().toString(), message: event.data, timestamp: Date.now(), type: "system" },
          ]);
        } catch {
          setLogs((prev) => [
            ...prev.slice(-99),
            { id: Date.now().toString(), message: event.data, timestamp: Date.now(), type: "system" },
          ]);
        }
      };
    }

    connect();

    return () => {
      shouldStop = true;
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  useEffect(() => {
    const handler = () => setLogs([])
    window.addEventListener('logs:clear', handler as EventListener)
    return () => window.removeEventListener('logs:clear', handler as EventListener)
  }, [])

  const sendCommand = (command: string, payload?: any): Promise<any> => {
    if (wsRef.current && wsRef.current.readyState === 1) {
      const id = Date.now().toString() + Math.random().toString(36).slice(2, 8)
      const msg: any = { type: command, id };
      if (payload !== undefined) msg.payload = payload;

      // Send and create a pending promise that will resolve when backend responds with same id
      const promise = new Promise<any>((resolve, reject) => {
        pendingRef.current.set(id, { resolve, reject })
        try {
          wsRef.current?.send(JSON.stringify(msg))
        } catch (e) {
          pendingRef.current.delete(id)
          reject(e)
        }
      })

      setLogs((prev) => [
        ...prev.slice(-99),
        { id: Date.now().toString(), message: `Command sent: ${command}`, timestamp: Date.now(), type: "command" },
      ]);

      return promise
    } else {
      toast.error("WebSocket not connected");
      return Promise.reject(new Error('WebSocket not connected'))
    }
  };


  // Handle battery emergency choice
  const handleBatteryEmergencyChoice = async (choice: 'RTL' | 'LAND') => {
    console.log(`🔄 Sending battery emergency response: ${choice} for prompt ${batteryEmergency.promptId}`);

    try {
      await sendCommand('battery_emergency_response', {
        prompt_id: batteryEmergency.promptId,
        choice: choice
      });

      console.log(`✅ Battery emergency response sent: ${choice}`);

      // Close the modal immediately after sending response
      setBatteryEmergency(prev => ({
        ...prev,
        isActive: false
      }));

      toast.success(`Emergency choice sent: ${choice}`);
    } catch (error) {
      console.error('❌ Failed to send battery emergency response:', error);
      toast.error('Failed to send emergency response');
    }
  };

  // For unimplemented features (ARM, DISARM, etc.)
  const notImplemented = (feature: string) => {
    toast("Not implemented: " + feature);
    setLogs((prev) => [
      ...prev.slice(-99),
      { id: Date.now().toString(), message: `Tried to use: ${feature} (not implemented)`, timestamp: Date.now(), type: "command" },
    ]);
  };

  return {
    droneData,
    alerts,
    logs,
    isConnected,
    telemetryHistory,
    batteryEmergency,
    sendCommand,
    handleBatteryEmergencyChoice,
    notImplemented,
  }
}
