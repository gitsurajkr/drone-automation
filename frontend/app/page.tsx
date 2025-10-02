"use client"

import { useDroneData } from "@/hooks/use-drone-data"
import { TelemetryDashboard } from "@/components/telemetry-dashboard"
import { EnhancedMapView } from "@/components/map-view"
import { VideoFeed } from "@/components/video-feed"
import { ControlPanel } from "@/components/control-panel"
import { AlertsPanel } from "@/components/alerts-panel"
import { LogsPanel } from "@/components/logs-panel"
import { BatteryEmergencyModal } from "@/components/battery-emergency-modal"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Map, Grid3X3 } from "lucide-react"
import { useState, useEffect } from "react"

export default function DroneDashboard() {
  const { droneData, alerts, logs, isConnected, telemetryHistory, batteryEmergency, sendCommand, handleBatteryEmergencyChoice } = useDroneData()
  const [currentView, setCurrentView] = useState<"dashboard" | "map">("dashboard")
  const [pythonConnected, setPythonConnected] = useState<boolean>(false)
  const [droneConnected, setDroneConnected] = useState<boolean>(false)
  const [backendHealthy, setBackendHealthy] = useState<boolean>(false)

  // Poll backend for health every 3s
  useEffect(() => {
    let mounted = true
    const checkHealth = async () => {
      try {
        const res = await fetch("http://localhost:4002/health") // Backend health endpoint
        if (!mounted) return
        if (res.ok) {
          const json = await res.json()
          setBackendHealthy(true)
          // Only update pythonConnected if we got a valid response
          if (typeof json.pythonConnected === 'boolean') {
            setPythonConnected(json.pythonConnected)
          }
        } else {
          setBackendHealthy(false)
          setPythonConnected(false)
        }
      } catch {
        if (!mounted) return
        setBackendHealthy(false)
        setPythonConnected(false)
      }
    }

    // Initial check with slight delay to avoid flickering
    const initialTimeout = setTimeout(checkHealth, 100)
    const intervalId = setInterval(checkHealth, 3000)

    return () => {
      mounted = false
      clearTimeout(initialTimeout)
      clearInterval(intervalId)
    }
  }, [])

  return (
    <div className="min-h-screen bg-background text-foreground p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold text-balance">FlightOps Console</h1>
          <div className="flex gap-2">
            <Badge variant={isConnected ? "default" : "destructive"}>
              {isConnected ? "🟢 Frontend" : "🔴 Frontend"}
            </Badge>
            <Badge variant={backendHealthy ? "default" : "destructive"}>
              {backendHealthy ? "🟢 Backend" : "🔴 Backend"}
            </Badge>
            <Badge variant={pythonConnected ? "default" : "destructive"}>
              {pythonConnected ? "🟢 Python WS" : "🔴 Python WS"}
            </Badge>
            <Badge variant={droneConnected ? "default" : "destructive"}>
              {droneConnected ? "🟢 Drone" : "🔴 Drone"}
            </Badge>
          </div>
          <div className="flex gap-2">
            <Button
              variant={currentView === "dashboard" ? "default" : "outline"}
              size="sm"
              onClick={() => setCurrentView("dashboard")}
            >
              <Grid3X3 className="h-4 w-4 mr-2" />
              Dashboard
            </Button>
            <Button
              variant={currentView === "map" ? "default" : "outline"}
              size="sm"
              onClick={() => setCurrentView("map")}
            >
              <Map className="h-4 w-4 mr-2" />
              Map View
            </Button>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-sm text-muted-foreground font-mono">Last Update: {droneData ? new Date(droneData.timestamp).toLocaleTimeString() : "—"}</div>
        </div>
      </div>

      {currentView === "dashboard" ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <TelemetryDashboard data={droneData} history={telemetryHistory} />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <VideoFeed />
            </div>
          </div>

          <div className="space-y-6">
            <ControlPanel
              onCommand={sendCommand}
              droneData={droneData}
              isConnected={isConnected && backendHealthy}
              pythonConnected={pythonConnected}
              droneConnected={droneConnected}
              setDroneConnected={setDroneConnected}
            />
            <AlertsPanel alerts={alerts} />
            <LogsPanel logs={logs} />
          </div>
        </div>
      ) : (
        <EnhancedMapView
          droneData={droneData}
          onCommand={sendCommand}
          alerts={alerts}
          logs={logs}
          isConnected={isConnected}
        />
      )}

      {/* Battery Emergency Modal */}
      <BatteryEmergencyModal
        isOpen={batteryEmergency.isActive}
        batteryLevel={batteryEmergency.batteryLevel}
        distanceToHome={batteryEmergency.distanceToHome}
        altitude={batteryEmergency.altitude}
        gpsfix={batteryEmergency.gpsfix}
        recommendation={batteryEmergency.recommendation}
        reason={batteryEmergency.reason}
        remainingSeconds={batteryEmergency.remainingSeconds}
        onChoice={handleBatteryEmergencyChoice}
      />
    </div>
  )
}