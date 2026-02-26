import { NextRequest, NextResponse } from "next/server";
import { verifyServerSideAuthentication } from "@/lib/auth/webauthn";
import type { AuthenticationResponseJSON } from "@simplewebauthn/server";

/**
 * POST /api/auth/webauthn/verify
 * Verify assertion using server-side challenge + server-side stored public key
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { response, userID }: { response?: AuthenticationResponseJSON; userID?: string } = body;

    if (!response || !userID) {
      return NextResponse.json(
        {
          success: false,
          error: "Missing required parameters",
        },
        { status: 400 }
      );
    }

    const result = await verifyServerSideAuthentication(userID, response);

    if (!result.verified) {
      return NextResponse.json(
        {
          success: false,
          error: result.error || "Verification failed",
        },
        { status: 401 }
      );
    }

    return NextResponse.json({
      success: true,
      data: {
        verified: true,
        newCounter: result.newCounter,
      },
    });
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
