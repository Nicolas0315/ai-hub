/**
 * SelectiveDisclosure.ts
 *
 * ZK-lite Selective Disclosure for IdentityVector attributes.
 *
 * Implements a lightweight, crypto-hash-based commitment scheme that lets one
 * party prove they hold specific attribute values without revealing the full
 * IdentityVector. This is NOT a full ZK-proof system (no circuits), but it
 * provides the same disclosure-without-exposure guarantees needed at this
 * stage of Katala's trust infrastructure.
 *
 * ## Protocol (per attribute)
 *  1. Prover picks random salt (16 bytes hex)
 *  2. Commitment = SHA-256(salt + ":" + JSON(value))
 *  3. Prover shares only commitments with verifier (blinded phase)
 *  4. To reveal a field: prover sends {salt, value} for that field
 *  5. Verifier recomputes commitment and confirms match
 *
 * ## Disclosure Policy
 *  Callers declare which top-level IdentityVector keys they consent to reveal.
 *  Unrevealed fields remain committed (hash-only) — verifier cannot infer them.
 *
 * Issue: #20 — Core: Implement Selective Disclosure via ZK-lite for Identity Vectors
 */

import { createHash, randomBytes } from "crypto";
import { IdentityVector } from "./IdentityVector";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Committed (hidden) value: only the commitment hash is shared */
export interface CommittedField {
  revealed: false;
  commitment: string; // hex SHA-256
}

/** Revealed value: commitment + plaintext proof */
export interface RevealedField<T = unknown> {
  revealed: true;
  commitment: string; // hex SHA-256 (for independent verification)
  salt: string;       // hex random nonce used during commitment
  value: T;           // plaintext value
}

export type DisclosedField<T = unknown> = CommittedField | RevealedField<T>;

/** Top-level keys of IdentityVector */
export type IdentityVectorKey = keyof IdentityVector;

/**
 * A Disclosure Envelope: for each IdentityVector key, either a commitment
 * (hidden) or a revealed proof. Shared with the verifier.
 */
export type DisclosureEnvelope = {
  [K in IdentityVectorKey]: DisclosedField<IdentityVector[K]>;
};

/** Internal per-field secret kept by the prover (never shared) */
interface FieldSecret<T = unknown> {
  salt: string;
  value: T;
  commitment: string;
}

/** Full prover state — contains salts & plaintext. NOT shared with verifier. */
export type ProverSecrets = {
  [K in IdentityVectorKey]: FieldSecret<IdentityVector[K]>;
};

// ---------------------------------------------------------------------------
// Core helpers
// ---------------------------------------------------------------------------

/** Compute commitment = SHA-256(salt + ":" + JSON(value)) */
function commit(salt: string, value: unknown): string {
  return createHash("sha256")
    .update(`${salt}:${JSON.stringify(value)}`)
    .digest("hex");
}

/** Generate a cryptographically random 16-byte hex salt */
function randomSalt(): string {
  return randomBytes(16).toString("hex");
}

// ---------------------------------------------------------------------------
// Prover API
// ---------------------------------------------------------------------------

/**
 * Build a prover's commitment set from an IdentityVector.
 * Generates a fresh random salt for every field.
 *
 * @param vector - The full IdentityVector to commit to
 * @returns ProverSecrets (keep private) — used later to build envelopes
 */
export function buildCommitments(vector: IdentityVector): ProverSecrets {
  const keys = Object.keys(vector) as IdentityVectorKey[];
  const secrets = {} as ProverSecrets;

  for (const key of keys) {
    const salt = randomSalt();
    const value = vector[key] as IdentityVector[typeof key];
    secrets[key] = {
      salt,
      value,
      commitment: commit(salt, value),
    };
  }

  return secrets;
}

/**
 * Create a DisclosureEnvelope from prover secrets.
 * Fields listed in `revealKeys` are included as RevealedField;
 * all others are CommittedField (hash-only).
 *
 * @param secrets    - Output of buildCommitments()
 * @param revealKeys - Fields the prover consents to disclose
 * @returns DisclosureEnvelope safe to send to verifier
 */
export function createEnvelope(
  secrets: ProverSecrets,
  revealKeys: IdentityVectorKey[],
): DisclosureEnvelope {
  const revealSet = new Set(revealKeys);
  const keys = Object.keys(secrets) as IdentityVectorKey[];
  const envelope = {} as DisclosureEnvelope;

  for (const key of keys) {
    const s = secrets[key];
    if (revealSet.has(key)) {
      (envelope[key] as RevealedField<IdentityVector[typeof key]>) = {
        revealed: true,
        commitment: s.commitment,
        salt: s.salt,
        value: s.value as IdentityVector[typeof key],
      };
    } else {
      (envelope[key] as CommittedField) = {
        revealed: false,
        commitment: s.commitment,
      };
    }
  }

  return envelope;
}

// ---------------------------------------------------------------------------
// Verifier API
// ---------------------------------------------------------------------------

export interface VerificationResult {
  /** True only if every revealed field's commitment verifies correctly */
  valid: boolean;
  /** Fields that passed verification */
  verified: IdentityVectorKey[];
  /** Fields that failed (commitment mismatch) */
  failed: IdentityVectorKey[];
  /** Fields that were not revealed (blinded) */
  blinded: IdentityVectorKey[];
}

/**
 * Verify a DisclosureEnvelope received from a prover.
 * For each revealed field, recomputes commitment and checks it matches.
 * Blinded fields are simply recorded — their values remain unknown.
 *
 * @param envelope - Received from prover
 * @returns VerificationResult with per-field breakdown
 */
export function verifyEnvelope(envelope: DisclosureEnvelope): VerificationResult {
  const verified: IdentityVectorKey[] = [];
  const failed: IdentityVectorKey[] = [];
  const blinded: IdentityVectorKey[] = [];

  const keys = Object.keys(envelope) as IdentityVectorKey[];

  for (const key of keys) {
    const field = envelope[key];
    if (!field.revealed) {
      blinded.push(key);
      continue;
    }

    const expected = commit(field.salt, field.value);
    if (expected === field.commitment) {
      verified.push(key);
    } else {
      failed.push(key);
    }
  }

  return {
    valid: failed.length === 0,
    verified,
    failed,
    blinded,
  };
}

/**
 * Extract the plaintext values from a verified envelope (revealed fields only).
 * Caller should run verifyEnvelope() first and check result.valid.
 *
 * @param envelope - A DisclosureEnvelope (partially or fully revealed)
 * @returns Partial IdentityVector containing only disclosed fields
 */
export function extractRevealedAttributes(
  envelope: DisclosureEnvelope,
): Partial<IdentityVector> {
  const result: Partial<IdentityVector> = {};
  const keys = Object.keys(envelope) as IdentityVectorKey[];

  for (const key of keys) {
    const field = envelope[key];
    if (field.revealed) {
      (result as Record<string, unknown>)[key] = field.value;
    }
  }

  return result;
}
