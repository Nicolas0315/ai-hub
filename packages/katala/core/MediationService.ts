import { SynergyRequest, SynergyResponse } from '../proto/synergy'; // Mock or generated types
import { SynergyScorer } from './SynergyScorer';
import { MatchmakingEngine } from './MatchmakingEngine';
import { IdentityVector } from './types';

/**
 * MediationService
 * Implementation for the Kani Manager to serve synergy scores via API.
 */
export class MediationService {
  private scorer: SynergyScorer;
  private matchmaking: MatchmakingEngine;

  constructor() {
    this.scorer = new SynergyScorer();
    this.matchmaking = new MatchmakingEngine();
  }

  /**
   * Calculate synergy between two agent profiles based on X-algorithm logic.
   * Supports both legacy interest-based and modern Identity Vector-based scoring.
   */
  public async calculateSynergy(req: any): Promise<any> {
    // Check if request is Identity Vector based (Privacy-first)
    if (req.user_a.identity_vector && req.user_b.identity_vector) {
      const score = this.matchmaking.calculateSynergy(
        req.user_a.identity_vector as IdentityVector,
        req.user_b.identity_vector as IdentityVector
      );

      return {
        synergy: {
          agent_id_a: req.user_a.user_id,
          agent_id_b: req.user_b.user_id,
          score: score,
          method: 'identity-vector-zk',
          breakdown: {
            privacy_level: 'high',
            synergy_score: score
          }
        }
      };
    }

    // Fallback to legacy interest-based scoring
    const mapA = new Map(req.user_a.interests.map((i: any) => [i.category, i.weight]));
    const mapB = new Map(req.user_b.interests.map((i: any) => [i.category, i.weight]));

    const score = this.scorer.computeSynergy(mapA, mapB);
    
    return {
      synergy: {
        agent_id_a: req.user_a.user_id,
        agent_id_b: req.user_b.user_id,
        score: score,
        method: 'legacy-interest-dot-product',
        breakdown: {
          interest_match: score
        }
      }
    };
  }
}
