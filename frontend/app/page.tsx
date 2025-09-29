"use client"

import { useDroneData } from "@/hooks/use-drone-data"
import { TelemetryDashboard } from "@/components/telemetry-dashboard"
import { EnhancedMapView } from "@/components/map-view"
// import { MapPreview } from "@/components/map-preview"
import { VideoFeed } from "@/components/video-feed"
import { ControlPanel } from "@/components/control-panel"
import { AlertsPanel } from "@/components/alerts-panel"
import { LogsPanel } from "@/components/logs-panel"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Map, Grid3X3 } from "lucide-react"
import { useState, useEffect } from "react"

export default function DroneDashboard() {
  const { droneData, alerts, logs, isConnected, telemetryHistory, sendCommand } = useDroneData()
  const [currentView, setCurrentView] = useState<"dashboard" | "map">("dashboard")
  const [pythonConnected, setPythonConnected] = useState<boolean | null>(null)

  useEffect(() => {
    let mounted = true
    const check = async () => {
      try {
        const res = await fetch('http://localhost:4001/health')
        if (!mounted) return
        if (res.ok) {
          const json = await res.json()
          setPythonConnected(Boolean(json.pythonConnected))
        } else {
          setPythonConnected(false)
        }
      } catch (e) {
        if (!mounted) return
        setPythonConnected(false)
      }
    }

    check()
    const id = setInterval(check, 3000)
    return () => {
      mounted = false
      clearInterval(id)
    }
  }, [])

  return (
    <div className="min-h-screen bg-background text-foreground p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold text-balance">FlightOps Console</h1>
          <Badge variant={isConnected ? "default" : "destructive"}>{isConnected ? "Connected" : "Disconnected"}</Badge>
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
          <div className="text-sm text-muted-foreground font-mono">Last Update: {droneData ? new Date(droneData.timestamp).toLocaleTimeString() : '—'}</div>
        </div>
      </div>

      {currentView === "dashboard" ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <TelemetryDashboard data={droneData} history={telemetryHistory} />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* <MapPreview droneData={droneData} onOpenFullMap={() => setCurrentView("map")} isConnected={isConnected} /> */}
              <VideoFeed />
            </div>
          </div>

          <div className="space-y-6">
            <ControlPanel onCommand={sendCommand} droneData={droneData} isConnected={isConnected} pythonConnected={pythonConnected} />
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
          // pass pythonConnected in case EnhancedMapView wants to reflect backend state
          // it's optional there
          // @ts-ignore
          pythonConnected={pythonConnected}
        />
      )}
    </div>
  )
}
