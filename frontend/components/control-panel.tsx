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
    onCommand: (command: string, payload?: any) => void
    droneData?: DroneData | null
    isConnected?: boolean
    pythonConnected?: boolean | null
}

export function ControlPanel({ onCommand, droneData, isConnected, pythonConnected }: ControlPanelProps) {
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

    const handleCommand = (command: string, payload?: any) => {
        // send command to parent (sendCommand lives in the hook)
        onCommand(command, payload)
    }

    const handleToggleArm = () => {
        const cmd = localArmed ? "disarm" : "arm"
        handleCommand(cmd)
        setLocalArmed(!localArmed)
    }

    // When connection state changes, dismiss the loading toast and show a success/error toast
    useEffect(() => {
        const id = (window as any).__lastConnToastId
        if (typeof id !== "undefined") {
            toast.dismiss(id)
            if (isConnected) toast.success("Connected to backend")
            else toast.error("Disconnected from backend")
            delete (window as any).__lastConnToastId
            setConnProcessing(false)
        }
    }, [isConnected])

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
                        onClick={() => {
                            const action = isConnected ? "disconnect" : "connect"
                            const id = toast.loading(action === "connect" ? "Connecting..." : "Disconnecting...")
                                ; (window as any).__lastConnToastId = id
                            setConnProcessing(true)
                            try {
                                handleCommand(action)
                            } catch (e) {
                                toast.dismiss(id)
                                toast.error("Failed to send command")
                                setConnProcessing(false)
                            }
                        }}
                        disabled={pythonConnected === false}
                    >
                        {connProcessing ? (isConnected ? "Disconnecting..." : "Connecting...") : (isConnected ? "Disconnect" : "Connect")}
                    </Button>

                    <Button onClick={() => handleToggleArm()} disabled={pythonConnected === false}>{localArmed ? "DISARM" : "ARM"}</Button>
                </div>

                <div>
                    <p className="text-sm font-medium mb-2">Throttle</p>
                    <div className="flex items-center gap-4">
                        <Slider value={throttle} onValueChange={setThrottle} max={100} step={1} className="flex-1" />
                        <div className="w-12 text-right">{throttle[0]}%</div>
                    </div>
                </div>

                <div className="grid grid-cols-3 gap-2">
                    <div></div>
                    <Button variant="outline" size="sm" onClick={() => handleCommand("move_forward")}>
                        <ArrowUp className="h-4 w-4" />
                    </Button>
                    <div></div>

                    <Button variant="outline" size="sm" onClick={() => handleCommand("move_left")}>
                        <ArrowLeft className="h-4 w-4" />
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => handleCommand("move_up")}>
                        ↑
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => handleCommand("move_right")}>
                        <ArrowRight className="h-4 w-4" />
                    </Button>

                    <Button variant="outline" size="sm" onClick={() => handleCommand("rotate_left")}>
                        <RotateCcw className="h-4 w-4" />
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => handleCommand("move_backward")}>
                        <ArrowDown className="h-4 w-4" />
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => handleCommand("rotate_right")}>
                        <RotateCw className="h-4 w-4" />
                    </Button>
                </div>

                <div className="flex gap-2">
                    <Button variant="destructive" onClick={() => handleCommand("emergency_stop")}>
                        EMERGENCY STOP
                    </Button>
                    <Button onClick={() => handleCommand("rtl")}>Return Home</Button>
                </div>

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





