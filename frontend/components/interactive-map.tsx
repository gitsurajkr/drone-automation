"use client"

import { useEffect, useRef, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { MapPin, Pencil, Play, RotateCcw } from "lucide-react"
import type { DroneData } from "@/hooks/use-drone-data"

interface InteractiveMapProps {
    droneData: DroneData | null
    onCommand: (command: string) => void
    isConnected: boolean
}

interface DrawnWaypoint {
    lat: number
    lng: number
    altitude: number
}

export function InteractiveMap({ droneData, onCommand, isConnected }: InteractiveMapProps) {
    const mapRef = useRef<HTMLDivElement>(null)
    const [map, setMap] = useState<any>(null)
    const [droneMarker, setDroneMarker] = useState<any>(null)
    const [pathLayer, setPathLayer] = useState<any>(null)
    const [drawnPath, setDrawnPath] = useState<DrawnWaypoint[]>([])
    const [isDrawing, setIsDrawing] = useState(false)
    const [drawingPath, setDrawingPath] = useState<any>(null)

    // Initialize Leaflet map on mount (don't wait for telemetry)
    useEffect(() => {
        if (!mapRef.current || map) return

        // Default center: Galgotias University, Noida, Uttar Pradesh, India
        const DEFAULT_CENTER: [number, number] = [28.5452, 77.5036]

        // Dynamically import Leaflet to avoid SSR issues
        const initMap = async () => {
            const L = (await import("leaflet")).default

            // Fix for default markers
            delete (L.Icon.Default.prototype as any)._getIconUrl
            L.Icon.Default.mergeOptions({
                iconRetinaUrl: "/map-marker-icon.png",
                iconUrl: "/map-marker-icon.png",
                shadowUrl: "/shadow.jpg",
            })

            if (mapRef.current && (mapRef.current as any)._leaflet_id) {
                // @ts-ignore
                ; (mapRef.current as any)._leaflet_id = null
            }

            const mapInstance = L.map(mapRef.current!, {
                center: DEFAULT_CENTER,
                zoom: 15,
                zoomControl: true,
                attributionControl: false,
            })

            // Add tile layer (OpenStreetMap)
            L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                maxZoom: 19,
            }).addTo(mapInstance)

            // University marker (Galgotias University)
            const uniMarker = L.marker(DEFAULT_CENTER, { title: "Galgotias University" }).addTo(mapInstance)
            uniMarker.bindPopup("Galgotias University, Noida, Uttar Pradesh, India")

            // Initial drone marker (will be updated when telemetry arrives)
            const droneIcon = L.divIcon({
                className: "drone-marker",
                html: `<div style="
                    width: 32px; 
                    height: 32px; 
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    transform: rotate(0deg);
                ">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <g filter="url(#shadow)">
              <ellipse cx="12" cy="12" rx="3" ry="1.5" fill="${isConnected ? "#10b981" : "#6b7280"}" stroke="white" strokeWidth="0.5"/>
              <line x1="6" y1="8" x2="18" y2="16" stroke="${isConnected ? "#10b981" : "#6b7280"}" strokeWidth="1.5" strokeLinecap="round"/>
              <line x1="18" y1="8" x2="6" y2="16" stroke="${isConnected ? "#10b981" : "#6b7280"}" strokeWidth="1.5" strokeLinecap="round"/>
              <circle cx="6" cy="8" r="2" fill="none" stroke="${isConnected ? "#10b981" : "#6b7280"}" strokeWidth="1" opacity="0.7"/>
              <circle cx="18" cy="8" r="2" fill="none" stroke="${isConnected ? "#10b981" : "#6b7280"}" strokeWidth="1" opacity="0.7"/>
              <circle cx="18" cy="16" r="2" fill="none" stroke="${isConnected ? "#10b981" : "#6b7280"}" strokeWidth="1" opacity="0.7"/>
              <circle cx="6" cy="16" r="2" fill="none" stroke="${isConnected ? "#10b981" : "#6b7280"}" strokeWidth="1" opacity="0.7"/>
              <polygon points="12,9 13.5,11 10.5,11" fill="${isConnected ? "#ef4444" : "#9ca3af"}" stroke="white" strokeWidth="0.3"/>
            </g>
            <defs>
              <filter id="shadow" x="-50%" y="-50%" width="200%" height="200%">
                <feDropShadow dx="0" dy="1" stdDeviation="1" floodColor="black" floodOpacity="0.3"/>
              </filter>
            </defs>
          </svg>
        </div>`,
                iconSize: [32, 32],
                iconAnchor: [16, 16],
            })

            const marker = L.marker(DEFAULT_CENTER, {
                icon: droneIcon,
            }).addTo(mapInstance)

            setMap(mapInstance)
            setDroneMarker(marker)

            // Add click handler for drawing waypoints
            mapInstance.on("click", (e: any) => {
                if (isDrawing) {
                    const newWaypoint: DrawnWaypoint = {
                        lat: e.latlng.lat,
                        lng: e.latlng.lng,
                        altitude: 50, // Default altitude
                    }

                    setDrawnPath((prev) => {
                        const updated = [...prev, newWaypoint]
                        updateDrawnPath(mapInstance, updated, L)
                        return updated
                    })
                }
            })

            // No telemetry yet: keep uni marker visible. When telemetry arrives the update effect
            // will move the drone marker and recenter the map as needed.
        }

        initMap()

        return () => {
            // remove the map instance we created
            // (use the internal leaflet instance if available)
            if (map) {
                map.remove()
                setMap(null)
            }
        }
    }, [])

    // Update drone position: only recenter when GPS looks valid. Start at DEFAULT_CENTER (uni)
    useEffect(() => {
        if (!droneMarker || !map || !droneData?.orientation) return
        const L = require("leaflet")

        const droneIcon = L.divIcon({
            className: "drone-marker",
            html: `<div style="
                    width: 32px; 
                    height: 32px; 
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    transform: rotate(${droneData.orientation.heading}deg);
                ">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <g filter="url(#shadow)">
                            <!-- Drone body -->
                            <ellipse cx="12" cy="12" rx="3" ry="1.5" fill="${isConnected ? "#10b981" : "#6b7280"}" stroke="white" strokeWidth="0.5"/>
              
                            <!-- Propeller arms -->
                            <line x1="6" y1="8" x2="18" y2="16" stroke="${isConnected ? "#10b981" : "#6b7280"}" strokeWidth="1.5" strokeLinecap="round"/>
                            <line x1="18" y1="8" x2="6" y2="16" stroke="${isConnected ? "#10b981" : "#6b7280"}" strokeWidth="1.5" strokeLinecap="round"/>
              
                            <!-- Propellers -->
                            <circle cx="6" cy="8" r="2" fill="none" stroke="${isConnected ? "#10b981" : "#6b7280"}" strokeWidth="1" opacity="0.7"/>
                            <circle cx="18" cy="8" r="2" fill="none" stroke="${isConnected ? "#10b981" : "#6b7280"}" strokeWidth="1" opacity="0.7"/>
                            <circle cx="18" cy="16" r="2" fill="none" stroke="${isConnected ? "#10b981" : "#6b7280"}" strokeWidth="1" opacity="0.7"/>
                            <circle cx="6" cy="16" r="2" fill="none" stroke="${isConnected ? "#10b981" : "#6b7280"}" strokeWidth="1" opacity="0.7"/>
              
                            <!-- Direction indicator -->
                            <polygon points="12,9 13.5,11 10.5,11" fill="${isConnected ? "#ef4444" : "#9ca3af"}" stroke="white" strokeWidth="0.3"/>
                        </g>
                        <defs>
                            <filter id="shadow" x="-50%" y="-50%" width="200%" height="200%">
                                <feDropShadow dx="0" dy="1" stdDeviation="1" floodColor="black" floodOpacity="0.3"/>
                            </filter>
                        </defs>
                    </svg>
                </div>`,
            iconSize: [32, 32],
            iconAnchor: [16, 16],
        })

        const lat = droneData?.gps?.latitude ?? 0
        const lon = droneData?.gps?.longitude ?? 0
        const sats = droneData?.satellites ?? 0

        // Consider GPS valid when satellites >= 4 OR lat/lon are non-zero (tolerance)
        const hasValidGps = sats >= 4 || (Math.abs(lat) > 0.0001 && Math.abs(lon) > 0.0001)

        // Always update the icon (color/rotation)
        droneMarker.setIcon(droneIcon)

        if (hasValidGps) {
            droneMarker.setLatLng([lat, lon])
            if (!pathLayer) {
                map.setView([lat, lon], 15)
            }
        } else {
            // GPS not valid yet: keep marker at fallback (DEFAULT_CENTER from init)
            // Optionally we could show a subtle pulse or popup to indicate no GPS.
        }
    }, [droneData?.gps?.latitude, droneData?.gps?.longitude, droneData?.orientation?.heading, droneData?.satellites, isConnected, droneMarker, map])

    const updateDrawnPath = (mapInstance: any, waypoints: DrawnWaypoint[], L: any) => {
        if (drawingPath) {
            mapInstance.removeLayer(drawingPath)
        }

        if (waypoints.length > 1) {
            const latlngs = waypoints.map((wp) => [wp.lat, wp.lng])
            const polyline = L.polyline(latlngs, {
                color: "#10b981",
                weight: 3,
                opacity: 0.8,
                dashArray: "10, 5",
            }).addTo(mapInstance)

            // Add waypoint markers
            waypoints.forEach((wp, index) => {
                const waypointIcon = L.divIcon({
                    className: "waypoint-marker",
                    html: `<div style="
            width: 24px; 
            height: 24px; 
            background: #10b981; 
            border: 2px solid white; 
            border-radius: 50%; 
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: bold;
            color: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
          ">${index + 1}</div>`,
                    iconSize: [24, 24],
                    iconAnchor: [12, 12],
                })

                L.marker([wp.lat, wp.lng], { icon: waypointIcon }).addTo(mapInstance)
            })

            setDrawingPath(polyline)
        }
    }

    const startDrawing = () => {
        setIsDrawing(true)
        setDrawnPath([])
        if (drawingPath && map) {
            map.removeLayer(drawingPath)
            setDrawingPath(null)
        }
    }

    const stopDrawing = () => {
        setIsDrawing(false)
    }

    const clearPath = () => {
        setDrawnPath([])
        setIsDrawing(false)
        if (drawingPath && map) {
            map.removeLayer(drawingPath)
            setDrawingPath(null)
        }
    }

    const startMission = () => {
        if (drawnPath.length > 0) {
            onCommand(`START_DRAWN_MISSION:${JSON.stringify(drawnPath)}`)
            console.log("[v0] Starting mission with drawn path:", drawnPath)
        }
    }

    return (
        <Card className="h-full bg-card border-border pb-2">
            <CardHeader>
                <div className="flex items-center justify-between">
                    <CardTitle className="text-lg flex items-center gap-2">
                        <MapPin className="h-5 w-5" />
                        Sky Navigator
                    </CardTitle>
                    <div className="flex items-center gap-2">
                        <Badge variant={isConnected ? "default" : "destructive"}>{isConnected ? "Live" : "Offline"}</Badge>
                        <Badge variant="outline">Waypoints: {drawnPath.length}</Badge>
                    </div>
                </div>
            </CardHeader>
            <CardContent className="h-[calc(100%-80px)] space-y-4">
                {/* Map Controls */}
                <div className="flex gap-2 flex-wrap">
                    <Button
                        variant={isDrawing ? "destructive" : "default"}
                        size="sm"
                        onClick={isDrawing ? stopDrawing : startDrawing}
                    >
                        <Pencil className="h-4 w-4 mr-2" />
                        {isDrawing ? "Stop Drawing" : "Draw Path"}
                    </Button>

                    <Button variant="outline" size="sm" onClick={clearPath} disabled={drawnPath.length === 0}>
                        <RotateCcw className="h-4 w-4 mr-2" />
                        Clear Path
                    </Button>

                    <Button variant="default" size="sm" onClick={startMission} disabled={drawnPath.length === 0}>
                        <Play className="h-4 w-4 mr-2" />
                        Start Mission
                    </Button>
                </div>

                {/* Drawing Instructions */}
                {isDrawing && (
                    <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3">
                        <p className="text-sm text-blue-400">
                            Click on the map to add waypoints and create a flight path. The drone will follow the line you draw.
                        </p>
                    </div>
                )}

                {/* Map Container */}
                <div className="relative bg-black rounded-lg overflow-hidden h-full min-h-[400px]">
                    {/* Map Overlay Info */}
                    <div className="absolute top-20 left-4 z-10 bg-black/80 text-white px-3 py-2 rounded text-sm font-mono">
                        <div className="flex items-center gap-2 mb-1">
                            <div className={`w-2 h-2 rounded-full ${isConnected ? "bg-green-500" : "bg-red-500"}`}></div>
                            {isConnected ? "Live Tracking" : "Disconnected"}
                        </div>
                        <div>Alt: {(droneData?.altitude ?? 0).toFixed(1)}m</div>
                        <div>Speed: {(droneData?.velocity.avgspeed ?? 0).toFixed(1)}m/s</div>
                    </div>

                    <div className="absolute top-4 right-4 z-10 bg-black/80 text-white px-3 py-2 rounded text-sm font-mono">
                        <div>Lat: {(droneData?.gps?.latitude ?? 0).toFixed(6)}</div>
                        <div>Lng: {(droneData?.gps?.longitude ?? 0).toFixed(6)}</div>
                        <div>Heading: {(droneData?.orientation?.heading ?? 0).toFixed(1)}°</div>
                    </div>

                    {/* Drawing Mode Indicator */}
                    {isDrawing && (
                        <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 z-10 bg-green-500/90 text-white px-4 py-2 rounded-full text-sm font-medium">
                            Drawing Mode Active - Click to add waypoints
                        </div>
                    )}

                    <div ref={mapRef} className="w-full h-full z-0" />
                </div>
            </CardContent>
        </Card>
    )
}
