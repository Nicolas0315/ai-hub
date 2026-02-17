import { SynergyRequest, SynergyResponse, Interest } from './types';
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
  public async calculateSynergy(req: SynergyRequest): Promise<SynergyResponse> {
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
    const interests_a: Interest[] = req.user_a.interests ?? [];
    const interests_b: Interest[] = req.user_b.interests ?? [];

    const mapA = new Map(interests_a.map((i) => [i.category, i.weight]));
    const mapB = new Map(interests_b.map((i) => [i.category, i.weight]));

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
