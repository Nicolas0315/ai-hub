import * as http from 'http';
import { LocalMediationManager } from '../core/LocalMediationManager';

/**
 * KatalaClawGateway
 * The "Katala-Claw" bridge for cross-agent communication.
 * Ensures secure handshakes and integrates local mediation.
 */
export class KatalaClawGateway {
    private manager: LocalMediationManager;
    private server: http.Server | null = null;
    private port: number;

    constructor(port: number = 18789) {
        this.port = port;
        this.manager = new LocalMediationManager();
    }

    /**
     * Starts the gateway server.
     */
    public start(): void {
        this.server = http.createServer(async (req, res) => {
            const clientIp = req.socket.remoteAddress || 'unknown';
            
            // 1. Secure Handshake using Tailscale Identity
            const isAuthorized = await this.manager.verifyIdentity(clientIp);
            
            if (!isAuthorized) {
                console.warn(`[Gateway] ⚠ Unauthorized connection attempt from ${clientIp}`);
                res.writeHead(403, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'Forbidden: Untrusted Tailscale identity' }));
                return;
            }

            // 2. Route Handling
            if (req.method === 'POST' && req.url === '/synergy/mediate') {
                this.handleMediation(req, res);
            } else if (req.method === 'GET' && req.url === '/health') {
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ status: 'active', bridge: 'Katala-Claw' }));
            } else {
                res.writeHead(404);
                res.end();
            }
        });

        this.server.listen(this.port, () => {
            console.log(`[Gateway] 🚀 Katala-Claw Bridge active on port ${this.port}`);
            console.log(`[Gateway] 🛡 Tailscale Identity Verification: ENABLED`);
        });
    }

    /**
     * Handles the synergy mediation request via the bridge.
     */
    private async handleMediation(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
        let body = '';
        req.on('data', chunk => { body += chunk; });
        req.on('end', async () => {
            try {
                const synergyReq = JSON.parse(body);
                const result = await this.manager.mediate(synergyReq);
                
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify(result));
            } catch (error) {
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'Internal Mediation Error' }));
            }
        });
    }

    /**
     * Stops the gateway server.
     */
    public stop(): void {
        if (this.server) {
            this.server.close();
            console.log(`[Gateway] 💤 Katala-Claw Bridge shut down gracefully`);
        }
    }
}
