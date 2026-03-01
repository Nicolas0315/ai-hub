import { describe, it, expect } from "vitest";
import { RemediationEngine } from "../RemediationEngine";
import type { VulnFinding } from "../types";

// ============================================================
// RemediationEngine — テスト
// Issue #44: BLUE Agent Patcher
// ============================================================

// --- テスト用フィクスチャ ---

const baseFinding: VulnFinding = {
  id: "finding-001",
  title: "SQL Injection vulnerability",
  description: "User input is directly concatenated into SQL query without parameterization",
  discoveredAt: new Date().toISOString(),
  reporterId: "red-agent-alpha",
  reporterType: "red-agent",
  cwe: "CWE-89",
  targetRepo: "https://github.com/Nicolas0315/Katala",
  confirmedBy: ["red-agent-beta"],
  reproducible: true,
};

const baseVerification = {
  severity: "High" as const,
  confidence: "High" as const,
  trustScore: 0.82,
};

describe("RemediationEngine", () => {
  describe("remediate() — SQL Injection", () => {
    it("should return a RemediationResult with a selected patch", async () => {
      const engine = new RemediationEngine();
      const result = await engine.remediate(baseFinding, baseVerification);

      expect(result.findingId).toBe("finding-001");
      expect(result.selectedPatch).toBeDefined();
      expect(result.selectedPatch.findingId).toBe("finding-001");
    });

    it("should select parameterization or input-validation strategy for SQL injection", async () => {
      const engine = new RemediationEngine();
      const result = await engine.remediate(baseFinding, baseVerification);

      const sqlStrategies = ["parameterization", "input-validation"];
      expect(sqlStrategies).toContain(result.selectedPatch.strategy);
    });

    it("should generate multiple candidates for SQL injection", async () => {
      const engine = new RemediationEngine();
      const result = await engine.remediate(baseFinding, baseVerification);

      expect(result.allCandidates.length).toBeGreaterThanOrEqual(2);
    });

    it("should select the highest quality candidate", async () => {
      const engine = new RemediationEngine();
      const result = await engine.remediate(baseFinding, baseVerification);

      const maxScore = Math.max(...result.allCandidates.map((c) => c.qualityScore));
      expect(result.selectedPatch.qualityScore).toBe(maxScore);
    });
  });

  describe("remediate() — XSS", () => {
    it("should select sanitization strategy for XSS", async () => {
      const engine = new RemediationEngine();
      const xssFinding: VulnFinding = {
        ...baseFinding,
        id: "finding-xss-001",
        title: "XSS via innerHTML",
        description: "User data is passed to innerHTML without sanitization",
        cwe: "CWE-79",
      };

      const result = await engine.remediate(xssFinding, { ...baseVerification, severity: "High" });
      const xssStrategies = ["sanitization", "input-validation"];
      expect(xssStrategies).toContain(result.selectedPatch.strategy);
    });
  });

  describe("remediate() — Weak Crypto", () => {
    it("should select crypto-upgrade strategy for MD5/Math.random", async () => {
      const engine = new RemediationEngine();
      const cryptoFinding: VulnFinding = {
        ...baseFinding,
        id: "finding-crypto-001",
        title: "Weak hash: MD5 used for password hashing",
        description: "MD5 is cryptographically broken and should not be used for password hashing",
        cwe: "CWE-327",
      };

      const result = await engine.remediate(cryptoFinding, baseVerification);
      expect(result.selectedPatch.strategy).toBe("crypto-upgrade");
    });
  });

  describe("remediate() — Hardcoded Secret", () => {
    it("should select config-hardening strategy for hardcoded secrets", async () => {
      const engine = new RemediationEngine();
      const secretFinding: VulnFinding = {
        ...baseFinding,
        id: "finding-secret-001",
        title: "Hardcoded API key",
        description: "API key is hardcoded directly in source code",
        cwe: "CWE-798",
      };

      const result = await engine.remediate(secretFinding, baseVerification);
      expect(result.selectedPatch.strategy).toBe("config-hardening");
    });
  });

  describe("remediate() — patch quality", () => {
    it("should set qualityScore between 0 and 1", async () => {
      const engine = new RemediationEngine();
      const result = await engine.remediate(baseFinding, baseVerification);

      expect(result.selectedPatch.qualityScore).toBeGreaterThan(0);
      expect(result.selectedPatch.qualityScore).toBeLessThanOrEqual(1);
    });

    it("should provide qualityAxes with all 4 dimensions", async () => {
      const engine = new RemediationEngine();
      const result = await engine.remediate(baseFinding, baseVerification);
      const axes = result.selectedPatch.qualityAxes;

      expect(axes.correctness).toBeGreaterThan(0);
      expect(axes.safety).toBeGreaterThan(0);
      expect(axes.testability).toBeGreaterThan(0);
      expect(axes.invasiveness).toBeGreaterThan(0);
    });

    it("should score lower safety for patches containing dangerous patterns in 'after' section", async () => {
      const engine = new RemediationEngine();
      // eval() finding — code-removal strategy should be generated
      const evalFinding: VulnFinding = {
        ...baseFinding,
        id: "finding-eval-001",
        title: "eval() usage",
        description: "eval() is used with user input enabling command injection",
        cwe: "CWE-95",
      };

      const result = await engine.remediate(evalFinding, baseVerification);
      // The selected patch should not have dangerous patterns in its code
      expect(result.selectedPatch.qualityAxes.safety).toBeGreaterThan(0.5);
    });
  });

  describe("remediate() — PR record", () => {
    it("should generate a PR record with correct fields", async () => {
      const engine = new RemediationEngine();
      const result = await engine.remediate(baseFinding, baseVerification);
      const pr = result.prRecord;

      expect(pr.patchId).toBe(result.selectedPatch.id);
      expect(pr.branchName).toMatch(/^blue\/remediate-/);
      expect(pr.prTitle).toContain("security");
      expect(pr.prBody).toContain("BLUE Agent");
      expect(pr.status).toBe("draft");
      expect(pr.submittedAt).toBeTruthy();
    });

    it("should use 'fix!' prefix for Critical severity", async () => {
      const engine = new RemediationEngine();
      const result = await engine.remediate(baseFinding, {
        ...baseVerification,
        severity: "Critical",
      });
      expect(result.prRecord.prTitle).toMatch(/^fix!/);
    });

    it("should use 'fix' prefix for High severity", async () => {
      const engine = new RemediationEngine();
      const result = await engine.remediate(baseFinding, baseVerification);
      expect(result.prRecord.prTitle).toMatch(/^fix\b/);
    });

    it("should use 'refactor' prefix for Low severity", async () => {
      const engine = new RemediationEngine();
      const result = await engine.remediate(baseFinding, {
        ...baseVerification,
        severity: "Low",
      });
      expect(result.prRecord.prTitle).toMatch(/^refactor/);
    });

    it("should include targetRepo in PR record when provided", async () => {
      const engine = new RemediationEngine();
      const result = await engine.remediate(baseFinding, baseVerification);
      expect(result.prRecord.targetRepo).toBe("https://github.com/Nicolas0315/Katala");
    });
  });

  describe("remediate() — metrics", () => {
    it("should record metrics including generationTimeMs", async () => {
      const engine = new RemediationEngine();
      const result = await engine.remediate(baseFinding, baseVerification);

      expect(result.metrics.candidatesGenerated).toBeGreaterThan(0);
      expect(result.metrics.avgQualityScore).toBeGreaterThan(0);
      expect(result.metrics.selectedQualityScore).toBeGreaterThan(0);
      expect(result.metrics.generationTimeMs).toBeGreaterThanOrEqual(0);
    });

    it("should record events in ImmutableLedger-compatible event log", async () => {
      const engine = new RemediationEngine();
      await engine.remediate(baseFinding, baseVerification);
      const events = engine.getEventLog();

      const types = events.map((e) => e.type);
      expect(types).toContain("FINDING_RECEIVED");
      expect(types).toContain("PATCH_GENERATED");
      expect(types).toContain("PATCH_SELECTED");
      expect(types).toContain("PR_SUBMITTED");
      expect(types).toContain("REMEDIATION_COMPLETE");
    });
  });

  describe("remediateAll() — batch processing", () => {
    it("should process multiple findings", async () => {
      const engine = new RemediationEngine();

      const findings: VulnFinding[] = [
        { ...baseFinding, id: "f-001" },
        {
          ...baseFinding,
          id: "f-002",
          title: "XSS",
          description: "innerHTML XSS",
          cwe: "CWE-79",
        },
      ];

      const verMap = new Map([
        ["f-001", { severity: "High" as const, confidence: "High" as const, trustScore: 0.8 }],
        ["f-002", { severity: "Medium" as const, confidence: "Medium" as const, trustScore: 0.6 }],
      ]);

      const results = await engine.remediateAll(findings, verMap);
      expect(results).toHaveLength(2);
      expect(results[0].findingId).toBe("f-001");
      expect(results[1].findingId).toBe("f-002");
    });

    it("should skip findings without a matching verification result", async () => {
      const engine = new RemediationEngine();
      const findings: VulnFinding[] = [
        { ...baseFinding, id: "f-001" },
        { ...baseFinding, id: "f-no-verification" },
      ];

      const verMap = new Map([
        ["f-001", { severity: "High" as const, confidence: "High" as const, trustScore: 0.8 }],
        // f-no-verification intentionally absent
      ]);

      const results = await engine.remediateAll(findings, verMap);
      expect(results).toHaveLength(1);
      expect(results[0].findingId).toBe("f-001");
    });
  });

  describe("getAggregateMetrics()", () => {
    it("should track success rate across multiple remediations", async () => {
      const engine = new RemediationEngine();

      await engine.remediate({ ...baseFinding, id: "f-1" }, baseVerification);
      await engine.remediate({ ...baseFinding, id: "f-2" }, baseVerification);
      await engine.remediate({ ...baseFinding, id: "f-3" }, baseVerification);

      const metrics = engine.getAggregateMetrics();
      expect(metrics.totalAttempts).toBe(3);
      expect(metrics.successCount).toBe(3);
      expect(metrics.successRate).toBe(1.0);
      expect(metrics.avgQualityScore).toBeGreaterThan(0);
    });
  });

  describe("generic strategy fallback", () => {
    it("should fall back to generic strategy for unknown vulnerability type", async () => {
      const engine = new RemediationEngine();
      const unknownFinding: VulnFinding = {
        ...baseFinding,
        id: "finding-unknown-001",
        title: "Unknown vulnerability type",
        description: "This is a very unusual vulnerability without standard CWE",
        cwe: undefined,
      };

      const result = await engine.remediate(unknownFinding, baseVerification);
      // At least one candidate should be generated (generic)
      expect(result.allCandidates.length).toBeGreaterThanOrEqual(1);
      expect(result.selectedPatch).toBeDefined();
    });
  });
});
