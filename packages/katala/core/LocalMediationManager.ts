// import * as grpc from "@grpc/grpc-js";
import { SynergyRequest, SynergyResponse } from "../proto/synergy";
import { MediationService } from "./MediationService";
import { SynergyEngine } from "./SynergyEngine";

/**
 * LocalMediationManager
 * Manages the local lifecycle and mediation between local agents.
 * Integrates with the Gateway for Katala-Claw bridge.
 */
export class LocalMediationManager {
  private service: MediationService;
  private engine: SynergyEngine;

  constructor() {
    this.service = new MediationService();
    this.engine = new SynergyEngine();
  }

  /**
   * Resolves a synergy request locally.
   */
  public async mediate(request: SynergyRequest): Promise<SynergyResponse> {
    const userA = request.user_a?.user_id || "unknown";
    const userB = request.user_b?.user_id || "unknown";

    // Log mediation attempt following Apple HIG (informative and concise)
    console.log(`[Mediation] ⚖️  Calculating synergy for ${userA} ↔ ${userB}`);

    try {
      const result = await this.service.calculateSynergy(request as any);
      console.log(
        `[Mediation] ✓ Result computed: ${(result.synergy?.score || 0).toFixed(2)} synergy`,
      );
      return result as SynergyResponse;
    } catch (error) {
      console.error(`[Mediation] ✕ Failed to calculate synergy:`, error);
      throw error;
    }
  }

  /**
   * Performs local identity verification for handshake using Tailscale metadata.
   */
  public async verifyIdentity(tailscaleIp: string): Promise<boolean> {
    // Tailscale IPs are always in the 100.64.0.0/10 range (CGNAT)
    // or IPv6 fd7a:115c:a1e0::/48 range.

    console.log(`[Security] 🛡  Verifying Tailscale identity: ${tailscaleIp}`);

    // Basic range check for Tailscale IPv4/IPv6
    const isTailscale = tailscaleIp.startsWith("100.") || tailscaleIp.startsWith("fd7a:115c:a1e0:");

    if (isTailscale) {
      // In production, this would call 'tailscale status' or use the local API
      // to verify the node is owned by the expected tailnet user.
      return true;
    }

    return false;
  }
}
