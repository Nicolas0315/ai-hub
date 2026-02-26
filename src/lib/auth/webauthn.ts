import crypto from "node:crypto";
import {
  generateAuthenticationOptions,
  verifyAuthenticationResponse,
} from "@simplewebauthn/server";
import type { AuthenticationResponseJSON, AuthenticatorTransport } from "@simplewebauthn/server";

const rpID = process.env.WEBAUTHN_RP_ID || "localhost";
const rpName = process.env.WEBAUTHN_RP_NAME || "Katala";
const origin = process.env.WEBAUTHN_ORIGIN || (rpID === "localhost" ? "http://localhost:3000" : `https://${rpID}`);

const CHALLENGE_TTL_MS = 5 * 60 * 1000;

let verifyAuthenticationResponseFn = verifyAuthenticationResponse;

export interface StoredCredential {
  id: string; // base64url encoded credential ID
  publicKey: string; // base64url encoded public key
  counter: number;
  transports?: AuthenticatorTransport[];
}

export interface WebAuthnChallenge {
  challenge: string;
  timeout: number;
  rpID: string;
  allowCredentials?: { id: string; type: "public-key" }[];
}

interface ChallengeRecord {
  challenge: string;
  userID: string;
  expiresAt: number;
  consumed: boolean;
}

const challengesByUser = new Map<string, ChallengeRecord>();
const credentialsByUser = new Map<string, Map<string, StoredCredential>>();

function now() {
  return Date.now();
}

function gcChallenges(): void {
  const ts = now();
  for (const [userID, record] of challengesByUser.entries()) {
    if (record.expiresAt <= ts || record.consumed) {
      challengesByUser.delete(userID);
    }
  }
}

export function registerCredential(userID: string, credential: StoredCredential): void {
  if (!userID) throw new Error("userID is required");
  if (!credential?.id || !credential.publicKey) throw new Error("Invalid credential");

  const userCreds = credentialsByUser.get(userID) ?? new Map<string, StoredCredential>();
  // upsert enables key rotation / credential update
  userCreds.set(credential.id, credential);
  credentialsByUser.set(userID, userCreds);
}

export function getCredential(userID: string, credentialID: string): StoredCredential | null {
  const userCreds = credentialsByUser.get(userID);
  if (!userCreds) return null;
  return userCreds.get(credentialID) ?? null;
}

export function listCredentialIDs(userID: string): string[] {
  const userCreds = credentialsByUser.get(userID);
  if (!userCreds) return [];
  return [...userCreds.keys()];
}

function generateServerChallenge(): string {
  return crypto.randomBytes(32).toString("base64url");
}

export async function generateAuthOptions(userID: string): Promise<WebAuthnChallenge> {
  if (!userID) {
    throw new Error("userID is required");
  }

  const credentialIDs = listCredentialIDs(userID);
  const challenge = generateServerChallenge();

  const options = await generateAuthenticationOptions({
    rpID,
    challenge,
    allowCredentials: credentialIDs.map((id) => ({
      id,
      type: "public-key" as const,
    })),
    userVerification: "preferred",
    timeout: CHALLENGE_TTL_MS,
  });

  challengesByUser.set(userID, {
    challenge,
    userID,
    expiresAt: now() + CHALLENGE_TTL_MS,
    consumed: false,
  });

  return {
    challenge: options.challenge,
    timeout: options.timeout || CHALLENGE_TTL_MS,
    rpID: options.rpId || rpID,
    allowCredentials: options.allowCredentials?.map((cred) => ({
      id: Buffer.from(cred.id).toString("base64url"),
      type: cred.type,
    })),
  };
}

export async function verifyAssertion(
  response: AuthenticationResponseJSON,
  expectedChallenge: string,
  credential: StoredCredential
): Promise<{
  verified: boolean;
  newCounter: number;
  error?: string;
}> {
  try {
    const verification = await verifyAuthenticationResponseFn({
      response,
      expectedChallenge,
      expectedOrigin: origin,
      expectedRPID: rpID,
      credential: {
        id: credential.id,
        publicKey: Buffer.from(credential.publicKey, "base64url"),
        counter: credential.counter,
        transports: credential.transports,
      },
      requireUserVerification: false,
    });

    return {
      verified: verification.verified,
      newCounter: verification.authenticationInfo.newCounter,
    };
  } catch (error) {
    return {
      verified: false,
      newCounter: credential.counter,
      error: error instanceof Error ? error.message : "Verification failed",
    };
  }
}

export async function verifyServerSideAuthentication(userID: string, response: AuthenticationResponseJSON): Promise<{
  verified: boolean;
  newCounter?: number;
  error?: string;
}> {
  if (!userID) return { verified: false, error: "Missing userID" };
  if (!response?.id) return { verified: false, error: "Missing response credential id" };

  gcChallenges();
  const challengeRecord = challengesByUser.get(userID);
  if (!challengeRecord || challengeRecord.consumed || challengeRecord.expiresAt <= now()) {
    return { verified: false, error: "Challenge not found or expired" };
  }

  const credential = getCredential(userID, response.id);
  if (!credential) {
    return { verified: false, error: "Credential not found" };
  }

  const result = await verifyAssertion(response, challengeRecord.challenge, credential);
  if (!result.verified) {
    return { verified: false, error: result.error || "Verification failed" };
  }

  // one-time challenge consumption prevents replay
  challengeRecord.consumed = true;
  challengesByUser.set(userID, challengeRecord);

  registerCredential(userID, {
    ...credential,
    counter: result.newCounter,
  });

  return {
    verified: true,
    newCounter: result.newCounter,
  };
}

export function setAuthenticationVerifierForTest(verifier: typeof verifyAuthenticationResponse): void {
  verifyAuthenticationResponseFn = verifier;
}

export function resetWebAuthnStores(): void {
  challengesByUser.clear();
  credentialsByUser.clear();
  verifyAuthenticationResponseFn = verifyAuthenticationResponse;
}

export async function verifyHumanAuthentication(
  message: string,
  signature: string,
  options?: {
    type: "hmac" | "webauthn";
    webauthnResponse?: AuthenticationResponseJSON;
    expectedChallenge?: string;
    credential?: StoredCredential;
    userID?: string;
  }
): Promise<{
  verified: boolean;
  type: "hmac" | "webauthn";
  error?: string;
}> {
  if (!options || options.type === "hmac") {
    const { verifyHumanIntentSignature } = await import("./humanSignature");
    const verified = verifyHumanIntentSignature(message, signature);
    return { verified, type: "hmac" };
  }

  if (options.type === "webauthn") {
    if (options.webauthnResponse && options.userID) {
      const result = await verifyServerSideAuthentication(options.userID, options.webauthnResponse);
      return {
        verified: result.verified,
        type: "webauthn",
        error: result.error,
      };
    }

    if (!options.webauthnResponse || !options.expectedChallenge || !options.credential) {
      return {
        verified: false,
        type: "webauthn",
        error: "Missing WebAuthn parameters",
      };
    }

    const result = await verifyAssertion(
      options.webauthnResponse,
      options.expectedChallenge,
      options.credential
    );

    return {
      verified: result.verified,
      type: "webauthn",
      error: result.error,
    };
  }

  return {
    verified: false,
    type: options?.type || "hmac",
    error: "Unknown verification type",
  };
}
