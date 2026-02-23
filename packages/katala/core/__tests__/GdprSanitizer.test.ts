import { describe, it, expect } from "vitest";
import { createDefaultVector } from "../IdentityVector";
import {
  getDimensionRiskLevel,
  getFieldRiskLevel,
  shouldRedact,
  sanitizeForMediation,
  type ConsentLevel,
} from "../GdprSanitizer";

// ─── Unit tests: getDimensionRiskLevel ────────────────────────────────────────

describe("getDimensionRiskLevel", () => {
  it("returns 'high' for thinking (thinking_feeling proxy)", () => {
    expect(getDimensionRiskLevel("thinking")).toBe("high");
  });

  it("returns 'high' for assertive_turbulent", () => {
    expect(getDimensionRiskLevel("assertive_turbulent")).toBe("high");
  });

  it("returns 'high' for individualism_collectivism", () => {
    expect(getDimensionRiskLevel("individualism_collectivism")).toBe("high");
  });

  it("returns 'medium' for extraversion", () => {
    expect(getDimensionRiskLevel("extraversion")).toBe("medium");
  });

  it("returns 'low' for judging", () => {
    expect(getDimensionRiskLevel("judging")).toBe("low");
  });

  it("returns 'low' for systematic_adaptive", () => {
    expect(getDimensionRiskLevel("systematic_adaptive")).toBe("low");
  });

  it("falls back to 'medium' for unknown dimensions (safe default)", () => {
    expect(getDimensionRiskLevel("totally_unknown_dimension")).toBe("medium");
  });
});

// ─── Unit tests: getFieldRiskLevel ────────────────────────────────────────────

describe("getFieldRiskLevel", () => {
  it("returns 'high' for values field", () => {
    expect(getFieldRiskLevel("values")).toBe("high");
  });

  it("returns 'medium' for professionalFocus", () => {
    expect(getFieldRiskLevel("professionalFocus")).toBe("medium");
  });

  it("returns 'low' for meta.lastUpdated", () => {
    expect(getFieldRiskLevel("meta.lastUpdated")).toBe("low");
  });

  it("falls back to 'medium' for unknown field", () => {
    expect(getFieldRiskLevel("unknownField")).toBe("medium");
  });
});

// ─── Unit tests: shouldRedact ─────────────────────────────────────────────────

describe("shouldRedact", () => {
  it("never redacts at consent='high'", () => {
    expect(shouldRedact("high", "high")).toBe(false);
    expect(shouldRedact("medium", "high")).toBe(false);
    expect(shouldRedact("low", "high")).toBe(false);
  });

  it("redacts HIGH only at consent='medium'", () => {
    expect(shouldRedact("high", "medium")).toBe(true);
    expect(shouldRedact("medium", "medium")).toBe(false);
    expect(shouldRedact("low", "medium")).toBe(false);
  });

  it("redacts HIGH and MEDIUM at consent='low'", () => {
    expect(shouldRedact("high", "low")).toBe(true);
    expect(shouldRedact("medium", "low")).toBe(true);
    expect(shouldRedact("low", "low")).toBe(false);
  });
});

// ─── Integration tests: sanitizeForMediation ─────────────────────────────────

describe("sanitizeForMediation", () => {
  const buildVector = () => {
    const v = createDefaultVector();
    v.personality.extraversion = 0.8;
    v.personality.intuition = 0.6;
    v.personality.thinking = 0.4;
    v.personality.judging = 0.7;
    v.values = ["honesty", "growth"];
    v.professionalFocus = ["engineering", "design"];
    v.socialEnergy.battery = 70;
    v.socialEnergy.preferredTone = "enthusiastic";
    return v;
  };

  it("consent='high': no dimensions are redacted", () => {
    const result = sanitizeForMediation(buildVector(), "high");
    expect(result.personality.extraversion).toBe(0.8);
    expect(result.personality.thinking).toBe(0.4);
    expect(result.values).toEqual(["honesty", "growth"]);
    expect(result.professionalFocus).toEqual(["engineering", "design"]);
    expect(result.gdpr.redactedFields).toHaveLength(0);
    expect(result.gdpr.consentLevel).toBe("high");
  });

  it("consent='medium': HIGH-risk dimensions are nulled; MEDIUM/LOW kept", () => {
    const result = sanitizeForMediation(buildVector(), "medium");

    // thinking is HIGH → redacted
    expect(result.personality.thinking).toBeNull();
    // extraversion is MEDIUM → kept
    expect(result.personality.extraversion).toBe(0.8);
    // judging is LOW → kept
    expect(result.personality.judging).toBe(0.7);
    // values is HIGH → redacted
    expect(result.values).toBeNull();
    // professionalFocus is MEDIUM → kept
    expect(result.professionalFocus).toEqual(["engineering", "design"]);

    expect(result.gdpr.consentLevel).toBe("medium");
    expect(result.gdpr.redactedFields).toContain("personality.thinking");
    expect(result.gdpr.redactedFields).toContain("values");
    expect(result.gdpr.redactedFields).not.toContain("personality.extraversion");
  });

  it("consent='low': HIGH + MEDIUM risk dimensions are nulled; only LOW kept", () => {
    const result = sanitizeForMediation(buildVector(), "low");

    // thinking is HIGH → null
    expect(result.personality.thinking).toBeNull();
    // extraversion is MEDIUM → null at low consent
    expect(result.personality.extraversion).toBeNull();
    // judging is LOW → kept
    expect(result.personality.judging).toBe(0.7);
    // values HIGH → null
    expect(result.values).toBeNull();
    // professionalFocus MEDIUM → null at low consent
    expect(result.professionalFocus).toBeNull();

    expect(result.gdpr.consentLevel).toBe("low");
    expect(result.gdpr.redactedFields).toContain("personality.thinking");
    expect(result.gdpr.redactedFields).toContain("personality.extraversion");
    expect(result.gdpr.redactedFields).toContain("values");
    expect(result.gdpr.redactedFields).toContain("professionalFocus");
    expect(result.gdpr.redactedFields).not.toContain("personality.judging");
  });

  it("always preserves socialEnergy and meta regardless of consent", () => {
    for (const level of ["low", "medium", "high"] as ConsentLevel[]) {
      const result = sanitizeForMediation(buildVector(), level);
      expect(result.socialEnergy.battery).toBe(70);
      expect(result.socialEnergy.preferredTone).toBe("enthusiastic");
      expect(result.meta.confidenceScore).toBe(0);
    }
  });

  it("injects gdpr metadata with a valid ISO timestamp", () => {
    const result = sanitizeForMediation(buildVector(), "medium");
    expect(result.gdpr.sanitisedAt).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
  });

  it("does not mutate the original vector", () => {
    const v = buildVector();
    sanitizeForMediation(v, "low");
    expect(v.personality.thinking).toBe(0.4);
    expect(v.values).toEqual(["honesty", "growth"]);
  });

  it("handles an empty vector gracefully", () => {
    const v = createDefaultVector();
    const result = sanitizeForMediation(v, "low");
    expect(result.values).toBeNull();
    expect(result.gdpr.consentLevel).toBe("low");
  });
});
