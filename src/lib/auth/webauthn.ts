import {
  generateAuthenticationOptions,
  verifyAuthenticationResponse,
} from "@simplewebauthn/server";
import type {
  AuthenticationResponseJSON,
} from "@simplewebauthn/server";

// RP (Relying Party) configuration
const rpID = process.env.WEBAUTHN_RP_ID || "localhost";
const rpName = process.env.WEBAUTHN_RP_NAME || "Katala";
const origin = process.env.WEBAUTHN_ORIGIN || (rpID === "localhost" ? "http://localhost:3000" : `https://${rpID}`);

/**
 * WebAuthn Challenge for authentication/assertion
 */
export interface WebAuthnChallenge {
  challenge: string;
  timeout: number;
  rpID: string;
  allowCredentials?: { id: string; type: "public-key" }[];
}

/**
 * Generate authentication options (challenge)
 * This is used to initiate a WebAuthn login/assertion
 */
export async function generateAuthOptions(
  userID?: string,
  credentialIDs?: string[]
): Promise<WebAuthnChallenge> {
  const opts = {
    rpID,
    allowCredentials: credentialIDs?.map((id) => ({
      id: Buffer.from(id, "base64url"),
      type: "public-key" as const,
    })),
    userVerification: "preferred" as const,
    timeout: 60000,
  };

  const options = await generateAuthenticationOptions(opts);

  return {
    challenge: options.challenge,
    timeout: options.timeout || 60000,
    rpID: options.rpId || rpID,
    allowCredentials: options.allowCredentials?.map((cred) => ({
      id: Buffer.from(cred.id).toString("base64url"),
      type: cred.type,
    })),
  };
}

/**
 * WebAuthn credential stored for a user
 */
export interface StoredCredential {
  id: string; // base64url encoded credential ID
  publicKey: string; // base64url encoded public key
  counter: number;
  transports?: AuthenticatorTransport[];
}

/**
 * Verify WebAuthn assertion
 * This validates the authenticator's response to a challenge
 */
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
    const opts = {
      response,
      expectedChallenge,
      expectedOrigin: origin,
      expectedRPID: rpID,
      authenticator: {
        credentialID: Buffer.from(credential.id, "base64url"),
        credentialPublicKey: Buffer.from(credential.publicKey, "base64url"),
        counter: credential.counter,
        transports: credential.transports,
      },
      requireUserVerification: false,
    };

    const verification = await verifyAuthenticationResponse(opts);

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

/**
 * Hybrid verification function
 * Supports both HMAC (legacy) and WebAuthn (new)
 * This allows gradual migration from HMAC to WebAuthn
 */
export async function verifyHumanAuthentication(
  message: string,
  signature: string,
  options?: {
    type: "hmac" | "webauthn";
    webauthnResponse?: AuthenticationResponseJSON;
    expectedChallenge?: string;
    credential?: StoredCredential;
  }
): Promise<{
  verified: boolean;
  type: "hmac" | "webauthn";
  error?: string;
}> {
  // Default to HMAC if no type specified (backward compatibility)
  if (!options || options.type === "hmac") {
    const { verifyHumanIntentSignature } = await import("./humanSignature");
    const verified = verifyHumanIntentSignature(message, signature);
    return { verified, type: "hmac" };
  }

  // WebAuthn verification
  if (options.type === "webauthn") {
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
