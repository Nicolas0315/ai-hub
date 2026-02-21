import { MBTIPlusPlus, IdentityVector } from "./types";

/**
 * X-Algorithm inspired engagement metrics for synergy calculation.
 * These reflect the "Heavy Ranker" logic: dwell time, velocity, and reciprocity.
 */
export interface EngagementMetrics {
  dwellTimeSeconds: number; // How long the interaction lasted
  shareVelocity: number; // How quickly content is shared/propagated
  reciprocalInteraction: number; // Mutual likes/replies/follows between agents
  clickProbability: number; // Likelihood of deep-diving into content
  negativeFeedback: number; // Mutes, blocks, or "not interested" signals
}

export interface SynergyResult {
  combinedScore: number;
  dimensions: {
    personalitySynergy: number;
    engagementBoost: number;
    confidenceAdjustment: number;
  };
  metadata: {
    timestamp: string;
    version: string;
    engine: "X-Algorithm-Integrated-v1";
  };
}

/**
 * SynergyEngine: A robust backend service for calculating agent-to-agent
 * and agent-to-user synergy using X-Algorithm heavy ranker logic and
 * MBTI++ 16-dimensional profiling.
 */
export class SynergyEngine {
  // Heavy Ranker Weights (Adapted from X/Twitter Algorithm)
  private static readonly WEIGHTS = {
    // High-impact engagement
    RECIPROCAL_WEIGHT: 5.0,
    SHARE_VELOCITY_WEIGHT: 2.5,
    DWELL_TIME_WEIGHT: 0.05, // Linear growth
    CLICK_WEIGHT: 1.5,

    // Identity synergy
    PERSONALITY_MATCH_WEIGHT: 10.0,

    // Penalties
    NEGATIVE_FEEDBACK_WEIGHT: -15.0,
  };

  /**
   * Calculates a comprehensive synergy score between two Identity Vectors.
   * Follows Apple HIG for metric transparency and clarity.
   */
  public calculateSynergy(
    source: IdentityVector,
    target: IdentityVector,
    engagement?: EngagementMetrics,
  ): SynergyResult {
    const personalityScore = this.computePersonalitySynergy(source.personality, target.personality);
    const engagementScore = engagement ? this.computeEngagementBoost(engagement) : 0;

    // Confidence as a quality multiplier (lower confidence = more regression to mean)
    const confidenceMultiplier = (source.meta.confidenceScore + target.meta.confidenceScore) / 2;

    const combinedScore = (personalityScore + engagementScore) * confidenceMultiplier;

    return {
      combinedScore,
      dimensions: {
        personalitySynergy: personalityScore,
        engagementBoost: engagementScore,
        confidenceAdjustment: confidenceMultiplier,
      },
      metadata: {
        timestamp: new Date().toISOString(),
        version: "1.0.0",
        engine: "X-Algorithm-Integrated-v1",
      },
    };
  }

  /**
   * MBTI++ 16-Dimensional Vector Comparison
   */
  private computePersonalitySynergy(p1: MBTIPlusPlus, p2: MBTIPlusPlus): number {
    let synergy = 0;
    const keys = Object.keys(p1) as (keyof MBTIPlusPlus)[];

    for (const key of keys) {
      // We calculate similarity: 1 - abs(v1 - v2)
      // If both are high or both are low on a dimension, they align.
      const similarity = 1 - Math.abs(p1[key] - p2[key]);
      synergy += similarity;
    }

    // Normalize and apply weight
    return (synergy / keys.length) * SynergyEngine.WEIGHTS.PERSONALITY_MATCH_WEIGHT;
  }

  /**
   * X-Algorithm Heavy Ranker Logic
   */
  private computeEngagementBoost(metrics: EngagementMetrics): number {
    let boost = 0;

    boost += metrics.reciprocalInteraction * SynergyEngine.WEIGHTS.RECIPROCAL_WEIGHT;
    boost += metrics.shareVelocity * SynergyEngine.WEIGHTS.SHARE_VELOCITY_WEIGHT;
    boost += metrics.dwellTimeSeconds * SynergyEngine.WEIGHTS.DWELL_TIME_WEIGHT;
    boost += metrics.clickProbability * SynergyEngine.WEIGHTS.CLICK_WEIGHT;
    boost += metrics.negativeFeedback * SynergyEngine.WEIGHTS.NEGATIVE_FEEDBACK_WEIGHT;

    return boost;
  }

  /**
   * Apple HIG compliant logging
   * Categorizes metrics into readable, actionable logs.
   */
  public logMetrics(result: SynergyResult): void {
    console.log(
      `[SynergyEngine] [${result.metadata.timestamp}] Synergy Score: ${result.combinedScore.toFixed(2)}`,
    );
    console.log(` └ Personality Alignment: ${result.dimensions.personalitySynergy.toFixed(2)}`);
    console.log(` └ Engagement Velocity: ${result.dimensions.engagementBoost.toFixed(2)}`);
    console.log(
      ` └ System Confidence: ${(result.dimensions.confidenceAdjustment * 100).toFixed(0)}%`,
    );
  }
}
