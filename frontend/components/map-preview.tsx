// "use client"

// import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
// import { Button } from "@/components/ui/button"
// import { MapPin, ExternalLink } from "lucide-react"
// import type { DroneData } from "@/hooks/use-drone-data"
// import { useEffect, useRef } from "react"

// interface MapPreviewProps {
//   droneData: DroneData | null
//   onOpenFullMap: () => void
//   isConnected: boolean
// }

// export function MapPreview({ droneData, onOpenFullMap, isConnected }: MapPreviewProps) {
//   const canvasRef = useRef<HTMLCanvasElement>(null)

//   useEffect(() => {
//     const canvas = canvasRef.current
//     if (!canvas) return

//     const ctx = canvas.getContext("2d")
//     if (!ctx) return

//     // Clear canvas
//     ctx.fillStyle = "#0a0a0a"
//     ctx.fillRect(0, 0, canvas.width, canvas.height)

//     // Draw grid
//     ctx.strokeStyle = "#333"
//     ctx.lineWidth = 1
//     for (let i = 0; i <= 20; i++) {
//       const x = (i / 20) * canvas.width
//       const y = (i / 20) * canvas.height

//       ctx.beginPath()
//       ctx.moveTo(x, 0)
//       ctx.lineTo(x, canvas.height)
//       ctx.stroke()

//       ctx.beginPath()
//       ctx.moveTo(0, y)
//       ctx.lineTo(canvas.width, y)
//       ctx.stroke()
//     }

//     // Draw drone position (center of preview)
//     const centerX = canvas.width / 2
//     const centerY = canvas.height / 2

//     // Drone marker
//     ctx.fillStyle = isConnected ? "#ef4444" : "#6b7280"
//     ctx.beginPath()
//     ctx.arc(centerX, centerY, 8, 0, 2 * Math.PI)
//     ctx.fill()

//     // Direction indicator (if available)
//     if (droneData?.orientation) {
//       ctx.strokeStyle = isConnected ? "#ef4444" : "#6b7280"
//       ctx.lineWidth = 2
//       ctx.beginPath()
//       const angle = ((droneData.orientation.yaw ?? 0) * Math.PI) / 180
//       const lineLength = 15
//       ctx.moveTo(centerX, centerY)
//       ctx.lineTo(centerX + Math.sin(angle) * lineLength, centerY - Math.cos(angle) * lineLength)
//       ctx.stroke()
//     }

//     // Add coordinates text (if GPS available)
//     if (droneData?.gps) {
//       ctx.fillStyle = "#ffffff"
//       ctx.font = "10px monospace"
//       ctx.textAlign = "center"
//       ctx.fillText(`${(droneData.gps.latitude ?? 0).toFixed(4)}`, centerX, canvas.height - 20)
//       ctx.fillText(`${(droneData.gps.longitude ?? 0).toFixed(4)}`, centerX, canvas.height - 8)
//     }
//   }, [droneData?.gps?.latitude, droneData?.gps?.longitude, droneData?.orientation?.yaw, isConnected])

//   return (
//     <Card className="bg-card border-border">
//       <CardHeader className="pb-3">
//         <CardTitle className="text-base flex items-center gap-2">
//           <MapPin className="h-4 w-4" />
//           Map Preview
//         </CardTitle>
//       </CardHeader>
//       <CardContent>
//         <div className="relative bg-black rounded-lg overflow-hidden cursor-pointer group" onClick={onOpenFullMap}>
//           <canvas ref={canvasRef} width={300} height={200} className="w-full h-full object-cover" />

//           {/* Hover overlay */}
//           <div className="absolute inset-0 bg-blue-500/10 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
//             <Button variant="secondary" size="sm">
//               <ExternalLink className="h-4 w-4 mr-2" />
//               Open Full Map
//             </Button>
//           </div>

//           {/* Status indicator */}
//           <div className="absolute top-2 left-2 bg-black/80 text-white px-2 py-1 rounded text-xs font-mono">
//             <div className="flex items-center gap-1">
//               <div className={`w-1.5 h-1.5 rounded-full ${isConnected ? "bg-green-500" : "bg-red-500"}`}></div>
//               {isConnected ? "Live" : "Offline"}
//             </div>
//           </div>

//           {/* Altitude indicator */}
//           <div className="absolute top-2 right-2 bg-black/80 text-white px-2 py-1 rounded text-xs font-mono">
//             {(droneData?.altitude ?? 0).toFixed(1)}m
//           </div>
//         </div>
//       </CardContent>
//     </Card>
//   )
// }
