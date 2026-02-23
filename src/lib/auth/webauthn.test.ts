import { describe, it, expect, beforeAll, afterAll } from "vitest";
import {
  generateAuthOptions,
  verifyAssertion,
  verifyHumanAuthentication,
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

  afterAll(() => {
    process.env = originalEnv;
  });

  describe("generateAuthOptions", () => {
    it("should generate authentication options with challenge", async () => {
      const options = await generateAuthOptions();

      expect(options).toHaveProperty("challenge");
      expect(options).toHaveProperty("timeout", 60000);
      expect(options).toHaveProperty("rpID", "localhost");
      expect(typeof options.challenge).toBe("string");
      expect(options.challenge.length).toBeGreaterThan(0);
    });

    it.skip("should include allowCredentials when credentialIDs provided", async () => {
      // Use base64url-encoded credential IDs (16 bytes = 24 chars in base64url)
      const credentialIDs = [
        Buffer.from("cred-id-1-12345678").toString("base64url"),
        Buffer.from("cred-id-2-87654321").toString("base64url"),
      ];
      const options = await generateAuthOptions("user-123", credentialIDs);

      expect(options.allowCredentials).toBeDefined();
      expect(options.allowCredentials?.length).toBe(2);
      expect(options.allowCredentials?.[0].type).toBe("public-key");
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

      const result = await verifyAssertion(
        mockResponse,
        "test-challenge",
        mockCredential
      );

      expect(result.verified).toBe(false);
      expect(result.error).toBeDefined();
      expect(result.newCounter).toBe(0);
    });
  });

  describe("verifyHumanAuthentication", () => {
    it("should fallback to HMAC when type is hmac", async () => {
      // This tests the backward compatibility path
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
