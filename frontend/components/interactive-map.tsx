"use client"

import { useEffect, useRef, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { MapPin, Pencil, Play, RotateCcw, Maximize2, Minimize2, Target } from "lucide-react"
import type { DroneData } from "@/hooks/use-drone-data"
import toast from "react-hot-toast"

declare global {
    interface Window {
        google: any
        __googleMapsScriptLoading?: boolean
    }
}

interface InteractiveMapProps {
    droneData: DroneData | null
    onCommand: (command: string, payload?: any) => Promise<any>
    isConnected: boolean
    takeoffProgress?: { status: 'idle'|'started'|'completed'|'failed', target_altitude?: number | null, mission_id?: string | null, current_altitude?: number | null, percent?: number | null }
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
        script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=drawing`
        script.async = true
        script.defer = true
        script.onload = () => resolve()
        script.onerror = (err) => reject(err)
        document.head.appendChild(script)
    })
}

export function InteractiveMap({ droneData, onCommand, isConnected, takeoffProgress }: InteractiveMapProps) {
    const mapRef = useRef<HTMLDivElement>(null)
    const mapInstanceRef = useRef<any>(null)
    const droneMarkerRef = useRef<any>(null)
    const [drawnPath, setDrawnPath] = useState<DrawnWaypoint[]>([])
    const [isDrawing, setIsDrawing] = useState(false)
    const isDrawingRef = useRef(false) // Use ref to avoid closure issues
    const [isFullscreen, setIsFullscreen] = useState(false)
    const polylineRef = useRef<any>(null)
    const waypointMarkersRef = useRef<any[]>([])
    const mapClickListenerRef = useRef<any>(null)
    const [mapsLoadedError, setMapsLoadedError] = useState<string | null>(null)
    const animationRequestRef = useRef<number | null>(null)
    const lastDronePositionRef = useRef<{lat: number, lng: number} | null>(null)
    const isTakeoffActive = takeoffProgress?.status === 'started'

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

                    scrollwheel: true,

                    // Enable gesture handling
                    gestureHandling: 'cooperative',

                    // Map cursor style (will be overridden when drawing)
                    draggableCursor: 'default',
                    draggingCursor: 'move',

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
                console.log("[Sky Navigator] Map initialized successfully")

                // Removed area drawing - keeping only path drawing

                // Create drone marker using the drone.png image
                const droneIcon = {
                    url: '/drone.png', // Using the existing drone1.png file
                    scaledSize: new window.google.maps.Size(40, 40),
                    anchor: new window.google.maps.Point(20, 20),
                    optimized: false
                }

                const marker = new window.google.maps.Marker({
                    map,
                    position: center,
                    icon: droneIcon,
                    title: `Drone Position - ${isConnected ? 'Connected' : 'Disconnected'}`,
                    clickable: true,
                    optimized: false,
                })

                // Add click listener to drone marker for quick commands
                marker.addListener('click', () => {
                    if (isConnected && droneData) {
                        const infoWindow = new window.google.maps.InfoWindow({
                            content: `
                                <div style="font-family: Arial, sans-serif; min-width: 200px;">
                                    <h4 style="margin: 0 0 10px 0; color: #333;">Drone Status</h4>
                                    <p><strong>Altitude:</strong> ${droneData.altitude?.toFixed(1) || 0}m</p>
                                    <p><strong>Battery:</strong> ${droneData.battery || 0}%</p>
                                    <p><strong>Speed:</strong> ${droneData.velocity?.avgspeed?.toFixed(1) || 0} m/s</p>
                                    <p><strong>Armed:</strong> ${droneData.armed ? 'Yes' : 'No'}</p>
                                    <p><strong>Mode:</strong> ${droneData.mode || 'Unknown'}</p>
                                </div>
                            `
                        })
                        infoWindow.open(map, marker)
                    }
                })

                droneMarkerRef.current = marker

         
                // Map click handler for drawing mode
                mapClickListenerRef.current = map.addListener("click", (e: any) => {
                    console.log("[Sky Navigator] Map clicked, isDrawing:", isDrawingRef.current)
                    if (!isDrawingRef.current) {
                        console.log("[Sky Navigator] Not in drawing mode, ignoring click")
                        return
                    }
                    const lat = e.latLng.lat()
                    const lng = e.latLng.lng()
                    const wp: DrawnWaypoint = { lat, lng, altitude: 20 } 
                    console.log("[Sky Navigator] Adding waypoint:", wp)
                    setDrawnPath((prev) => {
                        const next = [...prev, wp]
                        console.log("[Sky Navigator] Updated path:", next)
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
            
            // Cancel any ongoing animation
            if (animationRequestRef.current) {
                cancelAnimationFrame(animationRequestRef.current)
                animationRequestRef.current = null
            }
            
            mapInstanceRef.current = null
        }

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
        console.log("[Sky Navigator] startDrawing called")
        setIsDrawing(true)
        isDrawingRef.current = true 
        setDrawnPath([])
        if (polylineRef.current) {
            polylineRef.current.setMap(null)
            polylineRef.current = null
        }
        waypointMarkersRef.current.forEach((m) => m.setMap && m.setMap(null))
        waypointMarkersRef.current = []
        
        if (mapInstanceRef.current) {
            console.log("[Sky Navigator] Setting map options for drawing mode")
            mapInstanceRef.current.setOptions({ 
                draggable: false,  
                draggableCursor: 'crosshair',
                draggingCursor: 'crosshair',
                gestureHandling: 'cooperative', 
                scrollwheel: false,  
                disableDoubleClickZoom: true  
            })
        } else {
            console.log("[Sky Navigator] Map instance not ready")
        }
        
        console.log("[Sky Navigator] Drawing mode activated, isDrawing set to true")
    }

    const stopDrawing = () => {
        setIsDrawing(false)
        isDrawingRef.current = false // Update ref immediately
        
        // Re-enable map dragging and reset cursor to default
        if (mapInstanceRef.current) {
            mapInstanceRef.current.setOptions({ 
                draggable: true,  // Re-enable map dragging
                draggableCursor: 'default',
                draggingCursor: 'move',
                gestureHandling: 'cooperative',  // Re-enable gesture handling
                scrollwheel: true,  // Re-enable scroll zoom
                disableDoubleClickZoom: false  // Re-enable double-click zoom
            })
        }
        
        console.log("[Sky Navigator] Stopping drawing mode")
    }

    const clearPath = () => {
        setDrawnPath([])
        setIsDrawing(false)
        isDrawingRef.current = false // Update ref immediately
        
        // Re-enable map dragging and reset cursor to default
        if (mapInstanceRef.current) {
            mapInstanceRef.current.setOptions({ 
                draggable: true,  // Re-enable map dragging
                draggableCursor: 'default',
                draggingCursor: 'move',
                gestureHandling: 'cooperative',  // Re-enable gesture handling
                scrollwheel: true,  // Re-enable scroll zoom
                disableDoubleClickZoom: false  // Re-enable double-click zoom
            })
        }
        
        if (polylineRef.current) {
            polylineRef.current.setMap(null)
            polylineRef.current = null
        }
        waypointMarkersRef.current.forEach((m) => m.setMap && m.setMap(null))
        waypointMarkersRef.current = []
    }


    const startMission = async () => {
        // Validation checks before starting mission
        if (drawnPath.length === 0) {
            console.warn("[Sky Navigator] No waypoints drawn")
            return
        }

        // Battery check - must be above 25%
        if (droneData?.battery && droneData.battery < 25) {
            console.error(`[Sky Navigator] ❌ Battery too low: ${droneData.battery}% - Cannot set waypoints (minimum 25% required)`)
            toast.error(`⚠️ Battery too low: ${droneData.battery}%\nCannot execute waypoint mission.\nMinimum 25% battery required for safety.`)
            return
        }

        // GPS check - must have at least 6 satellites
        if (!droneData?.satellites || droneData.satellites < 6) {
            console.error(`[Sky Navigator] ❌ GPS insufficient: ${droneData?.satellites || 0} satellites - Cannot set waypoints (minimum 6 satellites required)`)
            toast.error(`⚠️ GPS signal insufficient: ${droneData?.satellites || 0} satellites\nCannot execute waypoint mission.\nMinimum 6 satellites required for navigation.`)
            return
        }

        // GPS coordinates check
        if (!droneData?.gps || Math.abs(droneData.gps.latitude) < 0.0001 || Math.abs(droneData.gps.longitude) < 0.0001) {
            console.error("[Sky Navigator] ❌ Invalid GPS coordinates - Cannot set waypoints")
            toast.error("⚠️ Invalid GPS coordinates\nCannot execute waypoint mission.\nWaiting for valid GPS lock.")
            return
        }

        // Connection check
        if (!isConnected) {
            console.error("[Sky Navigator] ❌ Drone not connected - Cannot set waypoints")
            toast.error("⚠️ Drone not connected\nCannot execute waypoint mission.\nPlease connect to drone first.")
            return
        }

        try {
            console.log(`[Sky Navigator] ✅ Pre-flight checks passed - Battery: ${droneData.battery}%, GPS: ${droneData.satellites} sats`)
            
            // Execute waypoint mission using the new waypoint system
            const waypoints = drawnPath.map((point, index) => ({
                latitude: point.lat,
                longitude: point.lng,
                altitude: point.altitude || 20,
                order: index
            }))
            
            console.log("[Sky Navigator] Sending waypoints:", waypoints)
            
            const result = await onCommand("execute_waypoint_mission", {
                waypoints: waypoints,
                takeoff_altitude: 20
            })
            
            console.log("[Sky Navigator] Waypoint mission result:", result)
            
            if (result?.status === "ok") {
                console.log("[Sky Navigator] ✅ Waypoint mission started successfully")
                toast.success("🚁 Waypoint mission started successfully!")
            } else {
                console.error("[Sky Navigator] ❌ Failed to start waypoint mission:", result?.detail || result)
                toast.error(`Failed to start waypoint mission: ${result?.detail || result?.message || 'Unknown error'}`)
            }
        } catch (error) {
            console.error("Failed to start waypoint mission:", error)
            toast.error(`Error starting waypoint mission: ${error}`)
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

    const stopWaypointMission = async () => {
        try {
            const result = await onCommand("stop_waypoint_mission")
            if (result?.status === "success") {
                console.log("[Sky Navigator] Waypoint mission stopped successfully")
            } else {
                console.error("[Sky Navigator] Failed to stop waypoint mission:", result)
            }
        } catch (error) {
            console.error("Failed to stop waypoint mission:", error)
        }
    }

    const checkMissionStatus = async () => {
        try {
            const result = await onCommand("waypoint_mission_status")
            console.log("[Sky Navigator] Mission status:", result)
        } catch (error) {
            console.error("Failed to get mission status:", error)
        }
    }

    // Button click handlers
    const handleDrawPath = () => startDrawing()
    const handleStopDrawing = () => stopDrawing()

    // Smooth animation function for drone movement
    const animateDroneToPosition = (targetPosition: {lat: number, lng: number}) => {
        const marker = droneMarkerRef.current
        if (!marker) return

        const startPosition = marker.getPosition()
        if (!startPosition) {
            // Use explicit LatLng to avoid any LatLngLiteral mismatch
            marker.setPosition(new window.google.maps.LatLng(targetPosition.lat, targetPosition.lng))
            return
        }

        const startLat = startPosition.lat()
        const startLng = startPosition.lng()
        const deltaLat = targetPosition.lat - startLat
        const deltaLng = targetPosition.lng - startLng
        
        // Calculate distance to determine animation duration
        const distance = Math.sqrt(deltaLat * deltaLat + deltaLng * deltaLng)
        const duration = Math.min(2000, Math.max(500, distance * 100000)) // 0.5-2s based on distance
        
        const startTime = performance.now()
        
        const animate = (currentTime: number) => {
            const elapsed = currentTime - startTime
            const progress = Math.min(elapsed / duration, 1)
            
            // Easing function for smooth movement
            const easeProgress = 1 - Math.pow(1 - progress, 3)
            
            const currentLat = startLat + deltaLat * easeProgress
            const currentLng = startLng + deltaLng * easeProgress
            
            // Use explicit LatLng to ensure correct API behavior
            marker.setPosition(new window.google.maps.LatLng(currentLat, currentLng))
            
            if (progress < 1) {
                animationRequestRef.current = requestAnimationFrame(animate)
            }
        }
        
        if (animationRequestRef.current) {
            cancelAnimationFrame(animationRequestRef.current)
        }
        animationRequestRef.current = requestAnimationFrame(animate)
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
        const hasValidGps = sats >= 6 && Math.abs(lat) > 0.0001 && Math.abs(lng) > 0.0001

        // Debug: log incoming GPS vs marker position
        try {
            const curPos = marker.getPosition()
            if (curPos) {
                console.debug('[Drone Marker] current marker pos:', curPos.lat(), curPos.lng())
            }
        } catch (e) {
            console.debug('[Drone Marker] could not read marker position', e)
        }

        // Update drone icon with proper size and rotation based on connection status
        const size = isConnected ? 40 : 30
        const droneIcon = {
            url: '/drone.png',
            scaledSize: new window.google.maps.Size(size, size),
            anchor: new window.google.maps.Point(size / 2, size / 2),
            rotation: heading,
            optimized: false
        }

    marker.setIcon(droneIcon)

    console.debug('[Drone Marker] incoming GPS:', lat, lng, 'hasValidGps:', hasValidGps)

        // Update position with smooth animation 
        if (hasValidGps) {
            const newPosition = { lat, lng }
            const lastPosition = lastDronePositionRef.current
            
            // Only animate if position actually changed significantly
            if (!lastPosition || 
                Math.abs(newPosition.lat - lastPosition.lat) > 0.0001 || 
                Math.abs(newPosition.lng - lastPosition.lng) > 0.0001) {
                
                console.debug('[Drone Marker] animating to new position:', newPosition, 'lastPosition:', lastPosition)
                animateDroneToPosition(newPosition)
                lastDronePositionRef.current = newPosition
            }

            // Center map on drone if not in drawing mode
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
    }, [drawnPath])

    useEffect(() => {
        const map = mapInstanceRef.current
        if (!map) return

        const timeout = setTimeout(() => {
            window.google.maps.event.trigger(map, 'resize')

            if (droneData?.gps && Math.abs(droneData.gps.latitude) > 0.0001) {
                map.panTo({
                    lat: droneData.gps.latitude,
                    lng: droneData.gps.longitude
                })
            }
        }, 100)

        return () => clearTimeout(timeout)
    }, [isFullscreen, droneData?.gps?.latitude, droneData?.gps?.longitude])

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
                            <Badge variant={droneData.satellites >= 6 ? "default" : "destructive"}>
                                GPS: {droneData.satellites}
                            </Badge>
                        )}
                        {droneData?.battery && (
                            <Badge variant={droneData.battery >= 25 ? "default" : "destructive"}>
                                🔋 {droneData.battery.toFixed(0)}%
                            </Badge>
                        )}
                    </div>
                </div>
            </CardHeader>
            <CardContent className="h-[calc(100%-80px)] space-y-4">
                {/* Blocking modal during auto-takeoff */}
                {isTakeoffActive && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
                        <div className="bg-white rounded-lg p-6 max-w-md w-full text-center">
                            <h3 className="text-lg font-semibold mb-2">Automatic Takeoff in Progress</h3>
                            <p className="text-sm text-muted-foreground">The drone is performing an automated takeoff. Mission controls are disabled until takeoff completes.</p>
                            <div className="mt-2 text-sm text-gray-700">
                                <div>Mission: <strong>{takeoffProgress?.mission_id ?? '—'}</strong></div>
                                <div>Target Altitude: <strong>{takeoffProgress?.target_altitude ?? '—'} m</strong></div>
                                <div>Current Altitude: <strong>{(takeoffProgress?.current_altitude ?? 0).toFixed(1)} m</strong></div>
                            </div>
                            <div className="mt-4">
                                <div className="h-3 bg-gray-200 rounded overflow-hidden">
                                    <div className="bg-blue-500 h-full" style={{ width: `${takeoffProgress?.percent ?? 0}%` }} />
                                </div>
                                <div className="mt-2 text-xs text-gray-500">{takeoffProgress?.percent ?? 0}%</div>
                            </div>
                            <div className="mt-4 flex gap-3 justify-center">
                                <Button
                                    variant="destructive"
                                    size="sm"
                                    onClick={async () => {
                                        const ok = confirm('Confirm cancel takeoff? This will place the vehicle into LOITER and abort the mission.');
                                        if (!ok) return;
                                        try {
                                            const res = await onCommand('cancel_takeoff')
                                            if (res?.status === 'ok') {
                                                // Let the standard takeoff messages update UI
                                                console.log('Cancel takeoff requested')
                                            } else {
                                                console.error('Cancel takeoff failed', res)
                                            }
                                        } catch (e) {
                                            console.error('Cancel takeoff error', e)
                                        }
                                    }}
                                >
                                    Cancel Takeoff
                                </Button>
                            </div>
                        </div>
                    </div>
                )}


                {/* Drawing Instructions */}
                {isDrawing && (
                    <div className="bg-green-500/20 border border-green-500/40 rounded-lg p-4 animate-pulse">
                        <div className="flex items-center gap-2 mb-2">
                            <div className="w-3 h-3 bg-green-400 rounded-full animate-ping"></div>
                            <p className="text-lg font-semibold text-green-300">Drawing Mode Active</p>
                        </div>
                        <p className="text-sm text-green-200">
                            🎯 Click anywhere on the map to add waypoints. The crosshair cursor shows you're ready to draw!
                        </p>
                        <p className="text-xs text-green-300 mt-2">
                            Added waypoints: {drawnPath.length} | Click "Stop Drawing" when finished
                        </p>
                    </div>
                )}

                {/* Map Controls */}
                <div className="flex gap-2 flex-wrap items-center justify-between">
                    <div className="flex gap-2 flex-wrap">
                        <Button
                            variant={isDrawing ? "destructive" : "default"}
                            size="sm"
                            onClick={isDrawing ? handleStopDrawing : handleDrawPath}
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
                            disabled={
                                drawnPath.length === 0 || 
                                !isConnected || 
                                isTakeoffActive ||
                                (droneData?.battery && droneData.battery < 25) ||
                                !droneData?.satellites || 
                                droneData.satellites < 6
                            }
                            className={
                                (droneData?.battery && droneData.battery < 25) ||
                                (!droneData?.satellites || droneData.satellites < 6) 
                                ? "opacity-50 cursor-not-allowed" 
                                : ""
                            }
                        >
                            <Play className="h-4 w-4 mr-2" />
                            {(droneData?.battery && droneData.battery < 25) ? 
                                `Low Battery (${droneData.battery}%)` :
                                (!droneData?.satellites || droneData.satellites < 6) ?
                                `Poor GPS (${droneData?.satellites || 0} sats)` :
                                "Start Mission"
                            }
                        </Button>

                        <Button
                            variant="destructive"
                            size="sm"
                            onClick={stopWaypointMission}
                            disabled={!isConnected || isTakeoffActive}
                        >
                            Stop Mission
                        </Button>

                        <Button
                            variant="secondary"
                            size="sm"
                            onClick={checkMissionStatus}
                            disabled={!isConnected || isTakeoffActive}
                        >
                            Mission Status
                        </Button>
``
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

                   
                </div>

              

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
                    <div className="absolute top-40 left-4 z-10 bg-black/80 backdrop-blur-sm text-white px-3 py-2 rounded-lg text-sm font-mono shadow-lg border border-white/10">
                        <div className="space-y-1">
                            <div>Lat: <span className="text-green-400">{(droneData?.gps?.latitude ?? 0).toFixed(6)}</span></div>
                            <div>Lng: <span className="text-green-400">{(droneData?.gps?.longitude ?? 0).toFixed(6)}</span></div>
                            <div>Heading: <span className="text-orange-400">{(droneData?.orientation?.heading ?? 0).toFixed(1)}°</span></div>
                            <div>GPS Valid: <span className="text-yellow-400">{(droneData?.satellites ?? 0) >= 6 && Math.abs(droneData?.gps?.latitude ?? 0) > 0.0001 ? 'Yes' : 'No'}</span></div>
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
