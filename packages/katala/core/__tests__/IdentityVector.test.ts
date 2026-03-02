/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect } from "vitest";
import { createDefaultVector, validateVector } from "../IdentityVector";

describe("IdentityVector", () => {
  // --- Passing cases ---

  it("createDefaultVector returns a valid vector", () => {
    const v = createDefaultVector();
    expect(() => validateVector(v)).not.toThrow();
    expect(v.personality.extraversion).toBe(0.5);
  });

  it("validates a fully populated vector", () => {
    const input = {
      personality: { extraversion: 0.0, intuition: 1.0, thinking: 0.3, judging: 0.7 },
      values: ["honesty", "growth"],
      professionalFocus: ["engineering"],
      socialEnergy: { battery: 80, preferredTone: "enthusiastic" as const },
      meta: { confidenceScore: 0.9, lastUpdated: "2026-01-01T00:00:00.000Z" },
    };
    expect(validateVector(input)).toEqual(input);
  });

  it("accepts boundary personality values 0.0 and 1.0", () => {
    const v = createDefaultVector();
    v.personality.extraversion = 0.0;
    v.personality.intuition = 1.0;
    expect(() => validateVector(v)).not.toThrow();
  });

  // --- Failing cases ---

  it("rejects personality value > 1.0", () => {
    const v = createDefaultVector();
    (v as any).personality.extraversion = 1.5;
    expect(() => validateVector(v)).toThrow();
  });

  it("rejects personality value < 0.0", () => {
    const v = createDefaultVector();
    (v as any).personality.thinking = -0.1;
    expect(() => validateVector(v)).toThrow();
  });

  it("rejects invalid preferredTone", () => {
    const v = createDefaultVector();
    (v as any).socialEnergy.preferredTone = "aggressive";
    expect(() => validateVector(v)).toThrow();
  });
});
