import { z } from "zod";

/**
 * ClawWork系の「品質×コスト×生存性」評価をKatalaへ移植する最小実装
 */
export const EconomicMetricsSchema = z.object({
  qualityScore: z.number().min(0).max(1),
  estimatedHours: z.number().positive(),
  hourlyWageUsd: z.number().positive(),
  tokenCostUsd: z.number().min(0),
  balanceBeforeUsd: z.number().min(0),
  balanceAfterUsd: z.number().min(0),
});

export type EconomicMetrics = z.infer<typeof EconomicMetricsSchema>;

export const EconomicTrustResultSchema = z.object({
  valueUsd: z.number().min(0),
  costToValue: z.number().min(0),
  survivalRate: z.number().min(0).max(1),
  economicScore: z.number().min(0).max(1),
  riskBand: z.enum(["low", "medium", "high"]),
});

export type EconomicTrustResult = z.infer<typeof EconomicTrustResultSchema>;

export interface EconomicScoreWeights {
  quality: number;
  efficiency: number;
  survival: number;
}

const DEFAULT_WEIGHTS: EconomicScoreWeights = {
  quality: 0.4,
  efficiency: 0.35,
  survival: 0.25,
};

export class EconomicTrustScorer {
  private weights: EconomicScoreWeights;

  constructor(weights?: Partial<EconomicScoreWeights>) {
    this.weights = { ...DEFAULT_WEIGHTS, ...weights };
    const sum = this.weights.quality + this.weights.efficiency + this.weights.survival;
    if (Math.abs(sum - 1) > 0.001) {
      this.weights.quality /= sum;
      this.weights.efficiency /= sum;
      this.weights.survival /= sum;
    }
  }

  score(input: EconomicMetrics): EconomicTrustResult {
    const m = EconomicMetricsSchema.parse(input);

    // ClawWork近似: 支払価値 = 品質 × 推定工数 × 市場時給
    const valueUsd = m.qualityScore * m.estimatedHours * m.hourlyWageUsd;

    // 0に近いコストは∞になるためεを加える
    const eps = 1e-6;
    const costToValue = valueUsd / (m.tokenCostUsd + eps);

    // 生存性: 残高維持率（0〜1）
    const survivalRate =
      m.balanceBeforeUsd === 0 ? 0 : Math.min(1, m.balanceAfterUsd / m.balanceBeforeUsd);

    // 効率スコア（対数圧縮）
    const efficiencyScore = this.logNormalize(costToValue);

    const economicScore = this.clamp01(
      m.qualityScore * this.weights.quality +
        efficiencyScore * this.weights.efficiency +
        survivalRate * this.weights.survival,
    );

    return {
      valueUsd,
      costToValue,
      survivalRate,
      economicScore,
      riskBand: this.toRiskBand(economicScore, survivalRate),
    };
  }

  private logNormalize(v: number): number {
    // v=1 → ~0.3, v=10 → ~0.7, v>=100 → ~1
    return this.clamp01(Math.log10(v + 1) / 2);
  }

  private toRiskBand(score: number, survivalRate: number): "low" | "medium" | "high" {
    if (survivalRate < 0.25 || score < 0.35) return "high";
    if (survivalRate < 0.5 || score < 0.6) return "medium";
    return "low";
  }

  private clamp01(v: number): number {
    if (v < 0) return 0;
    if (v > 1) return 1;
    return v;
  }
}
