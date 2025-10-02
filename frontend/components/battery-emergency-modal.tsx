"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { AlertTriangle, Home, Navigation } from "lucide-react"

interface BatteryEmergencyModalProps {
    isOpen: boolean
    batteryLevel: number
    distanceToHome?: number | null
    altitude: number
    gpsfix: number
    recommendation: string
    reason: string
    timeoutSeconds: number
    promptId: string
    onChoice: (choice: 'RTL' | 'LAND') => void
}

export function BatteryEmergencyModal({
    isOpen,
    batteryLevel,
    distanceToHome,
    altitude,
    gpsfix,
    recommendation,
    reason,
    timeoutSeconds,
    promptId,
    onChoice
}: BatteryEmergencyModalProps) {
    const [remainingTime, setRemainingTime] = useState(timeoutSeconds)
    const [choiceMade, setChoiceMade] = useState(false)

    useEffect(() => {
        if (!isOpen) {
            setRemainingTime(timeoutSeconds)
            setChoiceMade(false)
            return
        }

        const timer = setInterval(() => {
            setRemainingTime((prev) => {
                if (prev <= 1) {
                    clearInterval(timer)
                    return 0
                }
                return prev - 1
            })
        }, 1000)

        return () => clearInterval(timer)
    }, [isOpen, timeoutSeconds])

    const handleChoice = (choice: 'RTL' | 'LAND') => {
        if (choiceMade) return // Prevent multiple clicks
        setChoiceMade(true)
        onChoice(choice)
    }

    if (!isOpen) return null

    const formatDistance = (distance: number | null | undefined) => {
        if (distance === null || distance === undefined) return "Unknown"
        return distance < 1000 ? `${distance.toFixed(1)}m` : `${(distance / 1000).toFixed(1)}km`
    }

    const getGpsStatus = (fix: number) => {
        if (fix >= 3) return { text: "Good", color: "bg-green-500" }
        if (fix === 2) return { text: "Fair", color: "bg-yellow-500" }
        return { text: "Poor", color: "bg-red-500" }
    }

    const gpsStatus = getGpsStatus(gpsfix)

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <Card className="w-full max-w-lg mx-4 border-2 border-red-500 shadow-2xl">
                <CardHeader className="text-center bg-red-50 border-b border-red-200">
                    <div className="flex items-center justify-center gap-2 mb-2">
                        <AlertTriangle className="h-8 w-8 text-red-600 animate-pulse" />
                        <CardTitle className="text-2xl font-bold text-red-700">
                            BATTERY EMERGENCY
                        </CardTitle>
                    </div>
                    <div className="text-4xl font-bold text-red-600">
                        {batteryLevel}% Battery
                    </div>
                    <div className="text-lg font-semibold text-gray-700">
                        Auto-RTL in {Math.ceil(remainingTime)}s
                    </div>
                </CardHeader>

                <CardContent className="p-6">
                    {/* Flight Status */}
                    <div className="grid grid-cols-2 gap-4 mb-6">
                        <div className="text-center">
                            <div className="text-sm text-gray-500">Distance to Home</div>
                            <div className="font-semibold">{formatDistance(distanceToHome)}</div>
                        </div>
                        <div className="text-center">
                            <div className="text-sm text-gray-500">Altitude</div>
                            <div className="font-semibold">{altitude.toFixed(1)}m</div>
                        </div>
                        <div className="text-center">
                            <div className="text-sm text-gray-500">GPS Status</div>
                            <Badge className={`${gpsStatus.color} text-white`}>
                                {gpsStatus.text}
                            </Badge>
                        </div>
                        <div className="text-center">
                            <div className="text-sm text-gray-500">GPS Fix</div>
                            <div className="font-semibold">{gpsfix}</div>
                        </div>
                    </div>

                    {/* Recommendation */}
                    <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
                        <div className="font-semibold text-blue-800 mb-1">
                            💡 Recommended: {recommendation}
                        </div>
                        <div className="text-sm text-blue-700">{reason}</div>
                    </div>

                    {/* Action Buttons */}
                    <div className="grid grid-cols-2 gap-4">
                        <Button
                            onClick={() => handleChoice('RTL')}
                            disabled={choiceMade}
                            className={`h-16 text-lg font-bold flex flex-col items-center gap-1 ${choiceMade
                                ? 'bg-gray-400 cursor-not-allowed'
                                : recommendation === 'RTL'
                                    ? 'bg-green-600 hover:bg-green-700 border-2 border-green-400'
                                    : 'bg-blue-600 hover:bg-blue-700'
                                }`}
                        >
                            <Home className="h-6 w-6" />
                            <span>{choiceMade ? 'Processing...' : 'Return to Launch'}</span>
                            {!choiceMade && recommendation === 'RTL' && <span className="text-xs">(Recommended)</span>}
                        </Button>

                        <Button
                            onClick={() => handleChoice('LAND')}
                            disabled={choiceMade}
                            className={`h-16 text-lg font-bold flex flex-col items-center gap-1 ${choiceMade
                                ? 'bg-gray-400 cursor-not-allowed'
                                : recommendation === 'LAND'
                                    ? 'bg-green-600 hover:bg-green-700 border-2 border-green-400'
                                    : 'bg-orange-600 hover:bg-orange-700'
                                }`}
                        >
                            <Navigation className="h-6 w-6" />
                            <span>{choiceMade ? 'Processing...' : 'Land Here'}</span>
                            {!choiceMade && recommendation === 'LAND' && <span className="text-xs">(Recommended)</span>}
                        </Button>
                    </div>

                    {/* Countdown Progress Bar */}
                    <div className="mt-6">
                        <div className="flex justify-between text-sm text-gray-600 mb-1">
                            <span>Auto-RTL countdown</span>
                            <span>{Math.ceil(remainingTime)}s remaining</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-3">
                            <div
                                className="bg-red-500 h-3 rounded-full transition-all duration-500 ease-linear"
                                style={{ width: `${(remainingTime / timeoutSeconds) * 100}%` }}
                            />
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}