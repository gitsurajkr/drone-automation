"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"
import { Badge } from "@/components/ui/badge"
import { Plane, ArrowUp, ArrowDown, ArrowLeft, ArrowRight, RotateCcw, RotateCw } from "lucide-react"
import type { DroneData } from "@/hooks/use-drone-data"
import toast from "react-hot-toast"

interface ControlPanelProps {
  onCommand: (command: string, payload?: any) => Promise<any>
  droneData?: DroneData | null
  isConnected?: boolean
  pythonConnected?: boolean
  droneConnected?: boolean
  setDroneConnected?: (val: boolean) => void
}

export function ControlPanel({ onCommand, droneData, isConnected, pythonConnected, droneConnected, setDroneConnected }: ControlPanelProps) {
  const [throttle, setThrottle] = useState<number[]>([50])
  const [connProcessing, setConnProcessing] = useState(false)
  const [localArmed, setLocalArmed] = useState<boolean>(droneData?.armed ?? false)
  const [flightMode, setFlightMode] = useState<string>(droneData?.mode ?? "-")

  useEffect(() => {
    if (droneData) {
      setLocalArmed(droneData.armed ?? false)
      setFlightMode(droneData.mode ?? "-")
    }
  }, [droneData])

  const handleCommandAsync = async (command: string, payload?: any) => {
    setConnProcessing(true)
    try {
      const response = await onCommand(command, payload)

      // Handle response and update drone connection status
      if (response && typeof response === 'object' && 'drone_connected' in response) {
        setDroneConnected?.(response.drone_connected as boolean)
      }

      // Success toast messages based on actual response
      if (command === "connect") {
        const connected = response && typeof response === 'object' && response.drone_connected
        if (connected) {
          toast.success("Drone connected successfully!")
        } else {
          toast.error("Drone connection failed - WebSocket OK but no drone")
        }
      } else if (command === "disconnect") {
        toast.success("Drone disconnected")
        setDroneConnected?.(false)
      } else if (command === "arm") {
        toast.success("Drone ARMED - Ready for flight")
        setLocalArmed(true)
      } else if (command === "disarm") {
        toast.success("Drone DISARMED - Safe state")
        setLocalArmed(false)
      } else if (command === "emergency_disarm") {
        toast.success("EMERGENCY DISARM successful")
        setLocalArmed(false)
      } else if (command === "land") {
        toast.success("Landing initiated")
      } else if (command === "rtl") {
        toast.success("Return to Launch initiated")
      } else if (command === "fly_timed") {
        toast.success("Timed flight mission started!")
      } else {
        toast.success(`Command "${command}" executed`)
      }

    } catch (e) {
      const err: any = e
      const errorMsg = err?.detail ?? err?.message ?? String(err)

      // Error toast messages
      if (command === "connect") {
        toast.error(`Connection failed: ${errorMsg}`)
      } else if (command === "disconnect") {
        toast.error(`Disconnect failed: ${errorMsg}`)
      } else if (command === "arm") {
        toast.error(`Failed to ARM: ${errorMsg}`)
      } else if (command === "disarm") {
        toast.error(`Failed to DISARM: ${errorMsg}`)
      } else if (command === "emergency_disarm") {
        toast.error(`EMERGENCY DISARM FAILED: ${errorMsg}`)
      } else if (command === "land") {
        toast.error(`Landing failed: ${errorMsg}`)
      } else if (command === "rtl") {
        toast.error(`Return to Launch failed: ${errorMsg}`)
      } else if (command === "fly_timed") {
        toast.error(`Timed flight mission failed: ${errorMsg}`)
      } else {
        toast.error(`Failed: ${command} - ${errorMsg}`)
      }
    } finally {
      setConnProcessing(false)
    }
  }


  const handleToggleArm = () => {
    const cmd = localArmed ? "disarm" : "arm"
    handleCommandAsync(cmd)
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <Plane className="h-5 w-5" />
            Control Panel
          </CardTitle>
          <div className="flex items-center gap-4">
            <div className="text-sm flex items-center gap-3">
              <div className="flex items-center gap-2">
                <span className={isConnected ? "text-green-500" : "text-red-500"}>●</span>
                <span className="font-medium">{isConnected ? "Connected" : "Disconnected"}</span>
              </div>
              <Badge variant={localArmed ? "destructive" : "secondary"}>{localArmed ? "ARMED" : "DISARMED"}</Badge>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Connection Controls */}
        <div className="flex gap-2 items-center">
          <Button
            onClick={() => handleCommandAsync(droneConnected ? "disconnect" : "connect")}
            disabled={connProcessing || !isConnected}
            variant={droneConnected ? "destructive" : "default"}
            className={`min-w-[100px] ${connProcessing ? 'opacity-50' : ''}`}
          >
            {connProcessing ? (
              <span className="flex items-center gap-2">
                <span className="animate-spin">⏳</span>
                {droneConnected ? "Disconnecting..." : "Connecting..."}
              </span>
            ) : (
              droneConnected ? "🔴 Disconnect" : "🟢 Connect"
            )}
          </Button>

          <Button
            onClick={() => handleCommandAsync("status")}
            disabled={connProcessing || !isConnected}
            variant="outline"
            size="sm"
          >
            Status
          </Button>
        </div>

        {/* Arm/Disarm Controls */}
        <div className="flex gap-2 items-center">
          <Button
            onClick={handleToggleArm}
            disabled={connProcessing || !droneConnected}
            variant={localArmed ? "destructive" : "default"}
          >
            {localArmed ? "DISARM" : "ARM"}
          </Button>

          <Button
            onClick={() => handleCommandAsync("emergency_disarm")}
            disabled={connProcessing || pythonConnected !== true || !localArmed}
            variant="destructive"
            size="sm"
          >
            EMERGENCY DISARM
          </Button>
        </div>

        {/* Throttle */}
        <div>
          <p className="text-sm font-medium mb-2">Throttle</p>
          <div className="flex items-center gap-4">
            <Slider value={throttle} onValueChange={setThrottle} max={100} step={1} className="flex-1" />
            <div className="w-12 text-right">{throttle[0]}%</div>
          </div>
        </div>

        {/* Directional controls */}
        <div className="grid grid-cols-3 gap-2">
          <div></div>
          <Button variant="outline" size="sm" onClick={() => handleCommandAsync("move_forward")}><ArrowUp className="h-4 w-4" /></Button>
          <div></div>

          <Button variant="outline" size="sm" onClick={() => handleCommandAsync("move_left")}><ArrowLeft className="h-4 w-4" /></Button>
          <Button variant="outline" size="sm" onClick={() => handleCommandAsync("move_up")}>↑</Button>
          <Button variant="outline" size="sm" onClick={() => handleCommandAsync("move_right")}><ArrowRight className="h-4 w-4" /></Button>

          <Button variant="outline" size="sm" onClick={() => handleCommandAsync("rotate_left")}><RotateCcw className="h-4 w-4" /></Button>
          <Button variant="outline" size="sm" onClick={() => handleCommandAsync("move_backward")}><ArrowDown className="h-4 w-4" /></Button>
          <Button variant="outline" size="sm" onClick={() => handleCommandAsync("rotate_right")}><RotateCw className="h-4 w-4" /></Button>
        </div>

        {/* Flight Controls */}
        <div className="flex gap-2 flex-wrap">
          <Button
            variant="default"
            onClick={() => handleCommandAsync("takeoff")}
            disabled={connProcessing || pythonConnected !== true || !localArmed}
          >
            Takeoff
          </Button>
          <Button
            variant="outline"
            onClick={() => handleCommandAsync("land")}
            disabled={connProcessing || pythonConnected !== true || !localArmed}
          >
            Land
          </Button>
          <Button
            variant="secondary"
            onClick={() => handleCommandAsync("rtl")}
            disabled={connProcessing || pythonConnected !== true || !localArmed}
          >
            Return Home
          </Button>
        </div>

        {/* Timed Flight Mission */}
        <div className="space-y-2 border-t pt-4">
          <p className="text-sm font-medium">Timed Flight Mission</p>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs text-muted-foreground">Altitude (m)</label>
              <input
                type="number"
                min="1"
                max="30"
                defaultValue="5"
                className="w-full px-2 py-1 text-sm border rounded"
                id="mission-altitude"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground">Duration (s)</label>
              <input
                type="number"
                min="1"
                max="300"
                defaultValue="5"
                className="w-full px-2 py-1 text-sm border rounded"
                id="mission-duration"
              />
            </div>
          </div>
          <Button
            variant="default"
            size="sm"
            onClick={() => {
              const altitude = parseFloat((document.getElementById('mission-altitude') as HTMLInputElement)?.value || '5')
              const duration = parseFloat((document.getElementById('mission-duration') as HTMLInputElement)?.value || '5')
              handleCommandAsync("fly_timed", { altitude, duration })
            }}
            disabled={connProcessing || pythonConnected !== true || !localArmed}
            className="w-full"
          >
            🚁 Start Timed Mission
          </Button>
        </div>

        {/* Flight info */}
        <div className="text-xs text-muted-foreground space-y-1">
          <div className="flex justify-between">
            <span>Mode:</span>
            <span>{flightMode}</span>
          </div>
          <div className="flex justify-between">
            <span>Armed:</span>
            <span className={localArmed ? "text-red-400" : "text-green-400"}>{localArmed ? "YES" : "NO"}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
