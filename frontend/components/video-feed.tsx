"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Video, VideoOff, Maximize2, Settings, CreditCard as Record } from "lucide-react"
import { useState, useRef, useEffect } from "react"

export function VideoFeed() {
    const [isStreaming, setIsStreaming] = useState(true)
    const [isRecording, setIsRecording] = useState(false)
    const [isFullscreen, setIsFullscreen] = useState(false)
    const canvasRef = useRef<HTMLCanvasElement>(null)
    const animationRef = useRef<number>()

    // Simulate video feed with animated noise pattern
    useEffect(() => {
        const canvas = canvasRef.current
        if (!canvas || !isStreaming) return

        const ctx = canvas.getContext("2d")
        if (!ctx) return

        const animate = () => {
            // Create video-like background
            const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height)
            gradient.addColorStop(0, "#1a1a2e")
            gradient.addColorStop(0.5, "#16213e")
            gradient.addColorStop(1, "#0f3460")

            ctx.fillStyle = gradient
            ctx.fillRect(0, 0, canvas.width, canvas.height)

            // Add some "video noise" effect
            for (let i = 0; i < 100; i++) {
                const x = Math.random() * canvas.width
                const y = Math.random() * canvas.height
                const size = Math.random() * 2
                const opacity = Math.random() * 0.3

                ctx.fillStyle = `rgba(255, 255, 255, ${opacity})`
                ctx.fillRect(x, y, size, size)
            }

            // Add crosshair overlay
            ctx.strokeStyle = "#00ff00"
            ctx.lineWidth = 1
            ctx.setLineDash([5, 5])

            // Center crosshair
            const centerX = canvas.width / 2
            const centerY = canvas.height / 2

            ctx.beginPath()
            ctx.moveTo(centerX - 20, centerY)
            ctx.lineTo(centerX + 20, centerY)
            ctx.moveTo(centerX, centerY - 20)
            ctx.lineTo(centerX, centerY + 20)
            ctx.stroke()

            // Corner brackets
            ctx.setLineDash([])
            ctx.strokeStyle = "#00ff00"
            ctx.lineWidth = 2

            const bracketSize = 20
            const margin = 20

            // Top-left
            ctx.beginPath()
            ctx.moveTo(margin, margin + bracketSize)
            ctx.lineTo(margin, margin)
            ctx.lineTo(margin + bracketSize, margin)
            ctx.stroke()

            // Top-right
            ctx.beginPath()
            ctx.moveTo(canvas.width - margin - bracketSize, margin)
            ctx.lineTo(canvas.width - margin, margin)
            ctx.lineTo(canvas.width - margin, margin + bracketSize)
            ctx.stroke()

            // Bottom-left
            ctx.beginPath()
            ctx.moveTo(margin, canvas.height - margin - bracketSize)
            ctx.lineTo(margin, canvas.height - margin)
            ctx.lineTo(margin + bracketSize, canvas.height - margin)
            ctx.stroke()

            // Bottom-right
            ctx.beginPath()
            ctx.moveTo(canvas.width - margin - bracketSize, canvas.height - margin)
            ctx.lineTo(canvas.width - margin, canvas.height - margin)
            ctx.lineTo(canvas.width - margin, canvas.height - margin - bracketSize)
            ctx.stroke()

            // Add timestamp
            ctx.fillStyle = "#00ff00"
            ctx.font = "12px monospace"
            let now = "";
            if (typeof window !== "undefined") {
                now = new Date().toLocaleTimeString();
            }
            ctx.fillText(now, 10, canvas.height - 10)

            animationRef.current = requestAnimationFrame(animate)
        }

        animate()

        return () => {
            if (animationRef.current) {
                cancelAnimationFrame(animationRef.current)
            }
        }
    }, [isStreaming])

    const toggleStream = () => {
        setIsStreaming(!isStreaming)
    }

    const toggleRecording = () => {
        setIsRecording(!isRecording)
    }

    const toggleFullscreen = () => {
        setIsFullscreen(!isFullscreen)
    }

    return (
        <Card className="bg-card border-border">
            <CardHeader>
                <div className="flex items-center justify-between">
                    <CardTitle className="text-lg flex items-center gap-2">
                        <Video className="h-5 w-5" />
                        Live Camera Feed
                    </CardTitle>
                    <div className="flex items-center gap-2">
                        <Badge variant={isStreaming ? "default" : "secondary"}>{isStreaming ? "LIVE" : "OFFLINE"}</Badge>
                        {isRecording && (
                            <Badge variant="destructive" className="animate-pulse">
                                REC
                            </Badge>
                        )}
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                <div className="space-y-4">
                    {/* Video Display */}
                    <div className="relative bg-black rounded-lg overflow-hidden">
                        {isStreaming ? (
                            <canvas ref={canvasRef} width={400} height={300} className="w-full h-[300px] object-cover" />
                        ) : (
                            <div className="w-full h-[300px] flex items-center justify-center bg-gray-900">
                                <div className="text-center">
                                    <VideoOff className="h-12 w-12 text-gray-500 mx-auto mb-2" />
                                    <p className="text-gray-400">Video Feed Offline</p>
                                </div>
                            </div>
                        )}

                        {/* Overlay Controls */}
                        <div className="absolute top-2 left-2 flex gap-2">
                            <div className="bg-black/80 text-white px-2 py-1 rounded text-xs font-mono">1080p • 30fps</div>
                            <div className="bg-black/80 text-white px-2 py-1 rounded text-xs font-mono">Gimbal: Stabilized</div>
                        </div>
                    </div>

                    {/* Video Controls */}
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Button variant={isStreaming ? "destructive" : "default"} size="sm" onClick={toggleStream}>
                                {isStreaming ? <VideoOff className="h-4 w-4" /> : <Video className="h-4 w-4" />}
                                {isStreaming ? "Stop" : "Start"}
                            </Button>

                            <Button
                                variant={isRecording ? "destructive" : "outline"}
                                size="sm"
                                onClick={toggleRecording}
                                disabled={!isStreaming}
                            >
                                <Record className="h-4 w-4" />
                                {isRecording ? "Stop Rec" : "Record"}
                            </Button>
                        </div>

                        <div className="flex items-center gap-2">
                            <Button variant="outline" size="sm">
                                <Settings className="h-4 w-4" />
                            </Button>

                            <Button variant="outline" size="sm" onClick={toggleFullscreen}>
                                <Maximize2 className="h-4 w-4" />
                            </Button>
                        </div>
                    </div>

                    {/* Video Stats */}
                    <div className="grid grid-cols-2 gap-4 pt-2 border-t border-border text-sm">
                        <div>
                            <p className="text-muted-foreground">Resolution</p>
                            <p className="font-mono">1920x1080</p>
                        </div>
                        <div>
                            <p className="text-muted-foreground">Bitrate</p>
                            <p className="font-mono">5.2 Mbps</p>
                        </div>
                        <div>
                            <p className="text-muted-foreground">Latency</p>
                            <p className="font-mono">120ms</p>
                        </div>
                        <div>
                            <p className="text-muted-foreground">Signal</p>
                            <p className="font-mono text-green-400">Strong</p>
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    )
}
