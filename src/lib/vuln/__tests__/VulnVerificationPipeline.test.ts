import { describe, it, expect } from "vitest";
import {
  VulnVerificationPipeline,
  calcAttackEase,
  classifySeverity,
  classifyConfidence,
} from "../VulnVerificationPipeline";
import type { VulnFinding } from "../types";

// ============================================================
// VulnVerificationPipeline — Tests
// Issue #43: TrustScorer + ConsensusEngine による脆弱性検証
// ============================================================

const now = new Date().toISOString();

/** テスト用VulnFindingを生成するファクトリ */
function makeFinding(overrides: Partial<VulnFinding> = {}): VulnFinding {
  return {
    id: "test-finding-1",
    title: "SQL Injection in /api/users endpoint",
    description: "Unsanitized user input in id parameter allows SQL injection.",
    cve: "CVE-2026-0001",
    discoveredAt: now,
    reporterId: "red-agent-alpha",
    reporterType: "red-agent",
    targetRepo: "https://github.com/Nicolas0315/Katala",
    affectedComponent: "src/app/api/users/route.ts",
    attackVector: "network",
    attackComplexity: "low",
    privilegesRequired: "none",
    userInteraction: "none",
    pocAvailable: true,
    reproducible: true,
    confirmedBy: ["red-agent-beta", "researcher-1"],
    retrievedAt: now,
    ...overrides,
  };
}

// ============================================================
// calcAttackEase
// ============================================================
describe("calcAttackEase()", () => {
  it("returns high score for critical attack profile", () => {
    const finding = makeFinding({
      attackVector: "network",
      attackComplexity: "low",
      privilegesRequired: "none",
      userInteraction: "none",
      pocAvailable: true,
    });
    const score = calcAttackEase(finding);
    expect(score).toBeGreaterThanOrEqual(0.8);
    expect(score).toBeLessThanOrEqual(1.0);
  });

  it("returns low score for hard-to-attack profile", () => {
    const finding = makeFinding({
      attackVector: "physical",
      attackComplexity: "high",
      privilegesRequired: "high",
      userInteraction: "required",
      pocAvailable: false,
    });
    const score = calcAttackEase(finding);
    expect(score).toBeLessThan(0.3);
  });

  it("returns moderate score when pocAvailable is false and network vector", () => {
    const finding = makeFinding({
      attackVector: "network",
      attackComplexity: "low",
      privilegesRequired: "low",
      userInteraction: "required",
      pocAvailable: false,
    });
    const score = calcAttackEase(finding);
    expect(score).toBeGreaterThan(0.3);
    expect(score).toBeLessThan(0.8);
  });

  it("returns baseline score when no attack characteristics given", () => {
    const finding = makeFinding({
      attackVector: undefined,
      attackComplexity: undefined,
      privilegesRequired: undefined,
      userInteraction: undefined,
      pocAvailable: undefined,
    });
    const score = calcAttackEase(finding);
    // ベースライン = 0.3
    expect(score).toBeCloseTo(0.3, 1);
  });
});

// ============================================================
// classifySeverity
// ============================================================
describe("classifySeverity()", () => {
  it("classifies Critical when high trust and high attack ease", () => {
    expect(classifySeverity(0.8, 0.9)).toBe("Critical");
    expect(classifySeverity(0.7, 0.7)).toBe("Critical");
  });

  it("classifies High for high trust + medium ease", () => {
    expect(classifySeverity(0.75, 0.5)).toBe("High");
  });

  it("classifies High for medium trust + high ease", () => {
    expect(classifySeverity(0.55, 0.8)).toBe("High");
  });

  it("classifies Medium for moderate trust and ease", () => {
    expect(classifySeverity(0.5, 0.4)).toBe("Medium");
    expect(classifySeverity(0.4, 0.3)).toBe("Medium");
  });

  it("classifies Low for weak findings", () => {
    expect(classifySeverity(0.3, 0.2)).toBe("Low");
    expect(classifySeverity(0.2, 0.8)).toBe("Low"); // 信頼性が低ければLow
  });

  it("boundary: trustScore = 0.7, attackEase = 0.69 => High not Critical", () => {
    expect(classifySeverity(0.7, 0.69)).toBe("High");
  });
});

// ============================================================
// classifyConfidence
// ============================================================
describe("classifyConfidence()", () => {
  it("returns High for unanimous consensus", () => {
    expect(classifyConfidence("unanimous", 0.03)).toBe("High");
  });

  it("returns High when divergence is very small", () => {
    expect(classifyConfidence("majority", 0.04)).toBe("High");
  });

  it("returns Medium for majority consensus", () => {
    expect(classifyConfidence("majority", 0.10)).toBe("Medium");
  });

  it("returns Low for tiebreaker", () => {
    expect(classifyConfidence("tiebreaker", 0.20)).toBe("Low");
  });

  it("returns Low for deadlock", () => {
    expect(classifyConfidence("deadlock", 0.40)).toBe("Low");
  });
});

// ============================================================
// VulnVerificationPipeline.verify()
// ============================================================
describe("VulnVerificationPipeline", () => {
  const pipeline = new VulnVerificationPipeline();

  it("classifies a well-confirmed Critical finding correctly", async () => {
    const finding = makeFinding(); // CriticalなSQL Injection
    const result = await pipeline.verify(finding);

    // 受入条件 1: TrustScorerの4軸でスコアリング
    expect(result.axes.freshness).toBeGreaterThan(0);
    expect(result.axes.provenance).toBeGreaterThan(0);
    expect(result.axes.verification).toBeGreaterThan(0);
    expect(result.axes.attackEase).toBeGreaterThan(0);

    // 受入条件 4: Critical/High/Medium/Lowの重大度をconfidence付きで出力
    expect(["Critical", "High", "Medium", "Low"]).toContain(result.severity);
    expect(["High", "Medium", "Low"]).toContain(result.confidence);

    // 高信頼性findingはCriticalまたはHighに分類されるべき
    expect(["Critical", "High"]).toContain(result.severity);

    // trustScoreとattackEaseScoreが存在する
    expect(result.trustScore).toBeGreaterThan(0);
    expect(result.attackEaseScore).toBeGreaterThan(0.5); // network+low+none+PoC
  });

  it("classifies an unconfirmed Low-ease finding as Medium or Low", async () => {
    const finding = makeFinding({
      id: "low-severity-finding",
      reporterType: "community",
      attackVector: "local",
      attackComplexity: "high",
      privilegesRequired: "high",
      userInteraction: "required",
      pocAvailable: false,
      reproducible: false,
      confirmedBy: [],
    });
    const result = await pipeline.verify(finding);

    // 低信頼性・低攻撃容易度は Low または Medium
    expect(["Low", "Medium"]).toContain(result.severity);
    expect(result.attackEaseScore).toBeLessThan(0.4);
  });

  it("includes dissent field in result (may be empty for unanimous)", async () => {
    // 受入条件 3: dissent（少数意見）を保存
    const finding = makeFinding({ id: "dissent-test" });
    const result = await pipeline.verify(finding);

    // dissentはarrayであること（内容はゼロでも可）
    expect(Array.isArray(result.dissent)).toBe(true);
  });

  it("adds PoC caveat when pocAvailable is true", async () => {
    const finding = makeFinding({ pocAvailable: true });
    const result = await pipeline.verify(finding);

    const hasPocCaveat = result.caveats.some((c) => c.includes("PoC"));
    expect(hasPocCaveat).toBe(true);
  });

  it("adds caveat when no confirmedBy agents", async () => {
    const finding = makeFinding({ confirmedBy: [] });
    const result = await pipeline.verify(finding);

    const hasConfirmCaveat = result.caveats.some((c) => c.includes("確認なし") || c.includes("誤検出"));
    expect(hasConfirmCaveat).toBe(true);
  });

  it("verifyBatch processes multiple findings", async () => {
    const findings = [
      makeFinding({ id: "batch-1" }),
      makeFinding({
        id: "batch-2",
        reporterType: "researcher",
        attackVector: "local",
        pocAvailable: false,
        confirmedBy: ["researcher-1"],
      }),
    ];
    const results = await pipeline.verifyBatch(findings);

    expect(results).toHaveLength(2);
    expect(results[0].findingId).toBe("batch-1");
    expect(results[1].findingId).toBe("batch-2");

    // 各結果が必須フィールドを持つ
    for (const r of results) {
      expect(r.severity).toBeDefined();
      expect(r.confidence).toBeDefined();
      expect(r.trustScore).toBeGreaterThanOrEqual(0);
      expect(r.trustScore).toBeLessThanOrEqual(1);
    }
  });

  it("result has verifiedAt timestamp", async () => {
    const finding = makeFinding({ id: "timestamp-test" });
    const result = await pipeline.verify(finding);

    expect(result.verifiedAt).toBeDefined();
    expect(() => new Date(result.verifiedAt)).not.toThrow();
  });
});
