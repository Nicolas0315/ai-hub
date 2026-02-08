import { SynergyRequest, SynergyResponse } from '../proto/synergy'; // Mock or generated types
import { SynergyScorer } from './SynergyScorer';

/**
 * MediationService
 * Implementation for the Kani Manager to serve synergy scores via API.
 */
export class MediationService {
  private scorer: SynergyScorer;

  constructor() {
    this.scorer = new SynergyScorer();
  }

  /**
   * Calculate synergy between two agent profiles based on X-algorithm logic.
   */
  public async calculateSynergy(req: any): Promise<any> {
    // Convert array of interests to Map for SynergyScorer
    const mapA = new Map(req.user_a.interests.map((i: any) => [i.category, i.weight]));
    const mapB = new Map(req.user_b.interests.map((i: any) => [i.category, i.weight]));

    const score = this.scorer.computeSynergy(mapA, mapB);
    
    return {
      synergy: {
        agent_id_a: req.user_a.user_id,
        agent_id_b: req.user_b.user_id,
        score: score,
        breakdown: {
          interest_match: score
          // TODO: Add more breakdown logic based on context
        }
      }
    };
  }
}
