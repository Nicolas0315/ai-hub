import {
  ConsensusEngine,
  MockTrustAgent,
  RuleBasedTrustAgent,
} from "../ConsensusEngine";
import { Claim } from "../TrustScorer";

describe("ConsensusEngine", () => {
  const now = new Date().toISOString();

  function makeClaim(overrides: Partial<Claim> = {}): Claim {
    return {
      id: "claim-1",
      content: "BTC will reach $100k",
      source: {
        type: "primary",
        author: "Analyst A",
        url: "https://example.com/btc",
        publishedAt: now,
        platform: "web",
      },
      domain: "crypto",
      retrievedAt: now,
      language: "en",
      ...overrides,
    };
  }

  describe("basic consensus", () => {
    it("returns unanimous when agents agree", async () => {
      const agents = [
        new MockTrustAgent("agent-a", 0.8, 0.9),
        new MockTrustAgent("agent-b", 0.82, 0.85),
      ];
      const engine = new ConsensusEngine(agents);
      const result = await engine.evaluate(makeClaim());

      expect(result.consensus).toBe("unanimous");
      expect(result.divergence).toBeLessThanOrEqual(0.05);
      expect(result.finalScore).toBeCloseTo(0.81, 1);
      expect(result.verdicts).toHaveLength(2);
    });

    it("returns majority when moderate divergence", async () => {
      const agents = [
        new MockTrustAgent("agent-a", 0.8, 0.9),
        new MockTrustAgent("agent-b", 0.7, 0.85),
      ];
      const engine = new ConsensusEngine(agents);
      const result = await engine.evaluate(makeClaim());

      expect(result.consensus).toBe("majority");
      expect(result.divergence).toBeGreaterThan(0.05);
      expect(result.divergence).toBeLessThanOrEqual(0.15);
    });

    it("invokes tiebreaker when divergence exceeds threshold", async () => {
      const agents = [
        new MockTrustAgent("agent-a", 0.9, 0.9),
        new MockTrustAgent("agent-b", 0.4, 0.8),
      ];
      const tiebreaker = new MockTrustAgent("tiebreaker", 0.7, 0.95);
      const engine = new ConsensusEngine(agents, tiebreaker);
      const result = await engine.evaluate(makeClaim());

      expect(result.consensus).toBe("tiebreaker");
      expect(result.verdicts).toHaveLength(3);
      expect(tiebreaker.callCount).toBe(1);
    });

    it("returns deadlock when divergent and no tiebreaker", async () => {
      const agents = [
        new MockTrustAgent("agent-a", 0.9, 0.9),
        new MockTrustAgent("agent-b", 0.3, 0.8),
      ];
      const engine = new ConsensusEngine(agents);
      const result = await engine.evaluate(makeClaim());

      expect(result.consensus).toBe("deadlock");
      expect(result.divergence).toBeGreaterThan(0.15);
    });
  });

  describe("confidence weighting", () => {
    it("weighs high-confidence agent more", async () => {
      const agents = [
        new MockTrustAgent("high-conf", 0.9, 0.95),
        new MockTrustAgent("low-conf", 0.5, 0.3),
      ];
      const engine = new ConsensusEngine(agents);
      const result = await engine.evaluate(makeClaim());

      // Final score should be closer to 0.9 than 0.5
      expect(result.finalScore).toBeGreaterThan(0.7);
    });

    it("uses simple average when confidence weighting disabled", async () => {
      const agents = [
        new MockTrustAgent("high-conf", 0.9, 0.95),
        new MockTrustAgent("low-conf", 0.5, 0.3),
      ];
      const engine = new ConsensusEngine(agents, undefined, {
        useConfidenceWeighting: false,
      });
      const result = await engine.evaluate(makeClaim());

      expect(result.finalScore).toBeCloseTo(0.7, 1);
    });
  });

  describe("RuleBasedTrustAgent", () => {
    it("wraps TrustScorer and returns valid verdict", async () => {
      const agent = new RuleBasedTrustAgent();
      const claim = makeClaim();
      const verdict = await agent.evaluate(claim);

      expect(verdict.agentId).toBe("rule-based");
      expect(verdict.model).toBe("rule-based-v1");
      expect(verdict.confidence).toBe(0.7);
      expect(verdict.result.claimId).toBe("claim-1");
      expect(verdict.result.compositeScore).toBeGreaterThan(0);
    });

    it("works as part of consensus", async () => {
      const agents = [
        new RuleBasedTrustAgent("rule-1"),
        new RuleBasedTrustAgent("rule-2"),
      ];
      const engine = new ConsensusEngine(agents);
      const result = await engine.evaluate(makeClaim());

      // Two identical rule-based agents → unanimous
      expect(result.consensus).toBe("unanimous");
      expect(result.divergence).toBeLessThan(0.0001);
    });
  });

  describe("batch evaluation", () => {
    it("evaluates multiple claims", async () => {
      const agents = [
        new MockTrustAgent("agent-a", 0.8, 0.9),
        new MockTrustAgent("agent-b", 0.75, 0.85),
      ];
      const engine = new ConsensusEngine(agents);
      const claims = [
        makeClaim({ id: "c1", content: "Claim 1" }),
        makeClaim({ id: "c2", content: "Claim 2" }),
        makeClaim({ id: "c3", content: "Claim 3" }),
      ];
      const results = await engine.evaluateBatch(claims);

      expect(results).toHaveLength(3);
      expect(results[0].claimId).toBe("c1");
      expect(results[2].claimId).toBe("c3");
    });
  });

  describe("dissent (minority opinion preservation)", () => {
    it("captures minority opinion when agent diverges from consensus", async () => {
      const agents = [
        new MockTrustAgent("majority-1", 0.85, 0.9),
        new MockTrustAgent("majority-2", 0.82, 0.85),
        new MockTrustAgent("minority", 0.3, 0.8),
      ];
      const engine = new ConsensusEngine(agents, undefined, { minAgents: 3 });
      const result = await engine.evaluate(makeClaim());

      expect(result.dissent.length).toBeGreaterThanOrEqual(1);
      const minorityDissent = result.dissent.find((d) => d.agentId === "minority");
      expect(minorityDissent).toBeDefined();
      expect(minorityDissent!.score).toBe(0.3);
    });

    it("has no dissent when all agents agree", async () => {
      const agents = [
        new MockTrustAgent("a", 0.8, 0.9),
        new MockTrustAgent("b", 0.82, 0.85),
      ];
      const engine = new ConsensusEngine(agents);
      const result = await engine.evaluate(makeClaim());

      expect(result.dissent).toHaveLength(0);
    });
  });

  describe("caveats (score limitations)", () => {
    it("always includes base caveat about scores not being truth", async () => {
      const agents = [
        new MockTrustAgent("a", 0.8, 0.9),
        new MockTrustAgent("b", 0.82, 0.85),
      ];
      const engine = new ConsensusEngine(agents);
      const result = await engine.evaluate(makeClaim());

      expect(result.caveats.some((c) => c.includes("真実の保証ではない"))).toBe(true);
    });

    it("flags financial domain incentive risk", async () => {
      const agents = [
        new MockTrustAgent("a", 0.8, 0.9),
        new MockTrustAgent("b", 0.82, 0.85),
      ];
      const engine = new ConsensusEngine(agents);
      const claim = makeClaim({ domain: "finance" });
      const result = await engine.evaluate(claim);

      expect(result.caveats.some((c) => c.includes("経済的インセンティブ"))).toBe(true);
    });

    it("flags political domain bias risk", async () => {
      const agents = [
        new MockTrustAgent("a", 0.8, 0.9),
        new MockTrustAgent("b", 0.82, 0.85),
      ];
      const engine = new ConsensusEngine(agents);
      const claim = makeClaim({ domain: "politics" });
      const result = await engine.evaluate(claim);

      expect(result.caveats.some((c) => c.includes("政治的立場"))).toBe(true);
    });

    it("warns about AI-generated content", async () => {
      const agents = [
        new MockTrustAgent("a", 0.8, 0.9),
        new MockTrustAgent("b", 0.82, 0.85),
      ];
      const engine = new ConsensusEngine(agents);
      const claim = makeClaim({
        source: { type: "generated", author: "GPT-4", publishedAt: now },
      });
      const result = await engine.evaluate(claim);

      expect(result.caveats.some((c) => c.includes("ハルシネーション"))).toBe(true);
    });
  });

  describe("error handling", () => {
    it("throws if fewer agents than minimum", () => {
      expect(
        () => new ConsensusEngine([new MockTrustAgent("solo", 0.8)])
      ).toThrow("at least 2 agents");
    });
  });

  describe("reasoning output", () => {
    it("includes agent details in reasoning", async () => {
      const agents = [
        new MockTrustAgent("claude", 0.85, 0.9),
        new MockTrustAgent("gemini", 0.82, 0.88),
      ];
      const engine = new ConsensusEngine(agents);
      const result = await engine.evaluate(makeClaim());

      expect(result.reasoning).toContain("claude");
      expect(result.reasoning).toContain("gemini");
      expect(result.reasoning).toContain("エージェント");
    });
  });
});
