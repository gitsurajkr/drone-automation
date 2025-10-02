"use client"

import React, { useEffect, useState } from 'react'
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { AlertTriangle, Battery, MapPin, Satellite, Gauge } from "lucide-react"

interface BatteryEmergencyModalProps {
    isOpen: boolean
    batteryLevel: number
    distanceToHome?: number
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

    useEffect(() => {
        if (!isOpen) {
            setRemainingTime(timeoutSeconds)
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

    if (!isOpen) return null

    const getBatteryColor = (level: number) => {
        if (level <= 15) return "text-red-600 bg-red-100"
        if (level <= 25) return "text-orange-600 bg-orange-100"
        return "text-yellow-600 bg-yellow-100"
    }

    const getGpsStatus = (fix: number) => {
        if (fix >= 3) return { text: "Good", color: "text-green-600" }
        if (fix === 2) return { text: "Poor", color: "text-orange-600" }
        return { text: "Bad", color: "text-red-600" }
    }

    const gpsStatus = getGpsStatus(gpsfix)

    return (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
            <Card className="max-w-md w-full mx-4 border-red-500 shadow-2xl">
                <CardHeader className="bg-red-50 border-b border-red-200">
                    <CardTitle className="flex items-center gap-2 text-red-700">
                        <AlertTriangle className="h-6 w-6 animate-pulse" />
                        🚨 BATTERY EMERGENCY
                    </CardTitle>
                </CardHeader>

                <CardContent className="p-6 space-y-4">
                    {/* Battery Level */}
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Battery className="h-5 w-5 text-red-600" />
                            <span className="font-medium">Battery Level</span>
                        </div>
                        <Badge className={getBatteryColor(batteryLevel)}>
                            {batteryLevel}%
                        </Badge>
                    </div>

                    {/* Flight Status */}
                    <div className="grid grid-cols-2 gap-4 text-sm">
                        <div className="flex items-center gap-2">
                            <Gauge className="h-4 w-4 text-blue-600" />
                            <span>Altitude: {altitude.toFixed(1)}m</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Satellite className={`h-4 w-4 ${gpsStatus.color}`} />
                            <span className={gpsStatus.color}>GPS: {gpsStatus.text}</span>
                        </div>
                        {distanceToHome !== null && distanceToHome !== undefined && (
                            <div className="col-span-2 flex items-center gap-2">
                                <MapPin className="h-4 w-4 text-green-600" />
                                <span>Distance to Home: {distanceToHome.toFixed(1)}m</span>
                            </div>
                        )}
                    </div>

                    {/* Recommendation */}
                    <div className="bg-blue-50 p-3 rounded-lg border border-blue-200">
                        <div className="font-medium text-blue-800 mb-1">
                            💡 Recommendation: {recommendation}
                        </div>
                        <div className="text-sm text-blue-700">{reason}</div>
                    </div>

                    {/* Countdown */}
                    <div className="text-center">
                        <div className="text-2xl font-bold text-red-600 mb-1">
                            {remainingTime}s
                        </div>
                        <div className="text-sm text-gray-600">
                            Choose action or RTL will be selected automatically
                        </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="grid grid-cols-2 gap-3">
                        <Button
                            onClick={() => onChoice('RTL')}
                            variant={recommendation === 'RTL' ? 'default' : 'outline'}
                            className={`h-16 text-lg font-semibold ${recommendation === 'RTL'
                                    ? 'bg-green-600 hover:bg-green-700 text-white'
                                    : ''
                                }`}
                            disabled={remainingTime === 0}
                        >
                            🏠 RTL
                            <div className="text-xs font-normal mt-1">Return to Launch</div>
                        </Button>

                        <Button
                            onClick={() => onChoice('LAND')}
                            variant={recommendation === 'LAND' ? 'default' : 'outline'}
                            className={`h-16 text-lg font-semibold ${recommendation === 'LAND'
                                    ? 'bg-orange-600 hover:bg-orange-700 text-white'
                                    : ''
                                }`}
                            disabled={remainingTime === 0}
                        >
                            ⬇️ LAND
                            <div className="text-xs font-normal mt-1">Emergency Land</div>
                        </Button>
                    </div>

                    {/* Progress Bar */}
                    <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                            className="bg-red-600 h-2 rounded-full transition-all duration-1000"
                            style={{ width: `${(remainingTime / timeoutSeconds) * 100}%` }}
                        />
                    </div>
                </CardContent>
            </Card>
        </div>
    )
}