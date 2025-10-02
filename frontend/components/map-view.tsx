"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { DroneData, DroneAlert, DroneLog } from "@/hooks/use-drone-data"
import { Plus, Trash2, Play, Shield, ShieldOff, Battery, Gauge, Plane, Target } from "lucide-react"
import { useEffect, useState } from "react"
import { InteractiveMap } from "./interactive-map"

interface Waypoint {
    id: string
    lat: number
    lng: number
    altitude: number
    name: string
}

interface Mission {
    altitude: number
    duration: number
    speed: number
}

interface EnhancedMapViewProps {
    droneData: DroneData | null
    onCommand: (command: string, payload?: any) => Promise<any>
    alerts: DroneAlert[]
    logs: DroneLog[]
    isConnected: boolean
}

export function EnhancedMapView({ droneData, onCommand, alerts, logs, isConnected }: EnhancedMapViewProps) {
    const [pathHistory, setPathHistory] = useState<Array<{ lat: number; lng: number }>>([])
    const [waypoints, setWaypoints] = useState<Waypoint[]>([])
    const [isArmed, setIsArmed] = useState(false)
    const [mission, setMission] = useState<Mission>({ altitude: 5, duration: 5, speed: 2 })
    const [newWaypoint, setNewWaypoint] = useState({ name: "", lat: "", lng: "", altitude: "5" })
    const [isProcessing, setIsProcessing] = useState(false)

    // Sync armed state with drone data
    useEffect(() => {
        if (droneData?.armed !== undefined) {
            setIsArmed(droneData.armed)
        }
    }, [droneData?.armed])

    useEffect(() => {
        if (!droneData?.gps) return
        setPathHistory((prev) => [...prev.slice(-100), { lat: droneData.gps.latitude, lng: droneData.gps.longitude }])
    }, [droneData?.gps?.latitude, droneData?.gps?.longitude])

    const addWaypoint = () => {
        if (newWaypoint.name && newWaypoint.lat && newWaypoint.lng) {
            const waypoint: Waypoint = {
                id: Date.now().toString(),
                name: newWaypoint.name,
                lat: Number.parseFloat(newWaypoint.lat),
                lng: Number.parseFloat(newWaypoint.lng),
                altitude: Number.parseFloat(newWaypoint.altitude),
            }
            setWaypoints([...waypoints, waypoint])
            setNewWaypoint({ name: "", lat: "", lng: "", altitude: "50" })
        }
    }

    const removeWaypoint = (id: string) => {
        setWaypoints(waypoints.filter((wp) => wp.id !== id))
    }

    const handleCommand = async (command: string, payload?: any) => {
        setIsProcessing(true)
        try {
            await onCommand(command, payload)
        } finally {
            setIsProcessing(false)
        }
    }

    const startTimedMission = async () => {
        if (!isArmed) {
            alert("Please ARM the drone first!")
            return
        }

        await handleCommand("fly_timed", {
            altitude: mission.altitude,
            duration: mission.duration * 60 // Convert minutes to seconds
        })
    }

    const startWaypointMission = () => {
        // This would be implemented for waypoint missions
        alert("Waypoint missions not yet implemented. Use timed flight instead.")
    }

    return (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 h-[calc(100vh-120px)]  ">
            {/* Main Map Area */}
            <div className="lg:col-span-3 pb-20">
                <InteractiveMap droneData={droneData} onCommand={onCommand} isConnected={isConnected} />
            </div>

            {/* Sidebar */}
            <div className="space-y-4 pb-20">
                {/* Arm/Disarm & Status */}
                <Card className="bg-card border-border">
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Mission Status</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="flex gap-2">
                            <Button
                                variant={isArmed ? "destructive" : "default"}
                                size="sm"
                                className="flex-1"
                                disabled={isProcessing || !isConnected}
                                onClick={() => handleCommand(isArmed ? "disarm" : "arm")}
                            >
                                {isArmed ? <ShieldOff className="h-4 w-4 mr-2" /> : <Shield className="h-4 w-4 mr-2" />}
                                {isProcessing ? "Processing..." : (isArmed ? "Disarm" : "Arm")}
                            </Button>
                        </div>

                        {/* Quick Flight Controls */}
                        <div className="grid grid-cols-3 gap-1">
                            <Button
                                size="sm"
                                variant="outline"
                                disabled={isProcessing || !isArmed || !isConnected}
                                onClick={() => handleCommand("takeoff", { altitude: 5 })}
                            >
                                Takeoff
                            </Button>
                            <Button
                                size="sm"
                                variant="outline"
                                disabled={isProcessing || !isArmed || !isConnected}
                                onClick={() => handleCommand("land")}
                            >
                                Land
                            </Button>
                            <Button
                                size="sm"
                                variant="outline"
                                disabled={isProcessing || !isArmed || !isConnected}
                                onClick={() => handleCommand("rtl")}
                            >
                                RTL
                            </Button>
                        </div>

                        <div className="space-y-2 text-sm">
                            <div className="flex items-center justify-between">
                                <span className="flex items-center gap-2">
                                    <Battery className="h-4 w-4" />
                                    Battery
                                </span>
                                <Badge variant={(droneData?.battery ?? 0) > 20 ? "default" : "destructive"}>{(droneData?.battery ?? 0)}%</Badge>
                            </div>

                            <div className="flex items-center justify-between">
                                <span className="flex items-center gap-2">
                                    <Gauge className="h-4 w-4" />
                                    Speed
                                </span>
                                <span className="font-mono">{(droneData?.velocity.avgspeed ?? 0).toFixed(1)} m/s</span>

                            </div>

                            <div className="flex items-center justify-between">
                                <span className="flex items-center gap-2">
                                    <Plane className="h-4 w-4" />
                                    Altitude
                                </span>
                                <span className="font-mono">{(droneData?.altitude ?? 0).toFixed(1)} m</span>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Mission Planning */}
                <Card className="bg-card border-border">
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base flex items-center gap-2">
                            <Target className="h-4 w-4" />
                            Mission Planning
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid grid-cols-2 gap-2">
                            <div>
                                <Label htmlFor="altitude" className="text-xs">
                                    Altitude (m)
                                </Label>
                                <Input
                                    id="altitude"
                                    type="number"
                                    min="1"
                                    max="30"
                                    value={mission.altitude}
                                    onChange={(e) => setMission({ ...mission, altitude: Number.parseFloat(e.target.value) || 5 })}
                                    className="h-8"
                                />
                            </div>
                            <div>
                                <Label htmlFor="duration" className="text-xs">
                                    Duration (min)
                                </Label>
                                <Input
                                    id="duration"
                                    type="number"
                                    min="0.1"
                                    max="5"
                                    step="0.1"
                                    value={mission.duration}
                                    onChange={(e) => setMission({ ...mission, duration: Number.parseFloat(e.target.value) || 1 })}
                                    className="h-8"
                                />
                            </div>
                        </div>

                        <div>
                            <Label htmlFor="speed" className="text-xs">
                                Max Speed (m/s)
                            </Label>
                            <Input
                                id="speed"
                                type="number"
                                min="0.5"
                                max="10"
                                step="0.5"
                                value={mission.speed}
                                onChange={(e) => setMission({ ...mission, speed: Number.parseFloat(e.target.value) || 2 })}
                                className="h-8"
                            />
                        </div>

                        <div className="text-xs text-muted-foreground bg-muted p-2 rounded">
                            <strong>Mission:</strong> Fly to {mission.altitude}m for {mission.duration} min, then return home
                        </div>

                        <div className="space-y-2">
                            <Button
                                onClick={startTimedMission}
                                disabled={isProcessing || !isArmed || !isConnected}
                                className="w-full"
                                size="sm"
                            >
                                <Play className="h-4 w-4 mr-2" />
                                Start Timed Flight
                            </Button>
                            <Button
                                onClick={startWaypointMission}
                                disabled={waypoints.length === 0 || !isArmed || !isConnected}
                                className="w-full"
                                size="sm"
                                variant="outline"
                            >
                                <Target className="h-4 w-4 mr-2" />
                                Waypoint Mission (WIP)
                            </Button>
                        </div>
                    </CardContent>
                </Card>

                {/* Waypoints */}
                <Card className="bg-card border-border">
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Waypoints</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="space-y-2">
                            <Input
                                placeholder="Waypoint name"
                                value={newWaypoint.name}
                                onChange={(e) => setNewWaypoint({ ...newWaypoint, name: e.target.value })}
                                className="h-8"
                            />
                            <div className="grid grid-cols-2 gap-2">
                                <Input
                                    placeholder="Latitude"
                                    value={newWaypoint.lat}
                                    onChange={(e) => setNewWaypoint({ ...newWaypoint, lat: e.target.value })}
                                    className="h-8"
                                />
                                <Input
                                    placeholder="Longitude"
                                    value={newWaypoint.lng}
                                    onChange={(e) => setNewWaypoint({ ...newWaypoint, lng: e.target.value })}
                                    className="h-8"
                                />
                            </div>
                            <Input
                                placeholder="Altitude (m)"
                                value={newWaypoint.altitude}
                                onChange={(e) => setNewWaypoint({ ...newWaypoint, altitude: e.target.value })}
                                className="h-8"
                            />
                            <Button onClick={addWaypoint} size="sm" className="w-full">
                                <Plus className="h-4 w-4 mr-2" />
                                Add Waypoint
                            </Button>
                        </div>

                        <ScrollArea className="h-32">
                            <div className="space-y-2">
                                {waypoints.map((waypoint, index) => (
                                    <div key={waypoint.id} className="flex items-center justify-between p-2 bg-muted rounded text-sm">
                                        <div>
                                            <div className="font-medium">
                                                {index + 1}. {waypoint.name}
                                            </div>
                                            <div className="text-xs text-muted-foreground font-mono">
                                                {waypoint.lat.toFixed(4)}, {waypoint.lng.toFixed(4)}
                                            </div>
                                        </div>
                                        <Button variant="ghost" size="sm" onClick={() => removeWaypoint(waypoint.id)}>
                                            <Trash2 className="h-3 w-3" />
                                        </Button>
                                    </div>
                                ))}
                            </div>
                        </ScrollArea>
                    </CardContent>
                </Card>

                {/* Recent Alerts */}
                <Card className="bg-card border-border ">
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Recent Alerts</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <ScrollArea className="h-24">
                            <div className="space-y-1">
                                {alerts.slice(-3).map((alert) => (
                                    <div key={alert.id} className="text-xs p-2 bg-muted rounded">
                                        <div className="flex items-center gap-2">
                                            <Badge variant={alert.type === "error" ? "destructive" : alert.type === "warning" ? "secondary" : "default"} className="text-xs">
                                                {alert.type}
                                            </Badge>
                                            <span>{alert.message}</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </ScrollArea>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
