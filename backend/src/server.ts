import WebSocket, { WebSocketServer } from 'ws';
import http from 'http'
const PYTHON_WS_URL = 'ws://localhost:8765';
const NODE_WS_PORT = 4000;

const wss = new WebSocketServer({ port: NODE_WS_PORT });
const clients = new Set<WebSocket>();
const pendingRequests: Map<string, WebSocket> = new Map();

wss.on('connection', (ws) => {
    clients.add(ws);
    console.log('Frontend client connected');

    ws.on('close', () => {
        clients.delete(ws);
        console.log('Frontend client disconnected');
    });

    ws.on('message', (data) => {
        const raw = data.toString();
        console.log('Received from frontend:', raw);

        // Always try to send JSON commands to Python first
        try {
            const parsed = JSON.parse(raw);
            if (parsed && (parsed.type || parsed.command)) {
                // Forward all JSON commands directly to Python
                if (pythonWs && pythonWs.readyState === WebSocket.OPEN) {
                    // Store pending request for response routing
                    const maybeId = parsed.id;
                    if (maybeId && typeof maybeId === 'string') {
                        pendingRequests.set(maybeId, ws);
                    }
                    pythonWs.send(raw);
                    return;
                }
            }
        } catch (e) {
            const cmd = raw.toLowerCase();
            if (['connect', 'disconnect', 'reconnect', 'status', 'arm', 'disarm'].includes(cmd)) {
                if (pythonWs && pythonWs.readyState === WebSocket.OPEN) {
                    pythonWs.send(cmd);
                    return;
                }
            }
        }

        // If we reach here, Python WS is not connected
        console.warn('Python WS not connected; cannot forward message');
        try {
            ws.send(JSON.stringify({
                error: 'Python backend not connected',
                id: (() => {
                    try {
                        const parsed = JSON.parse(raw);
                        return parsed.id;
                    } catch {
                        return null;
                    }
                })()
            }));
        } catch { }
    });
});

console.log(`Node.js WS server listening on ws://localhost:${NODE_WS_PORT}`);

let pythonWs: WebSocket | null = null;
let pythonConnected = false;

const HEALTH_PORT = 4001
const healthServer = http.createServer((req, res) => {
    if (req.method === 'GET' && req.url === '/health') {
        res.setHeader('Content-Type', 'application/json')
        res.setHeader('Access-Control-Allow-Origin', '*')
        res.end(JSON.stringify({ pythonConnected }))
        return
    }
    res.statusCode = 404
    res.end('Not found')
})

healthServer.listen(HEALTH_PORT, () => {
    console.log(`Health endpoint listening on http://localhost:${HEALTH_PORT}/health`)
})

function connectPythonWS() {
    pythonWs = new WebSocket(PYTHON_WS_URL);

    pythonWs.on('open', () => {
        console.log('Connected to Python WS server');
        pythonConnected = true;
        // Don't auto-connect to drone, let frontend control this
    });

    pythonWs.on('message', (data) => {
        const msg = data.toString();
        console.log('Python WS says:', msg);

        // Attempt to parse the message and, if it contains an id, send the response back to the client that made the request.
        try {
            const parsed = JSON.parse(msg);
            const respId = parsed && parsed.id;
            if (respId && typeof respId === 'string') {
                const origin = pendingRequests.get(respId);
                if (origin && origin.readyState === WebSocket.OPEN) {
                    origin.send(msg);
                    pendingRequests.delete(respId);
                    return;
                }
            }
        } catch (e) {
            // not JSON — fall through to broadcast
        }

        for (const client of clients) {
            if (client.readyState === WebSocket.OPEN) {
                client.send(msg);
            }
        }
    });

    pythonWs.on('close', () => {
        console.log('Disconnected from Python WS. Reconnecting in 2s...');
        pythonConnected = false;
        setTimeout(connectPythonWS, 2000);
    });

    pythonWs.on('error', (err) => {
        console.error('Python WS error:', err);
        pythonConnected = false;
    });
}

connectPythonWS();

export { pythonWs };
