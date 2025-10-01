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

export function useDroneData() {
  const [droneData, setDroneData] = useState<DroneData | null>(null)
  const [alerts, setAlerts] = useState<DroneAlert[]>([])
  const [logs, setLogs] = useState<DroneLog[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [telemetryHistory, setTelemetryHistory] = useState<DroneData[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const pendingRef = useRef<Map<string, { resolve: () => void, reject: (err?: any) => void }>>(new Map())



  useEffect(() => {
    let shouldStop = false;
    let retryDelay = 500; // ms

    function connect() {
      const ws = new WebSocket("ws://localhost:4000");
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
          // Prefer relative altitude (alt_rel) if the backend provided it (AGL). Fall back to alt.
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
            // convert attitude (radians) -> degrees for UI and map rotation
            roll: payload.attitude?.roll ?? 0,
            pitch: payload.attitude?.pitch ?? 0,
            yaw: payload.attitude?.yaw ?? 0,
            // prefer explicit payload.heading (0..360) when available, otherwise normalize yaw
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
                pending.resolve();
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
              return; // don't process further as normal event
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

  const sendCommand = async (command: string, payload?: any): Promise<void> => {
    if (wsRef.current && wsRef.current.readyState === 1) {
      const id = Date.now().toString() + Math.random().toString(36).slice(2, 8)
      const msg: any = { type: command, id };
      if (payload !== undefined) msg.payload = payload;

      // Send and create a pending promise that will resolve when backend responds with same id
      const promise = new Promise<void>((resolve, reject) => {
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
    sendCommand,
    notImplemented,
  }
}
