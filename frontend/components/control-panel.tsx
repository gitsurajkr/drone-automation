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
      } else if (command === "arm_and_takeoff") {
        toast.success("🚁 ARM + TAKEOFF - Preventing auto-disarm timeout")
        setLocalArmed(true)
      } else if (command === "disarm") {
        toast.success("Drone DISARMED - Safe state")
        setLocalArmed(false)
      } else if (command === "emergency_disarm") {
        toast.success("EMERGENCY DISARM successful")
        setLocalArmed(false)
      } else if (command === "land") {
        toast.success("🏠 Safe Landing (RTL) initiated")
      } else if (command === "rtl") {
        toast.success("Return to Launch initiated")
      } else if (command === "force_land_here") {
        toast("⚠️ FORCE LAND HERE - Dangerous!", { icon: "⚠️" })
      } else if (command === "verify_home") {
        toast.success("📍 Home location verified")
      } else if (command === "fly_timed") {
        toast.success("Timed flight mission started!")
      } else if (command === "set_throttle") {
        toast.success(`Throttle set to ${throttle[0]}%`)
      } else if (command === "release_throttle") {
        toast.success("Throttle control released to autopilot")
      } else if (command === "emergency_land") {
        toast.success("🚨 EMERGENCY LAND initiated!")
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
      } else if (command === "arm_and_takeoff") {
        toast.error(`ARM + TAKEOFF failed: ${errorMsg}`)
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
      } else if (command === "set_throttle") {
        toast.error(`Throttle control failed: ${errorMsg}`)
      } else if (command === "release_throttle") {
        toast.error(`Release throttle failed: ${errorMsg}`)
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
            onClick={() => handleCommandAsync("arm_and_takeoff", { altitude: 5.0 })}
            disabled={connProcessing || !droneConnected || localArmed}
            variant="default"
            className="bg-blue-600 hover:bg-blue-700"
            title="Arm drone and immediately takeoff to prevent auto-disarm timeout"
          >
            🚁 ARM + TAKEOFF
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

        {/* Throttle Control */}
        <div>
          <p className="text-sm font-medium mb-2">Manual Throttle Control</p>
          <div className="flex items-center gap-2 mb-2">
            <Slider
              value={throttle}
              onValueChange={setThrottle}
              max={100}
              step={1}
              className="flex-1"
              disabled={connProcessing || pythonConnected !== true}
            />
            <div className="w-12 text-right text-sm">{throttle[0]}%</div>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleCommandAsync("set_throttle", { throttle: throttle[0] })}
              disabled={connProcessing || pythonConnected !== true}
            >
              Set Throttle
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleCommandAsync("release_throttle")}
              disabled={connProcessing || pythonConnected !== true}
            >
              Release Control
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Manual throttle override for hardware drone control
          </p>
        </div>
        {/* Safety Status */}
        <div className="space-y-2 border-t pt-2">
          <p className="text-sm font-medium">🛡️ Safety Status</p>
          <div className="text-xs space-y-1">
            <div className="flex justify-between">
              <span>Connection:</span>
              <span className={pythonConnected ? "text-green-400" : "text-red-400"}>
                {pythonConnected ? "🟢 CONNECTED" : "🔴 DISCONNECTED"}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Drone:</span>
              <span className={droneConnected ? "text-green-400" : "text-yellow-400"}>
                {droneConnected ? "🟢 READY" : "🟡 NOT CONNECTED"}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Armed:</span>
              <span className={localArmed ? "text-red-400" : "text-green-400"}>
                {localArmed ? "🔴 ARMED" : "🟢 DISARMED"}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Mode:</span>
              <span className="text-blue-400">{flightMode}</span>
            </div>
          </div>
        </div>

        {/* Flight Controls */}
        <div className="space-y-2">
          <div className="flex gap-2 flex-wrap">
            <Button
              variant="default"
              onClick={() => handleCommandAsync("takeoff")}
              disabled={connProcessing || pythonConnected !== true || !localArmed}
            >
              ✈️ Takeoff
            </Button>
            <Button
              variant="outline"
              onClick={() => handleCommandAsync("land")}
              disabled={connProcessing || pythonConnected !== true || !localArmed}
              title="Safe Landing - Returns to Launch Location"
            >
              🏠 Land (RTL)
            </Button>
          </div>

          {/* Advanced Landing Options */}
          <div className="flex gap-2 flex-wrap border-t pt-2">
            
            <Button
              variant="destructive"
              onClick={() => {
                if (confirm("⚠️ DANGEROUS: This will land at current location instead of returning home. Continue?")) {
                  handleCommandAsync("force_land_here")
                }
              }}
              disabled={connProcessing || pythonConnected !== true || !localArmed}
              size="sm"
              className="bg-orange-600 hover:bg-orange-700"
            >
              ⚠️ Force Land Here
            </Button>
          </div>
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
