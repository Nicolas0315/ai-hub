import { describe, it, expect } from "vitest";
import {
  buildCommitments,
  createEnvelope,
  verifyEnvelope,
  extractRevealedAttributes,
  CommittedField,
  RevealedField,
  IdentityVectorKey,
} from "../SelectiveDisclosure";
import { createDefaultVector, IdentityVector } from "../IdentityVector";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeVector(): IdentityVector {
  return {
    personality: { extraversion: 0.8, intuition: 0.6, thinking: 0.4, judging: 0.7 },
    values: ["honesty", "growth"],
    professionalFocus: ["engineering", "AI"],
    socialEnergy: { battery: 75, preferredTone: "professional" },
    meta: { confidenceScore: 0.9, lastUpdated: "2026-03-01T00:00:00.000Z" },
  };
}

// ---------------------------------------------------------------------------
// buildCommitments
// ---------------------------------------------------------------------------

describe("buildCommitments", () => {
  it("produces a secret for every IdentityVector key", () => {
    const v = makeVector();
    const secrets = buildCommitments(v);
    const keys = Object.keys(v) as IdentityVectorKey[];
    for (const k of keys) {
      expect(secrets[k]).toBeDefined();
      expect(secrets[k].commitment).toMatch(/^[0-9a-f]{64}$/);
      expect(secrets[k].salt).toMatch(/^[0-9a-f]{32}$/);
    }
  });

  it("generates different salts on each call (randomness)", () => {
    const v = makeVector();
    const s1 = buildCommitments(v);
    const s2 = buildCommitments(v);
    // Probability of collision: 2^-128 — effectively impossible
    expect(s1.personality.salt).not.toBe(s2.personality.salt);
    expect(s1.personality.commitment).not.toBe(s2.personality.commitment);
  });

  it("preserves the original values in secrets", () => {
    const v = makeVector();
    const secrets = buildCommitments(v);
    expect(secrets.values.value).toEqual(["honesty", "growth"]);
    expect(secrets.personality.value).toEqual(v.personality);
  });
});

// ---------------------------------------------------------------------------
// createEnvelope
// ---------------------------------------------------------------------------

describe("createEnvelope", () => {
  it("marks requested keys as revealed", () => {
    const v = makeVector();
    const secrets = buildCommitments(v);
    const env = createEnvelope(secrets, ["values", "professionalFocus"]);

    expect(env.values.revealed).toBe(true);
    expect(env.professionalFocus.revealed).toBe(true);
  });

  it("marks non-requested keys as committed (blinded)", () => {
    const v = makeVector();
    const secrets = buildCommitments(v);
    const env = createEnvelope(secrets, ["values"]);

    expect(env.personality.revealed).toBe(false);
    expect(env.socialEnergy.revealed).toBe(false);
    expect(env.meta.revealed).toBe(false);
  });

  it("blinded fields expose commitment hash but NOT salt or value", () => {
    const v = makeVector();
    const secrets = buildCommitments(v);
    const env = createEnvelope(secrets, []);

    const field = env.personality as CommittedField;
    expect(field.commitment).toMatch(/^[0-9a-f]{64}$/);
    expect((field as any).salt).toBeUndefined();
    expect((field as any).value).toBeUndefined();
  });

  it("revealed fields include salt, value, and commitment", () => {
    const v = makeVector();
    const secrets = buildCommitments(v);
    const env = createEnvelope(secrets, ["meta"]);

    const field = env.meta as RevealedField<IdentityVector["meta"]>;
    expect(field.revealed).toBe(true);
    expect(field.salt).toMatch(/^[0-9a-f]{32}$/);
    expect(field.commitment).toMatch(/^[0-9a-f]{64}$/);
    expect(field.value).toEqual(v.meta);
  });

  it("empty revealKeys → all fields blinded", () => {
    const v = makeVector();
    const secrets = buildCommitments(v);
    const env = createEnvelope(secrets, []);
    const keys = Object.keys(env) as IdentityVectorKey[];
    for (const k of keys) {
      expect(env[k].revealed).toBe(false);
    }
  });

  it("all keys revealed → full disclosure", () => {
    const v = makeVector();
    const secrets = buildCommitments(v);
    const allKeys = Object.keys(v) as IdentityVectorKey[];
    const env = createEnvelope(secrets, allKeys);
    for (const k of allKeys) {
      expect(env[k].revealed).toBe(true);
    }
  });
});

// ---------------------------------------------------------------------------
// verifyEnvelope
// ---------------------------------------------------------------------------

describe("verifyEnvelope", () => {
  it("verifies a valid envelope with some revealed fields", () => {
    const v = makeVector();
    const secrets = buildCommitments(v);
    const env = createEnvelope(secrets, ["personality", "values"]);
    const result = verifyEnvelope(env);

    expect(result.valid).toBe(true);
    expect(result.verified).toContain("personality");
    expect(result.verified).toContain("values");
    expect(result.failed).toHaveLength(0);
  });

  it("records blinded fields without failing", () => {
    const v = makeVector();
    const secrets = buildCommitments(v);
    const env = createEnvelope(secrets, ["values"]);
    const result = verifyEnvelope(env);

    expect(result.valid).toBe(true);
    expect(result.blinded).toContain("personality");
    expect(result.blinded).toContain("socialEnergy");
  });

  it("detects a tampered value (commitment mismatch)", () => {
    const v = makeVector();
    const secrets = buildCommitments(v);
    const env = createEnvelope(secrets, ["values"]);

    // Tamper: swap values array
    (env.values as RevealedField<string[]>).value = ["evil", "manipulation"];

    const result = verifyEnvelope(env);
    expect(result.valid).toBe(false);
    expect(result.failed).toContain("values");
  });

  it("detects a tampered salt", () => {
    const v = makeVector();
    const secrets = buildCommitments(v);
    const env = createEnvelope(secrets, ["meta"]);

    // Tamper: corrupt salt
    (env.meta as RevealedField<unknown>).salt = "0".repeat(32);

    const result = verifyEnvelope(env);
    expect(result.valid).toBe(false);
    expect(result.failed).toContain("meta");
  });

  it("all blinded → valid=true, verified=[], blinded=all", () => {
    const v = makeVector();
    const secrets = buildCommitments(v);
    const env = createEnvelope(secrets, []);
    const result = verifyEnvelope(env);

    expect(result.valid).toBe(true);
    expect(result.verified).toHaveLength(0);
    expect(result.blinded.length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// extractRevealedAttributes
// ---------------------------------------------------------------------------

describe("extractRevealedAttributes", () => {
  it("returns only revealed fields", () => {
    const v = makeVector();
    const secrets = buildCommitments(v);
    const env = createEnvelope(secrets, ["values", "socialEnergy"]);
    const attrs = extractRevealedAttributes(env);

    expect(attrs.values).toEqual(v.values);
    expect(attrs.socialEnergy).toEqual(v.socialEnergy);
    expect(attrs.personality).toBeUndefined();
    expect(attrs.meta).toBeUndefined();
  });

  it("returns empty object when all blinded", () => {
    const v = makeVector();
    const secrets = buildCommitments(v);
    const env = createEnvelope(secrets, []);
    expect(extractRevealedAttributes(env)).toEqual({});
  });

  it("round-trips values correctly via full flow", () => {
    const v = makeVector();
    const secrets = buildCommitments(v);
    const env = createEnvelope(secrets, ["personality", "professionalFocus"]);
    const verifyResult = verifyEnvelope(env);
    expect(verifyResult.valid).toBe(true);

    const attrs = extractRevealedAttributes(env);
    expect(attrs.personality).toEqual(v.personality);
    expect(attrs.professionalFocus).toEqual(v.professionalFocus);
  });
});

// ---------------------------------------------------------------------------
// End-to-end: full prover/verifier protocol simulation
// ---------------------------------------------------------------------------

describe("E2E: prover-verifier protocol", () => {
  it("simulates minimal disclosure — verifier gets only consented fields", () => {
    // --- Prover side ---
    const myVector = makeVector();
    const secrets = buildCommitments(myVector);

    // Prover decides: only share professional focus & values
    const envelope = createEnvelope(secrets, ["professionalFocus", "values"]);

    // --- Verifier side ---
    const result = verifyEnvelope(envelope);
    expect(result.valid).toBe(true);

    const disclosed = extractRevealedAttributes(envelope);
    expect(Object.keys(disclosed)).toHaveLength(2);
    expect(disclosed.professionalFocus).toEqual(["engineering", "AI"]);
    expect(disclosed.values).toEqual(["honesty", "growth"]);

    // Verifier cannot see personality or socialEnergy
    expect(disclosed.personality).toBeUndefined();
    expect(disclosed.socialEnergy).toBeUndefined();
  });

  it("works with default vector (zero-values)", () => {
    const v = createDefaultVector();
    const secrets = buildCommitments(v);
    const env = createEnvelope(secrets, ["meta"]);
    const result = verifyEnvelope(env);
    expect(result.valid).toBe(true);
  });
});
