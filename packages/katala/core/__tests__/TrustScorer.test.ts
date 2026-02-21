import { TrustScorer, Claim, TrustResult, DOMAIN_HALF_LIFE } from "../TrustScorer";

describe("TrustScorer", () => {
  const scorer = new TrustScorer();
  const now = new Date().toISOString();

  function makeClaim(overrides: Partial<Claim> = {}): Claim {
    return {
      id: "test-1",
      content: "テスト情報",
      source: {
        type: "primary",
        author: "Nicolas Ogoshi",
        url: "https://example.com/article",
        publishedAt: now,
        platform: "web",
      },
      domain: "tech",
      retrievedAt: now,
      language: "ja",
      ...overrides,
    };
  }

  describe("score()", () => {
    it("scores a fresh primary source highly", () => {
      const claim = makeClaim();
      const result = scorer.score(claim);

      expect(result.compositeScore).toBeGreaterThan(0.6);
      expect(result.grade).toMatch(/^[SAB]$/);
      expect(result.axes.freshness).toBeGreaterThan(0.9);
      expect(result.axes.provenance).toBeGreaterThan(0.8);
    });

    it("penalizes tertiary sources", () => {
      const claim = makeClaim({
        source: {
          type: "tertiary",
          retrievedAt: now,
        },
      });
      const result = scorer.score(claim);

      expect(result.axes.provenance).toBeLessThan(0.4);
      expect(result.compositeScore).toBeLessThan(0.6);
    });

    it("penalizes AI-generated content", () => {
      const claim = makeClaim({
        source: {
          type: "generated",
          author: "GPT-4",
          publishedAt: now,
        },
      });
      const result = scorer.score(claim);

      expect(result.axes.provenance).toBeLessThanOrEqual(0.3);
    });

    it("boosts score with corroborating claims", () => {
      const claim = makeClaim({ id: "main" });
      const corroborating = [
        makeClaim({
          id: "support-1",
          source: { type: "primary", author: "Source B", publishedAt: now },
        }),
        makeClaim({
          id: "support-2",
          source: { type: "secondary", author: "Source C", publishedAt: now },
        }),
      ];

      const withCorr = scorer.score(claim, corroborating);
      const without = scorer.score(claim);

      expect(withCorr.axes.verification).toBeGreaterThan(without.axes.verification);
      expect(withCorr.corroboratingClaims).toHaveLength(2);
    });

    it("reduces score with contradicting claims", () => {
      const claim = makeClaim({ id: "main" });
      const contradicting = [makeClaim({ id: "contra-1" })];

      const withContra = scorer.score(claim, [], contradicting);
      const without = scorer.score(claim);

      expect(withContra.axes.verification).toBeLessThan(without.axes.verification);
      expect(withContra.contradictingClaims).toHaveLength(1);
    });

    it("degrades freshness for old information", () => {
      const oldDate = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(); // 30 days
      const claim = makeClaim({
        source: {
          type: "primary",
          author: "Test",
          publishedAt: oldDate,
        },
        domain: "tech", // half-life 72h
      });
      const result = scorer.score(claim);

      expect(result.axes.freshness).toBeLessThan(0.01); // 30 days >> 72h half-life
    });

    it("crypto domain decays faster than science", () => {
      const sixHoursAgo = new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString();
      const crypto = makeClaim({
        source: { type: "primary", publishedAt: sixHoursAgo },
        domain: "crypto",
      });
      const science = makeClaim({
        source: { type: "primary", publishedAt: sixHoursAgo },
        domain: "science",
      });

      const cryptoResult = scorer.score(crypto);
      const scienceResult = scorer.score(science);

      expect(cryptoResult.axes.freshness).toBeLessThan(scienceResult.axes.freshness);
    });
  });

  describe("scoreBatch()", () => {
    it("cross-validates claims in the same domain", () => {
      const claims = [
        makeClaim({
          id: "a",
          content: "BTC上昇",
          domain: "crypto",
          source: { type: "primary", author: "Alice", publishedAt: now },
        }),
        makeClaim({
          id: "b",
          content: "BTC上昇傾向",
          domain: "crypto",
          source: { type: "secondary", author: "Bob", publishedAt: now },
        }),
        makeClaim({
          id: "c",
          content: "天気は晴れ",
          domain: "general",
          source: { type: "primary", author: "Carol", publishedAt: now },
        }),
      ];

      const results = scorer.scoreBatch(claims);

      expect(results).toHaveLength(3);
      // Crypto claims should have corroboration from each other
      const resultA = results.find((r) => r.claimId === "a")!;
      expect(resultA.corroboratingClaims).toContain("b");
      // General claim has no same-domain siblings
      const resultC = results.find((r) => r.claimId === "c")!;
      expect(resultC.corroboratingClaims).toHaveLength(0);
    });
  });

  describe("grading", () => {
    it("maps scores to correct grades", () => {
      // Test via claims with known characteristics
      const perfectClaim = makeClaim();
      const result = scorer.score(perfectClaim, [
        makeClaim({ id: "s1", source: { type: "primary", author: "Other", publishedAt: now } }),
        makeClaim({ id: "s2", source: { type: "primary", author: "Another", publishedAt: now } }),
      ]);
      expect(["S", "A"]).toContain(result.grade);
    });
  });

  describe("reasoning", () => {
    it("generates Japanese reasoning text", () => {
      const claim = makeClaim();
      const result = scorer.score(claim);

      expect(result.reasoning).toContain("一次情報");
      expect(result.reasoning).toContain("。");
    });
  });

  describe("custom weights", () => {
    it("accepts custom weights and normalizes them", () => {
      const customScorer = new TrustScorer({
        freshness: 0.5,
        provenance: 0.5,
        verification: 0,
        accessibility: 0,
      });
      const claim = makeClaim();
      const result = customScorer.score(claim);

      // Should still produce valid results
      expect(result.compositeScore).toBeGreaterThanOrEqual(0);
      expect(result.compositeScore).toBeLessThanOrEqual(1);
    });
  });
});
