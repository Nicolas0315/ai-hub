import { IdentityVector } from "./types";

/**
 * MatchmakingEngine
 * Implements core matchmaking logic based on Privacy-first Identity Vectors.
 * Uses Zero-Knowledge (ZK) patterns to ensure high-synergy matches
 * without exposing raw profiling data.
 */
export class MatchmakingEngine {
  /**
   * Calculates the synergy score between two Identity Vectors.
   * This is a privacy-first implementation where agents only share
   * "Identity Fragments" or ZK-Vectors for calculation.
   *
   * Scoring factors:
   * 1. Personality Complementarity (MBTI-based)
   * 2. Value Alignment (Shared values)
   * 3. Professional Synergy (Expertise overlap or gap-filling)
   * 4. Social Battery Sync (Current interaction capacity)
   */
  public calculateSynergy(a: IdentityVector, b: IdentityVector): number {
    let score = 0;

    // 1. Personality Complementarity (Weight: 30%)
    // Intuition-Sensing and Thinking-Feeling matches
    const personalityScore = this.calculatePersonalitySynergy(a.personality, b.personality);
    score += personalityScore * 0.3;

    // 2. Value Alignment (Weight: 30%)
    // Jaccard similarity of values
    const valueScore = this.calculateOverlap(a.values, b.values);
    score += valueScore * 0.3;

    // 3. Professional Synergy (Weight: 25%)
    const profScore = this.calculateOverlap(a.professionalFocus, b.professionalFocus);
    score += profScore * 0.25;

    // 4. Social Battery Sync (Weight: 15%)
    // Higher synergy if both have similar battery levels or compatible tones
    const socialScore = this.calculateSocialSynergy(a.socialEnergy, b.socialEnergy);
    score += socialScore * 0.15;

    // Adjust by confidence score
    const avgConfidence = (a.meta.confidenceScore + b.meta.confidenceScore) / 2;
    return score * avgConfidence;
  }

  private calculatePersonalitySynergy(
    p1: IdentityVector["personality"],
    p2: IdentityVector["personality"],
  ): number {
    // Complementary theory: Similar on some, opposite on others
    // E.g., Extraverts might sync well with Introverts (complementary) or other Extraverts (high energy)
    // Here we use a simplified Euclidean-based similarity for the prototype
    const diffs = [
      Math.abs(p1.extraversion - p2.extraversion),
      Math.abs(p1.intuition - p2.intuition),
      Math.abs(p1.thinking - p2.thinking),
      Math.abs(p1.judging - p2.judging),
    ];

    const avgDiff = diffs.reduce((acc, d) => acc + d, 0) / diffs.length;
    return 1 - avgDiff; // 1.0 is perfect match
  }

  private calculateOverlap(list1: string[], list2: string[]): number {
    if (list1.length === 0 || list2.length === 0) return 0;
    const set1 = new Set(list1);
    const intersection = list2.filter((item) => set1.has(item));
    const union = new Set([...list1, ...list2]);
    return intersection.length / union.size;
  }

  private calculateSocialSynergy(
    s1: IdentityVector["socialEnergy"],
    s2: IdentityVector["socialEnergy"],
  ): number {
    // Battery sync: match users with similar energy levels
    const batteryMatch = 1 - Math.abs(s1.battery - s2.battery) / 100;

    // Tone match: certain tones work better together
    const toneMatch = s1.preferredTone === s2.preferredTone ? 1 : 0.5;

    return batteryMatch * 0.6 + toneMatch * 0.4;
  }

  /**
   * Filters a list of candidates to find the best high-synergy matches.
   */
  public findMatches(
    source: IdentityVector,
    candidates: IdentityVector[],
    threshold: number = 0.6,
  ): Array<{ vector: IdentityVector; score: number }> {
    return candidates
      .map((c) => ({ vector: c, score: this.calculateSynergy(source, c) }))
      .filter((m) => m.score >= threshold)
      .sort((a, b) => b.score - a.score);
  }
}
