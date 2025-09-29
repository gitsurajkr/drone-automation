import { pythonWs } from './server';

export function sendTelemetryCommand(cmd: "connect" | "disconnect" | "reconnect") {
    if (pythonWs && pythonWs.readyState === 1) {
        pythonWs.send(cmd);
    } else {
        console.warn('Cannot send command, Python WS not connected');
    }
}

export function checkDroneStatus() {
    if (pythonWs && pythonWs.readyState === 1) {
        pythonWs.send("status");
    } else {
        console.warn('Cannot check status, Python WS not connected');
    }
}

// export function sendArmCommand() {
//     if (pythonWs && pythonWs.readyState === 1) {
//         pythonWs.send(JSON.stringify({ command: "ARM" }));
//     }
// }
