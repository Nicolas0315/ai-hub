import { describe, expect, it } from "vitest";
import { EconomicTrustScorer } from "../EconomicTrustScorer";

describe("EconomicTrustScorer", () => {
  it("returns low risk for high quality / high efficiency / healthy balance", () => {
    const scorer = new EconomicTrustScorer();
    const r = scorer.score({
      qualityScore: 0.9,
      estimatedHours: 4,
      hourlyWageUsd: 120,
      tokenCostUsd: 6,
      balanceBeforeUsd: 100,
      balanceAfterUsd: 130,
    });

    expect(r.economicScore).toBeGreaterThan(0.7);
    expect(r.riskBand).toBe("low");
  });

  it("returns high risk when survival is poor", () => {
    const scorer = new EconomicTrustScorer();
    const r = scorer.score({
      qualityScore: 0.8,
      estimatedHours: 2,
      hourlyWageUsd: 80,
      tokenCostUsd: 20,
      balanceBeforeUsd: 40,
      balanceAfterUsd: 5,
    });

    expect(r.survivalRate).toBeLessThan(0.25);
    expect(r.riskBand).toBe("high");
  });
});
