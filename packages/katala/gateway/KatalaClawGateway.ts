import * as http from "http";
import { LocalMediationManager } from "../core/LocalMediationManager";
import { IntakeEnvelope, IntakeRouter } from "./IntakeRouter";
import { PythonInfCodingAdapter } from "./PythonInfCodingAdapter";

/**
 * KatalaClawGateway
 * The "Katala-Claw" bridge for cross-agent communication.
 * Ensures secure handshakes and integrates local mediation.
 */
export class KatalaClawGateway {
  private manager: LocalMediationManager;
  private intakeRouter: IntakeRouter;
  private pythonAdapter: PythonInfCodingAdapter;
  private server: http.Server | null = null;
  private port: number;

  constructor(port: number = 18789) {
    this.port = port;
    this.manager = new LocalMediationManager();
    this.intakeRouter = new IntakeRouter();
    this.pythonAdapter = new PythonInfCodingAdapter();
  }

  /**
   * Starts the gateway server.
   */
  public start(): void {
    this.server = http.createServer(async (req, res) => {
      const clientIp = req.socket.remoteAddress || "unknown";

      // Log incoming connection following Apple HIG (clear and professional)
      console.log(`[Gateway] ⚯ Incoming connection from ${clientIp}`);

      // 1. Secure Handshake using Tailscale Identity
      const isAuthorized = await this.manager.verifyIdentity(clientIp);

      if (!isAuthorized) {
        console.warn(`[Gateway] ⚠ Unauthorized connection attempt from ${clientIp}`);
        res.writeHead(403, { "Content-Type": "application/json" });
        res.end(
          JSON.stringify({
            error: "Forbidden: Untrusted Tailscale identity",
            detail: "Access is limited to verified Tailscale nodes within the private network.",
          }),
        );
        return;
      }

      // 2. Route Handling
      if (req.method === "POST" && req.url === "/synergy/mediate") {
        this.handleMediation(req, res);
      } else if (req.method === "POST" && req.url === "/intake/discord") {
        this.handleDiscordIntake(req, res);
      } else if (req.method === "GET" && req.url === "/health") {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(
          JSON.stringify({
            status: "active",
            bridge: "Katala-Claw",
            identity: "verified",
          }),
        );
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
  private async handleMediation(
    req: http.IncomingMessage,
    res: http.ServerResponse,
  ): Promise<void> {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
    });
    req.on("end", async () => {
      try {
        const synergyReq = JSON.parse(body);

        // Process through LocalMediationManager
        const result = await this.manager.mediate(synergyReq);

        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify(result));
      } catch (error) {
        console.error(`[Gateway] ✕ Mediation Error:`, error);
        res.writeHead(500, { "Content-Type": "application/json" });
        res.end(
          JSON.stringify({
            error: "Internal Mediation Error",
            message: error instanceof Error ? error.message : "Unknown error",
          }),
        );
      }
    });
  }

  private async handleDiscordIntake(
    req: http.IncomingMessage,
    res: http.ServerResponse,
  ): Promise<void> {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
    });
    req.on("end", async () => {
      try {
        const envelope = JSON.parse(body) as IntakeEnvelope;
        const routed = this.intakeRouter.routeDiscordMessage(envelope);

        if (!routed.ok) {
          res.writeHead(400, { "Content-Type": "application/json" });
          res.end(JSON.stringify(routed));
          return;
        }

        const handoff = await this.pythonAdapter.handoffDiscordEnvelope(routed.envelope, routed);
        const responsePayload = {
          ...routed,
          handoff: handoff.payload,
          reply: (handoff.payload as Record<string, unknown>).reply ?? routed.reply,
        };

        res.writeHead(handoff.ok ? 200 : handoff.status, { "Content-Type": "application/json" });
        res.end(JSON.stringify(responsePayload));
      } catch (error) {
        console.error(`[Gateway] ✕ Discord Intake Error:`, error);
        res.writeHead(500, { "Content-Type": "application/json" });
        res.end(
          JSON.stringify({
            error: "Internal Intake Error",
            message: error instanceof Error ? error.message : "Unknown error",
          }),
        );
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
