import { NextRequest, NextResponse } from "next/server";
import { verifyAssertion, type StoredCredential } from "@/lib/auth/webauthn";
import type { AuthenticationResponseJSON } from "@simplewebauthn/server";

/**
 * POST /api/auth/webauthn/verify
 * Verify a WebAuthn authentication response
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { 
      response, 
      expectedChallenge, 
      credential 
    }: {
      response: AuthenticationResponseJSON;
      expectedChallenge: string;
      credential: StoredCredential;
    } = body;

    if (!response || !expectedChallenge || !credential) {
      return NextResponse.json(
        {
          success: false,
          error: "Missing required parameters",
        },
        { status: 400 }
      );
    }

    const result = await verifyAssertion(response, expectedChallenge, credential);

    if (result.verified) {
      // Update credential counter in database
      // TODO: Implement credential counter update
      
      return NextResponse.json({
        success: true,
        data: {
          verified: true,
          newCounter: result.newCounter,
        },
      });
    } else {
      return NextResponse.json(
        {
          success: false,
          error: result.error || "Verification failed",
        },
        { status: 401 }
      );
    }
  } catch (error) {
    console.error("WebAuthn verification failed:", error);
    return NextResponse.json(
      {
        success: false,
        error: "Verification failed",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    );
  }
}
