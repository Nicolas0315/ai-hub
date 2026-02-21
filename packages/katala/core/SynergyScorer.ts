export interface PhoenixScores {
  favorite_score?: number;
  reply_score?: number;
  retweet_score?: number;
  photo_expand_score?: number;
  click_score?: number;
  profile_click_score?: number;
  vqv_score?: number;
  share_score?: number;
  share_via_dm_score?: number;
  share_via_copy_link_score?: number;
  dwell_score?: number;
  quote_score?: number;
  quoted_click_score?: number;
  dwell_time?: number;
  follow_author_score?: number;
  not_interested_score?: number;
  block_author_score?: number;
  mute_author_score?: number;
  report_score?: number;
}

export const SCORING_WEIGHTS = {
  FAVORITE_WEIGHT: 0.5,
  REPLY_WEIGHT: 1.0,
  RETWEET_WEIGHT: 0.8,
  PHOTO_EXPAND_WEIGHT: 0.2,
  CLICK_WEIGHT: 0.3,
  PROFILE_CLICK_WEIGHT: 0.4,
  VQV_WEIGHT: 0.6,
  SHARE_WEIGHT: 0.7,
  SHARE_VIA_DM_WEIGHT: 1.2,
  SHARE_VIA_COPY_LINK_WEIGHT: 0.9,
  DWELL_WEIGHT: 0.1,
  QUOTE_WEIGHT: 1.1,
  QUOTED_CLICK_WEIGHT: 0.5,
  CONT_DWELL_TIME_WEIGHT: 0.01,
  FOLLOW_AUTHOR_WEIGHT: 2.0,
  NOT_INTERESTED_WEIGHT: -1.0,
  BLOCK_AUTHOR_WEIGHT: -5.0,
  MUTE_AUTHOR_WEIGHT: -3.0,
  REPORT_WEIGHT: -10.0,
};

export class SynergyScorer {
  private weights: typeof SCORING_WEIGHTS;

  constructor(customWeights?: Partial<typeof SCORING_WEIGHTS>) {
    this.weights = { ...SCORING_WEIGHTS, ...customWeights };
  }

  private applyWeight(score: number | undefined, weight: number): number {
    return (score ?? 0) * weight;
  }

  public computeWeightedScore(scores: PhoenixScores): number {
    let combinedScore = 0;

    combinedScore += this.applyWeight(scores.favorite_score, this.weights.FAVORITE_WEIGHT);
    combinedScore += this.applyWeight(scores.reply_score, this.weights.REPLY_WEIGHT);
    combinedScore += this.applyWeight(scores.retweet_score, this.weights.RETWEET_WEIGHT);
    combinedScore += this.applyWeight(scores.photo_expand_score, this.weights.PHOTO_EXPAND_WEIGHT);
    combinedScore += this.applyWeight(scores.click_score, this.weights.CLICK_WEIGHT);
    combinedScore += this.applyWeight(
      scores.profile_click_score,
      this.weights.PROFILE_CLICK_WEIGHT,
    );
    combinedScore += this.applyWeight(scores.vqv_score, this.weights.VQV_WEIGHT);
    combinedScore += this.applyWeight(scores.share_score, this.weights.SHARE_WEIGHT);
    combinedScore += this.applyWeight(scores.share_via_dm_score, this.weights.SHARE_VIA_DM_WEIGHT);
    combinedScore += this.applyWeight(
      scores.share_via_copy_link_score,
      this.weights.SHARE_VIA_COPY_LINK_WEIGHT,
    );
    combinedScore += this.applyWeight(scores.dwell_score, this.weights.DWELL_WEIGHT);
    combinedScore += this.applyWeight(scores.quote_score, this.weights.QUOTE_WEIGHT);
    combinedScore += this.applyWeight(scores.quoted_click_score, this.weights.QUOTED_CLICK_WEIGHT);
    combinedScore += this.applyWeight(scores.dwell_time, this.weights.CONT_DWELL_TIME_WEIGHT);
    combinedScore += this.applyWeight(
      scores.follow_author_score,
      this.weights.FOLLOW_AUTHOR_WEIGHT,
    );
    combinedScore += this.applyWeight(
      scores.not_interested_score,
      this.weights.NOT_INTERESTED_WEIGHT,
    );
    combinedScore += this.applyWeight(scores.block_author_score, this.weights.BLOCK_AUTHOR_WEIGHT);
    combinedScore += this.applyWeight(scores.mute_author_score, this.weights.MUTE_AUTHOR_WEIGHT);
    combinedScore += this.applyWeight(scores.report_score, this.weights.REPORT_WEIGHT);

    return combinedScore;
  }

  /**
   * Computes synergy score between two agents based on their interests.
   * This is the core logic adapted for agent-to-agent synergy.
   */
  public computeSynergy(interestsA: Map<string, number>, interestsB: Map<string, number>): number {
    let synergy = 0;
    const allCategories = new Set([...interestsA.keys(), ...interestsB.keys()]);

    for (const category of allCategories) {
      const weightA = interestsA.get(category) ?? 0;
      const weightB = interestsB.get(category) ?? 0;
      // Simple dot product for synergy
      synergy += weightA * weightB;
    }

    return synergy;
  }
}
