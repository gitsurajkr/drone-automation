"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { AlertTriangle, Info, X, XCircle } from "lucide-react"
import type { DroneAlert } from "@/hooks/use-drone-data"

interface AlertsPanelProps {
    alerts: DroneAlert[]
}

export function AlertsPanel({ alerts }: AlertsPanelProps) {

    function TimeOnly({ timestamp }: { timestamp: number }) {
    const [time, setTime] = useState("");
    useEffect(() => {
        setTime(new Date(timestamp).toLocaleTimeString());
    }, [timestamp]);
    return <span className="text-xs text-muted-foreground font-mono">{time}</span>;
}

    const getAlertIcon = (type: DroneAlert["type"]) => {
        switch (type) {
            case "error":
                return <XCircle className="h-4 w-4 text-red-400" />
            case "warning":
                return <AlertTriangle className="h-4 w-4 text-yellow-400" />
            case "info":
                return <Info className="h-4 w-4 text-blue-400" />
            default:
                return <Info className="h-4 w-4 text-blue-400" />
        }
    }

    const getAlertColor = (type: DroneAlert["type"]) => {
        switch (type) {
            case "error":
                return "destructive"
            case "warning":
                return "secondary"
            case "info":
                return "default"
            default:
                return "default"
        }
    }

    const activeAlerts = alerts.slice(-5) 
    return (
        <Card className="bg-card border-border">
            <CardHeader>
                <div className="flex items-center justify-between">
                    <CardTitle className="text-lg flex items-center gap-2">
                        <AlertTriangle className="h-5 w-5" />
                        System Alerts
                    </CardTitle>
                    <Badge variant="outline">{activeAlerts.length} Active</Badge>
                </div>
            </CardHeader>
            <CardContent>
                <ScrollArea className="h-[200px]">
                    {activeAlerts.length === 0 ? (
                        <div className="flex items-center justify-center h-full text-muted-foreground">
                            <div className="text-center">
                                <Info className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                <p className="text-sm">No active alerts</p>
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {activeAlerts.reverse().map((alert) => (
                                <div key={alert.id} className="flex items-start gap-3 p-3 rounded-lg bg-muted/50 border border-border">
                                    <div className="flex-shrink-0 mt-0.5">{getAlertIcon(alert.type)}</div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <Badge variant={getAlertColor(alert.type)} className="text-xs">
                                                {alert.type.toUpperCase()}
                                            </Badge>
                                            <span className="text-xs text-muted-foreground font-mono">
                                                <TimeOnly timestamp={alert.timestamp} />
                                            </span>
                                        </div>
                                        <p className="text-sm text-foreground">{alert.message}</p>
                                    </div>
                                    <Button variant="ghost" size="sm" className="flex-shrink-0 h-6 w-6 p-0">
                                        <X className="h-3 w-3" />
                                    </Button>
                                </div>
                            ))}
                        </div>
                    )}
                </ScrollArea>

                {activeAlerts.length > 0 && (
                    <div className="flex justify-between items-center mt-4 pt-4 border-t border-border">
                        <span className="text-xs text-muted-foreground">{alerts.length} total alerts</span>
                        <Button variant="outline" size="sm">
                            Clear All
                        </Button>
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
