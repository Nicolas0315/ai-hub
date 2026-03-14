// ============================================================
// ZkLiteDisclosure — Unit Tests
// Issue #45: Vulnerability Mesh - ZK-lite Secure Disclosure
// ============================================================

import { describe, it, expect, beforeEach } from "vitest";
import { ImmutableLedger } from "../../../../packages/katala/core/ImmutableLedger";
import { SecureDisclosureManager, DisclosureInput } from "../ZkLiteDisclosure";

const sampleInput: DisclosureInput = {
  category: "injection",
  severity: "High",
  attackDetails:
    "SQL injection via unsanitized user input in /api/search endpoint. Payload: ' OR 1=1 --",
  affectedComponent: "api/search",
  cve: "CVE-2026-0001",
  disclosedBy: "red-agent-alpha",
};

describe("SecureDisclosureManager", () => {
  let ledger: ImmutableLedger;
  let manager: SecureDisclosureManager;

  beforeEach(() => {
    ledger = new ImmutableLedger();
    manager = new SecureDisclosureManager(ledger);
  });

  // ----------------------------------------------------------
  // createProof
  // ----------------------------------------------------------

  describe("createProof", () => {
    it("should return a proofId and secret", async () => {
      const { proofId, secret } = await manager.createProof(sampleInput);
      expect(proofId).toBeTruthy();
      expect(secret).toBeTruthy();
    });

    it("should store the proof as 'active' status", async () => {
      const { proofId } = await manager.createProof(sampleInput);
      const proof = manager.getProof(proofId);
      expect(proof?.status).toBe("active");
    });

    it("should set category and severity on the proof", async () => {
      const { proofId } = await manager.createProof(sampleInput);
      const proof = manager.getProof(proofId);
      expect(proof?.category).toBe("injection");
      expect(proof?.severity).toBe("High");
    });

    it("should NOT include attackDetails in the proof commitment (proof ≠ secret)", async () => {
      const { proofId, secret } = await manager.createProof(sampleInput);
      const proof = manager.getProof(proofId);
      // The proof itself should not contain the attack details
      expect(proof?.commitment).not.toBe(secret);
      expect(proof?.proof).not.toBe(secret);
    });

    it("should generate different proofs for the same input (due to nonce)", async () => {
      const { proofId: id1 } = await manager.createProof(sampleInput);
      const { proofId: id2 } = await manager.createProof(sampleInput);
      const p1 = manager.getProof(id1);
      const p2 = manager.getProof(id2);
      // Same category/severity, different commitments
      expect(p1?.commitment).not.toBe(p2?.commitment);
      expect(p1?.proof).not.toBe(p2?.proof);
    });

    it("should record a discovery event in ImmutableLedger", async () => {
      const { proofId } = await manager.createProof(sampleInput);
      const history = ledger.getHistory();
      const event = history.find(
        (e) =>
          e.eventType === "vuln:discovery:proof-created" &&
          (e.payload as Record<string, unknown>)["proofId"] === proofId
      );
      expect(event).toBeDefined();
    });

    it("should NOT record attackDetails in the ledger entry", async () => {
      const { proofId } = await manager.createProof(sampleInput);
      const history = ledger.getHistory();
      const event = history.find(
        (e) => (e.payload as Record<string, unknown>)["proofId"] === proofId
      );
      expect(event?.payload).not.toHaveProperty("attackDetails");
    });
  });

  // ----------------------------------------------------------
  // verifyProof
  // ----------------------------------------------------------

  describe("verifyProof", () => {
    it("should return true for a valid active proof", async () => {
      const { proofId } = await manager.createProof(sampleInput);
      expect(manager.verifyProof(proofId)).toBe(true);
    });

    it("should return false for an unknown proofId", () => {
      expect(manager.verifyProof("non-existent-id")).toBe(false);
    });

    it("should return false for a revoked proof", async () => {
      const { proofId } = await manager.createProof(sampleInput);
      await manager.revokeProof(proofId, {
        reason: "duplicate report",
        revokedBy: "admin",
      });
      expect(manager.verifyProof(proofId)).toBe(false);
    });
  });

  // ----------------------------------------------------------
  // markPatched
  // ----------------------------------------------------------

  describe("markPatched", () => {
    it("should transition proof to 'patched' state", async () => {
      const { proofId } = await manager.createProof(sampleInput);
      await manager.markPatched(proofId);
      expect(manager.getProof(proofId)?.status).toBe("patched");
    });

    it("should record a patched event in ImmutableLedger", async () => {
      const { proofId } = await manager.createProof(sampleInput);
      await manager.markPatched(proofId);
      const history = ledger.getHistory();
      const event = history.find(
        (e) =>
          e.eventType === "vuln:lifecycle:patched" &&
          (e.payload as Record<string, unknown>)["proofId"] === proofId
      );
      expect(event).toBeDefined();
    });

    it("should throw if proof is not in 'active' state", async () => {
      const { proofId } = await manager.createProof(sampleInput);
      await manager.markPatched(proofId); // → patched
      await expect(manager.markPatched(proofId)).rejects.toThrow("patched");
    });

    it("should throw for unknown proofId", async () => {
      await expect(manager.markPatched("no-such-id")).rejects.toThrow("not found");
    });
  });

  // ----------------------------------------------------------
  // revealFullReport
  // ----------------------------------------------------------

  describe("revealFullReport", () => {
    const revealDetails = {
      attackDetails: sampleInput.attackDetails,
      affectedComponent: sampleInput.affectedComponent,
      cve: sampleInput.cve,
      remediation: "Parameterize all SQL queries via ORM.",
      discoveredAt: "2026-01-15T10:00:00.000Z",
    };

    it("should publish a full report after patching", async () => {
      const { proofId, secret } = await manager.createProof(sampleInput);
      await manager.markPatched(proofId);
      const report = await manager.revealFullReport(proofId, secret, revealDetails);
      expect(report.proofId).toBe(proofId);
      expect(report.attackDetails).toBe(sampleInput.attackDetails);
      expect(report.category).toBe("injection");
      expect(report.severity).toBe("High");
    });

    it("should set proof status to 'revealed'", async () => {
      const { proofId, secret } = await manager.createProof(sampleInput);
      await manager.markPatched(proofId);
      await manager.revealFullReport(proofId, secret, revealDetails);
      expect(manager.getProof(proofId)?.status).toBe("revealed");
    });

    it("should record a full-report-revealed event in ImmutableLedger", async () => {
      const { proofId, secret } = await manager.createProof(sampleInput);
      await manager.markPatched(proofId);
      await manager.revealFullReport(proofId, secret, revealDetails);
      const history = ledger.getHistory();
      const event = history.find(
        (e) =>
          e.eventType === "vuln:disclosure:full-report-revealed" &&
          (e.payload as Record<string, unknown>)["proofId"] === proofId
      );
      expect(event).toBeDefined();
      expect((event?.payload as Record<string, unknown>)["attackDetails"]).toBe(
        sampleInput.attackDetails
      );
    });

    it("should throw if proof is not in 'patched' state", async () => {
      const { proofId, secret } = await manager.createProof(sampleInput);
      // Not yet patched — should throw
      await expect(manager.revealFullReport(proofId, secret, revealDetails)).rejects.toThrow(
        "patched"
      );
    });

    it("should throw for secret mismatch", async () => {
      const { proofId } = await manager.createProof(sampleInput);
      await manager.markPatched(proofId);
      await expect(
        manager.revealFullReport(proofId, "wrong-secret", revealDetails)
      ).rejects.toThrow("Secret mismatch");
    });

    it("should set patchedAt to the time markPatched was called, not revealFullReport", async () => {
      const { proofId, secret } = await manager.createProof(sampleInput);
      const beforePatch = new Date().toISOString();
      await manager.markPatched(proofId);
      const afterPatch = new Date().toISOString();

      // Small delay to ensure revealFullReport has a different timestamp
      await new Promise((resolve) => setTimeout(resolve, 5));

      const report = await manager.revealFullReport(proofId, secret, revealDetails);

      // patchedAt must fall within the markPatched window
      expect(report.patchedAt >= beforePatch).toBe(true);
      expect(report.patchedAt <= afterPatch).toBe(true);

      // patchedAt must be strictly before or equal to revealedAt (never after)
      expect(report.patchedAt <= report.revealedAt).toBe(true);
    });
  });

  // ----------------------------------------------------------
  // revokeProof
  // ----------------------------------------------------------

  describe("revokeProof", () => {
    it("should set proof status to 'revoked'", async () => {
      const { proofId } = await manager.createProof(sampleInput);
      await manager.revokeProof(proofId, { reason: "false positive", revokedBy: "admin" });
      expect(manager.getProof(proofId)?.status).toBe("revoked");
    });

    it("should attach revocation metadata to the proof", async () => {
      const { proofId } = await manager.createProof(sampleInput);
      await manager.revokeProof(proofId, { reason: "false positive", revokedBy: "admin" });
      const proof = manager.getProof(proofId);
      expect(proof?.revocation?.reason).toBe("false positive");
      expect(proof?.revocation?.revokedBy).toBe("admin");
      expect(proof?.revocation?.revokedAt).toBeTruthy();
    });

    it("should record a revocation event in ImmutableLedger", async () => {
      const { proofId } = await manager.createProof(sampleInput);
      await manager.revokeProof(proofId, { reason: "false positive", revokedBy: "admin" });
      const history = ledger.getHistory();
      const event = history.find(
        (e) =>
          e.eventType === "vuln:lifecycle:proof-revoked" &&
          (e.payload as Record<string, unknown>)["proofId"] === proofId
      );
      expect(event).toBeDefined();
    });

    it("should throw when trying to revoke an already-revoked proof", async () => {
      const { proofId } = await manager.createProof(sampleInput);
      await manager.revokeProof(proofId, { reason: "r1", revokedBy: "admin" });
      await expect(
        manager.revokeProof(proofId, { reason: "r2", revokedBy: "admin" })
      ).rejects.toThrow("already revoked");
    });

    it("should throw for unknown proofId", async () => {
      await expect(
        manager.revokeProof("no-such-id", { reason: "x", revokedBy: "admin" })
      ).rejects.toThrow("not found");
    });
  });

  // ----------------------------------------------------------
  // getTimeline — ImmutableLedger 全ライフサイクル記録
  // ----------------------------------------------------------

  describe("getTimeline", () => {
    it("should record the full lifecycle: discovery → patched → revealed", async () => {
      const { proofId, secret } = await manager.createProof(sampleInput);
      await manager.markPatched(proofId);
      await manager.revealFullReport(proofId, secret, {
        attackDetails: sampleInput.attackDetails,
        discoveredAt: "2026-01-15T10:00:00.000Z",
      });

      const timeline = manager.getTimeline(proofId);
      const eventTypes = timeline.map((e) => e.eventType);

      expect(eventTypes).toContain("vuln:discovery:proof-created");
      expect(eventTypes).toContain("vuln:lifecycle:patched");
      expect(eventTypes).toContain("vuln:disclosure:full-report-revealed");
    });

    it("should record discovery → revoked for revocation path", async () => {
      const { proofId } = await manager.createProof(sampleInput);
      await manager.revokeProof(proofId, { reason: "dup", revokedBy: "admin" });

      const timeline = manager.getTimeline(proofId);
      const eventTypes = timeline.map((e) => e.eventType);

      expect(eventTypes).toContain("vuln:discovery:proof-created");
      expect(eventTypes).toContain("vuln:lifecycle:proof-revoked");
    });

    it("should return empty array for unknown proofId", () => {
      const timeline = manager.getTimeline("non-existent");
      expect(timeline).toHaveLength(0);
    });
  });

  // ----------------------------------------------------------
  // listProofs
  // ----------------------------------------------------------

  describe("listProofs", () => {
    it("should list all created proofs", async () => {
      await manager.createProof(sampleInput);
      await manager.createProof({ ...sampleInput, category: "xss" });
      const list = manager.listProofs();
      expect(list).toHaveLength(2);
    });

    it("should return empty array when no proofs exist", () => {
      expect(manager.listProofs()).toHaveLength(0);
    });
  });
});
