import { describe, it, expect, beforeAll, afterAll, beforeEach, vi } from "vitest";
import {
  generateAuthOptions,
  verifyAssertion,
  verifyHumanAuthentication,
  verifyServerSideAuthentication,
  registerCredential,
  getCredential,
  setAuthenticationVerifierForTest,
  resetWebAuthnStores,
  type StoredCredential,
} from "./webauthn";
import type { AuthenticationResponseJSON } from "@simplewebauthn/server";

describe("WebAuthn Module", () => {
  const originalEnv = process.env;

  beforeAll(() => {
    process.env.WEBAUTHN_RP_ID = "localhost";
    process.env.WEBAUTHN_RP_NAME = "Katala Test";
    process.env.WEBAUTHN_ORIGIN = "http://localhost:3000";
  });

  beforeEach(() => {
    resetWebAuthnStores();
    vi.restoreAllMocks();
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  describe("generateAuthOptions", () => {
    it("should generate authentication options with server-side challenge", async () => {
      const userID = "user-123";
      const options = await generateAuthOptions(userID);

      expect(options).toHaveProperty("challenge");
      expect(options).toHaveProperty("timeout", 300000);
      expect(options).toHaveProperty("rpID", "localhost");
      expect(typeof options.challenge).toBe("string");
      expect(options.challenge.length).toBeGreaterThanOrEqual(43); // 32-byte base64url
    });
  });

  describe("credential store", () => {
    it("should upsert credentials for key rotation", () => {
      const userID = "user-rotate";
      const credA: StoredCredential = {
        id: "cred-1",
        publicKey: "pub-old",
        counter: 1,
      };
      const credB: StoredCredential = {
        id: "cred-1",
        publicKey: "pub-new",
        counter: 2,
      };

      registerCredential(userID, credA);
      registerCredential(userID, credB);

      const stored = getCredential(userID, "cred-1");
      expect(stored).toBeDefined();
      expect(stored?.publicKey).toBe("pub-new");
      expect(stored?.counter).toBe(2);
    });
  });

  describe("verifyAssertion", () => {
    it("should fail with invalid response", async () => {
      const mockCredential: StoredCredential = {
        id: "dGVzdC1jcmVkZW50aWFsLWlk",
        publicKey: "dGVzdC1wdWJsaWMta2V5",
        counter: 0,
      };

      const mockResponse = {
        id: "dGVzdC1jcmVkZW50aWFsLWlk",
        rawId: "dGVzdC1jcmVkZW50aWFsLWlk",
        response: {
          authenticatorData: "",
          clientDataJSON: "",
          signature: "",
          userHandle: null,
        },
        clientExtensionResults: {},
        type: "public-key",
      } as AuthenticationResponseJSON;

      const result = await verifyAssertion(mockResponse, "test-challenge", mockCredential);

      expect(result.verified).toBe(false);
      expect(result.error).toBeDefined();
      expect(result.newCounter).toBe(0);
    });
  });

  describe("verifyServerSideAuthentication", () => {
    const userID = "user-auth";
    const credential: StoredCredential = {
      id: "cred-server-1",
      publicKey: Buffer.from("public-key-binary").toString("base64url"),
      counter: 10,
    };

    const response = {
      id: "cred-server-1",
      rawId: "cred-server-1",
      response: {
        authenticatorData: "auth-data",
        clientDataJSON: "client-data",
        signature: "sig",
        userHandle: null,
      },
      clientExtensionResults: {},
      type: "public-key",
    } as unknown as AuthenticationResponseJSON;

    it("should reject unknown credential (client-provided credential is not trusted)", async () => {
      await generateAuthOptions(userID);
      const result = await verifyServerSideAuthentication(userID, response);

      expect(result.verified).toBe(false);
      expect(result.error).toBe("Credential not found");
    });

    it("should verify using stored challenge+credential and consume challenge to prevent replay", async () => {
      registerCredential(userID, credential);
      await generateAuthOptions(userID);

      setAuthenticationVerifierForTest(async () => ({
        verified: true,
        authenticationInfo: {
          newCounter: 11,
          credentialID: new Uint8Array(),
          userVerified: true,
          credentialDeviceType: "singleDevice",
          credentialBackedUp: false,
          origin: "http://localhost:3000",
          rpID: "localhost",
        },
      } as any));

      const first = await verifyServerSideAuthentication(userID, response);
      expect(first.verified).toBe(true);
      expect(first.newCounter).toBe(11);

      const second = await verifyServerSideAuthentication(userID, response);
      expect(second.verified).toBe(false);
      expect(second.error).toBe("Challenge not found or expired");
    });
  });

  describe("verifyHumanAuthentication", () => {
    it("should fallback to HMAC when type is hmac", async () => {
      process.env.HUMAN_LAYER_SIGNING_KEY = "test-secret-key";

      const { signHumanIntent } = await import("./humanSignature");
      const message = "test message";
      const signature = signHumanIntent(message, "test-secret-key");

      const result = await verifyHumanAuthentication(message, signature, {
        type: "hmac",
      });

      expect(result.verified).toBe(true);
      expect(result.type).toBe("hmac");
    });

    it("should return error for webauthn with missing parameters", async () => {
      const result = await verifyHumanAuthentication("test", "sig", {
        type: "webauthn",
      });

      expect(result.verified).toBe(false);
      expect(result.type).toBe("webauthn");
      expect(result.error).toBe("Missing WebAuthn parameters");
    });

    it("should default to HMAC when no type specified", async () => {
      process.env.HUMAN_LAYER_SIGNING_KEY = "test-secret-key";

      const { signHumanIntent } = await import("./humanSignature");
      const message = "test message";
      const signature = signHumanIntent(message, "test-secret-key");

      const result = await verifyHumanAuthentication(message, signature);

      expect(result.verified).toBe(true);
      expect(result.type).toBe("hmac");
    });
  });
});
