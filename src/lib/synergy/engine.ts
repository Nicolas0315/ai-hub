import { SynergyScorer, PhoenixScores, SCORING_WEIGHTS } from '../../../packages/katala/core/SynergyScorer';

/**
 * 16 Identity Dimensions (MBTI++ Profiling)
 */
export type IdentityDimensions = {
  // Traditional MBTI
  IE: number; // Introversion - Extroversion
  SN: number; // Sensing - Intuition
  TF: number; // Thinking - Feeling
  JP: number; // Judging - Perceiving
  // Extended Dimensions (MBTI++)
  EmotionalStability: number;
  Openness: number;
  Conscientiousness: number;
  Agreeableness: number;
  RiskTolerance: number;
  Empathy: number;
  SocialIntelligence: number;
  Creativity: number;
  Logic: number;
  Ambition: number;
  Adaptability: number;
  Altruism: number;
};

export interface XAlgorithmParams {
  dwellTimeSeconds: number;
  shareVelocity: number; // shares per unit time
  reciprocalInteraction: boolean; // if they have interacted before
}

export class SynergyEngine {
  private scorer: SynergyScorer;

  constructor() {
    this.scorer = new SynergyScorer({
      // Enhanced weighting for X-Algorithm heavy ranker logic
      DWELL_WEIGHT: 0.15, // Increased importance of dwell time
      SHARE_WEIGHT: 0.85, // Increased weight for share velocity proxy
      REPLY_WEIGHT: 1.5,  // Heavy weight for interaction
    });
  }

  /**
   * Calculate synergy based on X-Algorithm heavy ranker logic.
   * Dwell time, share velocity, and reciprocal interaction are key.
   */
  public calculateXRankerScore(baseScore: number, params: XAlgorithmParams): number {
    let multiplier = 1.0;

    // Dwell time effect (logarithmic scaling to prevent outliers)
    if (params.dwellTimeSeconds > 0) {
      multiplier += Math.log10(1 + params.dwellTimeSeconds) * 0.2;
    }

    // Share velocity boost
    multiplier += params.shareVelocity * 0.5;

    // Reciprocal interaction (High boost for mutual engagement)
    if (params.reciprocalInteraction) {
      multiplier *= 1.4;
    }

    return baseScore * multiplier;
  }

  /**
   * Calculate compatibility between two identities based on 16 dimensions.
   */
  public calculateIdentityMatch(dimA: IdentityDimensions, dimB: IdentityDimensions): number {
    const keys = Object.keys(dimA) as (keyof IdentityDimensions)[];
    let dotProduct = 0;
    
    for (const key of keys) {
      // Identity dimensions are assumed to be normalized between -1 and 1
      dotProduct += dimA[key] * dimB[key];
    }

    // Return normalized score
    return dotProduct / keys.length;
  }

  /**
   * Combined Synergy Score
   */
  public getCombinedSynergy(
    identityA: IdentityDimensions,
    identityB: IdentityDimensions,
    xParams: XAlgorithmParams
  ): number {
    const identityMatch = this.calculateIdentityMatch(identityA, identityB);
    
    // Convert identity match to a "base score" for the X-Ranker
    // Mapping [-1, 1] to [0, 100]
    const baseScore = (identityMatch + 1) * 50;

    const finalScore = this.calculateXRankerScore(baseScore, xParams);

    // Log metric in Apple HIG style (Clean, Semantic, Structured)
    this.logMetric('SynergyCalculation', {
      finalScore,
      identityMatch,
      dwellTime: xParams.dwellTimeSeconds,
      isReciprocal: xParams.reciprocalInteraction
    });

    return finalScore;
  }

  /**
   * Logs metrics following Apple HIG principles for clarity and focus.
   */
  private logMetric(event: string, data: any) {
    const timestamp = new Date().toISOString();
    console.log(`[${timestamp}] ◉ ${event}: ${JSON.stringify(data)}`);
    // Note: Apple HIG suggests focus on meaningful data without clutter.
    // The use of '◉' is a subtle visual cue often used in high-quality logs.
  }
}
