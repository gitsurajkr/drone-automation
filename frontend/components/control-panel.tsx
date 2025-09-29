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
  onCommand: (command: string, payload?: any) => Promise<void>
  droneData?: DroneData | null
  isConnected?: boolean
  pythonConnected?: boolean | null
  setPythonConnected?: (val: boolean) => void
}

export function ControlPanel({ onCommand, droneData, isConnected, pythonConnected, setPythonConnected }: ControlPanelProps) {
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
    await onCommand(command, payload)

    if (command === "connect" && setPythonConnected) setPythonConnected(true)
    if (command === "disconnect" && setPythonConnected) setPythonConnected(false)

    if (command === "arm") setLocalArmed(true)
    if (command === "disarm") setLocalArmed(false)
  } catch (e) {
    toast.error(`Failed to execute ${command}`)
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
        <div className="flex gap-2 items-center">
          <Button
  onClick={() => handleCommandAsync(pythonConnected ? "disconnect" : "connect")}
  disabled={connProcessing || pythonConnected === null}
>
  {connProcessing ? (pythonConnected ? "Disconnecting..." : "Connecting...") : pythonConnected ? "Disconnect" : "Connect"}
</Button>

<Button
  onClick={handleToggleArm}
  disabled={connProcessing || pythonConnected !== true}
>
  {localArmed ? "DISARM" : "ARM"}
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

        {/* Emergency / RTL */}
        <div className="flex gap-2">
          <Button variant="destructive" onClick={() => handleCommandAsync("emergency_stop")}>EMERGENCY STOP</Button>
          <Button onClick={() => handleCommandAsync("rtl")}>Return Home</Button>
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
