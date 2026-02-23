/**
 * GdprSanitizer
 *
 * Implements Issue #18: Automated GDPR Mapping for MBTI++ Identity Vectors.
 *
 * Provides:
 *  1. Type-safe access to the GDPR dimension risk mapping (gdpr-mapping.json).
 *  2. `sanitizeForMediation()` — redacts high-risk (and optionally medium-risk)
 *     personality dimensions from an IdentityVector before cross-node mediation,
 *     based on the user's declared consent level.
 *
 * Consent policy:
 *  - "high"   → All dimensions shared. No redaction.
 *  - "medium" → HIGH-risk dimensions redacted. MEDIUM/LOW shared.
 *  - "low"    → HIGH + MEDIUM risk dimensions redacted. Only LOW shared.
 *
 * GDPR legal basis: Art. 9 special-category data protection +
 *                   Art. 6(1)(a) lawfulness based on explicit consent.
 */

import gdprMapping from "./gdpr-mapping.json";
import type { IdentityVector } from "./IdentityVector";

// ─── Public types ─────────────────────────────────────────────────────────────

export type GdprRiskLevel = "high" | "medium" | "low";

export type ConsentLevel = "low" | "medium" | "high";

/** An IdentityVector where redacted personality dimensions are replaced with null. */
export type SanitizedPersonality = {
  [K in keyof IdentityVector["personality"]]: number | null;
};

export interface SanitizedIdentityVector
  extends Omit<IdentityVector, "personality" | "values" | "professionalFocus"> {
  personality: SanitizedPersonality;
  /** null when redacted (values revealed personal values → high risk) */
  values: string[] | null;
  /** null when redacted (professionalFocus revealed occupational data → medium risk) */
  professionalFocus: string[] | null;
  /** Injected metadata to inform receivers of sanitisation state */
  gdpr: {
    consentLevel: ConsentLevel;
    redactedFields: string[];
    sanitisedAt: string;
  };
}

// ─── Internal helpers ─────────────────────────────────────────────────────────

type DimensionEntry = {
  gdpr_risk_level: GdprRiskLevel;
  rationale: string;
  alias_for?: string;
};

type ProfileFieldEntry = {
  gdpr_risk_level: GdprRiskLevel;
  rationale: string;
};

const personalityMap: Record<string, DimensionEntry> =
  gdprMapping.personalityDimensions as Record<string, DimensionEntry>;

const profileFieldMap: Record<string, ProfileFieldEntry> =
  gdprMapping.profileFields as Record<string, ProfileFieldEntry>;

/**
 * Returns the GDPR risk level for a named personality dimension.
 * Defaults to "medium" when the dimension is unknown (safe fallback).
 */
export function getDimensionRiskLevel(dimension: string): GdprRiskLevel {
  return (personalityMap[dimension]?.gdpr_risk_level as GdprRiskLevel) ?? "medium";
}

/**
 * Returns the GDPR risk level for a top-level profile field.
 * Defaults to "medium" for unknown fields.
 */
export function getFieldRiskLevel(field: string): GdprRiskLevel {
  return (profileFieldMap[field]?.gdpr_risk_level as GdprRiskLevel) ?? "medium";
}

/**
 * Determines whether a given risk level should be redacted for the
 * supplied consent level.
 *
 *  consent "low"    → redact HIGH and MEDIUM
 *  consent "medium" → redact HIGH only
 *  consent "high"   → redact nothing
 */
export function shouldRedact(riskLevel: GdprRiskLevel, consentLevel: ConsentLevel): boolean {
  switch (consentLevel) {
    case "high":
      return false;
    case "medium":
      return riskLevel === "high";
    case "low":
      return riskLevel === "high" || riskLevel === "medium";
  }
}

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Sanitises an IdentityVector for cross-node mediation by redacting dimensions
 * that exceed the user's consent threshold.
 *
 * @param vector        The full IdentityVector to sanitise.
 * @param consentLevel  The user's current consent level ("low" | "medium" | "high").
 * @returns             A SanitizedIdentityVector safe for external transmission.
 *
 * @example
 * const safe = sanitizeForMediation(myVector, "medium");
 * // safe.personality.thinking === null  (HIGH risk, redacted)
 * // safe.personality.extraversion === 0.7  (MEDIUM risk, kept at medium consent)
 */
export function sanitizeForMediation(
  vector: IdentityVector,
  consentLevel: ConsentLevel,
): SanitizedIdentityVector {
  const redactedFields: string[] = [];

  // ── Personality dimensions ──────────────────────────────────────────────
  const rawPersonality = vector.personality as Record<string, number>;
  const sanitisedPersonality: Record<string, number | null> = {};

  for (const [dim, value] of Object.entries(rawPersonality)) {
    const risk = getDimensionRiskLevel(dim);
    if (shouldRedact(risk, consentLevel)) {
      sanitisedPersonality[dim] = null;
      redactedFields.push(`personality.${dim}`);
    } else {
      sanitisedPersonality[dim] = value;
    }
  }

  // ── values (high risk — may reveal religious/political beliefs) ──────────
  let sanitisedValues: string[] | null = vector.values;
  const valuesRisk = getFieldRiskLevel("values");
  if (shouldRedact(valuesRisk, consentLevel)) {
    sanitisedValues = null;
    redactedFields.push("values");
  }

  // ── professionalFocus (medium risk — occupational inference) ─────────────
  let sanitisedFocus: string[] | null = vector.professionalFocus;
  const focusRisk = getFieldRiskLevel("professionalFocus");
  if (shouldRedact(focusRisk, consentLevel)) {
    sanitisedFocus = null;
    redactedFields.push("professionalFocus");
  }

  return {
    personality: sanitisedPersonality as SanitizedPersonality,
    values: sanitisedValues,
    professionalFocus: sanitisedFocus,
    socialEnergy: vector.socialEnergy,
    meta: vector.meta,
    gdpr: {
      consentLevel,
      redactedFields,
      sanitisedAt: new Date().toISOString(),
    },
  };
}
