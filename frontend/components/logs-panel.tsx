"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Input } from "@/components/ui/input"
import { FileText, Search, Download, Filter } from "lucide-react"
import type { DroneLog } from "@/hooks/use-drone-data"
import { useState, useEffect } from "react"

function TimeOnly({ timestamp }: { timestamp: number }) {
    const [time, setTime] = useState("");
    useEffect(() => {
        setTime(new Date(timestamp).toLocaleTimeString());
    }, [timestamp]);
    return <span className="text-xs text-muted-foreground font-mono">{time}</span>;
}

interface LogsPanelProps {
    logs: DroneLog[]
}

export function LogsPanel({ logs }: LogsPanelProps) {
    const [searchTerm, setSearchTerm] = useState("")
    const [filterType, setFilterType] = useState<"all" | "telemetry" | "command" | "system">("all")

    const getLogColor = (type: DroneLog["type"]) => {
        switch (type) {
            case "telemetry":
                return "default"
            case "command":
                return "secondary"
            case "system":
                return "outline"
            default:
                return "outline"
        }
    }

    const filteredLogs = logs
        .filter((log) => filterType === "all" || log.type === filterType)
        .filter((log) => log.message.toLowerCase().includes(searchTerm.toLowerCase()))
        .slice(-50) 

    return (
        <Card className="bg-card border-border">
            <CardHeader>
                <div className="flex items-center justify-between">
                    <CardTitle className="text-lg flex items-center gap-2">
                        <FileText className="h-5 w-5" />
                        System Logs
                    </CardTitle>
                    <Badge variant="outline">{filteredLogs.length} Entries</Badge>
                </div>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Search and Filter */}
                <div className="flex gap-2">
                    <div className="relative flex-1">
                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                        <Input
                            placeholder="Search logs..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="pl-8"
                        />
                    </div>
                    <Button variant="outline" size="sm">
                        <Filter className="h-4 w-4" />
                    </Button>
                </div>

                {/* Filter Buttons */}
                <div className="flex gap-2">
                    {(["all", "telemetry", "command", "system"] as const).map((type) => (
                        <Button
                            key={type}
                            variant={filterType === type ? "default" : "outline"}
                            size="sm"
                            onClick={() => setFilterType(type)}
                        >
                            {type.charAt(0).toUpperCase() + type.slice(1)}
                        </Button>
                    ))}
                </div>

                {/* Logs Display */}
                <ScrollArea className="h-[300px]">
                    {filteredLogs.length === 0 ? (
                        <div className="flex items-center justify-center h-full text-muted-foreground">
                            <div className="text-center">
                                <FileText className="h-8 w-8 mx-auto mb-2 opacity-50" />
                                <p className="text-sm">No logs found</p>
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-2">
                            {filteredLogs.reverse().map((log) => (
                                <div
                                    key={log.id}
                                    className="flex items-start gap-3 p-2 rounded border border-border/50 hover:bg-muted/30 transition-colors"
                                >
                                    <div className="flex-shrink-0">
                                        <Badge variant={getLogColor(log.type)} className="text-xs">
                                            {log.type.charAt(0).toUpperCase()}
                                        </Badge>
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className="text-xs text-muted-foreground font-mono">
                                                <TimeOnly timestamp={log.timestamp} />
                                            </span>
                                        </div>
                                        <p className="text-sm text-foreground font-mono break-all">{log.message}</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </ScrollArea>

                {/* Log Actions */}
                <div className="flex justify-between items-center pt-4 border-t border-border">
                    <span className="text-xs text-muted-foreground">
                        Showing {filteredLogs.length} of {logs.length} logs
                    </span>
                    <div className="flex gap-2">
                        <Button variant="outline" size="sm">
                            <Download className="h-4 w-4 mr-2" />
                            Export
                        </Button>
                        <Button variant="outline" size="sm">
                            Clear
                        </Button>
                    </div>
                </div>
            </CardContent>
        </Card>
    )
}
