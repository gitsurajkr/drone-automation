import WebSocket, { WebSocketServer } from 'ws';

const PYTHON_WS_URL = 'ws://localhost:8765';
const NODE_WS_PORT = 4000;

const wss = new WebSocketServer({ port: NODE_WS_PORT });
const clients = new Set<WebSocket>();

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

        let commandToSend: string | null = null;
        let jsonToSend: string | null = null;
        try {
            const parsed = JSON.parse(raw);
            if (parsed && typeof parsed.command === 'string') {
                const cmd = parsed.command.toLowerCase();
                if (['connect', 'disconnect', 'reconnect', 'status'].includes(cmd)) {
                    commandToSend = cmd;
                } else {
                    jsonToSend = JSON.stringify(parsed);
                }
            } else {
                commandToSend = raw;
            }
        } catch (e) {
            commandToSend = raw;
        }

        if (pythonWs && pythonWs.readyState === WebSocket.OPEN) {
            try {
                if (commandToSend) pythonWs.send(commandToSend);
                else if (jsonToSend) pythonWs.send(jsonToSend);
                else pythonWs.send(raw);
            } catch (err) {
                console.error('Failed to send to Python WS:', err);
                try { ws.send(JSON.stringify({ error: 'Failed to forward to Python WS' })); } catch { };
            }
        } else {
            console.warn('Python WS not connected; cannot forward message');
            try { ws.send(JSON.stringify({ error: 'Python backend not connected' })); } catch { };
        }
    });
});

console.log(`Node.js WS server listening on ws://localhost:${NODE_WS_PORT}`);

let pythonWs: WebSocket | null = null;
let pythonConnected = false;

import http from 'http'

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
        pythonWs?.send("connect");
    });

    pythonWs.on('message', (data) => {
        const msg = data.toString();
        console.log('Python WS says:', msg);

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
