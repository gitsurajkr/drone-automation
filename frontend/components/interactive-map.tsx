"use client"

import { useEffect, useRef, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { MapPin, Pencil, Play, RotateCcw, Maximize2, Minimize2, Target } from "lucide-react"
import type { DroneData } from "@/hooks/use-drone-data"

declare global {
    interface Window {
        google: any
        __googleMapsScriptLoading?: boolean
    }
}

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

// Default center (Delhi, India)
const DEFAULT_CENTER = { lat: 28.5245, lng: 77.5770 }


function loadGoogleMaps(apiKey: string | undefined): Promise<void> {
    return new Promise((resolve, reject) => {
        if (!apiKey) {
            reject(new Error("Missing Google Maps API key (set NEXT_PUBLIC_GOOGLE_MAPS_API_KEY)."))
            return
        }

        if (window.google && window.google.maps) {
            resolve()
            return
        }

        if (window.__googleMapsScriptLoading) {
            const check = setInterval(() => {
                if (window.google && window.google.maps) {
                    clearInterval(check)
                    resolve()
                }
            }, 100)
            return
        }

        window.__googleMapsScriptLoading = true
        const script = document.createElement("script")
        script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}`
        script.async = true
        script.defer = true
        script.onload = () => resolve()
        script.onerror = (err) => reject(err)
        document.head.appendChild(script)
    })
}

export function InteractiveMap({ droneData, onCommand, isConnected }: InteractiveMapProps) {
    const mapRef = useRef<HTMLDivElement>(null)
    const mapInstanceRef = useRef<any>(null)
    const droneMarkerRef = useRef<any>(null)
    const [drawnPath, setDrawnPath] = useState<DrawnWaypoint[]>([])
    const [isDrawing, setIsDrawing] = useState(false)
    const [isFullscreen, setIsFullscreen] = useState(false)
    const polylineRef = useRef<any>(null)
    const waypointMarkersRef = useRef<any[]>([])
    const mapClickListenerRef = useRef<any>(null)
    const [mapsLoadedError, setMapsLoadedError] = useState<string | null>(null)

    // Initialize Google Maps
    useEffect(() => {
        const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY

        let mounted = true

        loadGoogleMaps(apiKey)
            .then(() => {
                if (!mounted) return
                if (!mapRef.current) return

                // Use GPS coordinates if available and valid, otherwise use default center
                const hasValidGps = droneData?.gps &&
                    Math.abs(droneData.gps.latitude || 0) > 0.0001 &&
                    Math.abs(droneData.gps.longitude || 0) > 0.0001 &&
                    droneData.gps.latitude !== null &&
                    droneData.gps.longitude !== null

                const center = hasValidGps
                    ? { lat: droneData.gps.latitude, lng: droneData.gps.longitude }
                    : DEFAULT_CENTER

                const map = new window.google.maps.Map(mapRef.current, {
                    center,
                    zoom: 15,
                    mapTypeId: window.google.maps.MapTypeId.HYBRID,

                    // Enable zoom controls
                    zoomControl: true,
                    zoomControlOptions: {
                        position: window.google.maps.ControlPosition.RIGHT_CENTER
                    },

                    // Enable scroll wheel zoom
                    scrollwheel: true,

                    // Enable gesture handling
                    gestureHandling: 'cooperative',

                    // Other controls
                    mapTypeControl: true,
                    mapTypeControlOptions: {
                        style: window.google.maps.MapTypeControlStyle.HORIZONTAL_BAR,
                        position: window.google.maps.ControlPosition.TOP_RIGHT,
                        mapTypeIds: [
                            window.google.maps.MapTypeId.ROADMAP,
                            window.google.maps.MapTypeId.SATELLITE,
                            window.google.maps.MapTypeId.HYBRID,
                            window.google.maps.MapTypeId.TERRAIN
                        ]
                    },
                    streetViewControl: false,
                    fullscreenControl: true,
                    fullscreenControlOptions: {
                        position: window.google.maps.ControlPosition.TOP_RIGHT
                    }
                })

                mapInstanceRef.current = map

                // Create drone marker using the drone.png image
                const droneIcon = {
                    url: '/drone.png',
                    scaledSize: new window.google.maps.Size(40, 40),
                    anchor: new window.google.maps.Point(20, 20),
                    optimized: false
                }

                const marker = new window.google.maps.Marker({
                    map,
                    position: center,
                    icon: droneIcon,
                    title: 'Drone Position',
                    clickable: false,
                    optimized: false,
                })

                droneMarkerRef.current = marker

                // Map click handler for drawing mode
                mapClickListenerRef.current = map.addListener("click", (e: any) => {
                    if (!isDrawing) return
                    const lat = e.latLng.lat()
                    const lng = e.latLng.lng()
                    const wp: DrawnWaypoint = { lat, lng, altitude: 0 }
                    setDrawnPath((prev) => {
                        const next = [...prev, wp]
                        updatePathOnMap(next, map)
                        return next
                    })
                })
            })
            .catch((err) => {
                console.error("Failed to load Google Maps:", err)
                setMapsLoadedError(String(err.message || err))
            })

        return () => {
            mounted = false
            if (mapClickListenerRef.current) {
                window.google && window.google.maps.event.removeListener(mapClickListenerRef.current)
                mapClickListenerRef.current = null
            }
            if (droneMarkerRef.current) {
                try {
                    droneMarkerRef.current.setMap && droneMarkerRef.current.setMap(null)
                } catch { }
                droneMarkerRef.current = null
            }
            if (polylineRef.current) {
                polylineRef.current.setMap(null)
                polylineRef.current = null
            }
            waypointMarkersRef.current.forEach((m) => m.setMap && m.setMap(null))
            waypointMarkersRef.current = []
            mapInstanceRef.current = null
        }
        // We intentionally do not include isDrawing/droneData in deps here for controlled updates below
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    // Helper to update drawn path polyline + waypoint markers
    const updatePathOnMap = (waypoints: DrawnWaypoint[], map: any) => {
        // clear previous
        if (polylineRef.current) {
            polylineRef.current.setMap(null)
            polylineRef.current = null
        }
        waypointMarkersRef.current.forEach((m) => m.setMap && m.setMap(null))
        waypointMarkersRef.current = []

        if (waypoints.length > 0) {
            const path = waypoints.map((w) => ({ lat: w.lat, lng: w.lng }))
            polylineRef.current = new window.google.maps.Polyline({
                path,
                strokeColor: "#10b981",
                strokeOpacity: 0.9,
                strokeWeight: 3,
                geodesic: true,
                icons: [{ icon: { path: "M 0,-1 0,1", strokeOpacity: 0.0 }, offset: "0" }],
            })
            polylineRef.current.setMap(map)

            // add numbered waypoint markers
            waypoints.forEach((wp, idx) => {
                const marker = new window.google.maps.Marker({
                    position: { lat: wp.lat, lng: wp.lng },
                    map,
                    label: {
                        text: String(idx + 1),
                        color: "white",
                        fontSize: "12px",
                        fontWeight: "700",
                    },
                    icon: {
                        path: window.google.maps.SymbolPath.CIRCLE,
                        fillColor: "#10b981",
                        fillOpacity: 1,
                        strokeColor: "white",
                        strokeWeight: 2,
                        scale: 10,
                    },
                })
                waypointMarkersRef.current.push(marker)
            })
        }
    }

    const startDrawing = () => {
        setIsDrawing(true)
        setDrawnPath([])
        if (polylineRef.current) {
            polylineRef.current.setMap(null)
            polylineRef.current = null
        }
        waypointMarkersRef.current.forEach((m) => m.setMap && m.setMap(null))
        waypointMarkersRef.current = []
    }

    const stopDrawing = () => {
        setIsDrawing(false)
    }

    const clearPath = () => {
        setDrawnPath([])
        setIsDrawing(false)
        if (polylineRef.current) {
            polylineRef.current.setMap(null)
            polylineRef.current = null
        }
        waypointMarkersRef.current.forEach((m) => m.setMap && m.setMap(null))
        waypointMarkersRef.current = []
    }

    const startMission = () => {
        if (drawnPath.length > 0) {
            onCommand(`START_DRAWN_MISSION:${JSON.stringify(drawnPath)}`)
            console.log("[Sky Navigator] Starting mission with drawn path:", drawnPath)
        }
    }

    const centerOnDrone = () => {
        const map = mapInstanceRef.current
        if (!map || !droneData?.gps) return

        const lat = droneData.gps.latitude
        const lng = droneData.gps.longitude

        if (lat && lng && Math.abs(lat) > 0.0001 && Math.abs(lng) > 0.0001) {
            map.panTo({ lat, lng })
            map.setZoom(18) // Zoom in closer
        }
    }

    // Update drone marker position & rotation when droneData changes
    useEffect(() => {
        const map = mapInstanceRef.current
        const marker = droneMarkerRef.current
        if (!map || !marker) return

        const lat = droneData?.gps?.latitude ?? 0
        const lng = droneData?.gps?.longitude ?? 0
        const sats = droneData?.satellites ?? 0
        const heading = droneData?.orientation?.heading ?? 0

        // Check for valid GPS coordinates
        const hasValidGps = sats >= 4 && Math.abs(lat) > 0.0001 && Math.abs(lng) > 0.0001

        // Update drone icon with proper size based on connection status
        const size = isConnected ? 40 : 30
        const droneIcon = {
            url: '/drone.png',
            scaledSize: new window.google.maps.Size(size, size),
            anchor: new window.google.maps.Point(size / 2, size / 2),
            optimized: false
        }

        marker.setIcon(droneIcon)

        // Update position and center map on valid GPS
        if (hasValidGps) {
            const newPosition = { lat, lng }
            marker.setPosition(newPosition)

            // Center map on drone if not in drawing mode and map hasn't been manually moved
            if (!isDrawing) {
                map.panTo(newPosition)
            }
        }

        // Update marker visibility based on connection status
        marker.setOpacity(isConnected ? 1.0 : 0.6)

    }, [droneData?.gps?.latitude, droneData?.gps?.longitude, droneData?.orientation?.heading, droneData?.satellites, isConnected, isDrawing])

    // When drawnPath state updates we must update the map polyline (map may not be ready yet)
    useEffect(() => {
        const map = mapInstanceRef.current
        if (!map) return
        updatePathOnMap(drawnPath, map)
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [drawnPath])

    // Handle map resize when toggling fullscreen
    useEffect(() => {
        const map = mapInstanceRef.current
        if (!map) return

        // Delay to ensure the DOM has updated
        const timeout = setTimeout(() => {
            window.google.maps.event.trigger(map, 'resize')

            // Re-center on drone if we have valid GPS
            if (droneData?.gps && Math.abs(droneData.gps.latitude) > 0.0001) {
                map.panTo({
                    lat: droneData.gps.latitude,
                    lng: droneData.gps.longitude
                })
            }
        }, 100)

        return () => clearTimeout(timeout)
    }, [isFullscreen, droneData?.gps?.latitude, droneData?.gps?.longitude])

    // Lock body scroll when in fullscreen
    useEffect(() => {
        if (isFullscreen) {
            document.body.style.overflow = 'hidden'
        } else {
            document.body.style.overflow = ''
        }

        return () => {
            document.body.style.overflow = ''
        }
    }, [isFullscreen])

    return (
        <Card className="h-full bg-card border-border">
            <CardHeader>
                <div className="flex items-center justify-between">
                    <CardTitle className="text-lg flex items-center gap-2">
                        <MapPin className="h-5 w-5" />
                        Sky Navigator
                    </CardTitle>
                    <div className="flex items-center gap-2">
                        <Badge variant={isConnected ? "default" : "destructive"}>
                            {isConnected ? "🟢 Live" : "🔴 Offline"}
                        </Badge>
                        <Badge variant="outline">Waypoints: {drawnPath.length}</Badge>
                        {droneData?.satellites && (
                            <Badge variant={droneData.satellites >= 4 ? "default" : "destructive"}>
                                GPS: {droneData.satellites}
                            </Badge>
                        )}
                    </div>
                </div>
            </CardHeader>
            <CardContent className="h-[calc(100%-80px)] space-y-4">
                {/* Map Controls */}
                <div className="flex gap-2 flex-wrap items-center justify-between">
                    <div className="flex gap-2 flex-wrap">
                        <Button
                            variant={isDrawing ? "destructive" : "default"}
                            size="sm"
                            onClick={isDrawing ? stopDrawing : startDrawing}
                            disabled={!isConnected}
                        >
                            <Pencil className="h-4 w-4 mr-2" />
                            {isDrawing ? "Stop Drawing" : "Draw Path"}
                        </Button>

                        <Button
                            variant="outline"
                            size="sm"
                            onClick={clearPath}
                            disabled={drawnPath.length === 0}
                        >
                            <RotateCcw className="h-4 w-4 mr-2" />
                            Clear Path
                        </Button>

                        <Button
                            variant="default"
                            size="sm"
                            onClick={startMission}
                            disabled={drawnPath.length === 0 || !isConnected}
                        >
                            <Play className="h-4 w-4 mr-2" />
                            Start Mission
                        </Button>

                        <Button
                            variant="outline"
                            size="sm"
                            onClick={centerOnDrone}
                            disabled={!droneData?.gps || Math.abs(droneData.gps.latitude || 0) < 0.0001}
                        >
                            <Target className="h-4 w-4 mr-2" />
                            Center on Drone
                        </Button>
                    </div>

                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setIsFullscreen(!isFullscreen)}
                    >
                        {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
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
                <div className={`relative bg-black rounded-lg overflow-hidden transition-all duration-300 ${isFullscreen
                        ? 'fixed inset-0 z-50 rounded-none'
                        : 'h-full min-h-[400px]'
                    }`}>

                    {/* Map Overlay Info - Left Side */}
                    <div className="absolute top-4 left-4 z-10 bg-black/80 backdrop-blur-sm text-white px-3 py-2 rounded-lg text-sm font-mono shadow-lg border border-white/10">
                        <div className="flex items-center gap-2 mb-2">
                            <div className={`w-3 h-3 rounded-full ${isConnected ? "bg-green-500 animate-pulse" : "bg-red-500"}`}></div>
                            <span className="font-semibold">{isConnected ? "Live Tracking" : "Disconnected"}</span>
                        </div>
                        <div className="space-y-1">
                            <div>Alt: <span className="text-green-400">{(droneData?.altitude ?? 0).toFixed(1)}m</span></div>
                            <div>Speed: <span className="text-blue-400">{(droneData?.velocity?.avgspeed ?? 0).toFixed(1)}m/s</span></div>
                            <div>Sats: <span className="text-yellow-400">{droneData?.satellites ?? 0}</span></div>
                        </div>
                    </div>

                    {/* GPS Coordinates - Right Side */}
                    <div className="absolute top-4 right-4 z-10 bg-black/80 backdrop-blur-sm text-white px-3 py-2 rounded-lg text-sm font-mono shadow-lg border border-white/10">
                        <div className="space-y-1">
                            <div>Lat: <span className="text-green-400">{(droneData?.gps?.latitude ?? 0).toFixed(6)}</span></div>
                            <div>Lng: <span className="text-green-400">{(droneData?.gps?.longitude ?? 0).toFixed(6)}</span></div>
                            <div>Heading: <span className="text-orange-400">{(droneData?.orientation?.heading ?? 0).toFixed(1)}°</span></div>
                        </div>
                    </div>

                    {/* Drawing Mode Indicator */}
                    {isDrawing && (
                        <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 z-10 bg-green-500/90 backdrop-blur-sm text-white px-4 py-2 rounded-full text-sm font-medium shadow-lg animate-pulse">
                            🎯 Drawing Mode Active - Click to add waypoints
                        </div>
                    )}

                    {/* Connection Status Banner */}
                    {!isConnected && (
                        <div className="absolute top-16 left-1/2 transform -translate-x-1/2 z-10 bg-red-500/90 backdrop-blur-sm text-white px-4 py-2 rounded-lg text-sm font-medium shadow-lg">
                            ⚠️ Drone Disconnected - Map showing last known position
                        </div>
                    )}

                    {/* Fullscreen Exit Button */}
                    {isFullscreen && (
                        <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-10">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setIsFullscreen(false)}
                                className="bg-black/80 backdrop-blur-sm border-white/20 text-white hover:bg-white/20"
                            >
                                <Minimize2 className="h-4 w-4 mr-2" />
                                Exit Fullscreen
                            </Button>
                        </div>
                    )}

                    {mapsLoadedError ? (
                        <div className="w-full h-full flex items-center justify-center text-white p-6">
                            <div className="max-w-md text-center bg-red-900/50 p-6 rounded-lg border border-red-500/30">
                                <p className="font-semibold text-red-300 mb-2">🗺️ Google Maps Failed to Load</p>
                                <p className="text-sm text-red-200 mb-2">{mapsLoadedError}</p>
                                <p className="text-xs text-red-300">Set NEXT_PUBLIC_GOOGLE_MAPS_API_KEY in your environment to enable Google Maps.</p>
                            </div>
                        </div>
                    ) : (
                        <div ref={mapRef} className="w-full h-full z-0" />
                    )}
                </div>
            </CardContent>
        </Card>
    )
}
