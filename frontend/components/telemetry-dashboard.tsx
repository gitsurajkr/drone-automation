"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Line, LineChart, XAxis, YAxis, ResponsiveContainer } from "recharts"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import type { DroneData } from "@/hooks/use-drone-data"
import { Battery, Gauge, Navigation, Zap } from "lucide-react"

interface TelemetryDashboardProps {
    data: DroneData | null
    history: DroneData[]
}

export function TelemetryDashboard({ data, history }: TelemetryDashboardProps) {
    if (!data) {
        return (
            <div className="flex items-center justify-center h-64 text-muted-foreground">
                Loading telemetry data...
            </div>
        )
    }

    const chartData = history.slice(-20).map((item, index) => ({
        time: index,
        altitude: item.altitude ?? 0,
        velocity: item.velocity.avgspeed ?? 0,
        battery: item.battery ?? 0,
    }))

    const getBatteryColor = (level: number) => {
        if (level > 50) return "text-green-400"
        if (level > 20) return "text-yellow-400"
        return "text-red-400"
    }

    return (
        <div className="space-y-6">
            {/* Key Metrics Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card className="bg-card border-border">
                    <CardContent className="p-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-primary/10 rounded-lg">
                                <Gauge className="h-5 w-5 text-primary" />
                            </div>
                            <div>
                                <p className="text-sm text-muted-foreground">Altitude</p>
                                <p className="text-xl font-bold">{(data.altitude ?? 0).toFixed(1)}m</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-card border-border">
                    <CardContent className="p-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-chart-2/10 rounded-lg">
                                <Zap className="h-5 w-5 text-chart-2" />
                            </div>
                            <div>
                                <p className="text-sm text-muted-foreground">Speed</p>
                                <p className="text-xl font-bold">{(data.velocity.avgspeed ?? 0).toFixed(1)} m/s</p>
                                {/* <p className="text-xl font-bold">VX: {(data.velocity.vx ?? 0).toFixed(1)} m/s</p> */}

                            </div>
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-card border-border">
                    <CardContent className="p-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-chart-3/10 rounded-lg">
                                <Battery className={`h-5 w-5 ${getBatteryColor(data.battery ?? 0)}`} />
                            </div>
                            <div>
                                <p className="text-sm text-muted-foreground">Battery</p>
                                <p className={`text-xl font-bold ${getBatteryColor(data.battery ?? 0)}`}>{(data.battery ?? 0).toFixed(1)}%</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <Card className="bg-card border-border">
                    <CardContent className="p-4">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-chart-4/10 rounded-lg">
                                <Navigation className="h-5 w-5 text-chart-4" />
                            </div>
                            <div>
                                <p className="text-sm text-muted-foreground">Heading</p>
                                <p className="text-xl font-bold">{(data.orientation?.heading ?? 0).toFixed(0)}°</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Status Row */}
            <div className="flex gap-4">
                <div className="px-3 py-2 bg-muted rounded-md">
                    <div className="text-xs">Mode</div>
                    <div className="font-semibold">{data.mode ?? "-"}</div>
                </div>
                <div className="px-3 py-2 bg-muted rounded-md">
                    <div className="text-xs">Armed</div>
                    <div className="font-semibold">{data.armed === undefined ? "-" : data.armed ? "Yes" : "No"}</div>
                </div>
                <div className="px-3 py-2 bg-muted rounded-md">
                    <div className="text-xs">EKF OK</div>
                    <div className="font-semibold">{data.ekfOk === undefined ? "-" : data.ekfOk ? "Yes" : "No"}</div>
                </div>
                <div className="px-3 py-2 bg-muted rounded-md">
                    <div className="text-xs">Sats</div>
                    <div className="font-semibold">{data.satellites ?? "-"}</div>
                </div>
                <div className="px-3 py-2 bg-muted rounded-md">
                    <div className="text-xs">Gnd Spd</div>
                    <div className="font-semibold">{(data.groundspeed ?? 0).toFixed(2)} m/s</div>
                </div>
            </div>

            {/* Orientation Display */}
            <Card className="bg-card border-border">
                <CardHeader>
                    <CardTitle className="text-lg">Orientation</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-3 gap-6">
                        <div className="text-center">
                            <p className="text-sm text-muted-foreground mb-2">Roll</p>
                            <div className="relative w-16 h-16 mx-auto">
                                <div
                                    className="absolute inset-0 border-2 border-chart-1 rounded-full"
                                    style={{ transform: `rotate(${data.orientation?.roll ?? 0}deg)` }}
                                >
                                    <div className="absolute top-0 left-1/2 w-0.5 h-4 bg-chart-1 -translate-x-0.5"></div>
                                </div>
                            </div>
                            <p className="text-lg font-bold mt-2">{(data.orientation?.roll ?? 0).toFixed(2)}°</p>
                        </div>

                        <div className="text-center">
                            <p className="text-sm text-muted-foreground mb-2">Pitch</p>
                            <div className="relative w-16 h-16 mx-auto">
                                <div
                                    className="absolute inset-0 border-2 border-chart-2 rounded-full"
                                    style={{ transform: `rotate(${data.orientation?.pitch ?? 0}deg)` }}
                                >
                                    <div className="absolute top-0 left-1/2 w-0.5 h-4 bg-chart-2 -translate-x-0.5"></div>
                                </div>
                            </div>
                            <p className="text-lg font-bold mt-2">{(data.orientation?.pitch ?? 0).toFixed(2)}°</p>
                        </div>

                        <div className="text-center">
                            <p className="text-sm text-muted-foreground mb-2">Yaw</p>
                            <div className="relative w-16 h-16 mx-auto">
                                <div
                                    className="absolute inset-0 border-2 border-chart-3 rounded-full"
                                    style={{ transform: `rotate(${data.orientation?.yaw ?? 0}deg)` }}
                                >
                                    <div className="absolute top-0 left-1/2 w-0.5 h-4 bg-chart-3 -translate-x-0.5"></div>
                                </div>
                            </div>
                            <p className="text-lg font-bold mt-2">{(data.orientation?.yaw ?? 0).toFixed(2)}°</p>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* GPS Coordinates */}
            <Card className="bg-card border-border">
                <CardHeader>
                    <CardTitle className="text-lg">GPS Coordinates</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <p className="text-sm text-muted-foreground">Latitude</p>
                            <p className="text-lg font-mono">{data.gps?.latitude !== undefined ? data.gps.latitude.toFixed(6) : "-"}</p>
                        </div>
                        <div>
                            <p className="text-sm text-muted-foreground">Longitude</p>
                            <p className="text-lg font-mono">{data.gps?.longitude !== undefined ? data.gps.longitude.toFixed(6) : "-"}</p>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}
