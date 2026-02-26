import { NextRequest, NextResponse } from "next/server";
import { registerCredential, type StoredCredential } from "@/lib/auth/webauthn";

/**
 * POST /api/auth/webauthn/register
 * Persist credential public key server-side (supports key rotation via upsert)
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { userID, credential }: { userID?: string; credential?: StoredCredential } = body;

    if (!userID || !credential) {
      return NextResponse.json(
        {
          success: false,
          error: "Missing required parameters",
        },
        { status: 400 }
      );
    }

    registerCredential(userID, credential);

    return NextResponse.json({
      success: true,
      data: {
        registered: true,
        credentialID: credential.id,
      },
    });
  } catch (error) {
    console.error("WebAuthn registration failed:", error);
    return NextResponse.json(
      {
        success: false,
        error: "Registration failed",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    );
  }
}
