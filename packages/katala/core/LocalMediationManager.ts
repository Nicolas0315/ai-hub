import * as grpc from '@grpc/grpc-js';
import { SynergyRequest, SynergyResponse } from '../proto/synergy';
import { MediationService } from './MediationService';
import { SynergyEngine } from './SynergyEngine';

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
        // Log mediation attempt following Apple HIG (clear, concise)
        console.log(`[Mediation] Processing synergy request for ${request.user_a?.user_id} and ${request.user_b?.user_id}`);
        
        try {
            const result = await this.service.calculateSynergy(request);
            return result as SynergyResponse;
        } catch (error) {
            console.error(`[Mediation] ✕ Failed to calculate synergy:`, error);
            throw error;
        }
    }

    /**
     * Performs local identity verification for handshake.
     */
    public async verifyIdentity(tailscaleIp: string): Promise<boolean> {
        // In a real implementation, we would use Tailscale API or local environment
        // to verify that the IP belongs to a trusted node in the same tailnet.
        console.log(`[Security] Verifying Tailscale identity for ${tailscaleIp}`);
        
        // Placeholder: assume all Tailscale IPs (100.x.y.z) are valid for this bridge demo
        return tailscaleIp.startsWith('100.');
    }
}
